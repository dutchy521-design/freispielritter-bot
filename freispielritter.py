import telebot
import os
import random
import string
from telebot import types
from flask import Flask
import threading
from datetime import datetime, timedelta
from supabase import create_client, Client

# ---------------- SUPABASE ----------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")

ADMIN_ID = os.getenv("ADMIN_ID")
try:
    ADMIN_ID = int(ADMIN_ID)
except:
    ADMIN_ID = 0

bot = telebot.TeleBot(TOKEN)

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Freispielritter läuft 🚀"

# ---------------- MEMORY ----------------
pending_xp_requests = {}

# ---------------- LEVEL SYSTEM ----------------

def get_level_name(level):

    levels = {
        1: "🪙 Bettler-Ritter",
        2: "🛡️ Schank-Ritter",
        3: "⚔️ Eisen-Ritter",
        4: "🐎 Turnier-Ritter",
        5: "🏰 Burg-Ritter",
        6: "👑 Casino-Champion",
        7: "💎 Royal High Roller",
        8: "🔥 Shadow Knight",
        9: "⚡ Mythic Dealer",
        10: "🏆 Legend of the Casino"
    }

    return levels.get(level, "🏆 Unsterblicher Ritter")

# ---------------- HELPERS ----------------

def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))


def get_user(user_id):
    user_id = str(user_id).strip()

    res = supabase.table("users").select("*").eq("id", user_id).execute()

    if res.data:
        return res.data[0]

    new_user = {
        "id": user_id,
        "xp": 0,
        "level": 1,
        "invites": 0,
        "ref_code": generate_code(),
        "used_ref": None,
        "invite_list": [],
        "last_xp": None
    }

    supabase.table("users").upsert(new_user).execute()
    return new_user


def update_user(user_id, fields: dict):
    supabase.table("users").update(fields).eq("id", str(user_id)).execute()


def find_user_by_ref(code):
    res = supabase.table("users").select("id").eq("ref_code", code).execute()
    if res.data:
        return res.data[0]["id"]
    return None

# ---------------- XP SYSTEM ----------------

def add_xp(user_id, amount=10):

    user = get_user(user_id)
    now = datetime.utcnow()

    last = user.get("last_xp")

    if last:
        try:
            last_time = datetime.fromisoformat(last)
            if now - last_time < timedelta(seconds=10):
                return user.get("xp"), user.get("level")
        except:
            pass

    xp = int(user.get("xp") or 0) + amount
    level = (xp // 100) + 1

    update_user(user_id, {
        "xp": xp,
        "level": level,
        "last_xp": now.isoformat()
    })

    return xp, level

# ---------------- START ----------------

@bot.message_handler(commands=["start"])
def start(message):

    user_id = str(message.from_user.id)
    user = get_user(user_id)

    args = message.text.split()

    if len(args) > 1:
        ref_code = args[1]
        ref_user_id = find_user_by_ref(ref_code)

        if ref_user_id and ref_user_id != user_id:

            ref_user = get_user(ref_user_id)

            if not ref_user.get("used_ref"):

                update_user(ref_user_id, {
                    "invites": int(ref_user.get("invites", 0)) + 1,
                    "invite_list": (ref_user.get("invite_list") or []) + [{
                        "id": user_id,
                        "username": message.from_user.username or "unknown",
                        "date": datetime.now().strftime("%d.%m.%Y")
                    }]
                })

                add_xp(ref_user_id, 10)

                update_user(user_id, {
                    "used_ref": ref_code
                })

    markup = types.InlineKeyboardMarkup()

    # 👉 TOP DEAL BUTTON
    markup.add(
        types.InlineKeyboardButton("🔥 Top Deal 😉", callback_data="top_deal_request")
    )

    markup.add(
        types.InlineKeyboardButton("🚀 Mini App starten", web_app=types.WebAppInfo("https://freispielritter.pages.dev/"))
    )

    markup.add(
        types.InlineKeyboardButton("📢 Kanal beitreten", url="https://t.me/Freispielritter")
    )

    markup.add(
        types.InlineKeyboardButton("✅ Ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Willkommen im Ritter Casino", reply_markup=markup)

# ---------------- CALLBACK ----------------

CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

    # ---------------- TOP DEAL REQUEST ----------------
    if call.data == "top_deal_request":

        user = call.from_user

        bot.send_message(
            ADMIN_ID,
            f"🔥 TOP DEAL ANFRAGE\n\n"
            f"👤 User: {user.id}\n"
            f"🧑 @{user.username or 'unknown'}\n\n"
            f"📩 Anfrage: Top Deal angefordert\n"
            f"✉️ Bitte manuell per Mail versenden 😉"
        )

        bot.send_message(
            chat_id,
            "🔥 Top Deal angefragt!\n\n"
            "👀 Der Admin kümmert sich gleich darum 😉"
        )
        return

    # ---------------- AGE ----------------
    if call.data == "age_no":
        bot.send_message(chat_id, "❌ Zugriff verweigert.")
        return

    if call.data == "age_yes":

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "📢 Kanal beitreten",
            url="https://t.me/Freispielritter"
        ))
        markup.add(types.InlineKeyboardButton(
            "✅ Ich bin beigetreten",
            callback_data="check_channel"
        ))

        bot.send_message(chat_id, "👉 Bitte trete dem Kanal bei:", reply_markup=markup)
        return

    if call.data == "check_channel":

        try:
            member = bot.get_chat_member(CHANNEL, call.from_user.id)
            status = member.status
        except:
            bot.send_message(chat_id, "⚠️ Kanalprüfung fehlgeschlagen.")
            return

        if status not in ["member", "administrator", "creator"]:
            bot.send_message(chat_id, "❌ Du bist noch nicht im Kanal.")
            return

        user = get_user(str(chat_id))
        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "🚀 Mini App starten",
            web_app=types.WebAppInfo("https://freispielritter.pages.dev/")
        ))

        bot.send_message(
            chat_id,
            "✅ Freigeschaltet!\n\n"
            f"🔗 Dein Ref-Link:\n{ref_link}\n\n"
            "⭐ 10 XP pro Invite",
            reply_markup=markup
        )

# ---------------- SCREENSHOT ----------------

@bot.message_handler(content_types=['photo'])
def screenshot(message):

    if ADMIN_ID == 0:
        return

    username = message.from_user.username or "unknown"
    note = message.caption if message.caption else "Keine Notiz"

    req_id = str(message.message_id)

    pending_xp_requests[req_id] = {
        "user_id": str(message.from_user.id)
    }

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ +5 XP geben", callback_data=f"xp_yes_{req_id}"),
        types.InlineKeyboardButton("❌ Ablehnen", callback_data=f"xp_no_{req_id}")
    )

    bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=(
            f"📸 SCREENSHOT\n\n"
            f"👤 User ID: {message.from_user.id}\n"
            f"🧑 @{username}\n\n"
            f"💬 Notiz:\n{note}"
        ),
        reply_markup=markup
    )

# ---------------- XP CALLBACK ----------------

    if call.data.startswith("xp_yes_"):

        req_id = call.data.split("_")[2]
        data = pending_xp_requests.get(req_id)

        if not data:
            return

        user_id = data["user_id"]

        user = get_user(user_id)
        xp = int(user.get("xp", 0)) + 5
        level = (xp // 100) + 1

        update_user(user_id, {
            "xp": xp,
            "level": level
        })

        bot.send_message(chat_id, "✅ +5 XP vergeben!")

        try:
            bot.send_message(
                user_id,
                "💳 Einzahlung bestätigt!\n\n⭐ +5 XP gutgeschrieben."
            )
        except:
            pass

        pending_xp_requests.pop(req_id, None)
        return

    if call.data.startswith("xp_no_"):

        req_id = call.data.split("_")[2]
        pending_xp_requests.pop(req_id, None)

        bot.send_message(chat_id, "❌ Abgelehnt.")
        return

# ---------------- /XP ----------------

@bot.message_handler(commands=["xp"])
def xp(message):

    user = get_user(str(message.from_user.id))

    bot.send_message(
        message.chat.id,
        f"⭐ XP: {user.get('xp', 0)}\n"
        f"🏆 Level: {user.get('level', 1)}\n"
        f"🎖 Rang: {get_level_name(user.get('level', 1))}\n\n"
        f"📌 1 Invite = 10 XP\n📸 Screenshot = 5 XP"
    )

# ---------------- RUN ----------------

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    print("Bot läuft 🚀")
    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)

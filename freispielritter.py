import telebot
import os
import random
import string
from telebot import types
from flask import Flask, request, jsonify
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

    # REF SYSTEM
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

    # 18+ CHECK
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du 18 Jahre oder älter?", reply_markup=markup)

# ---------------- CALLBACK FLOW ----------------

CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

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
            f"🔗 Dein Ref-Link:\n{ref_link}",
            reply_markup=markup
        )

# ---------------- SCREENSHOT ----------------

@bot.message_handler(content_types=['photo'])
def screenshot(message):

    if ADMIN_ID == 0:
        return

    username = message.from_user.username or "unknown"
    time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    note = message.caption if message.caption else "Keine Notiz"

    caption = (
        f"📸 SCREENSHOT\n\n"
        f"👤 User ID: {message.from_user.id}\n"
        f"🧑 @{username}\n"
        f"🕒 {time}\n\n"
        f"💬 Notiz:\n{note}"
    )

    bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption)

# ---------------- 👥 /invites ----------------

@bot.message_handler(commands=["invites"])
def invites(message):

    user = get_user(str(message.from_user.id))

    invite_list = user.get("invite_list") or []

    text = (
        f"👥 Invites: {user.get('invites', 0)}\n"
        f"🔗 Code: {user.get('ref_code')}\n\n"
        f"📜 Letzte Invites:\n"
    )

    if not invite_list:
        text += "Keine Invites"
    else:
        for i in invite_list[-5:]:
            text += f"• {i['username']} | {i['date']}\n"

    bot.send_message(message.chat.id, text)

# ---------------- 🏆 /top ----------------

@bot.message_handler(commands=["top"])
def top(message):

    res = supabase.table("users").select("*").execute()
    users = res.data or []

    users.sort(key=lambda x: x.get("invites", 0), reverse=True)

    text = "🏆 TOP 5 INVITER:\n\n"

    for i, u in enumerate(users[:5], 1):
        name = (u.get("invite_list") or [{"username": "user"}])[0]["username"]
        name = name[:3] + "***"

        text += f"{i}. {name} – {u.get('invites', 0)} Invites\n"

    bot.send_message(message.chat.id, text)

# ---------------- 📊 /rank ----------------

@bot.message_handler(commands=["rank"])
def rank(message):

    user_id = str(message.from_user.id)

    res = supabase.table("users").select("*").execute()
    users = res.data or []

    users.sort(key=lambda x: x.get("invites", 0), reverse=True)

    pos = 0
    invites = 0

    for i, u in enumerate(users, 1):
        if str(u.get("id")) == user_id:
            pos = i
            invites = u.get("invites", 0)
            break

    bot.send_message(
        message.chat.id,
        f"📊 Dein Rank:\n\n🏅 Platz: {pos}\n👥 Invites: {invites}"
    )

# ---------------- RUN ----------------

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    print("Bot läuft stabil 🚀")
    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)

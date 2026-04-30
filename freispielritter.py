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
ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)

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

    # UPsert = stabiler als insert (verhindert Race Issues)
    supabase.table("users").upsert(new_user).execute()

    return new_user


def update_user(user_id, fields: dict):
    user_id = str(user_id).strip()
    supabase.table("users").update(fields).eq("id", user_id).execute()


def find_user_by_ref(code):
    res = supabase.table("users").select("id").eq("ref_code", code).execute()
    if res.data:
        return res.data[0]["id"]
    return None


def is_admin(user_id):
    try:
        return int(user_id) == int(ADMIN_ID)
    except:
        return False


# ---------------- XP SYSTEM (FIXED & SAFE) ----------------

def add_xp(user_id, amount=10):

    user = get_user(user_id)

    now = datetime.utcnow()

    last = user.get("last_xp")

    # cooldown 10 sec
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


# ---------------- MINI APP API ----------------

@app.route("/xp")
def xp_get():

    user_id = request.args.get("id")
    if not user_id:
        return jsonify({"error": "no id"})

    user = get_user(user_id)

    return jsonify({
        "xp": user.get("xp", 0),
        "level": user.get("level", 1)
    })


@app.route("/xp/update", methods=["POST"])
def xp_update():

    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "no data"}), 400

        user_id = str(data.get("id")).strip()
        action = data.get("action")

        if not user_id or action != "deal_click":
            return jsonify({"error": "invalid request"}), 400

        xp, level = add_xp(user_id, 10)

        return jsonify({
            "ok": True,
            "xp": xp,
            "level": level
        })

    except Exception as e:
        print("XP ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/ref")
def ref_get():

    user_id = request.args.get("id")
    if not user_id:
        return jsonify({"error": "no id"})

    user = get_user(user_id)

    return jsonify({
        "ref_code": user.get("ref_code", ""),
        "invites": user.get("invites", 0)
    })


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

                try:
                    bot.send_message(ref_user_id, "🎉 Neuer Invite + XP erhalten!")
                except:
                    pass

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du 18 Jahre oder älter?", reply_markup=markup)


# ---------------- CALLBACK (UNVERÄNDERT) ----------------

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

        except Exception as e:
            print("CHANNEL ERROR:", e)
            bot.send_message(chat_id, "⚠️ Kanalprüfung aktuell nicht möglich.")
            return

        if status not in ["member", "administrator", "creator"]:
            bot.send_message(chat_id, "❌ Du bist noch nicht im Kanal.")
            return

        user = get_user(str(chat_id))

        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        web_app = types.WebAppInfo(
            "https://freispielritter.pages.dev/"
        )

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("🚀 Mini App starten", web_app=web_app))

        bot.send_message(
            chat_id,
            "✅ Freigeschaltet!\n\n"
            f"🔗 Dein Ref-Link:\n{ref_link}",
            reply_markup=markup
        )


# ---------------- SCREENSHOT (UNVERÄNDERT) ----------------

@bot.message_handler(content_types=['photo'])
def screenshot(message):

    if ADMIN_ID == 0:
        return

    try:
        admin = int(ADMIN_ID)
    except:
        return

    username = message.from_user.username or "unknown"
    time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    user_text = message.caption if message.caption else "❌ Kein Text angegeben"

    caption = (
        "📸 SCREENSHOT\n\n"
        f"👤 User ID: {message.from_user.id}\n"
        f"🧑 Username: @{username}\n"
        f"🕒 Zeit: {time}\n\n"
        f"💬 Nachricht:\n{user_text}"
    )

    try:
        bot.send_photo(admin, message.photo[-1].file_id, caption=caption)
    except Exception as e:
        print("Screenshot error:", e)


# ---------------- WEB SERVER ----------------

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# ---------------- START ----------------

if __name__ == "__main__":
    print("Bot läuft stabil 🚀")

    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)

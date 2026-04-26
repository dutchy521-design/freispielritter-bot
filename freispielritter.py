import telebot
import os
import random
import string
from telebot import types
from flask import Flask, request, jsonify
import threading
from datetime import datetime
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
    user_id = str(user_id)

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
        "invite_list": []
    }

    supabase.table("users").insert(new_user).execute()
    return new_user

def update_user(user_id, fields: dict):
    supabase.table("users").update(fields).eq("id", str(user_id)).execute()

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

# ---------------- XP SYSTEM ----------------
def add_xp(user_id, amount=10):

    user = get_user(user_id)

    xp = user.get("xp", 0) + amount
    level = (xp // 100) + 1

    update_user(user_id, {
        "xp": xp,
        "level": level
    })

    return xp, level

# ---------------- MINI APP API ----------------

@app.route("/xp")
def get_xp():

    user_id = request.args.get("id")

    if not user_id:
        return jsonify({"error": "no id"})

    user = get_user(user_id)

    return jsonify({
        "xp": user.get("xp", 0),
        "level": user.get("level", 1)
    })


@app.route("/xp/update", methods=["POST"])
def update_xp():

    data = request.json or {}

    user_id = str(data.get("id"))
    add_amount = int(data.get("xp", 0))

    if not user_id:
        return jsonify({"error": "no id"})

    user = get_user(user_id)

    new_xp = user.get("xp", 0) + add_amount
    new_level = (new_xp // 100) + 1

    update_user(user_id, {
        "xp": new_xp,
        "level": new_level
    })

    return jsonify({
        "ok": True,
        "xp": new_xp,
        "level": new_level
    })


@app.route("/ref")
def get_ref():

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
                    "invites": ref_user["invites"] + 1,
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

    bot.send_message(
        message.chat.id,
        "🔞 Bist du 18 Jahre oder älter?",
        reply_markup=markup
    )

# ---------------- SCREENSHOT FIX ----------------
@bot.message_handler(content_types=['photo'])
def handle_photo(message):

    if not ADMIN_ID:
        return

    try:
        admin = int(ADMIN_ID)
    except:
        return

    if admin == 0:
        return

    username = message.from_user.username or "unknown"
    time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    caption = (
        "📸 SCREENSHOT\n\n"
        f"👤 User ID: {message.from_user.id}\n"
        f"🧑 Username: @{username}\n"
        f"🕒 Zeit: {time}"
    )

    try:
        bot.send_photo(admin, message.photo[-1].file_id, caption=caption)
    except Exception as e:
        print("Screenshot error:", e)

# ---------------- ADMIN ----------------
@bot.message_handler(commands=["admin_user"])
def admin_user(message):

    if not is_admin(message.from_user.id):
        return

    args = message.text.split()

    if len(args) < 2:
        bot.send_message(message.chat.id, "Nutze: /admin_user ID")
        return

    uid = args[1]

    res = supabase.table("users").select("*").eq("id", uid).execute()

    if not res.data:
        bot.send_message(message.chat.id, "User nicht gefunden")
        return

    u = res.data[0]

    text = (
        f"👤 USER INFO\n\n"
        f"ID: {u['id']}\n"
        f"Invites: {u.get('invites',0)}\n"
        f"XP: {u.get('xp',0)}\n"
        f"Level: {u.get('level',1)}\n"
        f"Ref: {u.get('ref_code','-')}\n"
    )

    bot.send_message(message.chat.id, text)

# ---------------- WEB ----------------
def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    print("Bot läuft 🚀")

    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)

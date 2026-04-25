import telebot
import os
import json
import random
import string
from telebot import types
from flask import Flask, request, jsonify
import threading

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN:
    print("TOKEN fehlt!")
    exit()

ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else 0

bot = telebot.TeleBot(TOKEN)

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Freispielritter läuft 🚀"

# ---------------- SAFE DATA INIT ----------------
DATA_FILE = "data.json"

def init_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"users": {}}, f)

init_data()

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

if "users" not in data:
    data["users"] = {}

# ---------------- REF SYSTEM ----------------
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def get_user(user_id):
    user_id = str(user_id)

    if user_id not in data["users"]:
        data["users"][user_id] = {
            "ref_code": generate_code(),
            "invites": 0,
            "used_ref": None
        }
        save_data()

    return data["users"][user_id]

def find_user_by_code(code):
    for uid, u in data["users"].items():
        if u.get("ref_code") == code:
            return uid
    return None

# ---------------- API ----------------
@app.route("/ref")
def ref():
    user_id = request.args.get("id")

    if not user_id:
        return jsonify({"error": "no id"}), 400

    user_id = str(user_id)

    users = data.get("users", {})

    if user_id not in users:
        return jsonify({"error": "not found"}), 404

    user = users[user_id]

    return jsonify({
        "ref_code": user.get("ref_code", ""),
        "invites": user.get("invites", 0)
    })

# ---------------- BOT ----------------
@bot.message_handler(commands=["start"])
def start(message):

    user_id = str(message.from_user.id)
    user = get_user(user_id)

    args = message.text.split()

    if len(args) > 1:
        ref_code = args[1]
        ref_user_id = find_user_by_code(ref_code)

        if ref_user_id and user.get("used_ref") is None and ref_user_id != user_id:
            data["users"][ref_user_id]["invites"] += 1
            user["used_ref"] = ref_code
            save_data()

            try:
                bot.send_message(ref_user_id, "🎉 +1 Invite")
            except:
                pass

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ 18+", callback_data="yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du 18+?", reply_markup=markup)

# ---------------- CALLBACK ----------------
CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = str(call.message.chat.id)

    if call.data == "yes":

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Kanal", url=f"https://t.me/{CHANNEL.replace('@','')}"))
        markup.add(types.InlineKeyboardButton("✅ Weiter", callback_data="go"))

        bot.send_message(chat_id, "👉 Kanal beitreten", reply_markup=markup)

    elif call.data == "go":

        user = get_user(chat_id)
        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        web_app = types.WebAppInfo("https://shiny-dolphin-f9ce7d.netlify.app/")
        markup.add(types.KeyboardButton("🚀 Start", web_app=web_app))

        bot.send_message(chat_id, f"✅ Freigeschaltet\nRef: {ref_link}", reply_markup=markup)

    bot.answer_callback_query(call.id)

# ---------------- WEB ----------------
def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ---------------- START ----------------
if __name__ == "__main__":
    print("Bot + Web startet...")

    threading.Thread(target=run_web, daemon=True).start()

    bot.infinity_polling(skip_pending=True)

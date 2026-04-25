import telebot
import os
import json
import random
import string
from telebot import types
from datetime import datetime
from flask import Flask, request, jsonify
import threading

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(TOKEN)

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Freispielritter läuft 🚀"

@app.route("/ref")
def get_ref():
    user_id = request.args.get("id")

    if not user_id or user_id not in data["users"]:
        return jsonify({"error": "not found"})

    user = data["users"][user_id]

    return jsonify({
        "ref_code": user["ref_code"],
        "invites": user["invites"]
    })

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ---------------- DATA ----------------
DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"users": {}}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

verified_users = set()

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
    for uid, udata in data["users"].items():
        if udata["ref_code"] == code:
            return uid
    return None

# ---------------- START ----------------

@bot.message_handler(commands=['start'])
def start(message):

    user_id = str(message.from_user.id)
    user = get_user(user_id)

    args = message.text.split()

    if len(args) > 1:
        ref_code = args[1]
        ref_user_id = find_user_by_code(ref_code)

        if ref_user_id and user["used_ref"] is None and ref_user_id != user_id:
            data["users"][ref_user_id]["invites"] += 1
            user["used_ref"] = ref_code
            save_data()

            try:
                bot.send_message(ref_user_id, "🎉 Neuer Invite +1!")
            except:
                pass

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du 18+?", reply_markup=markup)

# ---------------- CALLBACK ----------------

CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = str(call.message.chat.id)

    if call.data == "age_yes":

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "📢 Kanal beitreten",
                url=f"https://t.me/{CHANNEL.replace('@','')}"
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                "✅ Fertig",
                callback_data="join_channel"
            )
        )

        bot.send_message(chat_id, "👉 Bitte Kanal beitreten", reply_markup=markup)

    elif call.data == "join_channel":

        user = get_user(chat_id)
        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        web_app = types.WebAppInfo("https://shiny-dolphin-f9ce7d.netlify.app/")
        markup.add(types.KeyboardButton("🚀 Start", web_app=web_app))

        bot.send_message(
            chat_id,
            f"✅ Freigeschaltet!\nRef: {ref_link}",
            reply_markup=markup
        )

    bot.answer_callback_query(call.id)

# ---------------- SCREENSHOT ----------------

@bot.message_handler(content_types=['photo'])
def handle_photo(message):

    user = message.from_user
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    username = user.username if user.username else f"user_{user.id}"

    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    file_path = f"uploads/{username}_{user.id}_{timestamp}.jpg"

    os.makedirs("uploads", exist_ok=True)

    with open(file_path, 'wb') as f:
        f.write(downloaded_file)

    if ADMIN_ID:
        try:
            caption = f"📸 Screenshot @{username} ({user.id})"
            bot.send_photo(ADMIN_ID, downloaded_file, caption=caption)
        except:
            pass

    bot.send_message(message.chat.id, "📸 gespeichert 🚀")

# ---------------- TOP ----------------

@bot.message_handler(commands=['top'])
def top(message):

    sorted_users = sorted(
        data["users"].items(),
        key=lambda x: x[1]["invites"],
        reverse=True
    )

    text = "🏆 TOP INVITER:\n\n"

    for i, (uid, udata) in enumerate(sorted_users[:10], 1):
        text += f"{i}. {uid} → {udata['invites']}\n"

    bot.send_message(message.chat.id, text)

# ---------------- START SYSTEM ----------------

if __name__ == "__main__":
    print("Bot + Web startet...")

    threading.Thread(target=run_web, daemon=True).start()

    bot.infinity_polling(skip_pending=True)

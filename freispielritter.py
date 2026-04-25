import telebot
import os
import json
import random
import string
from telebot import types
from flask import Flask, request, jsonify
import threading
from datetime import datetime

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

# ---------------- DATA ----------------
DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"users": {}}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

if "users" not in data:
    data["users"] = {}

# ---------------- REF + USER ----------------
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def get_user(user_id):
    user_id = str(user_id)

    if user_id not in data["users"]:
        data["users"][user_id] = {
            "ref_code": generate_code(),
            "invites": 0,
            "invite_list": [],
            "xp": 0,
            "level": 1,
            "used_ref": None
        }
        save_data(data)

    return data["users"][user_id]

def find_user_by_ref(code):
    for uid, u in data["users"].items():
        if u.get("ref_code") == code:
            return uid
    return None

# ---------------- XP API ----------------
@app.route("/xp")
def get_xp():
    user_id = request.args.get("id")

    if not user_id:
        return jsonify({"error": "no id"}), 400

    user_id = str(user_id)

    if user_id not in data["users"]:
        return jsonify({"error": "not found"}), 404

    u = data["users"][user_id]

    return jsonify({
        "xp": u.get("xp", 0),
        "level": u.get("level", 1)
    })

@app.route("/xp/update", methods=["POST"])
def update_xp():
    body = request.json

    user_id = str(body.get("id"))
    xp = int(body.get("xp", 0))
    level = int(body.get("level", 1))

    if user_id not in data["users"]:
        return jsonify({"error": "not found"}), 404

    data["users"][user_id]["xp"] = xp
    data["users"][user_id]["level"] = level

    save_data(data)

    return jsonify({"ok": True})

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(message):

    user_id = str(message.from_user.id)
    user = get_user(user_id)

    args = message.text.split()

    if len(args) > 1:
        ref_code = args[1]
        ref_user_id = find_user_by_ref(ref_code)

        if ref_user_id and ref_user_id != user_id and user.get("used_ref") is None:

            inviter = data["users"][ref_user_id]

            inviter["invites"] += 1
            inviter["invite_list"].append({
                "id": user_id,
                "username": message.from_user.username or "unknown",
                "date": datetime.now().strftime("%d.%m.%Y")
            })

            user["used_ref"] = ref_code
            save_data(data)

            try:
                bot.send_message(ref_user_id, "🎉 Neuer Invite!")
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

# ---------------- TOP ----------------
@bot.message_handler(commands=["top"])
def top(message):

    user_id = str(message.from_user.id)

    ranking = sorted(
        data["users"].items(),
        key=lambda x: x[1].get("invites", 0),
        reverse=True
    )

    text = "🏆 Top 5 Inviter\n\n"

    for i, (uid, u) in enumerate(ranking[:5], start=1):
        text += f"{i}. User*** — {u.get('invites',0)}\n"

    pos = 0
    for i, (uid, _) in enumerate(ranking, start=1):
        if uid == user_id:
            pos = i
            break

    my_inv = data["users"].get(user_id, {}).get("invites", 0)

    text += "\n────────────\n"
    text += f"Du bist Platz #{pos}\n"
    text += f"Deine Invites: {my_inv}"

    bot.send_message(message.chat.id, text)

# ---------------- USER INVITES ----------------
@bot.message_handler(commands=["invites"])
def invites(message):

    user_id = str(message.from_user.id)
    user = get_user(user_id)

    invites = user.get("invite_list", [])

    if not invites:
        bot.send_message(message.chat.id, "Keine Invites vorhanden.")
        return

    text = "👥 Deine Invites\n\n"

    for i, inv in enumerate(invites, start=1):
        name = inv["username"]
        date = inv["date"]

        if name != "unknown":
            name = "@" + name

        text += f"{i}. {name} — {date}\n"

    bot.send_message(message.chat.id, text)

# ---------------- ADMIN ALL ----------------
@bot.message_handler(commands=["admin_invites"])
def admin_invites(message):

    if message.from_user.id != ADMIN_ID:
        return

    text = "📊 Invite Log\n\n"

    for uid, u in data["users"].items():

        invites = u.get("invite_list", [])

        if not invites:
            continue

        text += f"{uid}\n"

        for inv in invites:
            name = inv["username"]
            date = inv["date"]

            if name != "unknown":
                name = "@" + name

            text += f" └ {name} — {date}\n"

        text += "\n"

    bot.send_message(message.chat.id, text)

# ---------------- ADMIN USER ----------------
@bot.message_handler(commands=["admin_user"])
def admin_user(message):

    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()

    if len(args) < 2:
        bot.send_message(message.chat.id, "Nutze: /admin_user ID")
        return

    uid = args[1]

    if uid not in data["users"]:
        bot.send_message(message.chat.id, "User nicht gefunden")
        return

    user = data["users"][uid]
    invites = user.get("invite_list", [])

    text = f"User: {uid}\n"
    text += f"Invites: {len(invites)}\n\n"

    for i, inv in enumerate(invites, start=1):
        name = inv["username"]
        date = inv["date"]

        if name != "unknown":
            name = "@" + name

        text += f"{i}. {name} — {date}\n"

    bot.send_message(message.chat.id, text)

# ---------------- SCREENSHOTS / FILES ----------------
@bot.message_handler(content_types=['photo'])
def handle_photo(message):

    if ADMIN_ID == 0:
        return

    username = message.from_user.username
    username = f"@{username}" if username else "unknown"

    time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    caption = (
        "📸 SCREENSHOT\n\n"
        f"👤 User ID: {message.from_user.id}\n"
        f"🧑 Username: {username}\n"
        f"🕒 Zeit: {time}"
    )

    bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=caption
    )

@bot.message_handler(content_types=['document'])
def handle_document(message):

    if ADMIN_ID == 0:
        return

    username = message.from_user.username
    username = f"@{username}" if username else "unknown"

    time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    caption = (
        "📎 DATEI / SCREENSHOT\n\n"
        f"👤 User ID: {message.from_user.id}\n"
        f"🧑 Username: {username}\n"
        f"🕒 Zeit: {time}"
    )

    bot.send_document(
        ADMIN_ID,
        message.document.file_id,
        caption=caption
    )

# ---------------- CALLBACK ----------------
CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = str(call.message.chat.id)

    if call.data == "age_no":
        bot.send_message(chat_id, "❌ Zugriff verweigert.")
        bot.answer_callback_query(call.id)
        return

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
                "✅ Ich bin beigetreten",
                callback_data="check_channel"
            )
        )

        bot.send_message(chat_id, "👉 Bitte trete dem Kanal bei:", reply_markup=markup)

    elif call.data == "check_channel":

        try:
            member = bot.get_chat_member(CHANNEL, chat_id)

            if member.status not in ["member", "administrator", "creator"]:
                bot.answer_callback_query(call.id, "❌ Bitte zuerst beitreten!", show_alert=True)
                return

        except:
            bot.answer_callback_query(call.id, "❌ Fehler beim Prüfen", show_alert=True)
            return

        user = get_user(chat_id)

        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        web_app = types.WebAppInfo(
            "https://shiny-dolphin-f9ce7d.netlify.app/"
        )

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("🚀 Mini App starten", web_app=web_app))

        bot.send_message(
            chat_id,
            "✅ Freigeschaltet!\n\n"
            f"🔗 Dein Ref-Link:\n{ref_link}",
            reply_markup=markup
        )

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

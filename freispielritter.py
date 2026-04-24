import telebot
import os
import json
import random
import string
from telebot import types
from datetime import datetime

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(TOKEN)

# ---------------- SETUP ----------------

if not os.path.exists("uploads"):
    os.makedirs("uploads")

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
                bot.send_message(ref_user_id, "🎉 Neuer Invite +1 für dich!")
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

# ---------------- CALLBACK ----------------

CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: call.data in ["age_yes", "age_no", "join_channel"])
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
                "✅ Ich bin beigetreten",
                callback_data="join_channel"
            )
        )

        bot.send_message(chat_id, "🔔 Bitte tritt zuerst dem Kanal bei:", reply_markup=markup)

    elif call.data == "join_channel":

        try:
            member = bot.get_chat_member(CHANNEL, chat_id)

            if member.status not in ["member", "creator", "administrator"]:
                bot.answer_callback_query(call.id, "❌ Du musst erst beitreten!", show_alert=True)
                return

        except:
            bot.answer_callback_query(call.id, "❌ Kanalprüfung fehlgeschlagen", show_alert=True)
            return

        if chat_id in verified_users:
            bot.answer_callback_query(call.id)
            return

        verified_users.add(chat_id)

        user = get_user(chat_id)
        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        web_app = types.WebAppInfo("https://shiny-dolphin-f9ce7d.netlify.app/")
        markup.add(types.KeyboardButton("Jetzt starten 🚀", web_app=web_app))

        bot.send_message(
            chat_id,
            "✅ Zugriff freigeschaltet!\n\n"
            f"🔗 Dein Referral Link:\n{ref_link}",
            reply_markup=markup
        )

    else:
        bot.send_message(chat_id, "❌ Zugriff verweigert.")

    bot.answer_callback_query(call.id)

# ---------------- SCREENSHOT (FIXED) ----------------

@bot.message_handler(content_types=['photo'])
def handle_photo(message):

    user = message.from_user
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    username = user.username if user.username else f"user_{user.id}"

    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    file_path = f"uploads/{username}_{user.id}_{timestamp}.jpg"

    with open(file_path, 'wb') as f:
        f.write(downloaded_file)

    # 📲 SEND TO ADMIN
    if ADMIN_ID:
        try:
            caption = f"📸 Screenshot\n👤 @{username}\n🆔 {user.id}\n🕒 {timestamp}"
            bot.send_photo(ADMIN_ID, downloaded_file, caption=caption)
        except Exception as e:
            print("Admin send error:", e)

    bot.send_message(message.chat.id, "📸 Screenshot gespeichert & gesendet 🚀")

# ---------------- AVATAR ----------------

@bot.message_handler(commands=['avatar'])
def avatar(message):

    photos = bot.get_user_profile_photos(message.from_user.id)

    if photos.total_count > 0:
        file_info = bot.get_file(photos.photos[0][-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        file_path = f"uploads/{message.from_user.id}_avatar.jpg"

        with open(file_path, 'wb') as f:
            f.write(downloaded_file)

        bot.send_message(message.chat.id, "Avatar gespeichert 🧑‍💻")
    else:
        bot.send_message(message.chat.id, "Kein Avatar gefunden")

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
        text += f"{i}. {uid} → {udata['invites']} Invites\n"

    bot.send_message(message.chat.id, text)

print("Bot läuft...")
bot.infinity_polling()

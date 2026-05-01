import telebot
import os
import random
import string
from telebot import types
from flask import Flask
import threading
from datetime import datetime
from supabase import create_client, Client

# ---------------- SUPABASE ----------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot läuft 🚀"

# ---------------- MEMORY ----------------
pending_xp_requests = {}
pending_pet = {}

# ---------------- USER ----------------
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
        "ref_code": ''.join(random.choices(string.ascii_letters + string.digits, k=6)),
        "used_ref": None,
        "invite_list": [],
        "daily_pet": None,
        "daily_pet_name": None,
        "daily_stage": 0,
        "last_daily": None
    }

    supabase.table("users").upsert(new_user).execute()
    return new_user

def update_user(user_id, fields):
    supabase.table("users").update(fields).eq("id", str(user_id)).execute()

def add_xp(user_id, amount):
    user = get_user(user_id)
    xp = int(user.get("xp", 0)) + amount
    level = (xp // 100) + 1
    update_user(user_id, {"xp": xp, "level": level})

# ---------------- CALLBACK ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    try:
        chat_id = call.message.chat.id
        bot.answer_callback_query(call.id)

        # ---------------- PET ACTIONS (FIXED TEXTS) ----------------
        if call.data == "feed":
            bot.send_message(chat_id, random.choice([
                "🍖 Dein Tier verschlingt das Essen glücklich!",
                "😋 Es hat deinem Tier richtig gut geschmeckt!",
                "🍗 Dein Tier schnurrt zufrieden nach dem Fressen!",
                "😍 Es schaut dich dankbar an!"
            ]))
            update_user(chat_id, {"daily_stage": 1})
            return

        if call.data == "walk":
            bot.send_message(chat_id, random.choice([
                "🚶 Ihr geht entspannt durch den Park 🌳",
                "🎰 Auf dem Weg Richtung Casino… dein Tier ist aufgeregt!",
                "🌿 Frische Luft, dein Tier fühlt sich frei!",
                "🐾 Ihr erkundet gemeinsam die Umgebung!"
            ]))
            update_user(chat_id, {"daily_stage": 2})
            return

        if call.data == "play":
            user = get_user(chat_id)

            bot.send_message(chat_id, random.choice([
                "🎰 Ihr setzt euch an den Spielautomaten…",
                "💰 BIG WIN steht heute in der Luft!",
                "🔥 Dein Tier schaut gespannt auf die Slots!",
                "🎲 Ihr spielt voller Hoffnung…"
            ]))

            if user.get("daily_stage") == 2:
                add_xp(chat_id, 3)
                update_user(chat_id, {
                    "last_daily": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                bot.send_message(chat_id, "🏆 Daily Quest abgeschlossen +3 XP")
            return

        # ---------------- XP CALLBACK FIX ----------------
        if call.data.startswith("xp_"):

            req_id = call.data.split("_")[2]
            data = pending_xp_requests.get(req_id)

            if not data:
                return

            user_id = data["user_id"]

            if call.data.startswith("xp_yes"):
                add_xp(user_id, 5)

                bot.send_message(user_id, "💳 Screenshot bestätigt +5 XP erhalten")
                bot.send_message(ADMIN_ID, "✅ XP erfolgreich vergeben")

            pending_xp_requests.pop(req_id, None)
            return

    except Exception as e:
        print("CALLBACK ERROR:", e)

# ---------------- SCREENSHOT FIX ----------------
@bot.message_handler(content_types=['photo'])
def screenshot(message):

    req_id = str(message.message_id)

    pending_xp_requests[req_id] = {
        "user_id": str(message.from_user.id)
    }

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Bestätigen +5 XP", callback_data=f"xp_yes_{req_id}"),
        types.InlineKeyboardButton("❌ Ablehnen", callback_data=f"xp_no_{req_id}")
    )

    bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"📸 @{message.from_user.username or 'unknown'}\n💬 {message.caption or 'keine Notiz'}\n🕒 {datetime.now().strftime('%H:%M:%S')}",
        reply_markup=markup
    )

# ---------------- COMMANDS FIX ----------------
@bot.message_handler(commands=["xp"])
def xp(message):
    user = get_user(message.from_user.id)
    bot.send_message(message.chat.id, f"⭐ XP: {user['xp']}\n🏆 Level: {user['level']}")

@bot.message_handler(commands=["notes"])
def notes(message):
    res = supabase.table("notes").select("*").eq("user_id", str(message.from_user.id)).execute()

    if not res.data:
        bot.send_message(message.chat.id, "Keine Notes")
        return

    text = ""
    for n in res.data:
        text += f"{n['note']} ({n.get('date','kein Datum')})\n"

    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["invites"])
def invites(message):
    user = get_user(message.from_user.id)
    bot.send_message(message.chat.id, f"👥 Invites: {user.get('invites',0)}")

@bot.message_handler(commands=["top"])
def top(message):

    res = supabase.table("users").select("id,invites").order("invites", desc=True).limit(5).execute()

    text = "🏆 TOP USERS:\n\n"
    for i,u in enumerate(res.data,1):
        text += f"{i}. {u['id']} - {u['invites']}\n"

    bot.send_message(message.chat.id, text)

# ---------------- RUN ----------------
def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()

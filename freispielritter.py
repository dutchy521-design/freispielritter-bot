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

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(TOKEN)

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot läuft 🚀"

# ---------------- MEMORY ----------------
pending_xp_requests = {}

# ---------------- LEVEL ----------------
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
        "invite_list": [],
        "last_xp": None,
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

    update_user(user_id, {
        "xp": xp,
        "level": level
    })

# ---------------- FLASK ----------------
def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# =========================================================
# START (FIXED SAFE)
# =========================================================
@bot.message_handler(commands=["start"])
def start(message):
    try:
        args = message.text.split()
        ref = args[1] if len(args) > 1 else None

        user = get_user(message.from_user.id)

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
            types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
        )

        bot.send_message(message.chat.id, "🔞 Bist du über 18 Jahre alt?", reply_markup=markup)

    except Exception as e:
        print("START ERROR:", e)
        bot.send_message(message.chat.id, "⚠️ Fehler beim Start")

# =========================================================
# CALLBACK (UNVERÄNDERT, nur safe wrapper)
# =========================================================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    try:
        if not call.message:
            return

        chat_id = call.message.chat.id
        bot.answer_callback_query(call.id)

        if call.data == "age_no":
            bot.send_message(chat_id, "❌ Kein Zugriff.")
            return

        if call.data == "age_yes":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📢 Zum Kanal", url="https://t.me/Freispielritter"))
            markup.add(types.InlineKeyboardButton("✅ Ich bin beigetreten", callback_data="check_channel"))
            bot.send_message(chat_id, "👉 Folgst du schon unserem Kanal?", reply_markup=markup)
            return

        if call.data == "check_channel":
            try:
                member = bot.get_chat_member("@Freispielritter", call.from_user.id)
                if member.status not in ["member", "administrator", "creator"]:
                    bot.send_message(chat_id, "❌ Nicht im Kanal.")
                    return
            except:
                bot.send_message(chat_id, "⚠️ Fehler.")
                return

            user = get_user(chat_id)
            ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🚀 Mini App", web_app=types.WebAppInfo("https://freispielritter.pages.dev/")))
            markup.add(types.InlineKeyboardButton("📦 Deals öffnen", callback_data="open_deals"))

            bot.send_message(chat_id, f"✅ Freigeschaltet\n\n{ref_link}", reply_markup=markup)
            return

        if call.data == "open_deals":

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔥 Top Deal 😉", callback_data="top_deal"))
            markup.add(types.InlineKeyboardButton("🐾 Daily Quest", callback_data="daily_start"))

            bot.send_message(chat_id, "🎰 Wähle deinen Deal:", reply_markup=markup)
            return

        if call.data == "top_deal":
            user = call.from_user

            bot.send_message(
                ADMIN_ID,
                f"🔥 TOP DEAL\n👤 {user.id}\n@{user.username}"
            )

            bot.send_message(chat_id, "🔥 Anfrage gesendet")
            return

        if call.data == "daily_start":
            user = get_user(chat_id)

            if user.get("last_daily"):
                bot.send_message(chat_id, "⏳ Schon gemacht")
                return

            pets = ["🐶","🐱","🐺","🦊","🐵","🐸","🐼","🐉"]

            markup = types.InlineKeyboardMarkup()
            for p in pets:
                markup.add(types.InlineKeyboardButton(p, callback_data=f"pet_select_{p}"))

            bot.send_message(chat_id, "🐾 Tier wählen:", reply_markup=markup)
            return

        if call.data.startswith("pet_select_"):
            pet = call.data.split("_")[2]

            update_user(chat_id, {
                "daily_pet": pet,
                "daily_stage": 0
            })

            bot.send_message(chat_id, f"✨ Tier: {pet}\nJetzt Namen eingeben:")
            return

        if call.data == "daily_feed":
            bot.send_message(chat_id, random.choice(["🍖 gut", "😐 ok", "🤢 schlecht"]))
            update_user(chat_id, {"daily_stage": 1})
            return

        if call.data == "daily_walk":
            bot.send_message(chat_id, random.choice(["🚶 unterwegs", "🌳 entspannt", "🎰 Casino vibes"]))
            update_user(chat_id, {"daily_stage": 2})
            return

        if call.data == "daily_play":
            bot.send_message(chat_id, random.choice(["🎰 spin", "💰 win", "🔥 jackpot vibe"]))

            user = get_user(chat_id)

            if user.get("daily_stage") == 2:
                add_xp(chat_id, 3)
                update_user(chat_id, {
                    "last_daily": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                bot.send_message(chat_id, "🏆 +3 XP")
            return

    except Exception as e:
        print("CALLBACK ERROR:", e)
        return

# ---------------- RUN ----------------
if __name__ == "__main__":
    threading.Thread(target=run).start()
    print("BOT STARTED")
    bot.infinity_polling()

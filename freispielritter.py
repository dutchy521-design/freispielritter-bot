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

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot läuft 🚀"

# ---------------- MEMORY ----------------
pending_xp_requests = {}
pending_name = {}
pet_state = {}

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

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(message):

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Bist du über 18?", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bestätigung:", reply_markup=markup)

# ---------------- CALLBACK ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    try:
        chat_id = call.message.chat.id
        bot.answer_callback_query(call.id)

        # ---------------- AGE ----------------
        if call.data == "age_no":
            bot.send_message(chat_id, "❌ Kein Zugriff.")
            return

        if call.data == "age_yes":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Zum Kanal", url="https://t.me/Freispielritter"))
            markup.add(types.InlineKeyboardButton("Ich bin beigetreten", callback_data="check_channel"))

            bot.send_message(chat_id, "👉 Treten unserem Kanal bei.", reply_markup=markup)
            return

        # ---------------- CHANNEL CHECK ----------------
        if call.data == "check_channel":

            user = get_user(chat_id)
            ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🚀 Mini App", web_app=types.WebAppInfo("https://freispielritter.pages.dev/")))
            markup.add(types.InlineKeyboardButton("📦 Deals öffnen", callback_data="open_deals"))

            bot.send_message(chat_id, f"✅ Freigeschaltet\n\n{ref_link}", reply_markup=markup)
            return

        # ---------------- DEALS ----------------
        if call.data == "open_deals":

            markup = types.InlineKeyboardMarkup()

            markup.add(types.InlineKeyboardButton("🔥 Top Deal", callback_data="top_deal"))
            markup.add(types.InlineKeyboardButton("🐾 Daily Quest", callback_data="daily_start"))

            markup.add(types.InlineKeyboardButton("🥇 Goldzino", url="https://track.stormaffiliates.com/visit/?bta=35714"))
            markup.add(types.InlineKeyboardButton("🎁 Freispiele", url="https://1f0s0.fit/r/XJTWVH25"))
            markup.add(types.InlineKeyboardButton("💰 Crypto Casino", url="https://t.me/tgcplaybot/?start=UsHEI0AGB"))

            bot.send_message(chat_id, "🎰 Deals:", reply_markup=markup)
            return

        # ---------------- TOP DEAL FIX ----------------
        if call.data == "top_deal":

            bot.send_message(
                ADMIN_ID,
                f"TOP DEAL ANFRAGE\nUSER ID: {call.from_user.id}"
            )

            bot.send_message(
                chat_id,
                "🔥 Exklusiv – ein Admin wird sich in Kürze bei dir melden."
            )
            return

        # ---------------- DAILY ----------------
        if call.data == "daily_start":

            pets = ["🐶","🐱","🐺","🦊","🐵","🐸","🐼","🐉"]

            markup = types.InlineKeyboardMarkup()
            for p in pets:
                markup.add(types.InlineKeyboardButton(p, callback_data=f"pet_{p}"))

            bot.send_message(chat_id, "🐾 Tier wählen:", reply_markup=markup)
            return

        # ---------------- PET ----------------
        if call.data.startswith("pet_"):

            pet = call.data.split("_")[1]
            pending_name[chat_id] = pet

            bot.send_message(chat_id, f"✨ Tier gewählt: {pet}\nJetzt Namen eingeben:")
            return

        # ---------------- ACTION MENU AFTER NAME ----------------
    except Exception as e:
        print("CALLBACK ERROR:", e)

# ---------------- NAME INPUT ----------------
@bot.message_handler(func=lambda m: True)
def text_handler(message):

    chat_id = message.chat.id

    if chat_id in pending_name:

        pet = pending_name.pop(chat_id)

        update_user(chat_id, {
            "daily_pet": pet,
            "daily_pet_name": message.text,
            "daily_stage": 0
        })

        pet_state[chat_id] = True

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🍖 Füttern", callback_data="feed"))
        markup.add(types.InlineKeyboardButton("🚶 Spazieren", callback_data="walk"))
        markup.add(types.InlineKeyboardButton("🎰 Spielen", callback_data="play"))

        bot.send_message(chat_id, f"🐾 Dein Tier {message.text} ist bereit!", reply_markup=markup)

        return

# ---------------- PET ACTIONS ----------------
@bot.callback_query_handler(func=lambda call: call.data in ["feed","walk","play"])
def pet_actions(call):

    chat_id = call.message.chat.id

    if call.data == "feed":
        bot.send_message(chat_id, random.choice(["🍖 lecker", "😐 ok", "🤢 bäh"]))
        update_user(chat_id, {"daily_stage": 1})

    if call.data == "walk":
        bot.send_message(chat_id, random.choice(["🚶 unterwegs", "🌳 happy", "🎰 casino vibes"]))
        update_user(chat_id, {"daily_stage": 2})

    if call.data == "play":
        user = get_user(chat_id)

        bot.send_message(chat_id, random.choice(["🎰 spin", "💰 win", "🔥 jackpot"]))

        if user.get("daily_stage") == 2:
            add_xp(chat_id, 3)
            update_user(chat_id, {"last_daily": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            bot.send_message(chat_id, "🏆 +3 XP Daily Quest abgeschlossen")

# ---------------- SCREENSHOT FIX ----------------
@bot.message_handler(content_types=['photo'])
def screenshot(message):

    req_id = str(message.message_id)

    pending_xp_requests[req_id] = {
        "user_id": str(message.from_user.id)
    }

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("XP +5", callback_data=f"xp_yes_{req_id}"),
        types.InlineKeyboardButton("Ablehnen", callback_data=f"xp_no_{req_id}")
    )

    bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"Screenshot von {message.from_user.id}",
        reply_markup=markup
    )

# ---------------- XP CALLBACK FIX ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("xp_"))
def xp_handler(call):

    req_id = call.data.split("_")[2]
    data = pending_xp_requests.get(req_id)

    if not data:
        return

    user_id = data["user_id"]

    if call.data.startswith("xp_yes"):
        add_xp(user_id, 5)
        bot.send_message(user_id, "💳 +5 XP bestätigt")

    pending_xp_requests.pop(req_id, None)

# ---------------- RUN ----------------
def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()

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

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(message):

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🟢 Ja", callback_data="age_yes"),
        types.InlineKeyboardButton("🔴 Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "Bist du über 18 Jahre alt?", reply_markup=markup)

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

        # ---------------- CHANNEL ----------------
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

        # ---------------- TOP DEAL ----------------
        if call.data == "top_deal":

            user = call.from_user

            bot.send_message(
                ADMIN_ID,
                f"TOP DEAL ANFRAGE\nID: {user.id}\n@{user.username or 'unknown'}"
            )

            bot.send_message(chat_id, "🔥 Exklusiv – ein Admin meldet sich bald bei dir.")
            return

        # ---------------- PET ----------------
        if call.data == "daily_start":

            pets = ["🐶","🐱","🐺","🦊","🐵","🐸","🐼","🐉"]

            markup = types.InlineKeyboardMarkup()
            for p in pets:
                markup.add(types.InlineKeyboardButton(p, callback_data=f"pet_{p}"))

            bot.send_message(chat_id, "🐾 Tier wählen:", reply_markup=markup)
            return

        if call.data.startswith("pet_"):

            pet = call.data.split("_")[1]
            pending_pet[chat_id] = pet

            bot.send_message(chat_id, f"✨ Tier: {pet}\nJetzt Namen eingeben:")
            return

        # ---------------- PET ACTIONS ----------------
        if call.data == "feed":
            bot.send_message(chat_id, random.choice([
                "🍖 Dein Tier genießt das Essen sehr!",
                "😋 Es schmeckt ihm hervorragend!",
                "🐾 Zufriedenes Schnurren nach dem Füttern!"
            ]))
            update_user(chat_id, {"daily_stage": 1})
            return

        if call.data == "walk":
            bot.send_message(chat_id, random.choice([
                "🚶 Ihr spaziert durch den Park 🌳",
                "🎰 Auf dem Weg Richtung Casino...",
                "🐾 Dein Tier genießt die frische Luft!"
            ]))
            update_user(chat_id, {"daily_stage": 2})
            return

        if call.data == "play":

            user = get_user(chat_id)

            bot.send_message(chat_id, random.choice([
                "🎰 Ihr setzt euch an den Spielautomaten...",
                "💰 BIG WIN könnte gleich kommen!",
                "🔥 Dein Tier ist voller Spannung!"
            ]))

            if user.get("daily_stage") == 2:
                add_xp(chat_id, 3)
                update_user(chat_id, {
                    "last_daily": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                bot.send_message(chat_id, "🏆 Daily Quest abgeschlossen +3 XP")
            return

        # ---------------- XP CALLBACK ----------------
        if call.data.startswith("xp_"):

            req_id = call.data.split("_")[2]
            data = pending_xp_requests.get(req_id)

            if not data:
                return

            user_id = data["user_id"]

            if call.data.startswith("xp_yes"):
                add_xp(user_id, 5)
                bot.send_message(user_id, "💳 Screenshot bestätigt +5 XP")
                bot.send_message(ADMIN_ID, "✅ XP vergeben")

            pending_xp_requests.pop(req_id, None)
            return

    except Exception as e:
        print("CALLBACK ERROR:", e)

# ---------------- TEXT INPUT ----------------
@bot.message_handler(func=lambda m: True)
def text_handler(message):

    chat_id = message.chat.id

    if chat_id in pending_pet:

        pet = pending_pet.pop(chat_id)

        update_user(chat_id, {
            "daily_pet": pet,
            "daily_pet_name": message.text,
            "daily_stage": 0
        })

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🍖 Füttern", callback_data="feed"))
        markup.add(types.InlineKeyboardButton("🚶 Spazieren", callback_data="walk"))
        markup.add(types.InlineKeyboardButton("🎰 Spielen", callback_data="play"))

        bot.send_message(chat_id, f"🐾 Dein Tier {message.text} ist bereit!", reply_markup=markup)
        return

# ---------------- SCREENSHOT ----------------
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
        caption=f"📸 @{message.from_user.username or 'unknown'}\n💬 {message.caption or 'keine Notiz'}\n🕒 {datetime.now().strftime('%H:%M:%S')}",
        reply_markup=markup
    )

# ---------------- COMMANDS ----------------
@bot.message_handler(commands=["xp"])
def xp(message):
    user = get_user(message.from_user.id)
    bot.send_message(message.chat.id, f"⭐ XP: {user['xp']}\n🏆 Level: {user['level']}")

@bot.message_handler(commands=["notes"])
def notes(message):
    res = supabase.table("notes").select("*").eq("user_id", str(message.from_user.id)).execute()

    text = ""
    for n in res.data:
        text += f"{n['note']} ({n.get('date','kein Datum')})\n"

    bot.send_message(message.chat.id, text or "Keine Notes")

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

# ---------------- RUN (FIXED STABLE) ----------------
def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling(skip_pending=True)

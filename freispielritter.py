import telebot
import os
import random
import string
from telebot import types
from flask import Flask
import threading
from datetime import datetime, timedelta
from supabase import create_client, Client

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
pet_sessions = {}

# ---------------- LEVELS ----------------
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
        "last_daily": None
    }

    supabase.table("users").upsert(new_user).execute()
    return new_user

def update_user(user_id, data):
    supabase.table("users").update(data).eq("id", str(user_id)).execute()

def add_xp(user_id, amount):
    user = get_user(user_id)
    xp = int(user.get("xp", 0)) + amount
    level = (xp // 100) + 1

    update_user(user_id, {"xp": xp, "level": level})

# ---------------- DAILY BUTTON ----------------
@bot.message_handler(commands=["daily"])
def daily(message):

    user = get_user(message.from_user.id)
    last = user.get("last_daily")

    if last:
        try:
            last_time = datetime.fromisoformat(last)
            if datetime.utcnow() - last_time < timedelta(hours=24):
                bot.send_message(message.chat.id, "⏳ Daily Quest noch nicht bereit.")
                return
        except:
            pass

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🐾 Quest starten", callback_data="pet_start"))

    bot.send_message(
        message.chat.id,
        "━━━━━━━━━━━━━━\n🐾 DAILY QUEST\n━━━━━━━━━━━━━━\n\nStarte dein Haustier-Abenteuer!",
        reply_markup=markup
    )

# ---------------- PET SYSTEM ----------------
PET_TYPES = ["🐶","🐱","🐴","🦊","🐼","🐯","🐸","🐉"]

@bot.callback_query_handler(func=lambda call: call.data.startswith("pet_"))
def pet_handler(call):

    uid = str(call.from_user.id)

    # START
    if call.data == "pet_start":

        markup = types.InlineKeyboardMarkup()
        for p in PET_TYPES:
            markup.add(types.InlineKeyboardButton(p, callback_data=f"pet_{p}"))

        bot.send_message(call.message.chat.id, "Wähle dein Tier:", reply_markup=markup)
        return

    # PICK PET
    if call.data.startswith("pet_") and len(call.data) <= 6:

        pet = call.data.split("_")[1]

        pet_sessions[uid] = {
            "pet": pet,
            "name": None,
            "step": 1
        }

        bot.send_message(call.message.chat.id, f"Wie soll dein {pet} heißen?")
        bot.register_next_step_handler(call.message, pet_name)
        return

def pet_name(message):

    uid = str(message.from_user.id)

    if uid not in pet_sessions:
        return

    pet_sessions[uid]["name"] = message.text
    pet_sessions[uid]["step"] = 2

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🍖 Füttern", callback_data="pet_feed"))
    markup.add(types.InlineKeyboardButton("🚶 Spazieren", callback_data="pet_walk"))
    markup.add(types.InlineKeyboardButton("🎰 Spielen", callback_data="pet_play"))

    bot.send_message(
        message.chat.id,
        f"🐾 {message.text} ist bereit!\nWas willst du tun?",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("pet_"))
def pet_actions(call):

    uid = str(call.from_user.id)

    if uid not in pet_sessions:
        return

    pet = pet_sessions[uid]

    name = pet["name"]
    emoji = pet["pet"]

    if call.data == "pet_feed":

        res = random.choice([
            f"😋 {name} hat es geliebt!",
            f"🤢 {name} fand das komisch..."
        ])

        bot.send_message(call.message.chat.id, f"{emoji} {res}")

    if call.data == "pet_walk":

        res = random.choice([
            f"🚶 {name} und du gehen ins nächste Casino!",
            f"😴 {name} hatte keine Lust rauszugehen"
        ])

        bot.send_message(call.message.chat.id, f"{emoji} {res}")

    if call.data == "pet_play":

        res = random.choice([
            f"🎰 {name} fühlt sich glücklich am Slotautomaten!",
            f"🎲 {name} hat Spaß im Casino!"
        ])

        bot.send_message(call.message.chat.id, f"{emoji} {res}")

    # QUEST FINISH
    add_xp(uid, 3)

    user = get_user(uid)
    update_user(uid, {"last_daily": datetime.utcnow().isoformat()})

    bot.send_message(call.message.chat.id, "🎉 Daily Quest abgeschlossen!\n+3 XP")

    pet_sessions.pop(uid, None)

# ---------------- XP COMMAND (UPDATED ONLY DISPLAY) ----------------
@bot.message_handler(commands=["xp"])
def xp(message):

    user = get_user(message.from_user.id)

    bot.send_message(
        message.chat.id,
        "━━━━━━━━━━━━━━\n🏆 DEIN STATUS\n━━━━━━━━━━━━━━\n\n"
        f"⭐ XP: {user['xp']}\n"
        f"📈 Level: {user['level']}\n"
        f"🎖 Rang: {get_level_name(user['level'])}"
    )

# ---------------- RUN ----------------
def run():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()

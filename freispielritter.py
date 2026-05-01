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
quest_sessions = {}
quest_cooldowns = {}

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

# ---------------- START (UNVERÄNDERT) ----------------
@bot.message_handler(commands=["start"])
def start(message):

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📦 Deals öffnen", callback_data="open_deals"),
        types.InlineKeyboardButton("🧭 Quests", callback_data="quest_start")
    )

    bot.send_message(message.chat.id, "🔓 Willkommen im System", reply_markup=markup)

# ---------------- CALLBACK ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

    # ---------------- DEAL FIX ----------------
    if call.data == "open_deals":

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🔥 Top Deal", callback_data="top_deal")
        )
        markup.row(
            types.InlineKeyboardButton("🥇 Goldzino", url="https://track.stormaffiliates.com/visit/?bta=35714&brand=goldzino&afp=freispielritter"),
            types.InlineKeyboardButton("🎁 Freispiele", url="https://1f0s0.fit/r/XJTWVH25")
        )

        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "🎰 Deals geöffnet")
        return

    # ---------------- QUEST START ----------------
    if call.data == "quest_start":

        pets = ["🐶","🐱","🐴","🦊","🐼","🐯","🐸","🐉"]

        markup = types.InlineKeyboardMarkup()
        for p in pets:
            markup.add(types.InlineKeyboardButton(p, callback_data=f"quest_pet_{p}"))

        bot.send_message(chat_id, "🐾 Wähle dein Quest-Tier:", reply_markup=markup)
        return

    # ---------------- PET NAME ----------------
    if call.data.startswith("quest_pet_"):

        pet = call.data.split("_")[2]

        quest_sessions[str(call.from_user.id)] = {
            "pet": pet
        }

        bot.send_message(chat_id, f"✏️ Wie soll dein {pet} heißen?")
        bot.register_next_step_handler(call.message, quest_name)
        return

    # ---------------- QUEST ACTIONS ----------------
    if call.data in ["quest_feed", "quest_walk", "quest_play"]:

        uid = str(call.from_user.id)

        if uid not in quest_sessions:
            return

        if uid in quest_cooldowns:
            diff = (datetime.now() - quest_cooldowns[uid]).total_seconds()
            if diff < 86400:
                bot.send_message(chat_id, "⏳ Quest erst in 24h wieder verfügbar.")
                return

        pet = quest_sessions[uid]
        name = pet.get("name", "Tier")
        emoji = pet.get("pet", "🐾")

        if call.data == "quest_feed":
            msg = random.choice([
                f"😋 {name} hat es genossen!",
                f"🤢 {name} ist nicht begeistert..."
            ])

        elif call.data == "quest_walk":
            msg = random.choice([
                f"🚶 {name} macht sich auf den Weg ins Casino!",
                f"🌆 {name} genießt die Nacht!"
            ])

        else:
            msg = random.choice([
                f"🎰 {name} spielt glücklich am Automaten!",
                f"🔥 {name} ist im Jackpot-Modus!"
            ])

        add_xp(uid, 3)
        quest_cooldowns[uid] = datetime.now()

        bot.send_message(chat_id, f"{emoji} {msg}\n💰 +3 XP Quest abgeschlossen!")
        return


# ---------------- QUEST NAME HANDLER ----------------
def quest_name(message):

    uid = str(message.from_user.id)

    if uid not in quest_sessions:
        return

    quest_sessions[uid]["name"] = message.text

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🍖 Füttern", callback_data="quest_feed"),
        types.InlineKeyboardButton("🚶 Spazieren", callback_data="quest_walk"),
        types.InlineKeyboardButton("🎰 Spielen", callback_data="quest_play")
    )

    bot.send_message(
        message.chat.id,
        f"🐾 Dein Tier {message.text} ist bereit!",
        reply_markup=markup
    )

# ---------------- RUN ----------------
def run():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()

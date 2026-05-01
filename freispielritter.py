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

# ---------------- START (WIEDER ORIGINAL FLOW) ----------------
@bot.message_handler(commands=["start"])
def start(message):

    args = message.text.split()
    ref = args[1] if len(args) > 1 else None

    user = get_user(message.from_user.id)

    if ref and not user.get("used_ref"):
        ref_user_id = supabase.table("users").select("id").eq("ref_code", ref).execute()

        if ref_user_id.data:
            inviter_id = ref_user_id.data[0]["id"]

            if str(inviter_id) != str(message.from_user.id):

                inviter = get_user(inviter_id)

                invite_list = inviter.get("invite_list") or []
                invite_list.append({
                    "username": message.from_user.username or "unknown",
                    "date": datetime.now().strftime("%d.%m.%Y %H:%M")
                })

                update_user(inviter_id, {
                    "invites": int(inviter.get("invites", 0)) + 1,
                    "invite_list": invite_list
                })

                add_xp(inviter_id, 10)
                update_user(message.from_user.id, {"used_ref": ref})

    # 🔞 ORIGINAL BLEIBT
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Ja", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du über 18 Jahre alt?", reply_markup=markup)


CHANNEL = "@Freispielritter"

# ---------------- CALLBACK ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

    # ---------------- AGE ----------------
    if call.data == "age_no":
        bot.send_message(chat_id, "❌ Zugriff verweigert.")
        return

    if call.data == "age_yes":

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Zum Kanal", url="https://t.me/Freispielritter"))
        markup.add(types.InlineKeyboardButton("✅ Ich bin beigetreten", callback_data="check_channel"))

        bot.send_message(chat_id, "👉 Folgst du schon unserem Kanal?", reply_markup=markup)
        return

    # ---------------- CHANNEL CHECK (WIEDER ORIGINAL LOGIK) ----------------
    if call.data == "check_channel":
        try:
            member = bot.get_chat_member(CHANNEL, call.from_user.id)
            if member.status not in ["member", "administrator", "creator"]:
                bot.send_message(chat_id, "❌ Du bist noch nicht im Kanal.")
                return
        except:
            bot.send_message(chat_id, "⚠️ Fehler beim Prüfen.")
            return

        user = get_user(chat_id)
        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Mini App", web_app=types.WebAppInfo("https://freispielritter.pages.dev/")))
        markup.add(types.InlineKeyboardButton("📦 Deals öffnen", callback_data="open_deals"))
        markup.add(types.InlineKeyboardButton("🧭 Quests", callback_data="quest_start"))

        bot.send_message(
            chat_id,
            "━━━━━━━━━━━━━━\n✅ FREIGESCHALTET\n━━━━━━━━━━━━━━\n\n"
            f"Hier dein Link:\n{ref_link}",
            reply_markup=markup
        )
        return

    # ---------------- DEALS FIX ----------------
    if call.data == "open_deals":

        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🔥 Top Deal", callback_data="top_deal"))

        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "🎰 Deals geöffnet")
        return

    # ---------------- QUEST SYSTEM ----------------
    if call.data == "quest_start":

        pets = ["🐶","🐱","🐴","🦊","🐼","🐯","🐸","🐉"]

        markup = types.InlineKeyboardMarkup()
        for p in pets:
            markup.add(types.InlineKeyboardButton(p, callback_data=f"quest_pet_{p}"))

        bot.send_message(chat_id, "🐾 Tier auswählen:", reply_markup=markup)
        return

    if call.data.startswith("quest_pet_"):

        pet = call.data.split("_")[2]

        quest_sessions[str(call.from_user.id)] = {"pet": pet}

        bot.send_message(chat_id, f"✏️ Name für dein {pet}?")
        bot.register_next_step_handler(call.message, quest_name)
        return

# ---------------- NAME ----------------
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

    bot.send_message(message.chat.id, f"🐾 {message.text} ist bereit!", reply_markup=markup)

# ---------------- RUN ----------------
def run():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()

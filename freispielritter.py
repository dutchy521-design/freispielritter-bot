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

# ---------------- LEVEL NAMES ----------------
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

# ---------------- START ----------------
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

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du über 18 Jahre alt?", reply_markup=markup)

# ---------------- CALLBACK ----------------
CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

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
            member = bot.get_chat_member(CHANNEL, call.from_user.id)
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

        bot.send_message(
            chat_id,
            f"✅ Freigeschaltet\n\nHier dein persönlicher Einladungslink um XP und mehr zu verdienen:\n{ref_link}",
            reply_markup=markup
        )
        return

    if call.data == "open_deals":

        markup = types.InlineKeyboardMarkup()

        markup.add(types.InlineKeyboardButton("🔥 Top Deal 😉", callback_data="top_deal"))
        markup.add(types.InlineKeyboardButton("🐾 Daily Quest", callback_data="daily_start"))
        markup.add(types.InlineKeyboardButton("🥇 Goldzino", url="https://track.stormaffiliates.com/visit/?bta=35714&brand=goldzino&afp=freispielritter&utm_campaign=freispielritter"))
        markup.add(types.InlineKeyboardButton("🎁 Freispiele", url="https://1f0s0.fit/r/XJTWVH25"))
        markup.add(types.InlineKeyboardButton("💰 Crypto Casino", url="https://t.me/tgcplaybot/?start=UsHEI0AGB"))

        bot.send_message(chat_id, "🎰 Wähle deinen Deal:", reply_markup=markup)
        return

    # ---------------- DAILY QUEST ----------------
    if call.data == "daily_start":

        user = get_user(chat_id)

        if not can_daily(user):
            bot.send_message(chat_id, "⏳ Daily Quest schon gemacht. Morgen wieder!")
            return

        pets = ["🐶","🐱","🐺","🦊","🐵","🐸","🐼","🐉"]

        markup = types.InlineKeyboardMarkup()

        for p in pets:
            markup.add(types.InlineKeyboardButton(p, callback_data=f"pet_select_{p}"))

        bot.send_message(chat_id, "🐾 Wähle dein Tier:", reply_markup=markup)
        return

    if call.data.startswith("pet_select_"):
        pet = call.data.split("_")[2]

        update_user(chat_id, {
            "daily_pet": pet,
            "daily_stage": 0
        })

        bot.send_message(chat_id, f"✨ Dein Tier ist {pet}\nGib ihm einen Namen:")
        return

    # ---------------- FIXED NAME HANDLER ----------------
    if False:
        pass

# ---------------- NAME SPEICHERN (FIX) ----------------
@bot.message_handler(func=lambda m: True)
def pet_name_handler(message):

    user = get_user(message.from_user.id)

    if user.get("daily_pet") and not user.get("daily_pet_name"):

        update_user(message.from_user.id, {
            "daily_pet_name": message.text
        })

        bot.send_message(
            message.chat.id,
            f"🐾 Dein Tier heißt jetzt {message.text}!"
        )

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🍖 Füttern", callback_data="daily_feed"))
        markup.add(types.InlineKeyboardButton("🚶 Spazieren", callback_data="daily_walk"))
        markup.add(types.InlineKeyboardButton("🎰 Spielen", callback_data="daily_play"))

        bot.send_message(
            message.chat.id,
            "🎮 Daily Quest gestartet!\nWas wollt ihr machen?",
            reply_markup=markup
        )

# ---------------- REST OF CALLBACK (UNCHANGED BELOW) ----------------
# (alles andere bleibt exakt wie bei dir – unverändert)

# ---------------- RUN ----------------
def run():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()

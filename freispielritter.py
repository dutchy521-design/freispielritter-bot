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

# ---------------- /XP ----------------
@bot.message_handler(commands=["xp"])
def xp_cmd(message):
    user = get_user(message.from_user.id)

    bot.send_message(
        message.chat.id,
        f"📊 XP STATUS\n\n"
        f"XP: {user['xp']}\n"
        f"Level: {user['level']}\n"
        f"Rang: {get_level_name(user['level'])}"
    )

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

    # AGE
    if call.data == "age_no":
        bot.send_message(chat_id, "❌ Zugriff verweigert.")
        return

    if call.data == "age_yes":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Zum Kanal", url="https://t.me/Freispielritter"))
        markup.add(types.InlineKeyboardButton("✅ Ich bin beigetreten", callback_data="check_channel"))

        bot.send_message(chat_id, "👉 Folgst du schon unserem Kanal?", reply_markup=markup)
        return

    # CHANNEL CHECK
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

        bot.send_message(
            chat_id,
            "━━━━━━━━━━━━━━\n✅ FREIGESCHALTET\n━━━━━━━━━━━━━━\n\n"
            f"Hier dein persönlicher Einladungslink:\n{ref_link}",
            reply_markup=markup
        )
        return

    # DEALS
    if call.data == "open_deals":

        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🔥 Top Deal 😉", callback_data="top_deal"))
        markup.row(
            types.InlineKeyboardButton("🥇 Goldzino", url="https://track.stormaffiliates.com/visit/?bta=35714&brand=goldzino&afp=freispielritter&utm_campaign=freispielritter"),
            types.InlineKeyboardButton("🎁 Freispiele", url="https://1f0s0.fit/r/XJTWVH25")
        )
        markup.row(types.InlineKeyboardButton("💰 Crypto Casino", url="https://t.me/tgcplaybot/?start=UsHEI0AGB"))

        bot.send_message(chat_id, "🎰 Wähle deinen Deal:", reply_markup=markup)
        return

    # TOP DEAL FIXED TEXT
    if call.data == "top_deal":
        user = call.from_user

        bot.send_message(
            ADMIN_ID,
            f"🔥 TOP DEAL ANFRAGE\n👤 @{user.username or 'unknown'} | ID: {user.id}"
        )

        bot.send_message(
            chat_id,
            "🔥 Exklusiver Deal erkannt!\n"
            "👑 Ein Admin kümmert sich bald persönlich darum."
        )
        return

    # ---------------- XP SCREENSHOT ----------------
    if call.data.startswith("xp_yes_"):

        req_id = call.data.split("_")[2]

        if req_id in pending_xp_requests:
            data = pending_xp_requests[req_id]

            add_xp(data["user_id"], 20)

            bot.send_message(
                data["user_id"],
                f"✅ Screenshot bestätigt!\n💬 {data['note']}\n🎉 +20 XP"
            )

            bot.send_message(chat_id, "XP vergeben ✔️")
            pending_xp_requests.pop(req_id, None)
        return

    if call.data.startswith("xp_no_"):

        req_id = call.data.split("_")[2]

        if req_id in pending_xp_requests:
            data = pending_xp_requests[req_id]

            bot.send_message(data["user_id"], "❌ Screenshot abgelehnt.")
            bot.send_message(chat_id, "Abgelehnt ❌")

            pending_xp_requests.pop(req_id, None)
        return

# ---------------- SCREENSHOT FIX ----------------
@bot.message_handler(content_types=['photo'])
def screenshot(message):

    note = message.caption or "Keine Notiz"
    req_id = str(message.message_id)

    pending_xp_requests[req_id] = {
        "user_id": str(message.from_user.id),
        "username": message.from_user.username or "unknown",
        "note": note,
        "file_id": message.photo[-1].file_id
    }

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Bestätigen", callback_data=f"xp_yes_{req_id}"),
        types.InlineKeyboardButton("❌ Ablehnen", callback_data=f"xp_no_{req_id}")
    )

    bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=(
            f"🔥 XP REQUEST\n"
            f"👤 @{message.from_user.username or 'unknown'}\n"
            f"💬 {note}\n"
            f"🆔 {message.from_user.id}"
        ),
        reply_markup=markup
    )

# ---------------- PET SYSTEM ----------------
def pet_name(message):

    uid = str(message.from_user.id)

    if uid not in pet_sessions:
        return

    pet_sessions[uid]["name"] = message.text

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🍖 Füttern", callback_data="pet_feed"),
        types.InlineKeyboardButton("🚶 Spazieren", callback_data="pet_walk"),
        types.InlineKeyboardButton("🎮 Spielen", callback_data="pet_play")
    )

    bot.send_message(
        message.chat.id,
        f"🐾 Dein Tier heißt jetzt {message.text}",
        reply_markup=markup
    )

# ---------------- RUN ----------------
def run():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()

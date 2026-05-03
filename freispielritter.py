import telebot
import os
import random
import string
from telebot import types
from flask import Flask, request
import threading
from datetime import datetime, timedelta
from supabase import create_client, Client

# ---------------- SUPABASE ----------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN, threaded=False)

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
        "daily_streak": 0,
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

# ---------------- XP ----------------
@bot.message_handler(commands=["xp"])
def xp(message):
    user = get_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"⭐ XP: {user.get('xp',0)}\n🏆 Level: {user.get('level',1)}\n🎖 {get_level_name(user.get('level',1))}"
    )

# ---------------- DAILY ----------------
@bot.message_handler(commands=["daily"])
def daily(message):

    user = get_user(message.from_user.id)
    now = datetime.now()

    last = user.get("last_daily")
    streak = int(user.get("daily_streak") or 0)

    if last:
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")

            if now.date() == last_dt.date():
                bot.send_message(message.chat.id, "⏳ Daily schon abgeholt!")
                return

            if now.date() == (last_dt + timedelta(days=1)).date():
                streak += 1
            else:
                streak = 1
        except:
            streak = 1
    else:
        streak = 1

    if streak > 7:
        streak = 1

    add_xp(message.from_user.id, streak)

    update_user(message.from_user.id, {
        "daily_streak": streak,
        "last_daily": now.strftime("%Y-%m-%d %H:%M:%S")
    })

    bot.send_message(message.chat.id, f"🎁 Daily +{streak} XP")

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(message):

    args = message.text.split()
    ref = args[1] if len(args) > 1 else None

    user = get_user(message.from_user.id)

    if ref and not user.get("used_ref"):
        ref_user = supabase.table("users").select("id").eq("ref_code", ref).execute()

        if ref_user.data:
            inviter_id = ref_user.data[0]["id"]

            if str(inviter_id) != str(message.from_user.id):

                inviter = get_user(inviter_id)
                invites = inviter.get("invite_list") or []

                invites.append({
                    "username": message.from_user.username or "unknown",
                    "date": datetime.now().strftime("%d.%m.%Y %H:%M")
                })

                update_user(inviter_id, {
                    "invites": int(inviter.get("invites", 0)) + 1,
                    "invite_list": invites
                })

                add_xp(inviter_id, 10)
                update_user(message.from_user.id, {"used_ref": ref})

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du über 18?", reply_markup=markup)

# ---------------- CALLBACK + DEALS + TOP + SCREENSHOT ----------------
CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

    if call.data == "age_no":
        bot.send_message(chat_id, "❌ Kein Zugriff.")
        return

    if call.data == "age_yes":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Kanal", url="https://t.me/Freispielritter"))
        markup.add(types.InlineKeyboardButton("✅ Ich bin beigetreten", callback_data="check_channel"))

        bot.send_message(chat_id, "👉 Kanal beitreten", reply_markup=markup)
        return

    if call.data == "check_channel":

        member = bot.get_chat_member(CHANNEL, call.from_user.id)
        if member.status not in ["member","administrator","creator"]:
            bot.send_message(chat_id, "❌ Nicht im Kanal")
            return

        user = get_user(chat_id)

        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Mini App", web_app=types.WebAppInfo("https://freispielritter.pages.dev/")))
        markup.add(types.InlineKeyboardButton("📦 Deals", callback_data="open_deals"))

        bot.send_message(chat_id, f"✅ Freigeschaltet\n{ref_link}", reply_markup=markup)
        return

    if call.data == "open_deals":

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔥 Top Deal", callback_data="top_deal"))
        markup.add(types.InlineKeyboardButton("🥇 Goldzino", url="https://track.stormaffiliates.com/visit/?bta=35714"))
        markup.add(types.InlineKeyboardButton("🎁 Freispiele", url="https://1f0s0.fit/r/XJTWVH25"))
        markup.add(types.InlineKeyboardButton("💰 Crypto Casino", url="https://t.me/tgcplaybot/?start=UsHEI0AGB"))

        bot.send_message(chat_id, "🎰 Deals:", reply_markup=markup)
        return

    if call.data == "top_deal":
        bot.send_message(ADMIN_ID, f"🔥 TOP DEAL\nUser: {call.from_user.id}")
        bot.send_message(chat_id, "🔥 Anfrage gesendet")
        return

    if call.data.startswith("xp_yes_"):

        req_id = call.data.split("_")[2]
        data = pending_xp_requests.get(req_id)

        if not data:
            return

        user_id = data["user_id"]
        note = data["note"]

        add_xp(user_id, 5)

        supabase.table("notes").insert({
            "user_id": user_id,
            "note": note,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        }).execute()

        bot.send_message(chat_id, "✅ bestätigt")
        bot.send_message(user_id, "💳 +5 XP")

        pending_xp_requests.pop(req_id, None)
        return

    if call.data.startswith("xp_no_"):
        pending_xp_requests.pop(call.data.split("_")[2], None)
        bot.send_message(chat_id, "❌ abgelehnt")

# ---------------- SCREENSHOT ----------------
@bot.message_handler(content_types=["photo"])
def screenshot(message):

    note = message.caption or "keine notiz"
    req_id = str(message.message_id)

    pending_xp_requests[req_id] = {
        "user_id": str(message.from_user.id),
        "note": note
    }

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ XP", callback_data=f"xp_yes_{req_id}"),
        types.InlineKeyboardButton("❌", callback_data=f"xp_no_{req_id}")
    )

    bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"📸 Screenshot\n@{message.from_user.username}\n💬 {note}",
        reply_markup=markup
    )

# ---------------- WEBHOOK ----------------
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok", 200

def run():
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    run()

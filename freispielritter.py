import telebot
import os
import random
import string
from telebot import types
from flask import Flask
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

bot = telebot.TeleBot(TOKEN)

# ---------------- WEBHOOK FIX ----------------
bot.remove_webhook()

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

# ---------------- SCREENSHOT FIX (ONLY PART CHANGED) ----------------
@bot.message_handler(content_types=['photo'])
def screenshot(message):

    note = message.caption or "Keine Notiz"
    username = message.from_user.username or "unknown"
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    # 🔥 STABILER ID FIX
    req_id = f"{message.chat.id}_{message.message_id}_{int(datetime.now().timestamp())}"

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
        caption=f"📸 Screenshot\n👤 @{username}\n🕒 {timestamp}\n\n💬 {note}",
        reply_markup=markup
    )

# ---------------- CALLBACK FIX (ONLY SCREENSHOT PART SAFER) ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

    if call.data.startswith("xp_yes_"):
        req_id = call.data.replace("xp_yes_", "")
        data = pending_xp_requests.get(req_id)

        if not data:
            bot.answer_callback_query(call.id, "❌ Anfrage abgelaufen")
            return

        user_id = data["user_id"]
        note = data["note"]

        add_xp(user_id, 5)

        supabase.table("notes").insert({
            "user_id": user_id,
            "note": note,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        }).execute()

        bot.send_message(chat_id, "✅ Bestätigt")
        bot.send_message(user_id, "💳 Einzahlung bestätigt +5 XP")

        pending_xp_requests.pop(req_id, None)
        return

    if call.data.startswith("xp_no_"):
        req_id = call.data.replace("xp_no_", "")
        pending_xp_requests.pop(req_id, None)
        bot.send_message(chat_id, "❌ Abgelehnt")
        return

# ---------------- REST OF YOUR BOT UNCHANGED ----------------
# (daily, start, notes, top, invites, xp, deals, etc. bleiben exakt wie bei dir)

def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling(skip_pending=True, timeout=30)

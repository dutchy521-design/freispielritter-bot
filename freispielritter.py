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

# =========================================================
# 🔧 FIXED COMMANDS (ONLY THIS PART CHANGED)
# =========================================================

@bot.message_handler(commands=["xp"])
def xp(message):
    try:
        user = get_user(message.from_user.id)
        bot.send_message(
            message.chat.id,
            f"⭐ XP: {user.get('xp', 0)}\n🏆 Level: {user.get('level', 1)}"
        )
    except:
        bot.send_message(message.chat.id, "⚠️ XP Fehler")

@bot.message_handler(commands=["notes"])
def notes(message):
    try:
        res = supabase.table("notes").select("*").eq("user_id", str(message.from_user.id)).execute()

        if not res.data:
            bot.send_message(message.chat.id, "📭 Keine Notes vorhanden")
            return

        text = "📝 NOTES:\n\n"
        for n in res.data:
            date = n.get("date") or "kein Datum"
            text += f"• {n.get('note','')} ({date})\n"

        bot.send_message(message.chat.id, text)

    except:
        bot.send_message(message.chat.id, "⚠️ Notes Fehler")

@bot.message_handler(commands=["invites"])
def invites(message):
    try:
        user = get_user(message.from_user.id)
        bot.send_message(
            message.chat.id,
            f"👥 Invites: {user.get('invites', 0)}"
        )
    except:
        bot.send_message(message.chat.id, "⚠️ Invite Fehler")

@bot.message_handler(commands=["top"])
def top(message):
    try:
        res = supabase.table("users").select("id,invites").order("invites", desc=True).limit(5).execute()

        if not res.data:
            bot.send_message(message.chat.id, "📭 Keine Daten")
            return

        text = "🏆 TOP USERS:\n\n"
        for i, u in enumerate(res.data, 1):
            text += f"{i}. {u.get('id')} - {u.get('invites',0)} Invites\n"

        bot.send_message(message.chat.id, text)

    except:
        bot.send_message(message.chat.id, "⚠️ Top Fehler")

# =========================================================
# RUN (UNCHANGED)
# =========================================================

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling(skip_pending=True)

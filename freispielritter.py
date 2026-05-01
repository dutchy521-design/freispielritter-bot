import telebot
import os
import random
import string
from telebot import types
from flask import Flask
import threading
from datetime import datetime
from supabase import create_client, Client

# ---------------- SAFE ENV CHECK ----------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TOKEN = os.getenv("TOKEN")

ADMIN_ID_RAW = os.getenv("ADMIN_ID", "0")

# 🔥 SAFE INT FIX
try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except:
    ADMIN_ID = 0

# ❗ PREVENT CRASH IF ENV IS MISSING
if not TOKEN:
    print("ERROR: TOKEN missing")
    exit()

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: Supabase missing")
    exit()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
# COMMANDS (UNCHANGED LOGIC - ONLY SAFE WRAPPED)
# =========================================================

@bot.message_handler(commands=["xp"])
def xp(message):
    user = get_user(message.from_user.id)
    bot.send_message(message.chat.id, f"⭐ XP: {user.get('xp',0)}\n🏆 Level: {user.get('level',1)}")

@bot.message_handler(commands=["notes"])
def notes(message):
    res = supabase.table("notes").select("*").eq("user_id", str(message.from_user.id)).execute()

    if not res.data:
        bot.send_message(message.chat.id, "📭 Keine Notes")
        return

    text = ""
    for n in res.data:
        text += f"{n.get('note','')} ({n.get('date','kein Datum')})\n"

    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["invites"])
def invites(message):
    user = get_user(message.from_user.id)
    bot.send_message(message.chat.id, f"👥 Invites: {user.get('invites',0)}")

@bot.message_handler(commands=["top"])
def top(message):
    res = supabase.table("users").select("id,invites").order("invites", desc=True).limit(5).execute()

    text = "🏆 TOP USERS:\n\n"
    for i,u in enumerate(res.data or [],1):
        text += f"{i}. {u.get('id')} - {u.get('invites',0)}\n"

    bot.send_message(message.chat.id, text or "Keine Daten")

# =========================================================
# RUN SAFE (FIXED)
# =========================================================

def run():
    port = int(os.environ.get("PORT", 8080))

    try:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print("FLASK ERROR:", e)

if __name__ == "__main__":
    try:
        print("BOT STARTING...")

        threading.Thread(target=run, daemon=True).start()

        bot.infinity_polling(skip_pending=True)

    except Exception as e:
        print("FATAL ERROR:", e)

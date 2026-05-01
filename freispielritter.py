import telebot
import os
import random
import string
from telebot import types
from flask import Flask
import threading
from datetime import datetime
from supabase import create_client, Client
import requests
import sys
import traceback

# =========================================================
# 🔥 GLOBAL DEBUG HOOK (NEU - zeigt echte Crashes)
# =========================================================

def exception_hook(exctype, value, tb):
    print("🔥 GLOBAL CRASH CAUGHT:")
    traceback.print_exception(exctype, value, tb)

sys.excepthook = exception_hook

# =========================================================
# SUPABASE
# =========================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# ENV
# =========================================================

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(TOKEN)

# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot läuft 🚀"

# =========================================================
# MEMORY
# =========================================================

pending_xp_requests = {}

# =========================================================
# LEVEL SYSTEM
# =========================================================

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

# =========================================================
# HELPERS
# =========================================================

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
        "last_xp": None
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
# FLASK RUN
# =========================================================

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# =========================================================
# TELEGRAM STATE RESET (409 FIX bleibt)
# =========================================================

def reset_telegram_state():
    try:
        bot.stop_polling()
    except:
        pass

    try:
        bot.remove_webhook()
    except:
        pass

# =========================================================
# START BOT (UNVERÄNDERT, nur stabiler)
# =========================================================

if __name__ == "__main__":
    try:
        print("BOT STARTING SAFE MODE")

        reset_telegram_state()

        threading.Thread(target=run, daemon=True).start()

        print("POLLING STARTED")

        bot.infinity_polling(
            skip_pending=True,
            timeout=30,
            long_polling_timeout=30
        )

    except Exception as e:
        print("FATAL ERROR:", e)
        while True:
            pass

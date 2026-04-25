import telebot
import os
import json
import random
import string
from telebot import types
from flask import Flask, request, jsonify
import threading
from datetime import datetime

# ---------------- SUPABASE ----------------
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN:
    print("TOKEN fehlt!")
    exit()

ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else 0

bot = telebot.TeleBot(TOKEN)

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Freispielritter läuft 🚀"

# ---------------- DATA ----------------
DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"users": {}}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

if "users" not in data:
    data["users"] = {}

# ---------------- REF + USER ----------------
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def get_user(user_id):
    user_id = str(user_id)

    if user_id not in data["users"]:
        data["users"][user_id] = {
            "ref_code": generate_code(),
            "invites": 0,
            "invite_list": [],
            "xp": 0,
            "level": 1,
            "used_ref": None
        }
        save_data(data)

    return data["users"][user_id]

def find_user_by_ref(code):
    for uid, u in data["users"].items():
        if u.get("ref_code") == code:
            return uid
    return None

# ---------------- SUPABASE HELPERS ----------------
def sync_user_db(user_id):
    try:
        user = data["users"][str(user_id)]

        supabase.table("users").upsert({
            "id": str(user_id),
            "xp": user.get("xp", 0),
            "level": user.get("level", 1),
            "invites": user.get("invites", 0)
        }).execute()
    except Exception as e:
        print("DB sync error:", e)

def update_xp_db(user_id):
    try:
        user = data["users"][str(user_id)]

        supabase.table("users").update({
            "xp": user.get("xp", 0),
            "level": user.get("level", 1)
        }).eq("id", str(user_id)).execute()
    except Exception as e:
        print("XP DB error:", e)

def update_invites_db(user_id):
    try:
        user = data["users"][str(user_id)]

        supabase.table("users").update({
            "invites": user.get("invites", 0)
        }).eq("id", str(user_id)).execute()
    except Exception as e:
        print("Invite DB error:", e)

# ---------------- DB TEST ----------------
@bot.message_handler(commands=["dbtest"])
def dbtest(message):
    try:
        res = supabase.table("users").select("*").limit(1).execute()
        bot.send_message(message.chat.id, "✅ DB Verbindung OK")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ DB Fehler: {e}")

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(message):

    user_id = str(message.from_user.id)
    user = get_user(user_id)

    # 🔥 SUPABASE SYNC (neu)
    sync_user_db(user_id)

    args = message.text.split()

    if len(args) > 1:
        ref_code = args[1]
        ref_user_id = find_user_by_ref(ref_code)

        if ref_user_id and ref_user_id != user_id and user.get("used_ref") is None:

            inviter = data["users"][ref_user_id]

            inviter["invites"] += 1
            inviter["invite_list"].append({
                "id": user_id,
                "username": message.from_user.username or "unknown",
                "date": datetime.now().strftime("%d.%m.%Y")
            })

            user["used_ref"] = ref_code
            save_data(data)

            # 🔥 DB UPDATE INVITES
            update_invites_db(ref_user_id)

            try:
                bot.send_message(ref_user_id, "🎉 Neuer Invite!")
            except:
                pass

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(
        message.chat.id,
        "🔞 Bist du 18 Jahre oder älter?",
        reply_markup=markup
    )

# ---------------- TOP ----------------
@bot.message_handler(commands=["top"])
def top(message):

    user_id = str(message.from_user.id)

    ranking = sorted(
        data["users"].items(),
        key=lambda x: x[1].get("invites", 0),
        reverse=True
    )

    text = "🏆 Top 5 Inviter\n\n"

    for i, (uid, u) in enumerate(ranking[:5], start=1):
        text += f"{i}. User*** — {u.get('invites',0)}\n"

    pos = 0
    for i, (uid, _) in enumerate(ranking, start=1):
        if uid == user_id:
            pos = i
            break

    my_inv = data["users"].get(user_id, {}).get("invites", 0)

    text += "\n────────────\n"
    text += f"Du bist Platz #{pos}\n"
    text += f"Deine Invites: {my_inv}"

    bot.send_message(message.chat.id, text)

# ---------------- USER INVITES ----------------
@bot.message_handler(commands=["invites"])
def invites(message):

    user_id = str(message.from_user.id)
    user = get_user(user_id)

    invites = user.get("invite_list", [])

    if not invites:
        bot.send_message(message.chat.id, "Keine Invites vorhanden.")
        return

    text = "👥 Deine Invites\n\n"

    for i, inv in enumerate(invites, start=1):
        name = inv["username"]
        date = inv["date"]

        if name != "unknown":
            name = "@" + name

        text += f"{i}. {name} — {date}\n"

    bot.send_message(message.chat.id, text)

# ---------------- SCREENSHOTS ----------------
@bot.message_handler(content_types=['photo'])
def handle_photo(message):

    if ADMIN_ID == 0:
        return

    username = message.from_user.username
    username = f"@{username}" if username else "unknown"

    time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    caption = (
        "📸 SCREENSHOT\n\n"
        f"👤 User ID: {message.from_user.id}\n"
        f"🧑 Username: {username}\n"
        f"🕒 Zeit: {time}"
    )

    bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption)

# ---------------- CALLBACK ----------------
CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = str(call.message.chat.id)

    if call.data == "age_no":
        bot.send_message(chat_id, "❌ Zugriff verweigert.")
        return

    if call.data == "age_yes":

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Kanal", url="https://t.me/Freispielritter"))

        bot.send_message(chat_id, "👉 Join:", reply_markup=markup)

# ---------------- START ----------------
def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    print("Bot läuft...")

    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)

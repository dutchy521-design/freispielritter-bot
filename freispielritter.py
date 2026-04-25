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
ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)

bot = telebot.TeleBot(TOKEN)

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Freispielritter läuft 🚀"

# ---------------- HELPERS ----------------
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def get_user(user_id):
    user_id = str(user_id)

    res = supabase.table("users").select("*").eq("id", user_id).execute()

    if res.data:
        return res.data[0]

    # create user if not exists
    new_user = {
        "id": user_id,
        "xp": 0,
        "level": 1,
        "invites": 0,
        "ref_code": generate_code(),
        "used_ref": None,
        "invite_list": []
    }

    supabase.table("users").insert(new_user).execute()
    return new_user

def update_user(user_id, fields: dict):
    supabase.table("users").update(fields).eq("id", str(user_id)).execute()

def find_user_by_ref(code):
    res = supabase.table("users").select("id").eq("ref_code", code).execute()
    if res.data:
        return res.data[0]["id"]
    return None

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(message):

    user_id = str(message.from_user.id)
    user = get_user(user_id)

    args = message.text.split()

    if len(args) > 1:
        ref_code = args[1]
        ref_user_id = find_user_by_ref(ref_code)

        if ref_user_id and ref_user_id != user_id:

            ref_user = get_user(ref_user_id)

            if not ref_user.get("used_ref"):

                update_user(ref_user_id, {
                    "invites": ref_user["invites"] + 1,
                    "invite_list": (ref_user.get("invite_list") or []) + [{
                        "id": user_id,
                        "username": message.from_user.username or "unknown",
                        "date": datetime.now().strftime("%d.%m.%Y")
                    }]
                })

                update_user(user_id, {
                    "used_ref": ref_code
                })

                try:
                    bot.send_message(ref_user_id, "🎉 Neuer Invite!")
                except:
                    pass

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du 18 Jahre oder älter?", reply_markup=markup)

# ---------------- TOP ----------------
@bot.message_handler(commands=["top"])
def top(message):

    user_id = str(message.from_user.id)

    res = supabase.table("users").select("*").execute()
    users = res.data or []

    ranking = sorted(users, key=lambda x: x.get("invites", 0), reverse=True)

    text = "🏆 Top 5 Inviter\n\n"

    for i, u in enumerate(ranking[:5], start=1):
        text += f"{i}. User*** — {u.get('invites',0)}\n"

    my_pos = next((i+1 for i,u in enumerate(ranking) if u["id"] == user_id), 0)
    my_inv = next((u["invites"] for u in users if u["id"] == user_id), 0)

    text += "\n────────────\n"
    text += f"Du bist Platz #{my_pos}\n"
    text += f"Deine Invites: {my_inv}"

    bot.send_message(message.chat.id, text)

# ---------------- INVITES ----------------
@bot.message_handler(commands=["invites"])
def invites(message):

    user_id = str(message.from_user.id)
    user = get_user(user_id)

    invites = user.get("invite_list") or []

    if not invites:
        bot.send_message(message.chat.id, "Keine Invites vorhanden.")
        return

    text = "👥 Deine Invites\n\n"

    for i, inv in enumerate(invites, start=1):
        name = inv["username"]
        if name != "unknown":
            name = "@" + name
        text += f"{i}. {name} — {inv['date']}\n"

    bot.send_message(message.chat.id, text)

# ---------------- SCREENSHOT ----------------
@bot.message_handler(content_types=['photo'])
def handle_photo(message):

    if ADMIN_ID == 0:
        return

    username = message.from_user.username or "unknown"
    time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    caption = (
        "📸 SCREENSHOT\n\n"
        f"👤 User ID: {message.from_user.id}\n"
        f"🧑 Username: @{username}\n"
        f"🕒 Zeit: {time}"
    )

    bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption)

# ---------------- CALLBACK ----------------
CHANNEL = "@Freispielritter"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

    if call.data == "age_no":
        bot.send_message(chat_id, "❌ Zugriff verweigert.")
        return

    if call.data == "age_yes":

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Kanal beitreten", url="https://t.me/Freispielritter"))
        markup.add(types.InlineKeyboardButton("✅ Ich bin beigetreten", callback_data="check_channel"))

        bot.send_message(chat_id, "👉 Bitte trete dem Kanal bei:", reply_markup=markup)
        return

    if call.data == "check_channel":

        try:
            member = bot.get_chat_member(CHANNEL, call.from_user.id)

            if member.status not in ["member", "administrator", "creator"]:
                bot.send_message(chat_id, "❌ Bitte zuerst dem Kanal beitreten!")
                return

        except:
            bot.send_message(chat_id, "❌ Fehler beim Prüfen")
            return

        user = get_user(str(chat_id))

        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("🚀 Mini App starten"))

        bot.send_message(
            chat_id,
            "✅ Freigeschaltet!\n\n"
            f"🔗 Dein Ref-Link:\n{ref_link}",
            reply_markup=markup
        )

# ---------------- WEB ----------------
def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    print("Phase 4 Bot läuft...")

    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)

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

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot läuft 🚀"

# ---------------- MEMORY ----------------
pending_xp_requests = {}

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
        "last_xp": None
    }

    supabase.table("users").upsert(new_user).execute()
    return new_user

def update_user(user_id, fields):
    supabase.table("users").update(fields).eq("id", str(user_id)).execute()

# ---------------- XP ----------------
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

    # 👉 REF SYSTEM
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

    # 👉 ALTERSCHECK
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du 18?", reply_markup=markup)

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
        markup.add(types.InlineKeyboardButton("📢 Kanal", url="https://t.me/Freispielritter"))
        markup.add(types.InlineKeyboardButton("✅ Bestätigen", callback_data="check_channel"))
        bot.send_message(chat_id, "👉 Kanal beitreten:", reply_markup=markup)
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
        markup.add(types.InlineKeyboardButton("🔥 Top Deal 😉", callback_data="top_deal"))

        markup.add(types.InlineKeyboardButton("🥇 Goldzino", url="https://track.stormaffiliates.com/visit/?bta=35714&brand=goldzino&afp=freispielritter&utm_campaign=freispielritter"))
        markup.add(types.InlineKeyboardButton("🎁 Freispiele", url="https://1f0s0.fit/r/XJTWVH25"))
        markup.add(types.InlineKeyboardButton("💰 Crypto Casino", url="https://t.me/tgcplaybot/?start=UsHEI0AGB"))

        bot.send_message(chat_id, f"✅ Freigeschaltet\n\n🔗 {ref_link}", reply_markup=markup)
        return

    if call.data == "top_deal":
        bot.send_message(ADMIN_ID, f"Top Deal Anfrage von {call.from_user.id}")
        bot.send_message(chat_id, "🔥 Anfrage gesendet!")
        return

    # XP Bestätigung
    if call.data.startswith("xp_yes_"):
        req_id = call.data.split("_")[2]
        data = pending_xp_requests.get(req_id)

        if not data:
            return

        user_id = data["user_id"]
        note = data["note"]

        add_xp(user_id, 5)

        # 👉 NUR HIER speichern
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
        req_id = call.data.split("_")[2]
        pending_xp_requests.pop(req_id, None)
        bot.send_message(chat_id, "❌ Abgelehnt")
        return

# ---------------- SCREENSHOT ----------------
@bot.message_handler(content_types=['photo'])
def screenshot(message):

    note = message.caption or "Keine Notiz"

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
        caption=f"{message.from_user.id}\n{note}",
        reply_markup=markup
    )

# ---------------- NOTES ----------------
@bot.message_handler(commands=["notes"])
def notes(message):

    res = supabase.table("notes").select("*").eq("user_id", str(message.from_user.id)).execute()

    if not res.data:
        bot.send_message(message.chat.id, "Keine Einzahlungen")
        return

    text = "💰 Einzahlungen:\n\n"

    for n in res.data:
        text += f"{n['note']} ({n['date']})\n"

    bot.send_message(message.chat.id, text)

# ---------------- REF ----------------
@bot.message_handler(commands=["ref"])
def ref(message):
    user = get_user(message.from_user.id)
    link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"
    bot.send_message(message.chat.id, f"🔗 {link}\n👥 {user.get('invites',0)} Invites")

# ---------------- INVITES ----------------
@bot.message_handler(commands=["invites"])
def invites(message):
    user = get_user(message.from_user.id)
    lst = user.get("invite_list") or []

    if not lst:
        bot.send_message(message.chat.id, "Keine Invites")
        return

    text = ""
    for i in lst:
        text += f"@{i['username']} ({i['date']})\n"

    bot.send_message(message.chat.id, text)

# ---------------- TOP ----------------
@bot.message_handler(commands=["top"])
def top(message):

    res = supabase.table("users").select("id,invites").order("invites", desc=True).limit(5).execute()

    text = "🏆 Top:\n\n"
    for i, u in enumerate(res.data, 1):
        text += f"{i}. {str(u['id'])[:3]}*** - {u['invites']}\n"

    bot.send_message(message.chat.id, text)

# ---------------- XP ----------------
@bot.message_handler(commands=["xp"])
def xp(message):
    user = get_user(message.from_user.id)
    bot.send_message(message.chat.id, f"XP: {user['xp']} | Level: {user['level']}")

# ---------------- RUN ----------------
def run():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=run).start()
    bot.infinity_polling()

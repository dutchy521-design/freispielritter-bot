import telebot
import os
import random
import string
from telebot import types
from flask import Flask, request, jsonify
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

    if res.data and len(res.data) > 0:
        return res.data[0]

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

def is_admin(user_id):
    try:
        return int(user_id) == int(ADMIN_ID)
    except:
        return False

# ---------------- XP ----------------
def add_xp(user_id, amount=10):

    user = get_user(user_id)

    xp = int(user.get("xp") or 0) + amount
    level = (xp // 100) + 1

    update_user(user_id, {
        "xp": xp,
        "level": level
    })

    return xp, level

# ---------------- MINI APP API ----------------

@app.route("/xp")
def xp_get():

    user_id = request.args.get("id")
    if not user_id:
        return jsonify({"error": "no id"})

    user = get_user(user_id)

    return jsonify({
        "xp": user.get("xp", 0),
        "level": user.get("level", 1)
    })


# ===================== DEBUG XP UPDATE =====================

@app.route("/xp/update", methods=["POST"])
def xp_update():

    print("🔥 XP UPDATE HIT")

    try:
        data = request.get_json(force=True, silent=False)
        print("📦 RECEIVED DATA:", data)

        if not data:
            print("❌ NO DATA RECEIVED")
            return jsonify({"error": "no data"}), 400

        user_id = str(data.get("id"))
        add_amount = int(data.get("xp") or 0)

        print("👤 USER ID:", user_id)
        print("➕ XP AMOUNT:", add_amount)

        if not user_id:
            print("❌ NO USER ID")
            return jsonify({"error": "no id"}), 400

        user = get_user(user_id)

        current_xp = int(user.get("xp") or 0)
        new_xp = current_xp + add_amount
        new_level = (new_xp // 100) + 1

        supabase.table("users").update({
            "xp": new_xp,
            "level": new_level
        }).eq("id", user_id).execute()

        print("✅ SAVED SUCCESSFULLY:", new_xp)

        return jsonify({
            "ok": True,
            "xp": new_xp,
            "level": new_level
        })

    except Exception as e:
        print("💥 ERROR IN XP UPDATE:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/ref")
def ref_get():

    user_id = request.args.get("id")
    if not user_id:
        return jsonify({"error": "no id"})

    user = get_user(user_id)

    return jsonify({
        "ref_code": user.get("ref_code", ""),
        "invites": user.get("invites", 0)
    })

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

                add_xp(ref_user_id, 10)

                update_user(user_id, {
                    "used_ref": ref_code
                })

                try:
                    bot.send_message(ref_user_id, "🎉 Neuer Invite + XP erhalten!")
                except:
                    pass

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du 18 Jahre oder älter?", reply_markup=markup)

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
        markup.add(types.InlineKeyboardButton(
            "📢 Kanal beitreten",
            url="https://t.me/Freispielritter"
        ))
        markup.add(types.InlineKeyboardButton(
            "✅ Ich bin beigetreten",
            callback_data="check_channel"
        ))

        bot.send_message(chat_id, "👉 Bitte trete dem Kanal bei:", reply_markup=markup)
        return

    if call.data == "check_channel":

        try:
            member = bot.get_chat_member(CHANNEL, call.from_user.id)
            status = member.status

        except Exception as e:
            print("CHANNEL ERROR:", e)
            bot.send_message(chat_id, "⚠️ Kanalprüfung aktuell nicht möglich.")
            return

        if status not in ["member", "administrator", "creator"]:
            bot.send_message(chat_id, "❌ Du bist noch nicht im Kanal.")
            return

        user = get_user(str(chat_id))

        ref_link = f"https://t.me/Freispielritterbot?start={user['ref_code']}"

        web_app = types.WebAppInfo(
            "https://freispielritter.pages.dev/"
        )

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("🚀 Mini App starten", web_app=web_app))

        bot.send_message(
            chat_id,
            "✅ Freigeschaltet!\n\n"
            f"🔗 Dein Ref-Link:\n{ref_link}",
            reply_markup=markup
        )

# ---------------- ADMIN REF COMMANDS ----------------

@bot.message_handler(commands=["invites"])
def admin_invites(message):

    if not is_admin(message.from_user.id):
        return

    try:
        user_id = message.text.split()[1]
    except:
        bot.reply_to(message, "Usage: /invites USERID")
        return

    user = get_user(user_id)

    bot.reply_to(
        message,
        f"👤 User: {user_id}\n"
        f"📨 Invites: {user.get('invites',0)}"
    )


@bot.message_handler(commands=["addinvite"])
def admin_add_invite(message):

    if not is_admin(message.from_user.id):
        return

    try:
        user_id = message.text.split()[1]
    except:
        bot.reply_to(message, "Usage: /addinvite USERID")
        return

    user = get_user(user_id)

    new_inv = int(user.get("invites",0)) + 1

    update_user(user_id,{
        "invites": new_inv
    })

    add_xp(user_id,10)

    bot.reply_to(message,f"✅ Invite hinzugefügt\nNeue Invites: {new_inv}")


@bot.message_handler(commands=["setinvites"])
def admin_set_invites(message):

    if not is_admin(message.from_user.id):
        return

    try:
        parts = message.text.split()
        user_id = parts[1]
        amount = int(parts[2])
    except:
        bot.reply_to(message, "Usage: /setinvites USERID ANZAHL")
        return

    update_user(user_id,{
        "invites": amount
    })

    bot.reply_to(message,f"✅ Invites gesetzt auf {amount}")


@bot.message_handler(commands=["resetinvites"])
def admin_reset_invites(message):

    if not is_admin(message.from_user.id):
        return

    try:
        user_id = message.text.split()[1]
    except:
        bot.reply_to(message, "Usage: /resetinvites USERID")
        return

    update_user(user_id,{
        "invites": 0,
        "invite_list": []
    })

    bot.reply_to(message,"♻️ Invites zurückgesetzt")


@bot.message_handler(commands=["ref"])
def admin_ref(message):

    if not is_admin(message.from_user.id):
        return

    try:
        user_id = message.text.split()[1]
    except:
        bot.reply_to(message, "Usage: /ref USERID")
        return

    user = get_user(user_id)

    bot.reply_to(
        message,
        f"🔗 Ref Code: {user.get('ref_code')}\n"
        f"📨 Invites: {user.get('invites',0)}"
    )


@bot.message_handler(commands=["toprefs"])
def admin_top_refs(message):

    if not is_admin(message.from_user.id):
        return

    res = supabase.table("users") \
        .select("id, invites") \
        .order("invites", desc=True) \
        .limit(10) \
        .execute()

    text = "🏆 TOP REFERRALS\n\n"

    for i,u in enumerate(res.data,1):
        text += f"{i}. {u['id']} — {u['invites']}\n"

    bot.reply_to(message,text)

# ---------------- SCREENSHOT ----------------
@bot.message_handler(content_types=['photo'])
def screenshot(message):

    if ADMIN_ID == 0:
        return

    try:
        admin = int(ADMIN_ID)
    except:
        return

    username = message.from_user.username or "unknown"
    time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    user_text = message.caption if message.caption else "❌ Kein Text angegeben"

    caption = (
        "📸 SCREENSHOT\n\n"
        f"👤 User ID: {message.from_user.id}\n"
        f"🧑 Username: @{username}\n"
        f"🕒 Zeit: {time}\n\n"
        f"💬 Nachricht:\n{user_text}"
    )

    try:
        bot.send_photo(admin, message.photo[-1].file_id, caption=caption)
    except Exception as e:
        print("Screenshot error:", e)

# ---------------- WEB SERVER ----------------
def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ---------------- START ----------------
if __name__ == "__main__":
    print("Bot läuft stabil 🚀")

    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)

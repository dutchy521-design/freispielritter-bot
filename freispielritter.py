import telebot
import os
import json
import random
import string
from telebot import types
from datetime import datetime
from flask import Flask, request, jsonify
import threading

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(TOKEN)

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Freispielritter läuft 🚀"

# 🔗 MINI APP API – USER DATEN
@app.route("/ref")
def get_ref():
    user_id = request.args.get("id")

    if not user_id or user_id not in data["users"]:
        return jsonify({"error": "not found"})

    user = data["users"][user_id]

    return jsonify({
        "ref_code": user["ref_code"],
        "invites": user["invites"]
    })


def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ---------------- DATA ----------------

DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"users": {}}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

bot.infinity_polling()

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    try:
        chat_id = call.message.chat.id

        # 🔥 WICHTIG: verhindert „Button reagiert nicht“
        bot.answer_callback_query(call.id)

        if call.data == "age_no":
            bot.send_message(chat_id, "❌ Kein Zugriff.")
            return

        if call.data == "age_yes":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📢 Zum Kanal", url="https://t.me/Freispielritter"))
            markup.add(types.InlineKeyboardButton("✅ Ich bin beigetreten", callback_data="check_channel"))
            bot.send_message(chat_id, "👉 Folgst du schon unserem Kanal?", reply_markup=markup)
            return

        if call.data == "check_channel":
            try:
                member = bot.get_chat_member("@Freispielritter", call.from_user.id)
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
            markup.add(types.InlineKeyboardButton("📦 Deals öffnen", callback_data="open_deals"))

            bot.send_message(
                chat_id,
                f"✅ Freigeschaltet\n\nHier dein persönlicher Einladungslink um XP und mehr zu verdienen:\n{ref_link}",
                reply_markup=markup
            )
            return

        if call.data == "open_deals":

            markup = types.InlineKeyboardMarkup()

            markup.add(types.InlineKeyboardButton("🔥 Top Deal 😉", callback_data="top_deal"))
            markup.add(types.InlineKeyboardButton("🐾 Daily Quest", callback_data="daily_start"))
            markup.add(types.InlineKeyboardButton("🥇 Goldzino", url="https://track.stormaffiliates.com/visit/?bta=35714&brand=goldzino&afp=freispielritter&utm_campaign=freispielritter"))
            markup.add(types.InlineKeyboardButton("🎁 Freispiele", url="https://1f0s0.fit/r/XJTWVH25"))
            markup.add(types.InlineKeyboardButton("💰 Crypto Casino", url="https://t.me/tgcplaybot/?start=UsHEI0AGB"))

            bot.send_message(chat_id, "🎰 Wähle deinen Deal:", reply_markup=markup)
            return

        if call.data == "top_deal":
            user = call.from_user

            bot.send_message(
                ADMIN_ID,
                f"🔥 TOP DEAL ANFRAGE\n\n👤 ID: {user.id}\n🧑 @{user.username or 'unknown'}"
            )

            bot.send_message(
                chat_id,
                "🔥 Unsere Top Deals sind Exklusiv – ein Admin kümmert sich bald um deine Anfrage 😉"
            )
            return

        if call.data == "daily_start":

            user = get_user(chat_id)

            if user.get("last_daily"):
                bot.send_message(chat_id, "⏳ Daily Quest schon gemacht. Morgen wieder!")
                return

            pets = ["🐶","🐱","🐺","🦊","🐵","🐸","🐼","🐉"]

            markup = types.InlineKeyboardMarkup()

            for p in pets:
                markup.add(types.InlineKeyboardButton(p, callback_data=f"pet_select_{p}"))

            bot.send_message(chat_id, "🐾 Wähle dein Tier:", reply_markup=markup)
            return

        if call.data.startswith("pet_select_"):
            pet = call.data.split("_")[2]

            update_user(chat_id, {
                "daily_pet": pet,
                "daily_stage": 0
            })

            bot.send_message(chat_id, f"✨ Dein Tier ist {pet}\nGib ihm einen Namen:")
            return

        if call.data == "daily_feed":

            texts = [
                "🍖 Es hat geschmeckt!",
                "😐 Es war okay...",
                "🤢 Es hat nicht geschmeckt!",
                "😍 Dein Tier ist glücklich!"
            ]

            bot.send_message(chat_id, random.choice(texts))
            update_user(chat_id, {"daily_stage": 1})
            return

        if call.data == "daily_walk":

            texts = [
                "🚶 Ihr geht Richtung Casino...",
                "🌳 Spaziergang war entspannt",
                "😎 Dein Tier fühlt sich frei",
                "🎰 Es spürt die Gewinne!"
            ]

            bot.send_message(chat_id, random.choice(texts))
            update_user(chat_id, {"daily_stage": 2})
            return

        if call.data == "daily_play":

            texts = [
                "🎰 Ihr sitzt am Automaten...",
                "💰 BIG WIN ENERGY!",
                "😱 Fast Jackpot!",
                "🔥 Heute läuft es!"
            ]

            bot.send_message(chat_id, random.choice(texts))

            user = get_user(chat_id)

            if user.get("daily_stage") == 2:

                add_xp(chat_id, 3)

                update_user(chat_id, {
                    "daily_stage": 3,
                    "last_daily": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                bot.send_message(chat_id, "🏆 Daily Quest abgeschlossen +3 XP!")
            else:
                bot.send_message(chat_id, "❌ Du musst erst die anderen Aktionen machen!")
            return

    except Exception as e:
        print("Callback Error:", e)
        return

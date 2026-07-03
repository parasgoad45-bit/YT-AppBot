async def countdown_and_proceed(update, context, uid, seconds=5):
    """5 sec countdown dikhata hai phir True return karta hai"""
    msg = await update.message.reply_text(f"⏳ Verify ho raha hai... {seconds}")
    for i in range(seconds - 1, 0, -1):
        await asyncio.sleep(1)
        try:
            await msg.edit_text(f"⏳ Verify ho raha hai... {i}")
        except Exception:
            pass
    await asyncio.sleep(1)
    try:
        await msg.edit_text("✅ Verify ho gaya!")
    except Exception:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    serial = get_serial(uid)

    user_data[uid] = {
        "state": "choosing_device",
        "name": user.first_name,
        "username": user.username or "N/A",
        "serial": serial,
        "subscribe_attempts": 0,
        "like_attempts": 0,
    }

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=(
            f"🆕 *Naya User — #{serial}*\n\n"
            f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
            f"🆔 `{uid}`"
        ),
        parse_mode="Markdown"
    )

    # 🎉 Welcome message
    await update.message.reply_text(
        f"🎉 *Welcome {user.first_name}!*\n\n"
        f"🙏 *Jugadu Baba* mein tumhara swagat hai!\n"
        f"Tumhara serial number hai *#{serial}* 🔢\n\n"
        f"Chalo shuru karte hain 👇",
        parse_mode="Markdown"
    )

    keyboard = [[
        InlineKeyboardButton("🍎 iPhone", callback_data=f"device_iphone_{uid}"),
        InlineKeyboardButton("🤖 Android", callback_data=f"device_android_{uid}"),
    ]]
    await update.message.reply_text(
        f"📱 *Tumhara phone kaunsa hai?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    uinfo = user_data.get(uid, {})
    state = uinfo.get("state", "")
    serial = uinfo.get("serial", get_serial(uid))
    device = uinfo.get("device", "unknown")

    if state not in ("waiting_subscribe", "waiting_like"):
        await update.message.reply_text("⚠️ Abhi screenshot ki zaroorat nahi.\n/start karke dobara shuru karo!")
        return

    # ─────────────────────────────────────────
    # STEP 1 — Subscribe
    # ─────────────────────────────────────────
    if state == "waiting_subscribe":
        attempts = uinfo.get("subscribe_attempts", 0)

        if attempts == 0:
            user_data[uid]["subscribe_attempts"] = 1
            await update.message.reply_text(
                f"⚠️ *Network Problem!*\n\n"
                f"Mujhe screenshot sahi se nahi mila 😕\n"
                f"Please screenshot *dubara* bhejo! 📸",
                parse_mode="Markdown"
            )

        else:
            user_data[uid]["state"] = "waiting_like"
            user_data[uid]["subscribe_attempts"] = 0

            await context.bot.forward_message(
                chat_id=ADMIN_CHAT_ID,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"✅ *Step 1 - Subscribe AUTO APPROVED*\n\n"
                    f"🔢 *#{serial}*\n"
                    f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                    f"🆔 `{uid}`\n"
                    f"📱 {'🍎 iPhone' if device == 'iphone' else '🤖 Android'}"
                ),
                parse_mode="Markdown"
            )

            await countdown_and_proceed(update, context, uid)

            await update.message.reply_text(
                f"✅ *Subscribe Verified!* 🎉\n\n"
                f"*Step 2️⃣:* Ab *{YOUTUBE_CHANNEL}* ke kisi bhi video ko 👍 *Like* karo!\n\n"
                f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
                f"Like ke baad screenshot bhejo! 📸",
                parse_mode="Markdown"
            )

    # ─────────────────────────────────────────
    # STEP 2 — Like
    # ─────────────────────────────────────────
    elif state == "waiting_like":
        attempts = uinfo.get("like_attempts", 0)

        if attempts == 0:
            user_data[uid]["like_attempts"] = 1
            await update.message.reply_text(
                f"⚠️ *Network Problem!*\n\n"
                f"Mujhe screenshot sahi se nahi mila 😕\n"
                f"Please screenshot *dubara* bhejo! 📸",
                parse_mode="Markdown"
            )

        else:
            user_data[uid]["state"] = "done"

            await context.bot.forward_message(
                chat_id=ADMIN_CHAT_ID,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"✅ *Step 2 - Like AUTO APPROVED — Link bheja!*\n\n"
                    f"🔢 *#{serial}*\n"
                    f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                    f"🆔 `{uid}`\n"
                    f"📱 {'🍎 iPhone' if device == 'iphone' else '🤖 Android'}"
                ),
                parse_mode="Markdown"
            )

            await countdown_and_proceed(update, context, uid)
            await send_reward_link(context, uid, user_data[uid])

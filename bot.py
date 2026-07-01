import os
import logging
import asyncio
import base64
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ============ CONFIG ============
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
IPHONE_REWARD_LINK = "https://apps.apple.com/in/app/mehmandari/id6766165293"
ANDROID_REWARD_LINK = "https://t.me/jugaduBaba0"
YOUTUBE_CHANNEL = "Jugadu Baba"
YOUTUBE_CHANNEL_URL = "https://youtube.com/@JugaduBaba-bmw"
LINK_DELETE_SECONDS = 30
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot_mode = "manual"
# ================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}
user_counter = 0  # Global counter for serial numbers
uid_to_serial = {}  # uid -> serial number mapping


def get_serial(uid: int) -> int:
    """Return existing serial for uid, or assign new one."""
    global user_counter
    if uid not in uid_to_serial:
        user_counter += 1
        uid_to_serial[uid] = user_counter
    return uid_to_serial[uid]


async def verify_screenshot_with_ai(image_bytes: bytes, expected_type: str) -> dict:
    if not GEMINI_API_KEY:
        return {"valid": False, "reason": "AI verification not configured (no API key)"}

    if expected_type == "subscribe":
        question = (
            f"Is this a screenshot of a YouTube channel page showing the channel "
            f"'{YOUTUBE_CHANNEL}' in a SUBSCRIBED state (bell icon, 'Subscribed' label, not just 'Subscribe')? "
        )
    else:
        question = (
            f"Is this a screenshot of a YouTube video from the channel '{YOUTUBE_CHANNEL}' "
            f"showing the Like button already pressed/filled (liked state)?"
        )

    prompt = (
        f"{question} "
        f"Reply with ONLY raw JSON, no markdown, no extra text: "
        f'{{"valid": true or false, "reason": "short reason"}}'
    )

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )

    max_retries = 3
    base_delay = 5

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    json={
                        "contents": [{
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                            ]
                        }]
                    },
                )

            if resp.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = base_delay * (attempt + 1)
                    logger.warning(f"Gemini rate limited. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {"valid": False, "reason": "AI service busy (rate limited), please try again in a minute"}

            data = resp.json()

            if resp.status_code != 200 or "candidates" not in data:
                error_msg = data.get("error", {}).get("message", "unknown error")
                logger.error(f"Gemini API error: {error_msg} | Raw: {data}")
                return {"valid": False, "reason": f"AI check failed ({error_msg}), please use manual review"}

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = text.replace("```json", "").replace("```", "").strip()
            import json
            parsed = json.loads(text)
            return {"valid": bool(parsed.get("valid")), "reason": parsed.get("reason", "")}

        except Exception as e:
            logger.error(f"AI verification error: {e}")
            return {"valid": False, "reason": "AI check failed, please use manual review"}

    return {"valid": False, "reason": "AI check failed after retries, please use manual review"}


async def automode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_mode
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if not GEMINI_API_KEY:
        await update.message.reply_text("⚠️ GEMINI_API_KEY set nahi hai, Auto mode kaam nahi karega.")
        return
    bot_mode = "auto"
    await update.message.reply_text("🤖 *Auto mode ON*", parse_mode="Markdown")


async def manualmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_mode
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    bot_mode = "manual"
    await update.message.reply_text("👤 *Manual mode ON*", parse_mode="Markdown")


async def mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    await update.message.reply_text(f"Current mode: *{bot_mode}*", parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    serial = get_serial(uid)

    user_data[uid] = {
        "state": "choosing_device",
        "name": user.first_name,
        "username": user.username or "N/A",
        "serial": serial
    }

    # Notify admin about new user with serial number
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=(
            f"🆕 *Naya User — #{serial}*\n\n"
            f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
            f"🆔 Telegram ID: `{uid}`"
        ),
        parse_mode="Markdown"
    )

    keyboard = [[
        InlineKeyboardButton("🍎 iPhone", callback_data=f"device_iphone_{uid}"),
        InlineKeyboardButton("🤖 Android", callback_data=f"device_android_{uid}"),
    ]]
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        f"🎬 *Jugadu Baba Bot* mein aapka swagat hai!\n\n"
        f"📱 *Tumhara phone kaunsa hai?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def get_photo_bytes(update: Update) -> bytes:
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    else:
        file = await update.message.document.get_file()
    ba = await file.download_as_bytearray()
    return bytes(ba)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    state = user_data.get(uid, {}).get("state", "waiting_subscribe")
    serial = user_data.get(uid, {}).get("serial", get_serial(uid))

    if state not in ("waiting_subscribe", "waiting_like"):
        await update.message.reply_text("⚠️ Abhi screenshot ki zaroorat nahi.\n/start karke dobara shuru karo!")
        return

    expected_type = "subscribe" if state == "waiting_subscribe" else "like"
    step_label = "Step 1 - Subscribe" if expected_type == "subscribe" else "Step 2 - Like"
    device = user_data[uid].get("device", "unknown")

    if bot_mode == "auto":
        await update.message.reply_text("🤖 AI screenshot check kar raha hai... thoda wait karo!")
        try:
            img_bytes = await get_photo_bytes(update)
        except Exception as e:
            logger.error(f"Photo download error: {e}")
            await update.message.reply_text("⚠️ Screenshot download nahi hua, dobara bhejo!")
            return

        result = await verify_screenshot_with_ai(img_bytes, expected_type)

        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🤖 *Auto-check — {step_label}*\n\n"
                f"🔢 Serial: *#{serial}*\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                f"🆔 `{uid}`\n"
                f"📱 Device: {'🍎 iPhone' if device == 'iphone' else '🤖 Android'}\n"
                f"Result: {'✅ VALID' if result['valid'] else '❌ INVALID'}\n"
                f"Reason: {result['reason']}"
            ),
            parse_mode="Markdown"
        )
        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id
        )

        if not result["valid"]:
            await update.message.reply_text(
                f"❌ *Yeh {expected_type} ka screenshot nahi lag raha!*\n\n"
                f"Sahi {expected_type} screenshot bhejo:\n👉 {YOUTUBE_CHANNEL_URL}",
                parse_mode="Markdown"
            )
            return

        if expected_type == "subscribe":
            user_data[uid]["state"] = "waiting_like"
            await update.message.reply_text(
                f"✅ *Subscribe Verified!* 🎉\n\n"
                f"*Step 2️⃣:* Ab {YOUTUBE_CHANNEL} ke kisi bhi video ko 👍 Like karo!\n\n"
                f"👉 {YOUTUBE_CHANNEL_URL}\n\nLike karne ke baad screenshot bhejo! 📸",
                parse_mode="Markdown"
            )
        else:
            user_data[uid]["state"] = "done"
            name = user_data[uid].get("name", user.first_name)
            reward_link = IPHONE_REWARD_LINK if device == "iphone" else ANDROID_REWARD_LINK
            device_label = "iPhone Movie App" if device == "iphone" else "Android Movie App ka Telegram"
            reward_text = (
                f"🎉 *Congratulations {name}!*\n\nSab verify ho gaya! ✅\n\n"
                f"Yeh raha tumhara *{device_label}* link:\n\n👇👇👇\n{reward_link}\n\n"
                f"⚠️ *Yeh link sirf {LINK_DELETE_SECONDS} second mein delete ho jayega!*\nAbhi jaldi open karo! ⏰"
            )
            sent = await context.bot.send_message(chat_id=uid, text=reward_text, parse_mode="Markdown")
            asyncio.create_task(delete_message_later(context, uid, sent.message_id, LINK_DELETE_SECONDS))
        return

    # ============================================================
    # MANUAL MODE — Subscribe auto-pass, Like needs link approval
    # ============================================================

    if state == "waiting_subscribe":
        user_data[uid]["state"] = "waiting_like"

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"👁 *Step 1 - Subscribe Screenshot (FYI)*\n\n"
                f"🔢 Serial: *#{serial}*\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                f"🆔 `{uid}`\n"
                f"📱 Device: {'🍎 iPhone' if device == 'iphone' else '🤖 Android'}\n\n"
                f"✅ Auto-approved, user ko Step 2 bhej diya."
            ),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            f"✅ *Subscribe Verify Ho Gaya!* 🎉\n\n"
            f"*Step 2️⃣:* Ab *{YOUTUBE_CHANNEL}* ke kisi bhi video ko 👍 *Like* karo!\n\n"
            f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
            f"Like karne ke baad us video ka *screenshot* yahan bhejo! 📸",
            parse_mode="Markdown"
        )

    elif state == "waiting_like":
        user_data[uid]["state"] = "pending_like"

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        keyboard = [[
            InlineKeyboardButton("✅ Send Link", callback_data=f"approve_like_{uid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_like_{uid}"),
        ]]
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"👍 *Step 2 - Like Screenshot*\n\n"
                f"🔢 Serial: *#{serial}*\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                f"🆔 `{uid}`\n"
                f"📱 Device: {'🍎 iPhone' if device == 'iphone' else '🤖 Android'}\n\n"
                f"Link bhejna hai?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            "✅ Like screenshot mil gaya!\n"
            "⏳ Admin link approve karega, thodi der mein milega! 🙏"
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and "image" in doc.mime_type:
        await handle_photo(update, context)
    else:
        await update.message.reply_text("📸 Image ya screenshot bhejo!")


async def delete_message_later(context, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Delete error: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[0]
    step = parts[1]
    uid = int(parts[2])

    uinfo = user_data.get(uid, {})
    name = uinfo.get("name", "User")
    username = uinfo.get("username", "N/A")
    device = uinfo.get("device", "iphone")
    serial = uinfo.get("serial", uid_to_serial.get(uid, "?"))
    reward_link = IPHONE_REWARD_LINK if device == "iphone" else ANDROID_REWARD_LINK

    if action == "device":
        device_choice = step
        user_data[uid]["device"] = device_choice
        user_data[uid]["state"] = "waiting_subscribe"

        device_text = "🍎 iPhone" if device_choice == "iphone" else "🤖 Android"
        await query.edit_message_text(
            f"✅ *{device_text}* select kiya!\n\n"
            f"*Step 1️⃣:* YouTube pe *{YOUTUBE_CHANNEL}* ko Subscribe karo\n"
            f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
            f"Subscribe karne ke baad us page ka *screenshot* yahan bhejo! 📸",
            parse_mode="Markdown"
        )
        return

    if action == "approve" and step == "like":
        user_data[uid]["state"] = "done"
        await query.edit_message_text(f"✅ Link bheja! #{serial}\n👤 {name} (@{username})")

        device_label = "iPhone Movie App" if device == "iphone" else "Android Movie App ka Telegram"
        reward_text = (
            f"🎉 *Congratulations {name}!*\n\n"
            f"Sab verify ho gaya! ✅\n\n"
            f"Yeh raha tumhara *{device_label}* link:\n\n"
            f"👇👇👇\n{reward_link}\n\n"
            f"⚠️ *Yeh link sirf {LINK_DELETE_SECONDS} second mein delete ho jayega!*\n"
            f"Abhi jaldi open karo! ⏰"
        )
        sent = await context.bot.send_message(chat_id=uid, text=reward_text, parse_mode="Markdown")
        asyncio.create_task(delete_message_later(context, uid, sent.message_id, LINK_DELETE_SECONDS))

    elif action == "reject" and step == "like":
        user_data[uid]["state"] = "waiting_like"
        await query.edit_message_text(f"❌ Like rejected! #{serial}\n👤 {name} (@{username})")
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"❌ *Like verify nahi hua!*\n\n"
                f"Jugadu Baba ke kisi bhi video ko 👍 *Like* karo:\n"
                f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
                f"Like karne ke baad dobara screenshot bhejo! 📸"
            ),
            parse_mode="Markdown"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_data.get(uid, {}).get("state", "")

    if state == "waiting_subscribe":
        await update.message.reply_text(
            f"📸 Pehle *{YOUTUBE_CHANNEL}* subscribe karo:\n"
            f"👉 {YOUTUBE_CHANNEL_URL}\n\nSubscribe ke baad screenshot bhejo!",
            parse_mode="Markdown"
        )
    elif state == "waiting_like":
        await update.message.reply_text(
            f"📸 Jugadu Baba ke kisi bhi video ko 👍 Like karo:\n"
            f"👉 {YOUTUBE_CHANNEL_URL}\n\nLike ke baad screenshot bhejo!",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("/start karke shuru karo! 😊")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN set nahi hai!")
    if ADMIN_CHAT_ID == 0:
        raise ValueError("ADMIN_CHAT_ID set nahi hai!")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("automode", automode_cmd))
    app.add_handler(CommandHandler("manualmode", manualmode_cmd))
    app.add_handler(CommandHandler("mode", mode_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

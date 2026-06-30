import os
import logging
import asyncio
import base64
import httpx
from datetime import datetime, time as dtime
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

# Bot mode: "manual" (admin approves everything by hand) or "auto" (Gemini vision pre-checks screenshots)
bot_mode = "manual"

# Night queue: admin approval is STILL required manually, always.
# Only the reward-link DELIVERY gets delayed to morning if approval happens at night.
NIGHT_START_HOUR = 0   # 12 AM
NIGHT_END_HOUR = 6     # 6 AM
MORNING_HOUR = 6        # queued rewards get sent at 6:00 AM
# ================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}
night_queue = []  # list of dicts: {"uid": int, "text": str}


def is_night_time():
    now = datetime.now().time()
    return dtime(NIGHT_START_HOUR, 0) <= now < dtime(NIGHT_END_HOUR, 0)


async def deliver_or_queue(context, uid, text):
    """Send reward text now, or queue it for MORNING_HOUR if it's currently night."""
    if is_night_time():
        night_queue.append({"uid": uid, "text": text})
        return False  # queued
    sent = await context.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
    asyncio.create_task(delete_message_later(context, uid, sent.message_id, LINK_DELETE_SECONDS))
    return True  # sent immediately


async def delete_message_later_app(app, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await app.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Delete error: {e}")


async def morning_dispatcher(app):
    """Background task: every day at MORNING_HOUR, flush queued reward messages."""
    from datetime import timedelta
    while True:
        now = datetime.now()
        target = now.replace(hour=MORNING_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        if night_queue:
            pending = night_queue.copy()
            night_queue.clear()
            for item in pending:
                try:
                    sent = await app.bot.send_message(chat_id=item["uid"], text=item["text"], parse_mode="Markdown")
                    asyncio.create_task(delete_message_later_app(app, item["uid"], sent.message_id, LINK_DELETE_SECONDS))
                except Exception as e:
                    logger.error(f"Morning dispatch error for {item['uid']}: {e}")
            logger.info(f"Morning dispatcher: sent {len(pending)} queued reward(s).")


async def verify_screenshot_with_ai(image_bytes: bytes, expected_type: str) -> dict:
    """
    Uses Google Gemini vision to check if a screenshot genuinely shows what it claims.
    expected_type: "subscribe" or "like"
    Returns: {"valid": bool, "reason": str}
    Fails closed (valid=False) on any error, so a broken API never silently lets bad screenshots through.
    """
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
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = text.replace("```json", "").replace("```", "").strip()
            import json
            parsed = json.loads(text)
            return {"valid": bool(parsed.get("valid")), "reason": parsed.get("reason", "")}
    except Exception as e:
        logger.error(f"AI verification error: {e}")
        return {"valid": False, "reason": "AI check failed, please use manual review"}


async def automode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_mode
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if not GEMINI_API_KEY:
        await update.message.reply_text(
            "⚠️ GEMINI_API_KEY set nahi hai, isliye Auto mode kaam nahi karega.\n"
            "Manual mode mein hi rehna padega."
        )
        return
    bot_mode = "auto"
    await update.message.reply_text(
        "🤖 *Auto mode ON*\n\n"
        "Ab screenshots Claude vision se khud check honge. "
        "Sirf real subscribe/like screenshots hi pass honge, baaki turant reject ho jayenge.",
        parse_mode="Markdown"
    )


async def manualmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_mode
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    bot_mode = "manual"
    await update.message.reply_text(
        "👤 *Manual mode ON*\n\nAb har screenshot aapko khud Approve/Reject karna hoga.",
        parse_mode="Markdown"
    )


async def mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    await update.message.reply_text(f"Current mode: *{bot_mode}*", parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data[user.id] = {"state": "choosing_device", "name": user.first_name, "username": user.username or "N/A"}

    keyboard = [[
        InlineKeyboardButton("🍎 iPhone", callback_data=f"device_iphone_{user.id}"),
        InlineKeyboardButton("🤖 Android", callback_data=f"device_android_{user.id}"),
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

        # Always log to admin for audit, regardless of outcome
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🤖 *Auto-check — {step_label}*\n\n"
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

        # Valid — auto-advance same as admin approval would
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
            sent_now = await deliver_or_queue(context, uid, reward_text)
            if not sent_now:
                await update.message.reply_text(
                    "✅ *Verify ho gaya!* 🎉\n\nAbhi raat ka time hai, isliye reward link *subah 6 baje* "
                    "automatically bhej diya jayega. 🌙",
                    parse_mode="Markdown"
                )
        return

    # ----- manual mode (original flow) -----
    if state == "waiting_subscribe":
        await update.message.reply_text("⏳ Subscribe screenshot admin ko bheja ja raha hai... thoda wait karo!")
        user_data[uid]["state"] = "pending_subscribe"

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_sub_{uid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_sub_{uid}"),
        ]]
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🔔 *Step 1 - Subscribe Verification*\n\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                f"🆔 `{uid}`\n"
                f"📱 Device: {'🍎 iPhone' if device == 'iphone' else '🤖 Android'}\n\n"
                f"Kya usne Jugadu Baba ko subscribe kiya hai?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            "✅ Screenshot bhej diya admin ko!\n"
            "⏳ Admin verify karega, thodi der mein next step milega. 🙏"
        )

    elif state == "waiting_like":
        await update.message.reply_text("⏳ Like screenshot admin ko bheja ja raha hai... thoda wait karo!")
        user_data[uid]["state"] = "pending_like"

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_like_{uid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_like_{uid}"),
        ]]
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"👍 *Step 2 - Like Verification*\n\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                f"🆔 `{uid}`\n"
                f"📱 Device: {'🍎 iPhone' if device == 'iphone' else '🤖 Android'}\n\n"
                f"Kya usne Jugadu Baba ki video ko Like kiya hai?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            "✅ Like screenshot bhej diya admin ko!\n"
            "⏳ Admin verify karega, link milega jaldi! 🙏"
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
    reward_link = IPHONE_REWARD_LINK if device == "iphone" else ANDROID_REWARD_LINK

    # Device selection
    if action == "device":
        device_choice = step  # iphone or android
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

    # Subscribe verification
    if action == "approve" and step == "sub":
        user_data[uid]["state"] = "waiting_like"
        await query.edit_message_text(f"✅ Subscribe approved!\n👤 {name} (@{username})")

        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"✅ *Subscribe Verified! Shukriya!* 🎉\n\n"
                f"*Step 2️⃣:* Ab Jugadu Baba ke kisi bhi video ko 👍 *Like* karo!\n\n"
                f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
                f"📌 Video open karo → 👍 Like button dabao\n\n"
                f"Like karne ke baad us video ka *screenshot* yahan bhejo! 📸"
            ),
            parse_mode="Markdown"
        )

    elif action == "reject" and step == "sub":
        user_data[uid]["state"] = "waiting_subscribe"
        await query.edit_message_text(f"❌ Subscribe rejected!\n👤 {name} (@{username})")
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"❌ *Subscribe verify nahi hua!*\n\n"
                f"Pehle *{YOUTUBE_CHANNEL}* ko subscribe karo:\n"
                f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
                f"Subscribe karne ke baad dobara screenshot bhejo! 📸"
            ),
            parse_mode="Markdown"
        )

    # Like verification
    elif action == "approve" and step == "like":
        user_data[uid]["state"] = "done"
        await query.edit_message_text(f"✅ Like approved! Link bheja!\n👤 {name} (@{username})")

        device_label = "iPhone Movie App" if device == "iphone" else "Android Movie App ka Telegram"
        reward_text = (
            f"🎉 *Congratulations {name}!*\n\n"
            f"Sab verify ho gaya! ✅\n\n"
            f"Yeh raha tumhara *{device_label}* link:\n\n"
            f"👇👇👇\n{reward_link}\n\n"
            f"⚠️ *Yeh link sirf {LINK_DELETE_SECONDS} second mein delete ho jayega!*\n"
            f"Abhi jaldi open karo! ⏰"
        )

        sent_now = await deliver_or_queue(context, uid, reward_text)
        if not sent_now:
            # It's night time (12 AM - 6 AM) — admin already approved, but delivery is queued for 6 AM
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "✅ *Approve ho gaya!* 🎉\n\n"
                    "Abhi raat ka time hai, isliye tumhara reward link *subah 6 baje* tak "
                    "automatically bhej diya jayega. Tab tak ke liye shukriya! 🌙"
                ),
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"🌙 Night approval queued — {name} (@{username}) ka reward link 6 AM par jayega."
            )

    elif action == "reject" and step == "like":
        user_data[uid]["state"] = "waiting_like"
        await query.edit_message_text(f"❌ Like rejected!\n👤 {name} (@{username})")
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
            f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
            f"Subscribe ke baad screenshot bhejo!",
            parse_mode="Markdown"
        )
    elif state == "waiting_like":
        await update.message.reply_text(
            f"📸 Jugadu Baba ke kisi bhi video ko 👍 Like karo:\n"
            f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
            f"Like ke baad screenshot bhejo!",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("/start karke shuru karo! 😊")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN set nahi hai!")
    if ADMIN_CHAT_ID == 0:
        raise ValueError("ADMIN_CHAT_ID set nahi hai!")

    app 

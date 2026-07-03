import os
import logging
import asyncio
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
# ================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}
user_counter = 0
uid_to_serial = {}


def get_serial(uid: int) -> int:
    global user_counter
    if uid not in uid_to_serial:
        user_counter += 1
        uid_to_serial[uid] = user_counter
    return uid_to_serial[uid]


async def delete_message_later(context, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Delete error: {e}")


async def countdown_and_proceed(update, context, uid, seconds=5):
    """5 sec countdown dikhata hai phir verify complete karta hai"""
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


async def send_reward_link(context, uid: int, uinfo: dict):
    device = uinfo.get("device", "iphone")
    name = uinfo.get("name", "User")
    reward_link = IPHONE_REWARD_LINK if device == "iphone" else ANDROID_REWARD_LINK
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    serial = get_serial(uid)

    user_data[uid] = {
        "state": "choosing_device",
        "name": user.first_name,
        "username": user.username or "N/A",
        "serial": serial,
        "subscribe_attempts": 0,   # Step 1 screenshot attempts
        "like_attempts": 0,        # Step 2 screenshot attempts
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
            # Pehli baar → Network problem bolo
            user_data[uid]["subscribe_attempts"] = 1
            await update.message.reply_text(
                f"⚠️ *Network Problem!*\n\n"
                f"Mujhe screenshot sahi se nahi mila 😕\n"
                f"Please screenshot *dubara* bhejo! 📸",
                parse_mode="Markdown"
            )

        else:
            # Doosri baar → Approve, countdown, Step 2 pe bhejo
            user_data[uid]["state"] = "waiting_like"
            user_data[uid]["subscribe_attempts"] = 0  # reset for next step

            # Admin ko notify
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

            # 5 sec countdown
            await countdown_and_proceed(update, context, uid)

            # User ko Step 2 bhejo
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
        attem

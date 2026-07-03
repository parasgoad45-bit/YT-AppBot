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
        f"Abhi jaldi open ka

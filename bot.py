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

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=(
            f"🆕 *Naya User — #{serial}*\n\n"
            f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
            f"🆔 `{uid}`"
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


async def delete_message_later(context, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Delete error: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    state = user_data.get(uid, {}).get("state", "")
    serial = user_data.get(uid, {}).get("serial", get_serial(uid))
    device = user_data.get(uid, {}).get("device", "unknown")

    if state not in ("waiting_subscribe", "waiting_like"):
        await update.message.reply_text("⚠️ Abhi screenshot ki zaroorat nahi.\n/start karke dobara shuru karo!")
        return

    if state == "waiting_subscribe":
        user_data[uid]["state"] = "pending_subscribe"
        await update.message.reply_text("⏳ Screenshot admin ko bheja ja raha hai... thoda wait karo!")

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approvesub{uid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rejectsub{uid}"),
        ]]
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🔔 *Step 1 - Subscribe*\n\n"
                f"🔢 *#{serial}*\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                f"🆔 `{uid}`\n"
                f"📱 {'🍎 iPhone' if device == 'iphone' else '🤖 Android'}\n\n"
                f"Subscribe kiya hai?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await update.message.reply_text("✅ Admin ko bhej diya! Thodi der mein next step milega. 🙏")

    elif state == "waiting_like":
        user_data[uid]["state"] = "pending_like"
        await update.message.reply_text("⏳ Screenshot admin ko bheja ja raha hai... thoda wait karo!")

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        keyboard = [[
            InlineKeyboardButton("✅ Send Link", callback_data=f"approvelike{uid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rejectlike{uid}"),
        ]]
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"👍 *Step 2 - Like*\n\n"
                f"🔢 *#{serial}*\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                f"🆔 `{uid}`\n"
                f"📱 {'🍎 iPhone' if device == 'iphone' else '🤖 Android'}\n\n"
                f"Link bhejna hai?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await update.message.reply_text("✅ Admin ko bhej diya! Link jaldi milega. 🙏")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and "image" in doc.mime_type:
        await handle_photo(update, context)
    else:
        await update.message.reply_text("📸 Image ya screenshot bhejo!")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Device selection
    if data.startswith("device_iphone_"):
        uid = int(data.replace("device_iphone_", ""))
        user_data[uid]["device"] = "iphone"
        user_data[uid]["state"] = "waiting_subscribe"
        await query.edit_message_text(
            f"✅ *🍎 iPhone* select kiya!\n\n"
            f"*Step 1️⃣:* YouTube pe *{YOUTUBE_CHANNEL}* ko Subscribe karo\n"
            f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
            f"Screenshot bhejo! 📸",
            parse_mode="Markdown"
        )

    elif data.startswith("device_android_"):
        uid = int(data.replace("device_android_", ""))
        user_data[uid]["device"] = "android"
        user_data[uid]["state"] = "waiting_subscribe"
        await query.edit_message_text(
            f"✅ *🤖 Android* select kiya!\n\n"
            f"*Step 1️⃣:* YouTube pe *{YOUTUBE_CHANNEL}* ko Subscribe karo\n"
            f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
            f"Screenshot bhejo! 📸",
            parse_mode="Markdown"
        )

    # Subscribe approve
    elif data.startswith("approvesub"):
        uid = int(data.replace("approvesub", ""))
        user_data[uid]["state"] = "waiting_like"
        uinfo = user_data.get(uid, {})
        await query.edit_message_text(
            f"✅ Subscribe approved! #{uinfo.get('serial', '')}\n"
            f"👤 {uinfo.get('name', '')} (@{uinfo.get('username', '')})"
        )
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"✅ *Subscribe Verified!* 🎉\n\n"
                f"*Step 2️⃣:* Ab *{YOUTUBE_CHANNEL}* ke kisi bhi video ko 👍 *Like* karo!\n\n"
                f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
                f"Like ke baad screenshot bhejo! 📸"
            ),
            parse_mode="Markdown"
        )

    # Subscribe reject
    elif data.startswith("rejectsub"):
        uid = int(data.replace("rejectsub", ""))
        user_data[uid]["state"] = "waiting_subscribe"
        uinfo = user_data.get(uid, {})
        await query.edit_message_text(
            f"❌ Subscribe rejected! #{uinfo.get('serial', '')}\n"
            f"👤 {uinfo.get('name', '')} (@{uinfo.get('username', '')})"
        )
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"❌ *Subscribe verify nahi hua!*\n\n"
                f"Pehle *{YOUTUBE_CHANNEL}* ko subscribe karo:\n"
                f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
                f"Dobara screenshot bhejo! 📸"
            ),
            parse_mode="Markdown"
        )

    # Like approve — send link
    elif data.startswith("approvelike"):
        uid = int(data.replace("approvelike", ""))
        user_data[uid]["state"] = "done"
        uinfo = user_data.get(uid, {})
        device = uinfo.get("device", "iphone")
        name = uinfo.get("name", "User")
        reward_link = IPHONE_REWARD_LINK if device == "iphone" else ANDROID_REWARD_LINK
        device_label = "iPhone Movie App" if device == "iphone" else "Android Movie App ka Telegram"

        await query.edit_message_text(
            f"✅ Link bheja! #{uinfo.get('serial', '')}\n"
            f"👤 {name} (@{uinfo.get('username', '')})"
        )
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

    # Like reject
    elif data.startswith("rejectlike"):
        uid = int(data.replace("rejectlike", ""))
        user_data[uid]["state"] = "waiting_like"
        uinfo = user_data.get(uid, {})
        await query.edit_message_text(
            f"❌ Like rejected! #{uinfo.get('serial', '')}\n"
            f"👤 {uinfo.get('name', '')} (@{uinfo.get('username', '')})"
        )
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"❌ *Like verify nahi hua!*\n\n"
                f"Jugadu Baba ke kisi bhi video ko 👍 *Like* karo:\n"
                f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
                f"Dobara screenshot bhejo! 📸"
            ),
            parse_mode="Markdown"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_data.get(uid, {}).get("state", "")

    if state == "waiting_subscribe":
        await update.message.reply_text(
            f"📸 *{YOUTUBE_CHANNEL}* subscribe karo:\n"
            f"👉 {YOUTUBE_CHANNEL_URL}\n\nSubscribe ke baad screenshot bhejo!",
            parse_mode="Markdown"
        )
    elif state == "waiting_like":
        await update.message.reply_text(
            f"📸 Jugadu Baba ke video ko 👍 Like karo:\n"
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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

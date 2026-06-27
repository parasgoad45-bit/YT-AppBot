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


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    state = user_data.get(uid, {}).get("state", "waiting_subscribe")

    if state == "waiting_subscribe":
        await update.message.reply_text("⏳ Subscribe screenshot admin ko bheja ja raha hai... thoda wait karo!")
        user_data[uid]["state"] = "pending_subscribe"

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        device = user_data[uid].get("device", "unknown")
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
        device = user_data[uid].get("device", "unknown")
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

    else:
        await update.message.reply_text("⚠️ Abhi screenshot ki zaroorat nahi.\n/start karke dobara shuru karo!")


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

        if device == "iphone":
            sent = await context.bot.send_message(
                chat_id=uid,
                text=(
                    f"🎉 *Congratulations {name}!*\n\n"
                    f"Sab verify ho gaya! ✅\n\n"
                    f"Yeh raha tumhara *iPhone Movie App* link:\n\n"
                    f"👇👇👇\n{reward_link}\n\n"
                    f"⚠️ *Yeh link sirf {LINK_DELETE_SECONDS} second mein delete ho jayega!*\n"
                    f"Abhi jaldi open karo! ⏰"
                ),
                parse_mode="Markdown"
            )
            asyncio.create_task(
                delete_message_later(context, uid, sent.message_id, LINK_DELETE_SECONDS)
            )
        else:
            sent = await context.bot.send_message(
                chat_id=uid,
                text=(
                    f"🎉 *Congratulations {name}!*\n\n"
                    f"Sab verify ho gaya! ✅\n\n"
                    f"Yeh raha tumhara *Android Movie App* ka Telegram link:\n\n"
                    f"👇👇👇\n{reward_link}\n\n"
                    f"⚠️ *Yeh link sirf {LINK_DELETE_SECONDS} second mein delete ho jayega!*\n"
                    f"Abhi jaldi open karo! ⏰"
                ),
                parse_mode="Markdown"
            )
            asyncio.create_task(
                delete_message_later(context, uid, sent.message_id, LINK_DELETE_SECONDS)
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

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot start ho gaya!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    

import os
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ============ CONFIG ============
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))  # Tumhara Telegram ID
REWARD_LINK = "https://apps.apple.com/in/app/mehmandari/id6766165293"
YOUTUBE_CHANNEL = "Jugadu Baba"
YOUTUBE_CHANNEL_URL = "https://youtube.com/@JugaduBaba-bmw"
# ================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Pending users ka data store karo
pending_users = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"👋 Hello {user.first_name}!\n\n"
        f"🎬 *Jugadu Baba Bot* mein aapka swagat hai!\n\n"
        f"📱 *iPhone Movie App pana chahte ho?*\n\n"
        f"Bas yeh karo:\n"
        f"1️⃣ YouTube pe *{YOUTUBE_CHANNEL}* ko Subscribe karo\n"
        f"2️⃣ Subscribe ka screenshot lo\n"
        f"3️⃣ Yahan screenshot bhejo\n"
        f"4️⃣ Admin verify karega aur link milega! 🎉\n\n"
        f"👇 Pehle subscribe karo:\n{YOUTUBE_CHANNEL_URL}"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    await update.message.reply_text("⏳ Screenshot admin ko bheja ja raha hai... thoda wait karo!")

    # Admin ko forward karo with approve/reject buttons
    pending_users[user_id] = {
        "name": user.first_name,
        "username": user.username or "N/A"
    }

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption = (
        f"🔔 *New Verification Request*\n\n"
        f"👤 Name: {user.first_name}\n"
        f"🆔 Username: @{user.username or 'N/A'}\n"
        f"📌 User ID: `{user_id}`"
    )

    try:
        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=caption,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            "✅ Screenshot admin ko bhej diya gaya!\n\n"
            "⏳ Admin verify karega, thodi der mein link milega. Wait karo! 🙏"
        )
    except Exception as e:
        logger.error(f"Admin forward error: {e}")
        await update.message.reply_text("❌ Kuch error aaya! Dobara try karo.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and "image" in doc.mime_type:
        update.message.photo = None
        await handle_photo(update, context)
    else:
        await update.message.reply_text("📸 Bhai, image screenshot bhejo!")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("approve_"):
        user_id = int(data.split("_")[1])
        user_info = pending_users.get(user_id, {})

        # User ko link bhejo
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 *Congratulations!*\n\n"
                    f"Tumhara subscription verify ho gaya! ✅\n\n"
                    f"Yeh raha tumhara *iPhone Movie App* link:\n\n"
                    f"👇👇👇\n{REWARD_LINK}\n\n"
                    f"Enjoy karo! 🍿\n\n"
                    f"Jugadu Baba ka channel share karna mat bhoolna! 🙏"
                ),
                parse_mode="Markdown"
            )
            await query.edit_message_text(
                f"✅ Approved! Link bhej diya user ko.\n"
                f"👤 {user_info.get('name', 'User')} (@{user_info.get('username', 'N/A')})"
            )
            pending_users.pop(user_id, None)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif data.startswith("reject_"):
        user_id = int(data.split("_")[1])
        user_info = pending_users.get(user_id, {})

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ *Screenshot verify nahi hua!*\n\n"
                    f"Pehle *{YOUTUBE_CHANNEL}* ko subscribe karo:\n"
                    f"{YOUTUBE_CHANNEL_URL}\n\n"
                    "Sahi screenshot bhejo! 📸"
                ),
                parse_mode="Markdown"
            )
            await query.edit_message_text(
                f"❌ Rejected!\n"
                f"👤 {user_info.get('name', 'User')} (@{user_info.get('username', 'N/A')})"
            )
            pending_users.pop(user_id, None)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Bhai, screenshot bhejo na!\n\n"
        f"Pehle *{YOUTUBE_CHANNEL}* subscribe karo, phir screenshot yahan bhejo.",
        parse_mode="Markdown",
    )


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
    

import os
import logging
import base64
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ============ CONFIG ============
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REWARD_LINK = "https://apps.apple.com/in/app/mehmandari/id6766165293"
YOUTUBE_CHANNEL = "Jugadu Baba"
YOUTUBE_CHANNEL_URL = "https://youtube.com/@JugaduBaba-bmw"
# ================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

user_screenshots = {}

async def verify_with_gemini(image_bytes: bytes) -> bool:
    """Gemini se verify karo ki screenshot mein Jugadu Baba channel subscribed hai ya nahi"""
    try:
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        prompt = (
            f"Look at this YouTube screenshot carefully. "
            f"Is the user subscribed to the YouTube channel named '{YOUTUBE_CHANNEL}' (@JugaduBaba-bmw)? "
            f"Check if the subscribe button shows 'Subscribed' or similar text. "
            f"Reply with only YES or NO."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_b64,
                            }
                        },
                    ]
                }
            ]
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

        answer = result["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
        logger.info(f"Gemini response: {answer}")
        return "YES" in answer

    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    welcome_text = (
        f"👋 Hello {user.first_name}!\n\n"
        f"🎬 *Jugadu Baba Bot* mein aapka swagat hai!\n\n"
        f"📱 *iPhone Movie App pana chahte ho?*\n\n"
        f"Bas yeh karo:\n"
        f"1️⃣ YouTube pe *{YOUTUBE_CHANNEL}* ko Subscribe karo\n"
        f"2️⃣ Subscribe ka screenshot lo\n"
        f"3️⃣ Yahan screenshot bhejo\n"
        f"4️⃣ Free mein app link pao! 🎉\n\n"
        f"👇 Pehle subscribe karo:\n{YOUTUBE_CHANNEL_URL}"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Screenshot receive karo aur verify karo"""
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ Screenshot check ho raha hai... thoda wait karo!")

    # Photo download karo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    async with httpx.AsyncClient() as client:
        response = await client.get(file.file_path)
        image_bytes = response.content

    # Gemini se verify karo
    is_subscribed = await verify_with_gemini(image_bytes)

    if is_subscribed:
        # Subscribed hai - buttons dikhao
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, mujhe link chahiye!", callback_data=f"give_link_{user_id}"),
                InlineKeyboardButton("❌ No", callback_data="no_link"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "✅ *Subscribe Verified!*\n\n"
            "Kya aap iPhone Movie App ka link lena chahte ho?",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        # Subscribed nahi hai
        await update.message.reply_text(
            "❌ *Subscribe nahi dikh raha!*\n\n"
            f"Pehle *{YOUTUBE_CHANNEL}* ko subscribe karo:\n"
            f"{YOUTUBE_CHANNEL_URL}\n\n"
            "Subscribe karne ke baad dobara screenshot bhejo! 📸",
            parse_mode="Markdown",
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Button press handle karo"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("give_link_"):
        await query.edit_message_text(
            f"🎉 *Congratulations!*\n\n"
            f"Yeh raha tumhara *iPhone Movie App* link:\n\n"
            f"👇👇👇\n{REWARD_LINK}\n\n"
            f"Enjoy karo! 🍿\n\n"
            f"Aur Jugadu Baba ka channel share karna mat bhoolna! 🙏",
            parse_mode="Markdown",
        )
    elif query.data == "no_link":
        await query.edit_message_text(
            "Theek hai! Jab chahiye tab /start karke wapas aana. 😊"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Text message handle karo"""
    await update.message.reply_text(
        "📸 Bhai, screenshot bhejo na!\n\n"
        f"Pehle *{YOUTUBE_CHANNEL}* subscribe karo, phir screenshot yahan bhejo.",
        parse_mode="Markdown",
    )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable set nahi hai!")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable set nahi hai!")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot start ho gaya!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
  

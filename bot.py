import os
import logging
import base64
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
REWARD_LINK = "https://apps.apple.com/in/app/mehmandari/id6766165293"
YOUTUBE_LINK = "https://youtube.com/@jugadubaba-bmw?si=t5DR2kLvOixiZRcG"
YOUR_CHANNEL_NAME = "Jugadu Baba"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_with_gemini(image_bytes):
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}, {"text": "Look at this image. Is there a YouTube Subscribed button visible? Answer only in JSON format with valid true or false and reason"}]}]}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload)
    if response.status_code != 200:
        return {"valid": False, "reason": "Error"}
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    import json, re
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    if "true" in text.lower():
        return {"valid": True, "reason": "Subscribed found"}
    return {"valid": False, "reason": "Not subscribed"}

async def delete_after_delay(context, chat_id, message_id, delay=15):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        await context.bot.send_message(chat_id=chat_id, text="Link expire ho gaya!")
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Subscribe Karo", url=YOUTUBE_LINK)]]
    await update.message.reply_text(
        f"Namaskar! {YOUR_CHANNEL_NAME} ko subscribe karo aur screenshot bhejo, link milega!\n\nLink sirf 15 second tak rahega!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = msg.from_user
    processing = await msg.reply_text("Verify ho raha hai...")
    try:
        photo = msg.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(file.file_path)
        result = await verify_with_gemini(resp.content)
        await processing.delete()
        if result.get("valid"):
            link_msg = await msg.reply_text(
                f"Verified! Thank you {user.first_name}!\n\nYeh raha link:\n{REWARD_LINK}\n\n15 second mein delete ho jaayega!"
            )
            asyncio.create_task(delete_after_delay(context, msg.chat_id, link_msg.message_id, 15))
        else:
            keyboard = [[InlineKeyboardButton("Subscribe Karo", url=YOUTUBE_LINK)]]
            await msg.reply_text(
                f"Subscribe nahi dikh raha! Pehle {YOUR_CHANNEL_NAME} ko subscribe karo phir clear screenshot bhejo.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        await processing.delete()
        await msg.reply_text("Error aaya, dobara try karo!")
        logger.error(f"Error: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Subscribe Karo", url=YOUTUBE_LINK)]]
    await update.message.reply_text("Screenshot bhejo!", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot chal raha hai!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

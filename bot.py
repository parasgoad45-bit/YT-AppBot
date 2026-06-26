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

user_screenshots = {}

async def verify_with_gemini(image_bytes):
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                {"text": "Look at this image. Can you see the word Subscribed anywhere? Just answer YES or NO."}
            ]
        }]
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload)
    if response.status_code != 200:
        return None
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
    return "YES" in text

async def delete_after_delay(context, chat_id, message_id, delay=15):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🔴 Subscribe Karo", url=YOUTUBE_LINK)]]
    await update.message.reply_text(
        f"🎉 Namaskar!\n\n{YOUR_CHANNEL_NAME} ko YouTube par subscribe karo!\n\nPhir yeh steps follow karo:\n1. Subscribe ke baad screenshot lo\n2. Screenshot yahan bhejo\n3. Phir YES/NO button tap karo\n4. Link mil jaayega!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = msg.from_user
    chat_id = msg.chat_id
    
    processing = await msg.reply_text("📸 Screenshot received! Ab batao — kya subscribe kar diya?\n\nYes ya No tap karo 👇")
    
    try:
        photo = msg.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(file.file_path)
        
        user_screenshots[chat_id] = resp.content
        
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Subscribe Kar Diya!", callback_data=f"yes_{chat_id}"),
             InlineKeyboardButton("❌ No, Nahi Kiya", callback_data=f"no_{chat_id}")]
        ]
        
        await processing.edit_text(
            "Screenshot received! 📸\n\nAb batao — kya subscribe kar diya?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        await processing.delete()
        await msg.reply_text("⚠️ Error aaya!")
        logger.error(f"Error: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat_id
    
    await query.answer()
    
    if f"yes_{chat_id}" in query.data:
        if chat_id not in user_screenshots:
            await query.edit_text("❌ Pehle screenshot bhejo!")
            return
        
        image_bytes = user_screenshots[chat_id]
        is_subscribed = await verify_with_gemini(image_bytes)
        
        if is_subscribed:
            link_msg = await query.edit_text(
                f"✅ Verified! Thank you {user.first_name}!\n\nYeh raha tumhara link:\n\n🔗 {REWARD_LINK}\n\n⏳ 15 second mein delete ho jaayega!"
            )
            asyncio.create_task(delete_after_delay(context, chat_id, link_msg.message_id, 15))
            del user_screenshots[chat_id]
        else:
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = [[InlineKeyboardButton("🔴 Subscribe Karo", url=YOUTUBE_LINK)]]
            await query.edit_text(
                f"❌ Screenshot mein 'Subscribed' nahi dikh raha!\n\nYouTube par properly subscribe karo phir dobara try karo.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif f"no_{chat_id}" in query.data:
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = [[InlineKeyboardButton("🔴 Subscribe Karo", url=YOUTUBE_LINK)]]
        await query.edit_text(
            f"🙁 Pehle {YOUR_CHANNEL_NAME} ko subscribe karo, phir screenshot bhejo!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        if chat_id in user_screenshots:
            del user_screenshots[chat_id]

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("Bot chal raha hai!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

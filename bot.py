import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ============ CONFIG ============
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
REWARD_LINK = "https://apps.apple.com/in/app/mehmandari/id6766165293"
YOUTUBE_CHANNEL = "Jugadu Baba"
YOUTUBE_CHANNEL_URL = "https://youtube.com/@JugaduBaba-bmw"
LINK_DELETE_SECONDS = 30
# ================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data[user.id] = {"state": "waiting_subscribe", "name": user.first_name, "username": user.username or "N/A"}

    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        f"🎬 *Jugadu Baba Bot* mein aapka swagat hai!\n\n"
        f"📱 *iPhone Movie App chahiye?*\n\n"
        f"*Step 1️⃣:* YouTube pe *{YOUTUBE_CHANNEL}* ko Subscribe karo\n"
        f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
        f"Subscribe karne ke baad screenshot yahan bhejo! 📸",
        parse_mode="Markdown"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    state = user_data.get(uid, {}).get("state", "waiting_subscribe")

    if state == "waiting_subscribe":
        await update.message.reply_text("⏳ Screenshot admin ko bheja ja raha hai... wait karo!")

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
                f"🆔 `{uid}`\n\n"
                f"Kya usne Jugadu Baba ko subscribe kiya hai?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            "✅ Subscribe screenshot bhej diya!\n"
            "⏳ Admin verify karega, wait karo! 🙏"
        )

    elif state == "waiting_comment":
        await update.message.reply_text("⏳ Comment screenshot admin ko bheja ja raha hai... wait karo!")

        user_data[uid]["state"] = "pending_comment"

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_comment_{uid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_comment_{uid}"),
        ]]
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"💬 *Step 2 - Comment Verification*\n\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                f"🆔 `{uid}`\n\n"
                f"Kya usne 'Working' comment kiya hai?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            "✅ Comment screenshot bhej diya!\n"
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
    action = parts[0]   # approve / reject
    step = parts[1]     # sub / comment
    uid = int(parts[2])

    uinfo = user_data.get(uid, {})
    name = uinfo.get("name", "User")
    username = uinfo.get("username", "N/A")

    if action == "approve" and step == "sub":
        user_data[uid]["state"] = "waiting_comment"
        await query.edit_message_text(f"✅ Subscribe approved!\n👤 {name} (@{username})")

        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"✅ *Subscribe Verified!*\n\n"
                f"*Step 2️⃣:* Jugadu Baba ke kisi bhi video pe comment karo:\n\n"
                f"💬 Comment: *Working*\n\n"
                f"Comment karne ke baad screenshot yahan bhejo! 📸"
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
                f"{YOUTUBE_CHANNEL_URL}\n\n"
                f"Dobara subscribe screenshot bhejo! 📸"
            ),
            parse_mode="Markdown"
        )

    elif action == "approve" and step == "comment":
        user_data[uid]["state"] = "done"
        await query.edit_message_text(f"✅ Comment approved! Link bheja!\n👤 {name} (@{username})")

        sent = await context.bot.send_message(
            chat_id=uid,
            text=(
                f"🎉 *Congratulations {name}!*\n\n"
                f"Sab verify ho gaya! ✅\n\n"
                f"Yeh raha tumhara *iPhone Movie App* link:\n\n"
                f"👇👇👇\n{REWARD_LINK}\n\n"
                f"⚠️ *Yeh link {LINK_DELETE_SECONDS} second mein delete ho jayega!*\n"
                f"Jaldi open karo! ⏰"
            ),
            parse_mode="Markdown"
        )

        asyncio.create_task(
            delete_message_later(context, uid, sent.message_id, LINK_DELETE_SECONDS)
        )

    elif action == "reject" and step == "comment":
        user_data[uid]["state"] = "waiting_comment"
        await query.edit_message_text(f"❌ Comment rejected!\n👤 {name} (@{username})")
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"❌ *Comment verify nahi hua!*\n\n"
                f"Jugadu Baba ke kisi bhi video pe yeh comment karo:\n\n"
                f"💬 *Working*\n\n"
                f"Comment ka screenshot bhejo! 📸"
            ),
            parse_mode="Markdown"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_data.get(uid, {}).get("state", "")

    if state == "waiting_subscribe":
        await update.message.reply_text(
            f"📸 Subscribe screenshot bhejo!\n\n"
            f"Pehle *{YOUTUBE_CHANNEL}* subscribe karo:\n{YOUTUBE_CHANNEL_URL}",
            parse_mode="Markdown"
        )
    elif state == "waiting_comment":
        await update.message.reply_text(
            f"📸 Comment screenshot bhejo!\n\n"
            f"Jugadu Baba ke kisi bhi video pe *Working* comment karo!",
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
    

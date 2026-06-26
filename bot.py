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
UPI_ID = "parasgour1044@ybl"
UPI_NAME = "Paras Gour"
AMOUNT = "1"
QR_IMAGE_PATH = "Screenshot_20260626_123151.jpg"
LINK_DELETE_SECONDS = 30
# ================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# User states
# States: "waiting_subscribe", "waiting_payment", "done"
user_data = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data[user.id] = {"state": "waiting_subscribe", "name": user.first_name, "username": user.username or "N/A"}

    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        f"🎬 *Jugadu Baba Bot* mein aapka swagat hai!\n\n"
        f"📱 *iPhone Movie App chahiye?*\n\n"
        f"*Step 1:* YouTube pe *{YOUTUBE_CHANNEL}* ko Subscribe karo\n"
        f"👉 {YOUTUBE_CHANNEL_URL}\n\n"
        f"Subscribe karne ke baad screenshot yahan bhejo! 📸",
        parse_mode="Markdown"
    )


async def send_to_admin(context, user, step, caption):
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{step}_{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{step}_{user.id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=caption,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    state = user_data.get(uid, {}).get("state", "waiting_subscribe")

    if state == "waiting_subscribe":
        await update.message.reply_text("⏳ Screenshot admin ko bheja ja raha hai... wait karo!")

        user_data[uid] = {
            "state": "pending_subscribe",
            "name": user.first_name,
            "username": user.username or "N/A"
        }

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        await send_to_admin(
            context, user, "sub",
            f"🔔 *Subscribe Verification*\n\n"
            f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
            f"🆔 `{uid}`\n\n"
            f"Kya usne Jugadu Baba ko subscribe kiya hai?"
        )
        await update.message.reply_text(
            "✅ Screenshot bhej diya admin ko!\n"
            "⏳ Verify hone ke baad next step milega. Wait karo! 🙏"
        )

    elif state == "waiting_payment":
        await update.message.reply_text("⏳ Payment screenshot check ho raha hai... wait karo!")

        user_data[uid]["state"] = "pending_payment"

        await context.bot.forward_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        await send_to_admin(
            context, user, "pay",
            f"💰 *Payment Verification*\n\n"
            f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
            f"🆔 `{uid}`\n\n"
            f"Kya usne ₹1 pay kiya hai?"
        )
        await update.message.reply_text(
            "✅ Payment screenshot bhej diya admin ko!\n"
            "⏳ Verify hone ke baad link milega. Wait karo! 🙏"
        )

    else:
        await update.message.reply_text(
            "⚠️ Abhi koi screenshot ki zaroorat nahi.\n/start karke dobara shuru karo!"
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


async def handle_callback(context_or_update, context=None):
    # This is called as callback query handler
    update = context_or_update
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[0]   # approve / reject
    step = parts[1]     # sub / pay
    uid = int(parts[2])

    uinfo = user_data.get(uid, {})
    name = uinfo.get("name", "User")
    username = uinfo.get("username", "N/A")

    if action == "approve" and step == "sub":
        user_data[uid]["state"] = "waiting_payment"
        await query.edit_message_text(
            f"✅ Subscribe approved!\n👤 {name} (@{username})\nPayment step pe bheja."
        )
        # User ko payment step bhejo
        try:
            with open(QR_IMAGE_PATH, "rb") as qr:
                await context.bot.send_photo(
                    chat_id=uid,
                    photo=qr,
                    caption=(
                        f"✅ *Subscribe Verified!*\n\n"
                        f"*Step 2: Payment karo ₹1*\n\n"
                        f"📲 UPI ID: `{UPI_ID}`\n"
                        f"👤 Name: *{UPI_NAME}*\n"
                        f"💰 Amount: *₹{AMOUNT} only*\n\n"
                        f"Pay karne ke baad *payment screenshot* yahan bhejo! 📸"
                    ),
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"QR send error: {e}")
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    f"✅ *Subscribe Verified!*\n\n"
                    f"*Step 2: Payment karo ₹1*\n\n"
                    f"📲 UPI ID: `{UPI_ID}`\n"
                    f"👤 Name: *{UPI_NAME}*\n"
                    f"💰 Amount: *₹{AMOUNT} only*\n\n"
                    f"Pay karne ke baad *payment screenshot* yahan bhejo! 📸"
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

    elif action == "approve" and step == "pay":
        user_data[uid]["state"] = "done"
        await query.edit_message_text(f"✅ Payment approved!\n👤 {name} (@{username})\nLink bheja ja raha hai!")

        # User ko link bhejo
        sent = await context.bot.send_message(
            chat_id=uid,
            text=(
                f"🎉 *Congratulations {name}!*\n\n"
                f"Payment verify ho gaya! ✅\n\n"
                f"Yeh raha tumhara *iPhone Movie App* link:\n\n"
                f"👇👇👇\n{REWARD_LINK}\n\n"
                f"⚠️ *Yeh link {LINK_DELETE_SECONDS} second mein delete ho jayega!*\n"
                f"Jaldi open karo! ⏰"
            ),
            parse_mode="Markdown"
        )

        # 30 second baad delete karo
        asyncio.create_task(
            delete_message_later(context, uid, sent.message_id, LINK_DELETE_SECONDS)
        )

    elif action == "reject" and step == "pay":
        user_data[uid]["state"] = "waiting_payment"
        await query.edit_message_text(f"❌ Payment rejected!\n👤 {name} (@{username})")
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"❌ *Payment verify nahi hua!*\n\n"
                f"₹1 pay karo is UPI pe:\n"
                f"`{UPI_ID}`\n\n"
                f"Sahi payment screenshot bhejo! 📸"
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
    elif state == "waiting_payment":
        await update.message.reply_text(
            f"📸 Payment screenshot bhejo!\n\n"
            f"UPI ID: `{UPI_ID}`\n₹1 pay karo!",
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
                          

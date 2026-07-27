import os
import logging
import asyncio
import base64
import httpx
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://yt-appbot.onrender.com")
PING_INTERVAL_SECONDS = 600  # 10 minutes, safely under Render's 15-min sleep limit

def self_ping():
    import time
    import requests
    while True:
        time.sleep(PING_INTERVAL_SECONDS)
        try:
            r = requests.get(SELF_URL, timeout=15)
            logger.info(f"Self-ping ok: {r.status_code}")
        except Exception as e:
            logger.error(f"Self-ping failed: {e}")

def start_self_ping():
    t = Thread(target=self_ping, daemon=True)
    t.start()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
OCR_API_KEY = os.environ.get("OCR_API_KEY", "")

IPHONE_REWARD_LINK = "https://jugadutech2026.blogspot.com/?m=1"
ANDROID_REWARD_LINK = "https://jugadutech2026.blogspot.com/?m=1"
YOUTUBE_CHANNEL = "Jugadu Baba"
YOUTUBE_CHANNEL_URL = "https://youtube.com/@techjugad-9?si=pAzLXsooI2HpnZSL"
HOW_TO_DOWNLOAD_URL = "https://t.me/jugaduBaba0/156"
LINK_DELETE_SECONDS = 300

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# OCR keywords cover both Hindi and English so screenshot verification
# works no matter which language the user picked in the bot.
COMBINED_KEYWORDS = ["subscribed", "subscribers", "सदस्यता", "liked", "like", "पसंद", "share", "remix", "comment"]

def escape_md(text: str) -> str:
    """Escape Telegram legacy Markdown special characters so user-supplied
    text (like names) can't break message parsing."""
    if not text:
        return text
    for ch in ["_", "*", "`", "["]:
        text = text.replace(ch, "\\" + ch)
    return text

# ---------------------------------------------------------------------------
# All user-facing text, in Hindi and English. Pick with TEXTS[lang][key].
# ---------------------------------------------------------------------------
TEXTS = {
    "hi": {
        "choose_language": "🌐 *कृपया अपनी भाषा चुनें:*",
        "welcome": (
            "👋 *नमस्ते {name}! स्वागत है!*\n\n"
            "🔮 *{channel}* चैनल में आपका स्वागत है!\n"
            "रिवॉर्ड पाने के लिए पहले एक छोटा सा वेरिफिकेशन करना होगा। 😊\n\n"
            "📱 *सबसे पहले बताएं, आप कौन सा फ़ोन इस्तेमाल करते हैं?*"
        ),
        "device_iphone_btn": "🍏 आईफोन",
        "device_android_btn": "🤖 एंड्रॉइड",
        "youtube_btn": "📺 यूट्यूब चैनल पर जाएं",
        "device_selected": (
            "{emoji} *{device_name} चुना गया!*\n"
            "📊 *प्रगति:* `[░░░░░░░░░░] 0%` \n\n"
            "👉 *स्टेप 1:* नीचे दिए गए **यूट्यूब चैनल** बटन पर जाएं, वीडियो को *लाइक* करें और चैनल को *सब्सक्राइब* करें।\n\n"
            "📸 *स्टेप 2:* फिर एक स्क्रीनशॉट लें (जिसमें सब्सक्राइब + लाइक दोनों दिखें) और यहां भेज दें!"
        ),
        "need_start_first": "🚨 पहले /start कमांड भेजें, उसके बाद ही फोटो भेजें। 😊",
        "no_photo_needed": "🤷‍♂️ अभी फोटो भेजने की ज़रूरत नहीं है। पहले /start करें।",
        "processing": "🔍 *रुकिए ज़रा... आपकी स्क्रीनशॉट चेक की जा रही है!* ⏳",
        "verify_fail": (
            "❌ *वेरिफिकेशन फेल हो गया!*\n\n"
            "🔎 लगता है आपने स्क्रीनशॉट में *लाइक* या *सब्सक्राइब* साफ़ तौर पर नहीं दिखाया है।\n\n"
            "📸 यूट्यूब ऐप में जाकर वीडियो को लाइक करें, चैनल को सब्सक्राइब करें, और एक साफ़ स्क्रीनशॉट भेजें जिसमें दोनों दिखें! 🙏"
        ),
        "only_photo": "🛑 सिर्फ़ फोटो/स्क्रीनशॉट भेजें, कोई और फ़ाइल नहीं। 📸",
        "session_expired": "⏳ सेशन समाप्त हो गया है। कृपया दोबारा /start करें।",
        "waiting_screenshot_text": "☝️ पहले वीडियो को लाइक और चैनल को सब्सक्राइब करके, एक स्क्रीनशॉट भेजें। 📸",
        "start_prompt_text": "शुरू करने के लिए /start कमांड भेजें। 😊",
        "reward": (
            "🥳 *बधाई हो {name}!* 🎉\n"
            "────────────────────────\n"
            "आपका वेरिफिकेशन सफल हो गया है। ✅\n\n"
            "👇 *नीचे दिए बटन से अपना रिवॉर्ड लिंक लें:* 👇\n\n"
            "*(💡 अगर ऐप या मूवी डाउनलोड करना नहीं आता है, तो पहले 'How to Download' वीडियो देख लें)*\n\n"
            "⚠️ *ध्यान दें:* यह लिंक सिर्फ़ `5 मिनट` के लिए मान्य है! 💣\n"
            "जल्दी क्लिक करें, देरी मत करें! ⏰"
        ),
        "reward_btn": "🚀 {device_label} लें!",
        "download_btn": "🎬 डाउनलोड कैसे करें (ट्यूटोरियल)",
        "iphone_label": "आईफोन लिंक",
        "android_label": "एंड्रॉइड लिंक",
    },
    "en": {
        "choose_language": "🌐 *Kripya apni language chunein / Please choose your language:*",
        "welcome": (
            "👋 *Namaste {name}! Swagat hai!*\n\n"
            "🔮 *{channel}* channel mein aapka swagat hai!\n"
            "Reward pane ke liye pehle ek chota sa verification karna hoga. 😊\n\n"
            "📱 *Sabse pehle batayein, aap kaunsa phone use karte hain?*"
        ),
        "device_iphone_btn": "🍏 iPhone",
        "device_android_btn": "🤖 Android",
        "youtube_btn": "📺 YouTube Channel Pe Jaayein",
        "device_selected": (
            "{emoji} *{device_name} select kiya gaya!*\n"
            "📊 *Progress:* `[░░░░░░░░░░] 0%` \n\n"
            "👉 *STEP 1:* Neeche diye gaye **YouTube Channel** button pe jaayein, video ko *Like* karein aur channel *Subscribe* karein.\n\n"
            "📸 *STEP 2:* Fir ek screenshot lein (jisme Subscribe + Like dono dikhein) aur yahan bhej dein!"
        ),
        "need_start_first": "🚨 Pehle /start command bhejein, uske baad hi photo bhejein. 😊",
        "no_photo_needed": "🤷‍♂️ Abhi photo bhejne ki zaroorat nahi hai. Pehle /start karein.",
        "processing": "🔍 *Ruko zara... Aapki screenshot check ki jaa rahi hai!* ⏳",
        "verify_fail": (
            "❌ *Verification fail ho gaya!*\n\n"
            "🔎 Lagta hai aapne screenshot mein *Like* ya *Subscribe* clearly nahi dikhaya hai.\n\n"
            "📸 YouTube app mein jaake video ko Like karein, channel ko Subscribe karein, aur ek clear screenshot bhejein jisme dono dikhein! 🙏"
        ),
        "only_photo": "🛑 Sirf photo/screenshot bhejein, koi aur file nahi. 📸",
        "session_expired": "⏳ Session expire ho gaya hai. Please dobara /start karein.",
        "waiting_screenshot_text": "☝️ Pehle video ko Like aur channel ko Subscribe karke, ek screenshot bhejein. 📸",
        "start_prompt_text": "Shuru karne ke liye /start command bhejein. 😊",
        "reward": (
            "🥳 *Badhai Ho {name}!* 🎉\n"
            "────────────────────────\n"
            "Aapka verification successful ho gaya hai. ✅\n\n"
            "👇 *Neeche diye button se apna reward link lein:* 👇\n\n"
            "*(💡 Agar app ya movie download karna nahi aata hai, toh pehle 'How to Download' video dekh lein)*\n\n"
            "⚠️ *Dhyan dein:* Yeh link sirf `5 minute` ke liye valid hai! 💣\n"
            "Jaldi click karein, deri mat karein! ⏰"
        ),
        "reward_btn": "🚀 {device_label} Lein!",
        "download_btn": "🎬 How to Download (Tutorial)",
        "iphone_label": "iPhone Link",
        "android_label": "Android Link",
    },
}

def get_lang(uid: int) -> str:
    return user_data.get(uid, {}).get("lang", "hi")

async def verify_image_via_ocr(photo_bytes: bytes, keywords: list) -> tuple[bool, str]:
    try:
        b64 = base64.b64encode(photo_bytes).decode("utf-8")
        payload = {
            "apikey": OCR_API_KEY,
            "base64Image": f"data:image/jpeg;base64,{b64}",
            "language": "eng",
            "isOverlayRequired": False,
            "detectOrientation": True,
            "scale": True,
            "OCREngine": 2,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://api.ocr.space/parse/image", data=payload)
            resp.raise_for_status()
            data = resp.json()

        parsed = data.get("ParsedResults", [])
        if not parsed:
            return False, ""

        full_text = " ".join(r.get("ParsedText", "") for r in parsed).lower()
        is_verified = any(kw.lower() in full_text for kw in keywords)
        return is_verified, full_text

    except Exception as e:
        logger.error(f"OCR verification error: {e}")
        return False, ""

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
    lang = uinfo.get("lang", "hi")
    T = TEXTS[lang]
    device = uinfo.get("device", "iphone")
    name = escape_md(uinfo.get("name", "User"))
    reward_link = IPHONE_REWARD_LINK if device == "iphone" else ANDROID_REWARD_LINK
    device_label = T["iphone_label"] if device == "iphone" else T["android_label"]

    reward_text = T["reward"].format(name=name)

    keyboard = [
        [InlineKeyboardButton(T["reward_btn"].format(device_label=device_label), url=reward_link)],
        [InlineKeyboardButton(T["download_btn"], url=HOW_TO_DOWNLOAD_URL)]
    ]

    sent = await context.bot.send_message(
        chat_id=uid,
        text=reward_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    asyncio.create_task(delete_message_later(context, uid, sent.message_id, LINK_DELETE_SECONDS))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    serial = get_serial(uid)
    safe_name = escape_md(user.first_name)
    safe_username = escape_md(user.username) if user.username else "N/A"

    user_data[uid] = {
        "state": "choosing_language",
        "name": user.first_name,
        "username": user.username or "N/A",
        "serial": serial,
        "lang": "hi",
    }

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🔔 *Naya User Aaya Hai — #{serial}*\n"
                f"────────────────────────\n"
                f"👤 *Naam:* {safe_name}\n"
                f"🆔 *ID:* `{uid}`\n"
                f"🔗 *Username:* @{safe_username}"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Admin notification failed: {e}")

    keyboard = [[
        InlineKeyboardButton("🇮🇳 हिंदी", callback_data=f"lang_hi_{uid}"),
        InlineKeyboardButton("🇬🇧 English", callback_data=f"lang_en_{uid}"),
    ]]

    await update.message.reply_text(
        "🌐 *Kripya apni language chunein / Please choose your language:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    lang = get_lang(uid)
    T = TEXTS[lang]

    if uid not in user_data:
        await update.message.reply_text(T["need_start_first"])
        return

    uinfo = user_data[uid]
    state = uinfo.get("state", "")
    serial = uinfo.get("serial", get_serial(uid))
    device = uinfo.get("device", "unknown")

    if state != "waiting_screenshot":
        await update.message.reply_text(T["no_photo_needed"])
        return

    processing_msg = await update.message.reply_text(T["processing"], parse_mode="Markdown")

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    # Keywords include both Hindi and English terms, so verification works
    # correctly regardless of which language the user selected.
    is_verified, _ = await verify_image_via_ocr(bytes(photo_bytes), COMBINED_KEYWORDS)

    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=processing_msg.message_id)
    except Exception:
        pass

    if not is_verified:
        await update.message.reply_text(T["verify_fail"], parse_mode="Markdown")
        return

    user_data[uid]["state"] = "done"

    try:
        await context.bot.forward_message(chat_id=ADMIN_CHAT_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✅ *Verification Complete!* \n🔢 User: *#{serial}* | 📱 Phone: {device.upper()}\nReward link bhej diya gaya hai!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Admin forward failed: {e}")

    await send_reward_link(context, uid, user_data[uid])

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc and doc.mime_type and "image" in doc.mime_type:
        await handle_photo(update, context)
    else:
        uid = update.effective_user.id
        lang = get_lang(uid)
        await update.message.reply_text(TEXTS[lang]["only_photo"])

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    uid = update.effective_user.id
    if uid not in user_data:
        lang = "hi"
        await query.message.reply_text(TEXTS[lang]["session_expired"])
        return

    # --- Language selection ---
    if data.startswith("lang_hi_"):
        user_data[uid]["lang"] = "hi"
        user_data[uid]["state"] = "choosing_device"
        T = TEXTS["hi"]
        safe_name = escape_md(user_data[uid].get("name", "User"))
        keyboard = [[
            InlineKeyboardButton(T["device_iphone_btn"], callback_data=f"device_iphone_{uid}"),
            InlineKeyboardButton(T["device_android_btn"], callback_data=f"device_android_{uid}"),
        ]]
        await query.edit_message_text(
            T["welcome"].format(name=safe_name, channel=YOUTUBE_CHANNEL),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if data.startswith("lang_en_"):
        user_data[uid]["lang"] = "en"
        user_data[uid]["state"] = "choosing_device"
        T = TEXTS["en"]
        safe_name = escape_md(user_data[uid].get("name", "User"))
        keyboard = [[
            InlineKeyboardButton(T["device_iphone_btn"], callback_data=f"device_iphone_{uid}"),
            InlineKeyboardButton(T["device_android_btn"], callback_data=f"device_android_{uid}"),
        ]]
        await query.edit_message_text(
            T["welcome"].format(name=safe_name, channel=YOUTUBE_CHANNEL),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # --- Device selection ---
    lang = get_lang(uid)
    T = TEXTS[lang]
    keyboard = [
        [InlineKeyboardButton(T["youtube_btn"], url=YOUTUBE_CHANNEL_URL)]
    ]

    if data.startswith("device_iphone_"):
        user_data[uid]["device"] = "iphone"
        user_data[uid]["state"] = "waiting_screenshot"
        await query.edit_message_text(
            T["device_selected"].format(emoji="🍏", device_name="iPhone"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("device_android_"):
        user_data[uid]["device"] = "android"
        user_data[uid]["state"] = "waiting_screenshot"
        await query.edit_message_text(
            T["device_selected"].format(emoji="🤖", device_name="Android"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(uid)
    T = TEXTS[lang]
    state = user_data.get(uid, {}).get("state", "")

    if state == "waiting_screenshot":
        await update.message.reply_text(T["waiting_screenshot_text"])
    else:
        await update.message.reply_text(T["start_prompt_text"])

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN set nahi hai!")
    if not ADMIN_CHAT_ID or ADMIN_CHAT_ID == 0:
        raise ValueError("ADMIN_CHAT_ID set nahi hai!")

    keep_alive()
    start_self_ping()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Jugadu Baba Bot is online and laughing...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

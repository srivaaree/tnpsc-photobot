import os
import logging
from flask import Flask, request
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from PIL import Image, ImageFilter
from io import BytesIO
import asyncio
import base64

BOT_TOKEN = os.getenv("BOT_TOKEN")
RAZORPAY_LINK = os.getenv("RAZORPAY_LINK")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return "✅ TNPSC PhotoBot is LIVE (PTB v20)"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="👋 Welcome! Send your TNPSC photo now.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()

    # Blur the image
    image = Image.open(BytesIO(image_bytes))
    blurred = image.filter(ImageFilter.GaussianBlur(radius=12))

    # Save blurred image to buffer
    blurred_buffer = BytesIO()
    blurred.save(blurred_buffer, format="JPEG")
    blurred_buffer.seek(0)

    # Send blurred image
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=blurred_buffer, caption=f"🔒 Blurred Preview\n💳 Pay ₹10 to unlock: {RAZORPAY_LINK}")

    # Optionally store original image for manual delivery after payment
    # You can expand this with a DB + Razorpay webhook later

def build_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    return app_bot

# Run Telegram bot in background
async def run_bot():
    app_bot = build_bot()
    await app_bot.initialize()
    await app_bot.start()
    await app_bot.updater.start_polling()
    print("🤖 Telegram bot running")

@app.before_first_request
def activate_bot():
    asyncio.get_event_loop().create_task(run_bot())

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
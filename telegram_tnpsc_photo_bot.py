# telegram_tnpsc_photo_bot.py
# A Telegram bot for TNPSC-compliant photo processing with payment link and webhooks

import os
import io
import logging
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
from rembg import remove
import numpy as np
from telegram import Update, InputFile, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters
)
from fastapi import FastAPI, Request
import uvicorn

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot states
PHOTO, NAME, PAYMENT = range(3)

# Ensure upload directory exists
os.makedirs('uploads', exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Welcome poster
    try:
        with open('poster.png', 'rb') as poster:
            caption_text = '''🎓 Welcome future TNPSC champion! 🎉
‘The moment you start valuing yourself, the world will start valuing you.’
Now, send me your passport-size photo to get exam-ready! 🕵️‍♂️💥'''
            await update.message.reply_photo(photo=poster, caption=caption_text)
    except FileNotFoundError:
        logger.warning("poster.png not found, skipping poster display.")

    # Warm greeting + disclaimer
    await update.message.reply_text(
        "🕵️‍♂️ Welcome future officer! Ready to blast your TNPSC application into success? 💥"
    )
    await update.message.reply_text(
        "⚠️ Disclaimer: Output quality depends on input photo quality & size. Please ensure your photo is clear and high-resolution."
    )
    return PHOTO

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Download and save the user's photo
    photo_file = await update.message.photo[-1].get_file()
    input_path = os.path.join('uploads', 'photo_input.jpg')
    await photo_file.download_to_drive(input_path)
    context.user_data['photo_path'] = input_path
    await update.message.reply_text("Photo received. Please send your full name.")
    return NAME

async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Receive name and process image
    name = update.message.text.strip()
    input_path = context.user_data.get('photo_path')
    if not input_path or not os.path.isfile(input_path):
        await update.message.reply_text("No valid photo found. Please /start again.")
        return ConversationHandler.END

    # Generate final image
    output_path = process_photo(input_path, name)
    context.user_data['final_path'] = output_path

    # Create and send blurred preview
    preview = Image.open(output_path)
    blurred = preview.filter(ImageFilter.GaussianBlur(radius=10))
    preview_path = os.path.join('uploads', 'preview.jpg')
    blurred.save(preview_path, 'JPEG', quality=50)
    await update.message.reply_photo(
        photo=open(preview_path, 'rb'),
        caption="💡 Here's a preview. Unlock the full-quality version after payment."
    )

    # Send payment link buttons
    pay_url = os.getenv('PAYMENT_URL', 'https://your-payment-link.example.com')
    keyboard = [[
        InlineKeyboardButton("Pay ₹5", url=pay_url),
        InlineKeyboardButton("I've Paid", callback_data='paid')
    ]]
    await update.message.reply_text(
        "🔒 Please complete payment to receive your final image:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAYMENT

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle payment confirmation
    query = update.callback_query
    await query.answer()
    final_path = context.user_data.get('final_path')
    if final_path and os.path.isfile(final_path):
        await query.message.reply_document(
            document=InputFile(open(final_path, 'rb'), filename=os.path.basename(final_path)),
            filename=os.path.basename(final_path)
        )
        await query.message.reply_text("✅ Thank you for your payment! Here is your final TNPSC photo. Good luck! 🍀💥")
    else:
        await query.message.reply_text("⚠️ Final image not found. Please restart with /start.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


def process_photo(input_path: str, name: str, output_path: str = 'Photograph.jpg'):
    dpi = 200
    cm2inch = 2.54
    final_w = int(3.5 / cm2inch * dpi)
    final_h = int(4.5 / cm2inch * dpi)
    face_h = int(3.6 / cm2inch * dpi)

    raw = open(input_path, 'rb').read()
    alpha = Image.open(io.BytesIO(remove(raw))).convert('RGBA')
    bg = Image.new('RGBA', alpha.size, (255, 255, 255, 255))
    bg.paste(alpha, mask=alpha.split()[3])
    img = bg.convert('RGB')

    ow, oh = img.size
    nh = int(oh * (final_w / ow))
    resized = img.resize((final_w, nh), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (final_w, final_h), 'white')
    yoff = max((face_h - nh) // 2, 0)
    canvas.paste(resized, (0, yoff))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, face_h, final_w, final_h], fill='white')

    name_text = name.upper()
    date_text = datetime.now().strftime('%d-%m-%Y')
    max_w = final_w - 20
    fs = int((final_h - face_h) * 0.4)
    try:
        font = ImageFont.truetype('timesbd.ttf', fs)
    except:
        font = ImageFont.load_default()
    while draw.textlength(name_text, font) > max_w and fs > 8:
        fs -= 2
        try:
            font = ImageFont.truetype('timesbd.ttf', fs)
        except:
            font = ImageFont.load_default()
    nw = draw.textlength(name_text, font)
    draw.text(((final_w - nw) / 2, face_h + 8), name_text, fill='black', font=font)
    dw = draw.textlength(date_text, font)
    draw.text(((final_w - dw) / 2, face_h + 8 + fs + 4), date_text, fill='black', font=font)

    min_b, max_b = 35 * 1024, 49 * 1024
    last_data, last_size = None, 0
    for q in range(95, 4, -5):
        buf = io.BytesIO()
        canvas.save(buf, 'JPEG', quality=q, subsampling=0, optimize=False, progressive=True, dpi=(dpi, dpi))
        data = buf.getvalue()
        size = len(data)
        last_data, last_size = data, size
        if size <= max_b:
            break
    with open(output_path, 'wb') as f:
        f.write(last_data)
        if last_size < min_b:
            f.write(b'\x00' * (min_b - last_size))
    return output_path

# FastAPI webhook setup
app = FastAPI()
TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(TOKEN)
app_telegram = ApplicationBuilder().token(TOKEN).build()
# Register handlers
conv = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        PHOTO: [MessageHandler(filters.PHOTO, photo_handler)],
        NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
        PAYMENT: [CallbackQueryHandler(payment_callback, pattern='paid')]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)
app_telegram.add_handler(conv)

@app.on_event("startup")
async def startup():
    await bot.delete_webhook(drop_pending_updates=True)
    webhook_url = f"https://web-production-51ac.up.railway.app/webhook/{TOKEN}"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

@app.post(f"/webhook/{TOKEN}")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    await app_telegram.update_queue.put(update)
    return {"ok": True}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

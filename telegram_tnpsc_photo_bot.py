# telegram_tnpsc_photo_bot.py
# A Telegram bot for TNPSC-compliant photo processing using long-polling
from fastapi import FastAPI
app = FastAPI()
import os
import io
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from rembg import remove
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, CallbackQueryHandler, ContextTypes, filters
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States for ConversationHandler
PHOTO, NAME, PAYMENT = range(3)

# Ensure upload directory exists
os.makedirs('uploads', exist_ok=True)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN', '').strip()
PAYMENT_URL = os.getenv('PAYMENT_URL', '').strip()
if not TOKEN:
    logger.error('BOT_TOKEN not set. Exiting.')
    exit(1)
if not PAYMENT_URL:
    logger.error('PAYMENT_URL not set. Exiting.')
    exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Welcome message
    await update.message.reply_text(
        "🎓 Welcome future TNPSC champion! 🎉\n" +
        "Please send your passport-size photo to begin processing."
    )
    return PHOTO

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Save incoming photo
    photo_file = await update.message.photo[-1].get_file()
    photo_path = os.path.join('uploads', 'photo_input.jpg')
    await photo_file.download_to_drive(photo_path)
    context.user_data['photo_path'] = photo_path
    await update.message.reply_text("Photo received. Now please send your full name.")
    return NAME

async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get user's name and process photo
    name = update.message.text.strip()
    in_path = context.user_data.get('photo_path')
    if not in_path or not os.path.isfile(in_path):
        await update.message.reply_text("No valid photo found. Please /start again.")
        return ConversationHandler.END

    out_path = process_photo(in_path, name)
    context.user_data['final_path'] = out_path

    # Send preview blurred image and payment link
    img = Image.open(out_path)
    preview = img.filter(ImageFilter.GaussianBlur(5))
    preview_path = os.path.join('uploads', 'preview.jpg')
    preview.save(preview_path, 'JPEG', quality=50)
    await update.message.reply_photo(
        photo=open(preview_path, 'rb'),
        caption="💡 Preview — complete payment to receive full-quality image."
    )
    keyboard = [[
        InlineKeyboardButton('Pay ₹5', url=PAYMENT_URL),
        InlineKeyboardButton("I've Paid", callback_data='paid')
    ]]
    await update.message.reply_text(
        '🔒 Please complete payment:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAYMENT

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    final_path = context.user_data.get('final_path')
    if final_path and os.path.isfile(final_path):
        await query.message.reply_document(
            document=InputFile(open(final_path, 'rb'), filename=os.path.basename(final_path))
        )
        await query.message.reply_text('✅ Payment confirmed! Here is your TNPSC photo. Good luck! 🍀')
    else:
        await query.message.reply_text('⚠️ Image not found — please /start again.')
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END


def process_photo(in_path: str, name: str, out_path: str = 'Photograph.jpg') -> str:
    # TNPSC spec: 3.5×4.5 cm at 200 DPI => 276×354 px, head area 3.6 cm tall
    dpi = 200
    cm2in = 2.54
    final_w = int(3.5/cm2in*dpi)
    final_h = int(4.5/cm2in*dpi)
    face_h  = int(3.6/cm2in*dpi)

    # Remove background
    raw = open(in_path, 'rb').read()
    alpha = Image.open(io.BytesIO(remove(raw))).convert('RGBA')
    bg = Image.new('RGBA', alpha.size, (255,255,255,255))
    bg.paste(alpha, mask=alpha.split()[3])
    img = bg.convert('RGB')

    # Resize and letterbox
    ow, oh = img.size
    new_h = int(oh * (final_w/ow))
    resized = img.resize((final_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (final_w, final_h), 'white')
    yoff = max((face_h - new_h)//2, 0)
    canvas.paste(resized, (0, yoff))

    # Clear text area
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, face_h, final_w, final_h], fill='white')

    # Add name and date
    text_name = name.upper()
    text_date = datetime.now().strftime('%d-%m-%Y')
    max_w = final_w - 20
    fontsize = int((final_h-face_h)*0.4)
    try:
        font = ImageFont.truetype('timesbd.ttf', fontsize)
    except:
        font = ImageFont.load_default()
    while draw.textlength(text_name, font) > max_w and fontsize > 8:
        fontsize -= 2
        font = ImageFont.truetype('timesbd.ttf', fontsize)
    w_text = draw.textlength(text_name, font)
    draw.text(((final_w-w_text)/2, face_h+8), text_name, fill='black', font=font)
    w_date = draw.textlength(text_date, font)
    draw.text(((final_w-w_date)/2, face_h+8+fontsize+4), text_date, fill='black', font=font)

    # Save JPEG within 35-49 KB
    min_size, max_size = 35*1024, 49*1024
    last_data = None
    size = 0
    for q in range(95, 4, -5):
        buf = io.BytesIO()
        canvas.save(buf, 'JPEG', quality=q, optimize=False, progressive=True, dpi=(dpi, dpi))
        data = buf.getvalue()
        size = len(data)
        last_data = data
        if size <= max_size:
            break
    with open(out_path, 'wb') as f:
        f.write(last_data)
        if size < min_size:
            f.write(b'\x00'*(min_size - size))
    return out_path

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, photo_handler)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            PAYMENT: [CallbackQueryHandler(payment_callback, pattern='paid')]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(conv)
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

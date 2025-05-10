# telegram_tnpsc_photo_bot.py
# A Telegram bot for TNPSC-compliant photo processing with payment link and FastAPI webhooks

import os
import io
import logging
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from rembg import remove
from telegram import Update, InputFile, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, CallbackQueryHandler, filters
)
from fastapi import FastAPI, Request
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States for ConversationHandler
PHOTO, NAME, PAYMENT = range(3)

# Directories
os.makedirs('uploads', exist_ok=True)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
PAYMENT_URL = os.getenv('PAYMENT_URL', 'https://your-payment-link.example.com')
DOMAIN = os.getenv('RAILWAY_DOMAIN')  # e.g. 'web-production-51ac.up.railway.app'
if not TOKEN or not DOMAIN:
    logger.error('Environment vars BOT_TOKEN and RAILWAY_DOMAIN must be set.')
    exit(1)

# Initialize bot and application
bot = Bot(TOKEN)
app_telegram = ApplicationBuilder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Welcome poster
    try:
        with open('poster.png', 'rb') as poster:
            caption = (
                "🎓 Welcome future TNPSC champion! 🎉\n"
                "‘The moment you start valuing yourself, the world will start valuing you.’\n"
                "Now, send me your passport-size photo to get exam-ready! 🕵️‍♂️💥"
            )
            await update.message.reply_photo(photo=poster, caption=caption)
    except FileNotFoundError:
        logger.warning('poster.png not found, skipping poster display.')

    await update.message.reply_text(
        "🕵️‍♂️ Welcome future officer! Ready to blast your TNPSC application into success? 💥"
    )
    await update.message.reply_text(
        "⚠️ Disclaimer: Output quality depends on input photo quality & size. Ensure your photo is clear and high-resolution."
    )
    return PHOTO

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo  = await update.message.photo[-1].get_file()
    path   = os.path.join('uploads', 'photo_input.jpg')
    await photo.download_to_drive(path)
    context.user_data['photo_path'] = path
    await update.message.reply_text('Photo received. Please send your full name.')
    return NAME

async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    path = context.user_data.get('photo_path')
    if not path or not os.path.isfile(path):
        await update.message.reply_text('No valid photo found. Please /start again.')
        return ConversationHandler.END

    output = process_photo(path, name)
    context.user_data['final_path'] = output

    # Blurred preview
    img    = Image.open(output)
    blur   = img.filter(ImageFilter.GaussianBlur(8))
    preview= os.path.join('uploads', 'preview.jpg')
    blur.save(preview, 'JPEG', quality=50)
    await update.message.reply_photo(photo=open(preview,'rb'), caption='💡 Preview—complete payment to get full-quality image.')

    # Payment buttons
    keyboard = [[
        InlineKeyboardButton('Pay ₹5', url=PAYMENT_URL),
        InlineKeyboardButton("I've Paid", callback_data='paid')
    ]]
    await update.message.reply_text('🔒 Please complete payment:', reply_markup=InlineKeyboardMarkup(keyboard))
    return PAYMENT

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    final = context.user_data.get('final_path')
    if final and os.path.isfile(final):
        await query.message.reply_document(document=InputFile(open(final,'rb'), filename=os.path.basename(final)))
        await query.message.reply_text('✅ Payment confirmed! Here is your TNPSC photo. Good luck! 🍀💥')
    else:
        await query.message.reply_text('⚠️ Image not found—please /start again.')
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END


def process_photo(in_path: str, name: str, out_path: str = 'Photograph.jpg') -> str:
    dpi   = 200
    cm2in = 2.54
    w     = int(3.5/cm2in*dpi)
    h     = int(4.5/cm2in*dpi)
    face_h= int(3.6/cm2in*dpi)

    data  = open(in_path,'rb').read()
    alpha = Image.open(io.BytesIO(remove(data))).convert('RGBA')
    bg    = Image.new('RGBA', alpha.size, (255,255,255,255))
    bg.paste(alpha,mask=alpha.split()[3])
    img   = bg.convert('RGB')

    ow,oh = img.size
    nh    = int(oh*(w/ow))
    resized = img.resize((w,nh), Image.Resampling.LANCZOS)
    canvas  = Image.new('RGB',(w,h),'white')
    yoff    = max((face_h-nh)//2,0)
    canvas.paste(resized,(0,yoff))

    draw   = ImageDraw.Draw(canvas)
    draw.rectangle([0,face_h,w,h],fill='white')

    txt_name = name.upper()
    txt_date = datetime.now().strftime('%d-%m-%Y')
    max_w    = w-20
    fs       = int((h-face_h)*0.4)
    try:
        font = ImageFont.truetype('timesbd.ttf',fs)
    except:
        font = ImageFont.load_default()
    while draw.textlength(txt_name,font)>max_w and fs>8:
        fs-=2
        font=ImageFont.load_default()
    nw = draw.textlength(txt_name,font)
    draw.text(((w-nw)/2,face_h+8),txt_name,'black',font=font)
    dw = draw.textlength(txt_date,font)
    draw.text(((w-dw)/2,face_h+8+fs+4),txt_date,'black',font=font)

    min_b,max_b=35*1024,49*1024
    last_data,size=None,0
    for q in range(95,4,-5):
        buf=io.BytesIO()
        canvas.save(buf,'JPEG',quality=q,subsampling=0,progressive=True,dpi=(dpi,dpi))
        data=buf.getvalue();size=len(data);last_data=data
        if size<=max_b: break
    with open(out_path,'wb') as f:
        f.write(last_data)
        if size<min_b: f.write(b'\x00'*(min_b-size))
    return out_path

# Register handlers
conv=ConversationHandler(
    entry_points=[CommandHandler('start',start)],
    states={PHOTO:[MessageHandler(filters.PHOTO,photo_handler)],
            NAME:[MessageHandler(filters.TEXT&~filters.COMMAND,name_handler)],
            PAYMENT:[CallbackQueryHandler(payment_callback,pattern='paid')]},
    fallbacks=[CommandHandler('cancel',cancel)]
)
app_telegram.add_handler(conv)

# FastAPI app
app=FastAPI()

@app.on_event('startup')
async def on_startup():
    # Log domain and webhook URL for debugging
    logger.info(f"RAILWAY_DOMAIN = '{DOMAIN}'")
    webhook_url = f'https://{DOMAIN}/webhook'
    logger.info(f"Setting webhook to {webhook_url}")

    # Delete old webhook
    await bot.delete_webhook(drop_pending_updates=True)
    # Attempt to set new webhook
    try:
        result = await bot.set_webhook(webhook_url)
        logger.info(f"set_webhook result: {result}")
    except Exception as e:
        logger.error(f"Failed to set webhook to {webhook_url}: {e}")
        raise
    await bot.set_webhook(webhook_url)
    logger.info(f'Webhook set to {webhook_url}')

@app.on_event('shutdown')
async def on_shutdown():
    logger.info('Shutting down Telegram application...')
    await app_telegram.stop(); await app_telegram.shutdown()

@app.post('/webhook')
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)
    await app_telegram.update_queue.put(update)
    return {'ok':True}

if __name__=='__main__':
    uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('PORT',8000)))

from flask import Flask, request
import os
import telegram

# Initialize Flask app and Telegram bot
app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RAZORPAY_LINK = os.environ.get("RAZORPAY_LINK")
bot = telegram.Bot(token=BOT_TOKEN)

@app.route('/')
def home():
    return "TNPSC PhotoBot is Running!"

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)

    if update.message:
        chat_id = update.message.chat.id

        if update.message.photo:
            bot.send_message(
                chat_id=chat_id,
                text=f"📸 Photo received!\nPay ₹10 here: {RAZORPAY_LINK}\n\nYou'll get the final TNPSC photo after payment."
            )
        else:
            bot.send_message(
                chat_id=chat_id,
                text="👋 Please send your TNPSC passport-size photo."
            )

    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

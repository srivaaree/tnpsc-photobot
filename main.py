from flask import Flask, request
import os
import telegram

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telegram.Bot(token=BOT_TOKEN)

@app.route('/')
def home():
    return "TNPSC PhotoBot is Running!"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def receive_update():
    update = telegram.Update.de_json(request.get_json(force=True), bot)

    if update.message and update.message.photo:
        chat_id = update.message.chat.id
        bot.send_message(chat_id=chat_id, text="📸 Received your photo!\nPay ₹10 here to unlock final TNPSC photo:\n" + os.getenv("RAZORPAY_LINK"))

    elif update.message and update.message.text:
        bot.send_message(chat_id=update.message.chat.id, text="👋 Hello! Please upload your TNPSC photo.")

    return 'ok'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

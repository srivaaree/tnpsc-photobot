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
TOKEN = os.getenv('BOT_TOKEN', '').strip()
PAYMENT_URL = os.getenv('PAYMENT_URL', 'https://your-payment-link.example.com')
DOMAIN = os.getenv('RAILWAY_DOMAIN', '').strip()  # e.g. 'web-production-51ac.up.railway.app'

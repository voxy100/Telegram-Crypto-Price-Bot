# -*- coding: utf-8 -*-
import os
import requests
from telegram.ext import Updater, CommandHandler
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def get_price(symbol):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
    res = requests.get(url)
    data = res.json()
    if symbol.lower() in data:
        return data[symbol.lower()]['usd']
    return None

def price(update, context):
    if context.args:
        symbol = context.args[0].lower()
        price = get_price(symbol)
        if price:
            update.message.reply_text(f"💰 {symbol.upper()} price: ${price}")
        else:
            update.message.reply_text("❌ Symbol not found. Try again.")
    else:
        update.message.reply_text("ℹ️ Usage: /price BTC")

def start(update, context):
    update.message.reply_text("👋 Hello! Send /price <symbol> to get crypto price.")

updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("price", price))

updater.start_polling()
print("✅ Crypto Price Bot is running!")
updater.idle()

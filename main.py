# -*- coding: utf-8 -*-
import os
import logging
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime
from io import BytesIO
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# === Load env ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINGECKO_API = "https://api.coingecko.com/api/v3"

# === Logging ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

symbol_map = {}

async def fetch_symbol_map():
    global symbol_map
    logger.info("📡 Fetching symbol-to-ID mapping...")
    try:
        coins = requests.get(f"{COINGECKO_API}/coins/list").json()
        symbol_map = {coin["symbol"]: coin["id"] for coin in coins}
    except Exception as e:
        logger.error(f"Error fetching coin list: {e}")

def get_token_id(symbol):
    return symbol_map.get(symbol.lower())

async def fetch_price(token_id):
    try:
        url = f"{COINGECKO_API}/simple/price?ids={token_id}&vs_currencies=usd"
        data = requests.get(url).json()
        return data[token_id]["usd"]
    except Exception as e:
        logger.error(f"Error fetching price: {e}")
        return None

async def fetch_chart_data(token_id):
    try:
        url = f"{COINGECKO_API}/coins/{token_id}/market_chart"
        data = requests.get(url, params={"vs_currency": "usd", "days": 1}).json()
        return data["prices"]
    except Exception as e:
        logger.error(f"Chart fetch error: {e}")
        return None

def generate_gradient_chart(prices, token):
    timestamps = [datetime.fromtimestamp(p[0]/1000) for p in prices]
    values = [p[1] for p in prices]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(timestamps, values, color='#4bc0c0', linewidth=2)

    # Gradient fill
    ax.fill_between(timestamps, values, color='#4bc0c0', alpha=0.3)

    ax.set_title(f"{token.upper()} 24H Chart", fontsize=16)
    ax.set_xlabel("Time")
    ax.set_ylabel("Price (USD)")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
    fig.autofmt_xdate()

    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

# === Bot Commands ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """🤖 *RIVX Crypto Bot*
Real-time crypto prices and charts.

Commands:
/price btc — Get current price
/chart eth — Show 24H chart""",
        parse_mode='Markdown'
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /price [symbol]")
        return

    symbol = context.args[0].lower()
    token_id = get_token_id(symbol)
    if not token_id:
        await update.message.reply_text("❌ Unknown token symbol.")
        return

    price = await fetch_price(token_id)
    if price:
        await update.message.reply_text(f"💰 {symbol.upper()} = ${price:,.2f}")
    else:
        await update.message.reply_text("❌ Failed to fetch price.")

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /chart [symbol]")
        return

    symbol = context.args[0].lower()
    token_id = get_token_id(symbol)
    if not token_id:
        await update.message.reply_text("❌ Unknown token symbol.")
        return

    prices = await fetch_chart_data(token_id)
    if not prices:
        await update.message.reply_text("❌ Could not fetch chart data.")
        return

    try:
        chart_image = generate_gradient_chart(prices, symbol)
        await update.message.reply_photo(
            photo=InputFile(chart_image),
            caption=f"📊 {symbol.upper()} 24H Chart"
        )
    except Exception as e:
        logger.error(f"Chart error: {e}")
        await update.message.reply_text("❌ Error generating chart.")

# === Run Bot ===
async def main():
    await fetch_symbol_map()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("chart", chart))
    logger.info("✅ Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import sys
    import asyncio

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except RuntimeError as e:
        print(f"❌ Bot exited with error: {e}")

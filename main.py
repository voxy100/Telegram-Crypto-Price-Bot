# main.py — RIVX Crypto Bot (Final Version)
import os
import logging
import requests
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio

# === Load environment ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINGECKO_API = "https://api.coingecko.com/api/v3"

# === Logging ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Cache symbol-to-ID mapping ===
symbol_to_id = {}

def fetch_symbol_mapping():
    logger.info("📡 Fetching symbol-to-ID mapping...")
    try:
        res = requests.get(f"{COINGECKO_API}/coins/list")
        res.raise_for_status()
        coins = res.json()
        return {coin['symbol'].lower(): coin['id'] for coin in coins}
    except Exception as e:
        logger.error(f"Failed to fetch symbols: {e}")
        return {}

symbol_to_id = fetch_symbol_mapping()

# === CoinGecko API fetcher ===
async def fetch_coingecko_data(endpoint: str, params: dict = None):
    try:
        response = requests.get(f"{COINGECKO_API}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"API Error: {e}")
        return None

# === Chart generation ===
def generate_chart(prices: list, token: str):
    timestamps = [datetime.fromtimestamp(p[0]/1000) for p in prices]
    values = [p[1] for p in prices]

    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1e1e2f')
    ax.plot(timestamps, values, linewidth=2, color='#66bb6a')
    ax.fill_between(timestamps, values, color='#66bb6a', alpha=0.3)
    ax.set_title(f"{token.upper()} Price Chart (24h)", fontsize=16, color='white')
    ax.set_xlabel("Time", fontsize=12, color='white')
    ax.set_ylabel("Price (USD)", fontsize=12, color='white')
    ax.grid(True, alpha=0.2)
    ax.set_facecolor('#2a2a3b')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    fig.autofmt_xdate()
    ax.tick_params(colors='white')

    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

# === Telegram Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *RIVX Crypto Bot*\n\n"
        "Use the following commands:\n"
        "/price [token or ticker]\n"
        "/chart [token or ticker]\n\n"
        "Example: /price btc or /chart ethereum"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /price [token]")
        return

    symbol = context.args[0].lower()
    coin_id = symbol_to_id.get(symbol)

    if not coin_id:
        await update.message.reply_text("❌ Token not found")
        return

    data = await fetch_coingecko_data(f"simple/price", {"ids": coin_id, "vs_currencies": "usd"})
    if not data or coin_id not in data:
        await update.message.reply_text("❌ Failed to fetch price")
        return

    price_usd = data[coin_id]['usd']
    await update.message.reply_text(f"💰 {symbol.upper()} = ${price_usd:,.2f}")

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /chart [token]")
        return

    symbol = context.args[0].lower()
    coin_id = symbol_to_id.get(symbol)

    if not coin_id:
        await update.message.reply_text("❌ Token not found")
        return

    data = await fetch_coingecko_data(
        f"coins/{coin_id}/market_chart",
        params={"vs_currency": "usd", "days": 1}
    )

    if not data or "prices" not in data:
        await update.message.reply_text("❌ Failed to fetch chart data")
        return

    chart_image = generate_chart(data['prices'], symbol)
    await update.message.reply_photo(photo=InputFile(chart_image), caption=f"📊 24h Chart for {symbol.upper()}")

# === Main Runner ===
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("chart", chart))
    logger.info("✅ Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import sys
    import nest_asyncio
    nest_asyncio.apply()

    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except RuntimeError as e:
        print(f"❌ Bot exited with error: {e}")

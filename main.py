# main.py - RIVX Crypto Bot
import os
import logging
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === Load Environment Variables ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINGECKO_API = "https://api.coingecko.com/api/v3"

# === Logger Setup ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Global Coin Symbol Mapping ===
symbol_map = {}

def fetch_symbol_map():
    logger.info("📡 Fetching symbol-to-ID mapping...")
    try:
        res = requests.get(f"{COINGECKO_API}/coins/list")
        res.raise_for_status()
        data = res.json()
        mapping = {}
        for coin in data:
            sym = coin['symbol'].lower()
            if sym not in mapping or coin['id'] == "bitcoin":
                mapping[sym] = coin['id']
        return mapping
    except Exception as e:
        logger.error(f"❌ Error fetching symbol map: {e}")
        return {}

def format_price(token, symbol, price, market):
    return (
        f"🔸{token}: {symbol.upper()}\n"
        f"Price: ${price['usd']:,.2f}\n"
        f"Market Cap: ${market['market_cap']:,.2f}\n"
        f"24h Volume: ${market['total_volume']:,.2f}\n\n"
        f"📈Market Change\n"
        f"1h: {market['price_change_percentage_1h_in_currency']:.2f}%\n"
        f"24h: {market['price_change_percentage_24h_in_currency']:.2f}%\n"
        f"7d: {market['price_change_percentage_7d_in_currency']:.2f}%"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /p btc")
        return
    symbol = context.args[0].lower()
    coin_id = symbol_map.get(symbol)
    if not coin_id:
        await update.message.reply_text("❌ Token not found.")
        return
    try:
        price = requests.get(f"{COINGECKO_API}/simple/price", params={
            "ids": coin_id, "vs_currencies": "usd"
        }).json()[coin_id]

        market = requests.get(f"{COINGECKO_API}/coins/{coin_id}", params={
            "localization": "false", "market_data": "true"
        }).json()["market_data"]
        name = requests.get(f"{COINGECKO_API}/coins/{coin_id}").json()["name"]
        msg = format_price(name, symbol, price, market)
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Price error: {e}")
        await update.message.reply_text("❌ Error fetching price.")

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /c btc")
        return
    symbol = context.args[0].lower()
    coin_id = symbol_map.get(symbol)
    if not coin_id:
        await update.message.reply_text("❌ Token not found.")
        return
    try:
        chart_data = requests.get(f"{COINGECKO_API}/coins/{coin_id}/market_chart", params={
            "vs_currency": "usd", "days": "1", "interval": "hourly"
        }).json()

        times = [datetime.fromtimestamp(p[0] / 1000) for p in chart_data['prices']]
        prices = [p[1] for p in chart_data['prices']]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(times, prices, color="#1976D2", linewidth=2)
        ax.fill_between(times, prices, color="#64B5F6", alpha=0.3)

        ax.set_title(f"{symbol.upper()} Price Chart (24h)", fontsize=14)
        ax.set_xlabel("Time")
        ax.set_ylabel("Price (USD)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        fig.autofmt_xdate()
        ax.grid(True, linestyle='--', alpha=0.4)

        last_price = prices[-1]
        ax.annotate(f"${last_price:,.2f}", xy=(times[-1], last_price),
                    xytext=(-70, 20), textcoords="offset points",
                    bbox=dict(boxstyle="round", fc="white", ec="blue"),
                    arrowprops=dict(arrowstyle="->", color="blue"))

        buf = BytesIO()
        fig.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        await update.message.reply_photo(photo=InputFile(buf), caption=f"📈 24h Chart for {symbol.upper()}")
    except Exception as e:
        logger.error(f"Chart error: {e}")
        await update.message.reply_text("❌ Error fetching chart data.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *RIVX Crypto Bot*\n\n"
        "Check price or chart:\n"
        "`/p btc` – price\n"
        "`/c eth` – chart\n",
        parse_mode="Markdown"
    )

# === Start Bot ===
if __name__ == "__main__":
    symbol_map = fetch_symbol_map()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["price", "p"], price))
    app.add_handler(CommandHandler(["chart", "c"], chart))

    logger.info("✅ Bot is running...")
    app.run_polling()

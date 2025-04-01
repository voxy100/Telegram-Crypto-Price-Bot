# main.py - RIVX Crypto Bot
import os
import logging
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio
import nest_asyncio

nest_asyncio.apply()

# === Config ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINGECKO_API = "https://api.coingecko.com/api/v3"

# === Logger ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Global ===
SYMBOL_TO_ID = {}

# === Functions ===
async def fetch_symbol_map():
    logger.info("📡 Fetching symbol-to-ID mapping...")
    try:
        res = requests.get(f"{COINGECKO_API}/coins/list")
        res.raise_for_status()
        return {coin["symbol"]: coin["id"] for coin in res.json()}
    except Exception as e:
        logger.error(f"Symbol map error: {e}")
        return {}

async def fetch_data(endpoint, params=None):
    try:
        res = requests.get(f"{COINGECKO_API}/{endpoint}", params=params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.error(f"API error: {e}")
        return None

def format_price_info(data, market_data, coin_name, symbol):
    price = market_data["current_price"]["usd"]
    market_cap = market_data["market_cap"]["usd"]
    volume = market_data["total_volume"]["usd"]
    change_1h = market_data.get("price_change_percentage_1h_in_currency", {}).get("usd", 0)
    change_24h = market_data.get("price_change_percentage_24h", 0)
    change_7d = market_data.get("price_change_percentage_7d_in_currency", {}).get("usd", 0)

    return (
        f"🔸{coin_name}: {symbol.upper()}\n"
        f"Price: ${price:,.2f}\n"
        f"Market Cap: ${market_cap:,.2f}\n"
        f"24h Volume: ${volume:,.2f}\n\n"
        f"📈Market Change\n"
        f"1h: {change_1h:.2f}%\n"
        f"24h: {change_24h:.2f}%\n"
        f"7d: {change_7d:.2f}%"
    )

def generate_chart(prices: list, token: str):
    timestamps = [datetime.fromtimestamp(p[0]/1000) for p in prices]
    values = [p[1] for p in prices]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(timestamps, values, color="#00bcd4", linewidth=2)
    ax.fill_between(timestamps, values, color="#00bcd4", alpha=0.2)

    ax.set_title(f"{token.upper()} Price Chart (24h)", fontsize=14)
    ax.set_xlabel("Time")
    ax.set_ylabel("USD Price")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    fig.autofmt_xdate()

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

# === Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *RIVX Crypto Bot*\n\n"
        "/price or /p [token] - Get crypto info\n"
        "/chart or /c [token] - Show 24h chart\n\n"
        "_Example: /p btc or /c eth_",
        parse_mode="Markdown"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /p btc")
        return

    symbol = context.args[0].lower()
    coin_id = SYMBOL_TO_ID.get(symbol)
    if not coin_id:
        await update.message.reply_text("❌ Token not found.")
        return

    data = await fetch_data(f"coins/{coin_id}", params={"localization": "false"})
    if not data:
        await update.message.reply_text("❌ Error fetching price.")
        return

    info = format_price_info(data, data["market_data"], data["name"], symbol)
    await update.message.reply_text(info)

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /c btc")
        return

    symbol = context.args[0].lower()
    coin_id = SYMBOL_TO_ID.get(symbol)
    if not coin_id:
        await update.message.reply_text("❌ Token not found.")
        return

    data = await fetch_data(f"coins/{coin_id}/market_chart", params={"vs_currency": "usd", "days": 1})
    if not data or "prices" not in data:
        await update.message.reply_text("❌ Error fetching chart data.")
        return

    img = generate_chart(data["prices"], symbol)
    await update.message.reply_photo(photo=InputFile(img), caption=f"📊 24h Chart for {symbol.upper()}")

# === Main ===
async def main():
    global SYMBOL_TO_ID
    SYMBOL_TO_ID = await fetch_symbol_map()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["price", "p"], price))
    app.add_handler(CommandHandler(["chart", "c"], chart))

    logger.info("✅ Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        print(f"❌ Bot exited with error: {e}")

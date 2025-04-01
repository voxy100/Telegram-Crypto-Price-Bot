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

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Enable asyncio compatibility for Replit
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Helper Functions ===
def fetch_market_data(token_id):
    try:
        url = f"{COINGECKO_API}/coins/{token_id}"
        response = requests.get(url, params={"localization": "false"})
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        return None

def fetch_chart_data(token_id):
    try:
        url = f"{COINGECKO_API}/coins/{token_id}/market_chart"
        response = requests.get(url, params={"vs_currency": "usd", "days": 1})
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        logger.error(f"Error fetching chart data: {e}")
        return None

def generate_chart(prices, token_name):
    timestamps = [datetime.fromtimestamp(p[0] / 1000) for p in prices]
    values = [p[1] for p in prices]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(timestamps, values, linewidth=2, color='#0077ff')
    ax.fill_between(timestamps, values, color='#0077ff', alpha=0.3)
    ax.set_title(f"{token_name} - 24h Price Chart", fontsize=14)
    ax.set_xlabel("Time")
    ax.set_ylabel("Price (USD)")
    ax.grid(True, alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.autofmt_xdate()

    image_stream = BytesIO()
    fig.savefig(image_stream, format='png', bbox_inches='tight')
    plt.close(fig)
    image_stream.seek(0)
    return image_stream

# === Telegram Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🤖 *RIVX Crypto Bot*\n"
        "Welcome! Use the commands below:\n\n"
        "/p [token] - Check price\n"
        "/c [token] - View chart\n\n"
        "Example: /p bitcoin or /p btc"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a token. Example: /p btc")
        return

    token = context.args[0].lower()
    data = fetch_market_data(token)

    if not data or 'market_data' not in data:
        await update.message.reply_text("❌ Token not found or API error.")
        return

    market = data['market_data']
    name = data['name']
    symbol = data['symbol'].upper()
    price = market['current_price']['usd']
    market_cap = market['market_cap']['usd']
    volume = market['total_volume']['usd']
    change_1h = market['price_change_percentage_1h_in_currency']['usd']
    change_24h = market['price_change_percentage_24h']
    change_7d = market['price_change_percentage_7d']

    msg = (
        f"🔸{name}: {symbol}\n"
        f"Price: ${price:,.2f}\n"
        f"Market Cap: ${market_cap:,.2f}\n"
        f"24h Volume: ${volume:,.2f}\n\n"
        "📈Market Change\n"
        f"1h: {change_1h:.2f}%\n"
        f"24h: {change_24h:.2f}%\n"
        f"7d: {change_7d:.2f}%"
    )
    await update.message.reply_text(msg)

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a token. Example: /c eth")
        return

    token = context.args[0].lower()
    chart_data = fetch_chart_data(token)
    token_data = fetch_market_data(token)

    if not chart_data or 'prices' not in chart_data or not token_data:
        await update.message.reply_text("❌ Failed to fetch chart data.")
        return

    image = generate_chart(chart_data['prices'], token_data['name'])
    await update.message.reply_photo(photo=InputFile(image), caption=f"📊 {token_data['name']} 24h Chart")

# === Main App ===
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["p", "price"], price))
    app.add_handler(CommandHandler(["c", "chart"], chart))

    logger.info("✅ Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    try:
        asyncio.run(main())
    except RuntimeError as e:
        print(f"❌ Bot exited with error: {e}")

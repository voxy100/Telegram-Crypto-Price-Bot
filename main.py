# -*- coding: utf-8 -*-
import os
import logging
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from tempfile import NamedTemporaryFile
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# === Configuration ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Helper Functions ===
async def fetch_coingecko_data(endpoint: str, params: dict = None):
    try:
        response = requests.get(f"{COINGECKO_API}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API Error: {e}")
        return None

def generate_chart(prices: list, token: str):
    timestamps = [datetime.fromtimestamp(p[0]/1000) for p in prices]
    values = [p[1] for p in prices]

    plt.style.use('seaborn-darkgrid')
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(timestamps, values, linewidth=2, color='#2ecc71', label='Price')
    ax.fill_between(timestamps, values, color='#2ecc71', alpha=0.3)

    ax.set_title(f"{token.upper()} Price Chart (24h)", fontsize=14, pad=20)
    ax.set_xlabel("Time", fontsize=12)
    ax.set_ylabel("Price (USD)", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    fig.autofmt_xdate()
    return fig

# === Telegram Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "\U0001F4C8 *RIVX Crypto Bot*\n\n"
        "Commands:\n"
        "/p [token] or /price [token] - Get current price\n"
        "/c [token] or /chart [token] - Get 24h chart\n"
        "\nExample:\n/p bitcoin or /c eth"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please specify a token. Example: /p bitcoin")
        return

    token = context.args[0].lower()
    data = await fetch_coingecko_data(f"coins/{token}", params={"localization": "false"})
    if not data:
        await update.message.reply_text("❌ Token not found or API error")
        return

    try:
        name = data['name']
        symbol = data['symbol'].upper()
        market_data = data['market_data']
        price = market_data['current_price']['usd']
        market_cap = market_data['market_cap']['usd']
        volume = market_data['total_volume']['usd']
        change_1h = market_data['price_change_percentage_1h_in_currency']['usd']
        change_24h = market_data['price_change_percentage_24h_in_currency']['usd']
        change_7d = market_data['price_change_percentage_7d_in_currency']['usd']

        message = (
            f"🔸{name}: {symbol}\n"
            f"Price: ${price:,.2f}\n"
            f"Market Cap: ${market_cap:,.2f}\n"
            f"24h Volume: ${volume:,.2f}\n\n"
            f"📈Market Change\n"
            f"1h: {change_1h:.2f}%\n"
            f"24h: {change_24h:.2f}%\n"
            f"7d: {change_7d:.2f}%"
        )
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error parsing price data: {e}")
        await update.message.reply_text("❌ Error parsing price data")

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please specify a token. Example: /c ethereum")
        return

    token = context.args[0].lower()
    data = await fetch_coingecko_data(
        f"coins/{token}/market_chart",
        params={"vs_currency": "usd", "days": 1, "interval": "hourly"}
    )

    if not data or "prices" not in data:
        await update.message.reply_text("❌ Failed to fetch chart data")
        return

    try:
        fig = generate_chart(data["prices"], token)
        with NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            fig.savefig(tmp_file.name, bbox_inches='tight', dpi=150)
            plt.close(fig)
            await update.message.reply_photo(
                photo=InputFile(tmp_file.name),
                caption=f"📊 24h Chart for {token.upper()}"
            )
            os.unlink(tmp_file.name)
    except Exception as e:
        logger.error(f"Chart error: {e}")
        await update.message.reply_text("❌ Error generating chart")

# === Main App ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("p", price))
    app.add_handler(CommandHandler("chart", chart))
    app.add_handler(CommandHandler("c", chart))

    logger.info("✅ Bot is running...")
    app.run_polling()

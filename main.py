# main.py - RIVX Crypto Bot with styled image output for /p command
import os
import io
import requests
import logging
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
import nest_asyncio
import asyncio

# === Load Environment ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINRANKING_API_KEY = os.getenv("COINRANKING_API_KEY")
COINRANKING_API = "https://api.coinranking.com/v2"

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# === Helper Functions ===
def fetch_coin_uuid(symbol):
    url = f"{COINRANKING_API}/coins"
    headers = {"x-access-token": COINRANKING_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        coins = response.json().get("data", {}).get("coins", [])
        for coin in coins:
            if coin["symbol"].lower() == symbol.lower():
                return coin["uuid"]
        return None
    except Exception as e:
        logger.error(f"Error fetching coin UUID: {e}")
        return None


def fetch_coin_data(uuid):
    url = f"{COINRANKING_API}/coin/{uuid}"
    headers = {"x-access-token": COINRANKING_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("data", {}).get("coin", {})
    except Exception as e:
        logger.error(f"Error fetching coin data: {e}")
        return None


def fetch_market_chart(uuid):
    url = f"{COINRANKING_API}/coin/{uuid}/history"
    headers = {"x-access-token": COINRANKING_API_KEY}
    params = {"timePeriod": "24h"}
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("data", {}).get("history", [])
    except Exception as e:
        logger.error(f"Error fetching market chart: {e}")
        return None


def generate_image_card(coin_data, chart_data):
    name = coin_data.get("name", "Unknown")
    symbol = coin_data.get("symbol", "???").upper()
    price = float(coin_data.get("price", 0))
    market_cap = float(coin_data.get("marketCap", 0))
    volume = float(coin_data.get("24hVolume", 0))
    change = float(coin_data.get("change", 0))
    icon_url = coin_data.get("iconUrl", "")

    # Download logo
    try:
        logo_resp = requests.get(icon_url)
        logo = Image.open(io.BytesIO(logo_resp.content)).convert("RGBA")
    except:
        logo = Image.new("RGBA", (100, 100), (30, 30, 30))

    # Generate chart
    timestamps = [datetime.fromtimestamp(int(p["timestamp"])) for p in chart_data]
    prices = [float(p["price"]) for p in chart_data]

    fig, ax = plt.subplots(figsize=(6, 3), dpi=100)
    ax.plot(timestamps, prices, color="#00e5ff", linewidth=2)
    ax.fill_between(timestamps, prices, min(prices), alpha=0.2, color="#00e5ff")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axis("off")

    buf = io.BytesIO()
    fig.tight_layout(pad=0)
    plt.savefig(buf, format="png", transparent=True)
    plt.close(fig)
    buf.seek(0)
    chart = Image.open(buf).convert("RGBA")

    # Compose Card
    card = Image.new("RGBA", (800, 400), (25, 25, 25))
    draw = ImageDraw.Draw(card)

    font_bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 38)
    font_small = ImageFont.truetype("DejaVuSans.ttf", 22)

    # Paste logo
    logo = logo.resize((80, 80))
    card.paste(logo, (30, 30), logo)

    # Info Text
    draw.text((130, 30), f"{name}", font=font_bold, fill="white")
    draw.text((130, 80), f"{symbol}", font=font_small, fill="gray")
    draw.text((30, 140), f"${price:,.2f}", font=font_bold, fill="white")
    draw.text((30, 190), f"Market Cap: ${market_cap:,.0f}", font=font_small, fill="gray")
    draw.text((30, 220), f"24h Volume: ${volume:,.0f}", font=font_small, fill="gray")
    draw.text((30, 260), f"24h Change: {change:.2f}%", font=font_small, fill="white")

    # Chart
    chart = chart.resize((420, 200))
    card.paste(chart, (370, 180), chart)

    # Watermark
    draw.text((780, 370), "@rivxlabs", font=font_small, fill="gray", anchor="rs")

    output = io.BytesIO()
    card.save(output, format="PNG")
    output.seek(0)
    return output


# === Telegram Command Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *RIVX Crypto Bot*\n\n"
        "Use /p [symbol] to get a styled crypto card with live chart.\n"
        "Example: /p btc",
        parse_mode="Markdown"
    )


async def price_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a token symbol. Example: /p btc")
        return

    symbol = context.args[0].lower()
    uuid = fetch_coin_uuid(symbol)
    if not uuid:
        await update.message.reply_text("❌ Token not found.")
        return

    coin_data = fetch_coin_data(uuid)
    chart_data = fetch_market_chart(uuid)

    if not coin_data or not chart_data:
        await update.message.reply_text("❌ Failed to retrieve data.")
        return

    image = generate_image_card(coin_data, chart_data)
    await update.message.reply_photo(photo=image)


# === Main Runner ===
if __name__ == "__main__":
    nest_asyncio.apply()

    async def main():
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("p", price_card))
        logger.info("📡 Fetching symbol-to-ID mapping...")
        logger.info("✅ Bot is running...")
        await app.run_polling()

    asyncio.run(main())

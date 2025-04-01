import os
import io
import requests
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
import nest_asyncio
import asyncio

# === Load Environment ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINGECKO_API = "https://api.coingecko.com/api/v3"

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Symbol Mapping Cache ===
SYMBOL_TO_ID = {}

def load_symbol_mapping():
    try:
        response = requests.get(f"{COINGECKO_API}/coins/list")
        response.raise_for_status()
        for coin in response.json():
            SYMBOL_TO_ID[coin['symbol'].lower()] = coin['id']
        logger.info("✅ Coin symbol mapping loaded")
    except Exception as e:
        logger.error(f"Failed to load symbol mapping: {e}")

def get_coin_id(symbol):
    return SYMBOL_TO_ID.get(symbol.lower(), symbol.lower())

async def fetch_token_data(token_id):
    try:
        url = f"{COINGECKO_API}/coins/{token_id}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching token data: {e}")
        return None

async def fetch_market_chart(token_id):
    try:
        url = f"{COINGECKO_API}/coins/{token_id}/market_chart"
        params = {"vs_currency": "usd", "days": 1}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching chart data: {e}")
        return None

def get_dominant_color(image):
    image = image.resize((50, 50))
    result = image.convert('RGB').getcolors(50 * 50)
    return max(result, key=lambda x: x[0])[1]

def generate_image_card(token_info, chart_data):
    name = token_info['name']
    symbol = token_info['symbol'].upper()
    price = token_info['market_data']['current_price']['usd']
    market_cap = token_info['market_data']['market_cap']['usd']
    volume = token_info['market_data']['total_volume']['usd']
    change_1h = token_info['market_data']['price_change_percentage_1h_in_currency']['usd']
    change_24h = token_info['market_data']['price_change_percentage_24h_in_currency']['usd']
    change_7d = token_info['market_data']['price_change_percentage_7d_in_currency']['usd']
    logo_url = token_info['image']['large']

    # Download logo
    try:
        logo_resp = requests.get(logo_url)
        logo = Image.open(io.BytesIO(logo_resp.content)).convert("RGBA")
    except:
        logo = Image.new("RGBA", (100, 100), (30, 30, 30))

    dominant_color = get_dominant_color(logo)

    # Generate chart
    timestamps = [datetime.fromtimestamp(p[0] / 1000) for p in chart_data["prices"]]
    prices = [p[1] for p in chart_data["prices"]]
    fig, ax = plt.subplots(figsize=(6, 3), dpi=100)
    ax.plot(timestamps, prices, color=dominant_color, linewidth=2)
    ax.fill_between(timestamps, prices, min(prices), alpha=0.2, color=dominant_color)
    ax.axis("off")

    chart_buf = io.BytesIO()
    fig.tight_layout(pad=0)
    plt.savefig(chart_buf, format="png", transparent=True)
    plt.close(fig)
    chart_buf.seek(0)
    chart_img = Image.open(chart_buf).convert("RGBA")

    # Compose final image
    card = Image.new("RGBA", (800, 400), (20, 20, 20))
    draw = ImageDraw.Draw(card)

    # Fonts with fallback
    try:
        font_bold = ImageFont.truetype("dejavu-sans-bold.ttf", 40)
        font_small = ImageFont.truetype("dejavu-sans.ttf", 20)
    except:
        font_bold = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Paste logo
    logo = logo.resize((80, 80))
    card.paste(logo, (30, 30), logo)

    # Text
    draw.text((130, 30), f"{name}", font=font_bold, fill="white")
    draw.text((130, 80), f"{symbol}", font=font_small, fill="gray")
    draw.text((30, 140), f"${price:,.2f}", font=font_bold, fill="white")
    draw.text((30, 190), f"Market Cap: ${market_cap:,.0f}", font=font_small, fill="gray")
    draw.text((30, 220), f"24h Volume: ${volume:,.0f}", font=font_small, fill="gray")
    draw.text((30, 260), f"📈 1h: {change_1h:.2f}%", font=font_small, fill="white")
    draw.text((30, 290), f"24h: {change_24h:.2f}%", font=font_small, fill="white")
    draw.text((30, 320), f"7d: {change_7d:.2f}%", font=font_small, fill="white")

    # Paste chart
    chart_img = chart_img.resize((400, 200))
    card.paste(chart_img, (380, 180), chart_img)

    # Watermark
    draw.text((760, 370), "@rivxlabs", font=font_small, fill="gray", anchor="rs")

    output = io.BytesIO()
    card.save(output, format="PNG")
    output.seek(0)
    return output

async def price_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a token. Example: /p bitcoin")
        return

    query = context.args[0].lower()
    token_id = get_coin_id(query)
    token_data = await fetch_token_data(token_id)
    chart_data = await fetch_market_chart(token_id)

    if not token_data or not chart_data:
        await update.message.reply_text("❌ Token not found or API error.")
        return

    try:
        image = generate_image_card(token_data, chart_data)
        await update.message.reply_photo(photo=image)
    except Exception as e:
        logger.error(f"Image error: {e}")
        # fallback to text
        md = token_data['market_data']
        name = token_data['name']
        symbol = token_data['symbol'].upper()
        price = md['current_price']['usd']
        market_cap = md['market_cap']['usd']
        volume = md['total_volume']['usd']
        change_1h = md['price_change_percentage_1h_in_currency']['usd']
        change_24h = md['price_change_percentage_24h_in_currency']['usd']
        change_7d = md['price_change_percentage_7d_in_currency']['usd']

        text = (
            f"🔸{name}: {symbol}\n"
            f"Price: ${price:,.2f}\n"
            f"Market Cap: ${market_cap:,.0f}\n"
            f"24h Volume: ${volume:,.0f}\n\n"
            f"📈Market Change\n"
            f"1h: {change_1h:.2f}%\n"
            f"24h: {change_24h:.2f}%\n"
            f"7d: {change_7d:.2f}%"
        )
        await update.message.reply_text(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *RIVX Crypto Bot*\n\nUse /p [token] to get a styled price card.\nExample: /p btc",
        parse_mode="Markdown"
    )

# === Run Bot ===
if __name__ == "__main__":
    nest_asyncio.apply()

    async def main():
        load_symbol_mapping()
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("p", price_card))
        logger.info("📡 Fetching symbol-to-ID mapping...")
        logger.info("✅ Bot is running...")
        await app.run_polling()

    asyncio.run(main())

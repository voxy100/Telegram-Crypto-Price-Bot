
# main.py - RIVX Crypto Bot using CoinGecko API with styled image and text fallback
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
import numpy as np
import nest_asyncio

# === Load Environment ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINGECKO_API = "https://api.coingecko.com/api/v3"

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Font Fallback ===
def get_font(font_path, size):
    try:
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()

# === Helper Functions ===
def fetch_token_data(coin_id):
    try:
        url = f"{COINGECKO_API}/coins/{coin_id}"
        response = requests.get(url, params={"localization": "false"})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching token data: {e}")
        return None

def fetch_chart_data(coin_id):
    try:
        url = f"{COINGECKO_API}/coins/{coin_id}/market_chart"
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
    try:
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

        # Fonts
        font_bold = get_font("dejavu-sans-bold.ttf", 40)
        font_small = get_font("dejavu-sans.ttf", 20)

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
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return None

# === Telegram Bot Handlers ===
async def price_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a token. Example: /p bitcoin")
        return

    token = context.args[0].lower()
    token_info = fetch_token_data(token)
    chart_info = fetch_chart_data(token)

    if not token_info or not chart_info:
        await update.message.reply_text("❌ Could not retrieve token/chart data.")
        return

    img = generate_image_card(token_info, chart_info)
    if img:
        await update.message.reply_photo(photo=img)
    else:
        # fallback plain text
        try:
            md = token_info["market_data"]
            name = token_info["name"]
            symbol = token_info["symbol"].upper()
            price = md["current_price"]["usd"]
            cap = md["market_cap"]["usd"]
            vol = md["total_volume"]["usd"]
            h1 = md["price_change_percentage_1h_in_currency"]["usd"]
            h24 = md["price_change_percentage_24h_in_currency"]["usd"]
            d7 = md["price_change_percentage_7d_in_currency"]["usd"]

            text = (
                f"🔸{name}: {symbol}
"
                f"Price: ${price:,.2f}
"
                f"Market Cap: ${cap:,.0f}
"
                f"24h Volume: ${vol:,.0f}

"
                f"📈Market Change
"
                f"1h: {h1:.2f}%
24h: {h24:.2f}%
7d: {d7:.2f}%"
            )
            await update.message.reply_text(text)
        except:
            await update.message.reply_text("❌ Error parsing fallback text.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *RIVX Crypto Bot*
Use /p [token] to get price chart card.
Example: /p ethereum",
        parse_mode="Markdown"
    )

# === Main Bot Setup ===
if __name__ == "__main__":
    nest_asyncio.apply()
    import asyncio

    async def main():
        logger.info("📡 Fetching symbol-to-ID mapping...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("p", price_card))
        logger.info("✅ Bot is running...")
        await app.run_polling()

    asyncio.run(main())

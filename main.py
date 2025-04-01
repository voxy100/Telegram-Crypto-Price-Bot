# main.py - RIVX Crypto Bot using CoinGecko API with styled image and text fallback
import os
import io
import requests
import logging
import time
import random
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
import nest_asyncio

# === Load Environment ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COINGECKO_API = "https://api.coingecko.com/api/v3"

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Rate Limiting ===
LAST_API_CALL = time.time()
API_DELAY = 1.5  # 1.5 seconds between calls for 40 calls/minute

# === Symbol Mapping ===
SYMBOL_TO_ID = {}


def load_symbol_mapping():
    try:
        response = requests.get(f"{COINGECKO_API}/coins/list")
        response.raise_for_status()
        data = response.json()

        priority_map = {
            'btc': 'bitcoin',
            'eth': 'ethereum',
            'bnb': 'binancecoin',
            'xrp': 'ripple',
            'sol': 'solana',
            'doge': 'dogecoin',
        }

        for coin in data:
            symbol = coin['symbol'].lower()
            coin_id = coin['id']
            if symbol not in SYMBOL_TO_ID or priority_map.get(
                    symbol) == coin_id:
                SYMBOL_TO_ID[symbol] = coin_id

        logger.info("✅ Coin symbol mapping loaded")
    except Exception as e:
        logger.error(f"Error loading symbol mapping: {e}")


# === Font Fallback ===
def get_font(font_path, size):
    try:
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()


# === Helper Functions ===
def api_request(url, params=None):
    global LAST_API_CALL
    try:
        # Rate limiting
        elapsed = time.time() - LAST_API_CALL
        if elapsed < API_DELAY:
            sleep_time = API_DELAY - elapsed + random.uniform(0.1, 0.5)
            time.sleep(sleep_time)

        response = requests.get(url, params=params)
        LAST_API_CALL = time.time()

        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            logger.warning(
                f"Rate limited. Retrying after {retry_after} seconds")
            time.sleep(retry_after)
            return api_request(url, params)

        response.raise_for_status()
        return response
    except Exception as e:
        logger.error(f"API request failed: {e}")
        return None


def fetch_token_data(coin_id):
    try:
        url = f"{COINGECKO_API}/coins/{coin_id}"
        response = api_request(url, {"localization": "false"})
        return response.json() if response else None
    except Exception as e:
        logger.error(f"Error fetching token data: {e}")
        return None


def fetch_chart_data(coin_id):
    try:
        url = f"{COINGECKO_API}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": 1}
        response = api_request(url, params)
        return response.json() if response else None
    except Exception as e:
        logger.error(f"Error fetching chart data: {e}")
        return None


def get_dominant_color(image):
    try:
        image = image.resize((50, 50))
        result = image.convert('RGB').getcolors(50 * 50)
        if not result:
            return "#16c784"  # Fallback color

        rgb = max(result, key=lambda x: x[0])[1]
        return (rgb[0] / 255, rgb[1] / 255, rgb[2] / 255
                )  # Convert to 0-1 range
    except Exception as e:
        logger.error(f"Color detection error: {e}")
        return "#16c784"


def generate_image_card(token_info, chart_data):
    try:
        name = token_info['name']
        symbol = token_info['symbol'].upper()
        price = token_info['market_data']['current_price']['usd']
        market_cap = token_info['market_data']['market_cap']['usd']
        volume = token_info['market_data']['total_volume']['usd']
        change_1h = token_info['market_data'][
            'price_change_percentage_1h_in_currency']['usd']
        change_24h = token_info['market_data'][
            'price_change_percentage_24h_in_currency']['usd']
        change_7d = token_info['market_data'][
            'price_change_percentage_7d_in_currency']['usd']
        logo_url = token_info['image']['large']

        # Download logo
        try:
            logo_resp = requests.get(logo_url, timeout=10)
            logo = Image.open(io.BytesIO(logo_resp.content)).convert("RGBA")
        except Exception as e:
            logger.warning(f"Logo download failed: {e}")
            logo = Image.new("RGBA", (100, 100), (30, 30, 30))

        dominant_color = get_dominant_color(logo)

        # Generate chart
        timestamps = [
            datetime.fromtimestamp(p[0] / 1000) for p in chart_data["prices"]
        ]
        prices = [p[1] for p in chart_data["prices"]]

        fig, ax = plt.subplots(figsize=(6, 3), dpi=100)
        ax.plot(timestamps, prices, color=dominant_color, linewidth=2)
        ax.fill_between(timestamps,
                        prices,
                        min(prices),
                        alpha=0.2,
                        color=dominant_color)
        ax.axis("off")

        chart_buf = io.BytesIO()
        plt.savefig(chart_buf,
                    format="png",
                    transparent=True,
                    bbox_inches='tight')
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

        # Text elements
        text_config = [
            (130, 30, name, font_bold, "white"),
            (130, 80, symbol, font_small, "gray"),
            (30, 140, f"${price:,.2f}", font_bold, "white"),
            (30, 190, f"Market Cap: ${market_cap:,.0f}", font_small, "gray"),
            (30, 220, f"24h Volume: ${volume:,.0f}", font_small, "gray"),
            (30, 260, f"📈 1h: {change_1h:.2f}%", font_small, "white"),
            (30, 290, f"24h: {change_24h:.2f}%", font_small, "white"),
            (30, 320, f"7d: {change_7d:.2f}%", font_small, "white")
        ]

        for x, y, text, font, color in text_config:
            draw.text((x, y), text, font=font, fill=color)

        # Paste chart
        chart_img = chart_img.resize((400, 200))
        card.paste(chart_img, (380, 180), chart_img)

        # Watermark
        draw.text((760, 370),
                  "@rivxlabs",
                  font=font_small,
                  fill="gray",
                  anchor="rs")

        output = io.BytesIO()
        card.save(output, format="PNG")
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return None


# === Telegram Handlers ===
async def price_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a token. Example: /p bitcoin")
        return

    token = context.args[0].lower()
    coin_id = SYMBOL_TO_ID.get(token, token)

    token_info = fetch_token_data(coin_id)
    chart_info = fetch_chart_data(coin_id)

    if not token_info or not chart_info:
        await update.message.reply_text(
            "❌ Could not retrieve token/chart data.")
        return

    img = generate_image_card(token_info, chart_info)
    if img:
        await update.message.reply_photo(photo=InputFile(img))
    else:
        try:
            md = token_info["market_data"]
            text = (
                f"🔸 {token_info['name']} ({token.upper()})\n"
                f"Price: ${md['current_price']['usd']:,.2f}\n"
                f"Market Cap: ${md['market_cap']['usd']:,.2f}\n"
                f"24h Volume: ${md['total_volume']['usd']:,.2f}\n\n"
                f"📈 Market Change\n"
                f"1h: {md['price_change_percentage_1h_in_currency']['usd']:.2f}%\n"
                f"24h: {md['price_change_percentage_24h_in_currency']['usd']:.2f}%\n"
                f"7d: {md['price_change_percentage_7d_in_currency']['usd']:.2f}%"
            )
            await update.message.reply_text(text)
        except Exception as e:
            logger.error(f"Fallback error: {e}")
            await update.message.reply_text("❌ Error generating response")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *RIVX Crypto Bot*\n\n"
        "Use `/p [symbol]` to get price data\n"
        "Examples:\n`/p btc` - Bitcoin\n`/p eth` - Ethereum\n`/p doge` - Dogecoin",
        parse_mode="Markdown")


# === Main Execution ===
if __name__ == "__main__":
    nest_asyncio.apply()
    load_symbol_mapping()

    async def main():
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("p", price_card))
        logger.info("✅ Bot is running...")
        await app.run_polling()

    import asyncio
    asyncio.run(main())

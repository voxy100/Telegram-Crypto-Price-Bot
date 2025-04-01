# main.py - RIVX Crypto Bot with styled image output using CoinGecko API
import os
import io
import requests
import logging
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
symbol_to_id = {}

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# === Build symbol to ID map ===
async def build_symbol_mapping():
    global symbol_to_id
    try:
        response = requests.get(f"{COINGECKO_API}/coins/list")
        response.raise_for_status()
        coins = response.json()
        symbol_to_id = {coin["symbol"].lower(): coin["id"] for coin in coins}
        logger.info("✅ Coin symbol mapping loaded")
    except Exception as e:
        logger.error(f"Failed to load coin list: {e}")


# === Fetch data ===
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
            logo_resp = requests.get(logo_url)
            logo = Image.open(io.BytesIO(logo_resp.content)).convert("RGBA")
        except:
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
        fig.tight_layout(pad=0)
        plt.savefig(chart_buf, format="png", transparent=True)
        plt.close(fig)
        chart_buf.seek(0)
        chart_img = Image.open(chart_buf).convert("RGBA")

        # Compose image
        card = Image.new("RGBA", (800, 400), (20, 20, 20))
        draw = ImageDraw.Draw(card)
        try:
            font_bold = ImageFont.truetype("dejavu-sans-bold.ttf", 38)
            font_small = ImageFont.truetype("dejavu-sans.ttf", 22)
        except:
            font_bold = font_small = ImageFont.load_default()

        logo = logo.resize((80, 80))
        card.paste(logo, (30, 30), logo)

        draw.text((130, 30), f"{name}", font=font_bold, fill="white")
        draw.text((130, 80), f"{symbol}", font=font_small, fill="gray")
        draw.text((30, 140), f"${price:,.2f}", font=font_bold, fill="white")
        draw.text((30, 190),
                  f"Market Cap: ${market_cap:,.0f}",
                  font=font_small,
                  fill="gray")
        draw.text((30, 220),
                  f"24h Volume: ${volume:,.0f}",
                  font=font_small,
                  fill="gray")
        draw.text((30, 260),
                  f"📈 1h: {change_1h:.2f}%",
                  font=font_small,
                  fill="white")
        draw.text((30, 290),
                  f"24h: {change_24h:.2f}%",
                  font=font_small,
                  fill="white")
        draw.text((30, 320),
                  f"7d: {change_7d:.2f}%",
                  font=font_small,
                  fill="white")
        chart_img = chart_img.resize((400, 200))
        card.paste(chart_img, (380, 180), chart_img)
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
        logger.error(f"Image generation failed: {e}")
        return None


async def price_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a token. Example: /p btc")
        return

    input_symbol = context.args[0].lower()
    token_id = symbol_to_id.get(input_symbol)
    if not token_id:
        await update.message.reply_text("❌ Unknown token symbol.")
        return

    token_data = await fetch_token_data(token_id)
    chart_data = await fetch_market_chart(token_id)

    if not token_data or not chart_data:
        await update.message.reply_text("❌ Error fetching chart or token data."
                                        )
        return

    image = generate_image_card(token_data, chart_data)
    if image:
        await update.message.reply_photo(photo=image)
    else:
        name = token_data['name']
        symbol = token_data['symbol'].upper()
        price = token_data['market_data']['current_price']['usd']
        market_cap = token_data['market_data']['market_cap']['usd']
        volume = token_data['market_data']['total_volume']['usd']
        change_1h = token_data['market_data'][
            'price_change_percentage_1h_in_currency']['usd']
        change_24h = token_data['market_data'][
            'price_change_percentage_24h_in_currency']['usd']
        change_7d = token_data['market_data'][
            'price_change_percentage_7d_in_currency']['usd']

        text = (f"🔸{name}: {symbol}"
                f"Price: ${price:,.2f}"
                f"Market Cap: ${market_cap:,.0f}"
                f"24h Volume: ${volume:,.0f}"
                f"📈 Market Change"
                f"1h: {change_1h:.2f}%"
                f"24h: {change_24h:.2f}%"
                f"7d: {change_7d:.2f}%")
        await update.message.reply_text(text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *RIVX Crypto Bot*"
        "Use /p [token] to get styled price card"
        "Example: /p eth",
        parse_mode="Markdown")


if __name__ == "__main__":
    nest_asyncio.apply()
    import asyncio

    async def main():
        await build_symbol_mapping()
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("p", price_card))
        logger.info("📡 Fetching symbol-to-ID mapping...")
        logger.info("✅ Bot is running...")
        await app.run_polling()

    asyncio.run(main())

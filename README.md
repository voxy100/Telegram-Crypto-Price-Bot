# RIVX Crypto Price Bot

RIVX Crypto Bot is a stylish Telegram bot built using the CoinGecko API. It allows users to check live cryptocurrency prices and generate custom price chart images, complete with price info, market data, and branding.

## Features

- `/p [token]` — Get a styled image with:
  - Live price in USD
  - Market cap
  - 24h trading volume
  - Price changes in 1h, 24h, 7d
  - Chart with gradient color
  - Coin logo and watermark (@rivxlabs)
- `/c [token]` — Get a clean 24h line chart
- Fallback to plain text if image generation fails
- Automatically detects coin symbol (e.g. BTC, ETH, etc.)

## Installation

1. Clone this repository:

```bash
git clone https://github.com/voxy100/Telegram-Crypto-Price-Bot.git
cd Telegram-Crypto-Price-Bot
```

2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file:

```
BOT_TOKEN=your_telegram_bot_token_here
```

4. Run the bot:

```bash
python3 main.py
```

## Deployment on Replit

- Make sure to upload `dejavu-sans.ttf` and `dejavu-sans-bold.ttf` fonts
- Add `BOT_TOKEN` in the Secrets (Environment Variables)
- Use `.replit` file to define run command

## Credits

Made with ❤️ by **Voxy**  
Follow [@rivxlabs](https://t.me/rivxlabs) on Telegram for more bots and tools.

## License

MIT
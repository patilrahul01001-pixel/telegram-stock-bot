# Ready-to-Deploy Stock & MF Telegram Bot (Prototype)

This package contains a prototype Telegram bot that:
- Sends weekly portfolio alerts (Sunday 18:00 IST)
- Sends monthly top 10 stock picks (1st day, 09:00 IST)
- Allows commands: /start, /status, /picks, /stock <symbol>, /fund <name>, /settings
- Saves reports to the `reports/` folder

## What you will get
Files included:
- `main.py` - the bot code
- `portfolio.json` - your preloaded portfolio (edit if needed)
- `nse_tickers.txt` - bundled sample NSE tickers to scan (you can expand)
- `requirements.txt` - Python packages required
- `.env.example` - copy to `.env` or set environment variables in Railway
- `README.md` - this file
- `reports/` - folder where bot saves Excel reports after each run

## How to deploy on Railway.app (free)
1. Sign in to https://railway.app with GitHub or Google.
2. Create a new project -> Deploy from GitHub (or you can upload the files manually).
3. In Railway project settings -> Environment Variables, add:
   - `BOT_TOKEN` = your bot token (from BotFather)
   - `CHAT_ID` = your chat id (from userinfobot)
4. Ensure the `requirements.txt` is used; Railway installs dependencies automatically.
5. Start the project. The bot will start and send a live message to your Telegram chat.

## How to run locally (optional)
1. Install Python 3.9+ and pip.
2. Create and activate a virtual environment.
3. Install packages: `pip install -r requirements.txt`
4. Set environment variables or create a `.env` file with BOT_TOKEN and CHAT_ID.
5. Run: `python main.py`

## Notes & Limitations
- This is an educational prototype. It uses a simple rule-based scanner.
- The NSE ticker list is a sample — extend `nse_tickers.txt` with the tickers you want scanned.
- For more accurate MF data and news sentiment, integrate a paid API or aggregator.
- I did not put your BOT_TOKEN or CHAT_ID in the code — set them in Railway or .env.

If you want, I can also provide a GitHub repository link and step-by-step screenshots for Railway deployment.
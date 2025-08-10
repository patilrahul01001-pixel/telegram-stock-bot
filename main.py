"""
Simple Telegram Stock & MF Advisor Bot (Prototype)
- Reads BOT_TOKEN & CHAT_ID from environment variables or .env
- Preloaded portfolio in portfolio.json
- Weekly and monthly schedulers (APScheduler)
- Commands: /start, /status, /picks, /stock <symbol>, /fund <name>, /settings
- Sends reports via Telegram and saves Excel in reports/
DISCLAIMER: Educational prototype. Backtest and review before using real money.
"""

import os, sys, json, time, threading, math, datetime
from datetime import datetime as dt
from pathlib import Path
import pandas as pd
import yfinance as yf
import requests

# Telegram
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Scheduler
from apscheduler.schedulers.background import BackgroundScheduler

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Load config & portfolio
PORTF_FILE = BASE_DIR / "portfolio.json"
with open(PORTF_FILE, "r") as f:
    PORTF = json.load(f)

# Load NSE tickers (sample list)
TICKERS_FILE = BASE_DIR / "nse_tickers.txt"
with open(TICKERS_FILE, "r") as f:
    NSE_TICKERS = [line.strip() for line in f if line.strip()]

# Environment variables (or .env)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("ERROR: BOT_TOKEN and CHAT_ID must be set as environment variables.")
    sys.exit(1)

# Helper: send message
def send_msg(bot, text, reply_markup=None):
    try:
        bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e:
        print("Failed to send msg:", e)

# Simple technical helpers
def sma(series, window):
    return series.rolling(window).mean()

def rsi(series, period=14):
    delta = series.diff().dropna()
    up = delta.clip(lower=0)
    down = -1*delta.clip(upper=0)
    ma_up = up.rolling(period).mean()
    ma_down = down.rolling(period).mean()
    rs = ma_up / (ma_down + 1e-9)
    return 100 - (100 / (1 + rs))

# Analyze single ticker and return simple signal
def analyze_ticker(ticker):
    try:
        data = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if data.empty:
            return None
        close = data["Close"]
        sma50 = sma(close, 50).iloc[-1] if len(close)>=50 else None
        sma200 = sma(close, 200).iloc[-1] if len(close) >= 200 else None
        last = close.iloc[-1]
        r = rsi(close).iloc[-1] if len(close) > 14 else None

        signal = "HOLD"
        reasons = []
        if sma200 and sma50 and sma50 > sma200 and last > sma50:
            signal = "BUY"
            reasons.append("50>200 SMA & price>50SMA")
        if sma50 and last < sma50:
            signal = "SELL"
            reasons.append("price below 50SMA")
        if r and r > 75:
            signal = "SELL"
            reasons.append(f"RSI {r:.0f}>75")
        if r and r < 30 and signal != "BUY":
            signal = "BUY"
            reasons.append(f"RSI {r:.0f}<30")

        return {"ticker": ticker, "last": float(last), "sma50": float(sma50) if sma50==sma50 else None,
                "sma200": float(sma200) if sma200==sma200 else None, "rsi": float(r) if r==r else None,
                "signal": signal, "reasons": reasons}
    except Exception as e:
        return None

# Build top picks (price between 100 and 500)
def build_monthly_picks():
    picks = []
    sample = NSE_TICKERS  # pre-bundled list
    for t in sample:
        t_full = t if t.endswith(".NS") else t + ".NS"
        info = analyze_ticker(t_full)
        if not info:
            continue
        price = info["last"]
        if price >= 100 and price <= 500:
            score = 0
            if info["signal"] == "BUY":
                score += 2
            if info.get("rsi") and info["rsi"] < 40:
                score += 1
            if info.get("sma50") and info.get("sma200") and info["sma50"] > info["sma200"]:
                score += 1
            picks.append((score, info))
    picks_sorted = sorted(picks, key=lambda x:(-x[0], x[1]["last"]))
    top10 = [p[1] for p in picks_sorted[:10]]
    return top10

# Portfolio check
def check_portfolio():
    results = []
    for item in PORTF:
        tick = item.get("ticker")
        tick_full = tick if tick.endswith(".NS") else tick + ".NS"
        res = analyze_ticker(tick_full)
        if res:
            last = res["last"]
            if res["signal"] == "BUY":
                target = round(last * 1.25,2)
                stop = round(last * 0.90,2)
            elif res["signal"] == "SELL":
                target = round(last * 1.05,2)
                stop = round(last * 0.97,2)
            else:
                target = round(last * 1.10,2)
                stop = round(last * 0.95,2)
            res.update({"target": target, "stop": stop, "shares": item.get("shares", 0)})
            results.append(res)
    return results

# Mutual Fund suggestions (placeholder)
def mf_suggestions():
    return [
        {"name":"SBI Small Cap Fund", "reason":"Strong 3Y returns, diversified small-cap exposure"},
        {"name":"HDFC Index Fund - Nifty 50", "reason":"Low cost broad-market exposure"},
        {"name":"Axis Long Term Equity ELSS", "reason":"Tax saving + growth potential"}
    ]

# Generate and send weekly alert
def weekly_job(context_bot):
    txt = "<b>Weekly Portfolio Alert</b>\\nDate: %s\\n\\n" % dt.now().strftime("%Y-%m-%d %H:%M")
    res = check_portfolio()
    if not res:
        txt += "No portfolio data available or no results."
    for r in res:
        txt += f"{r['ticker']}: {r['signal']} | Last ₹{r['last']:.2f} | Target ₹{r['target']} | Stop ₹{r['stop']}\\nReasons: {', '.join(r['reasons'])}\\n\\n"
    df = pd.DataFrame(res)
    fname = REPORTS_DIR / f"weekly_{dt.now().strftime('%Y%m%d_%H%M')}.xlsx"
    df.to_excel(fname, index=False)
    send_msg(context_bot, txt)

# Generate and send monthly picks & MF suggestions
def monthly_job(context_bot):
    txt = "<b>Monthly Top 10 Picks (₹100-₹500)</b>\\nDate: %s\\n\\n" % dt.now().strftime("%Y-%m-%d %H:%M")
    picks = build_monthly_picks()
    if not picks:
        txt += "No picks generated."
    for p in picks:
        txt += f"{p['ticker']}: ₹{p['last']:.2f} | Signal: {p['signal']}\\nReasons: {', '.join(p['reasons'])}\\n\\n"
    mfs = mf_suggestions()
    txt += "<b>Mutual Fund Suggestions</b>\\n"
    for m in mfs:
        txt += f"{m['name']} - {m['reason']}\\n"
    df = pd.DataFrame(picks)
    fname = REPORTS_DIR / f"monthly_{dt.now().strftime('%Y%m%d_%H%M')}.xlsx"
    df.to_excel(fname, index=False)
    send_msg(context_bot, txt)

# Telegram command handlers
def start(update: Update, context: CallbackContext):
    user = update.effective_user.first_name if update.effective_user else 'User'
    kb = [['📊 Portfolio Status', '📈 Top 10 Picks'], ['🚪 Exit Alert', '💰 Mutual Funds'], ['⚙️ Settings']]
    reply = ReplyKeyboardMarkup(kb, resize_keyboard=True)
    update.message.reply_text(f"Hello {user}! I am your Stock & MF Advisor Bot. Use buttons or commands.\\nCommands: /stock, /fund, /status, /picks, /settings", reply_markup=reply)

def status_cmd(update: Update, context: CallbackContext):
    res = check_portfolio()
    txt = "<b>Portfolio Status</b>\\n\\n"
    for r in res:
        txt += f"{r['ticker']}: {r['signal']} | Last ₹{r['last']:.2f} | Target ₹{r['target']} | Stop ₹{r['stop']}\\n"
    update.message.reply_text(txt, parse_mode='HTML')

def picks_cmd(update: Update, context: CallbackContext):
    picks = build_monthly_picks()
    txt = "<b>Top 10 Picks</b>\\n\\n"
    for p in picks:
        txt += f"{p['ticker']}: ₹{p['last']:.2f} | Signal: {p['signal']}\\n"
    update.message.reply_text(txt, parse_mode='HTML')

def stock_cmd(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("Usage: /stock <TICKER>") 
        return
    ticker = args[0].upper()
    if not ticker.endswith('.NS'):
        ticker = ticker + '.NS'
    res = analyze_ticker(ticker)
    if not res:
        update.message.reply_text("No data for this ticker.")
        return
    txt = f"{res['ticker']}: Last ₹{res['last']:.2f} | Signal: {res['signal']}\\nReasons: {', '.join(res['reasons'])}\\nTarget/Stop: TBD"
    update.message.reply_text(txt)

def fund_cmd(update: Update, context: CallbackContext):
    args = context.args
    name = ' '.join(args) if args else ''
    mfs = mf_suggestions()
    found = [m for m in mfs if name.lower() in m['name'].lower()] if name else mfs
    txt = "<b>MF Suggestions</b>\\n\\n"
    for m in found:
        txt += f"{m['name']} - {m['reason']}\\n"
    update.message.reply_text(txt, parse_mode='HTML')

def settings_cmd(update: Update, context: CallbackContext):
    update.message.reply_text('Settings: (not fully dynamic in prototype) - change scheduling via host env vars.')

def main():
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('status', status_cmd))
    dp.add_handler(CommandHandler('picks', picks_cmd))
    dp.add_handler(CommandHandler('stock', stock_cmd))
    dp.add_handler(CommandHandler('fund', fund_cmd))
    dp.add_handler(CommandHandler('settings', settings_cmd))

    updater.start_polling()
    bot = updater.bot

    sched = BackgroundScheduler(timezone='Asia/Kolkata')
    sched.add_job(lambda: weekly_job(bot), 'cron', day_of_week='sun', hour=18, minute=0)
    sched.add_job(lambda: monthly_job(bot), 'cron', day=1, hour=9, minute=0)
    sched.start()

    print('Bot started.')
    try:
        send_msg(bot, 'Hello from your Stock Bot — I am LIVE and will send weekly & monthly alerts. Use /picks or /status anytime.')
    except Exception as e:
        print('Could not send initial message:', e)

    updater.idle()

if __name__ == '__main__':
    main()

"""
AuroraPriceBot — ربات تلگرام قیمت ارز/طلا/سکه/رمزارز
Run:  python bot.py
Env:  BOT_TOKEN (required)
"""
import os
import logging

import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import prices

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ.get("BOT_TOKEN", "")
WELCOME = (
    "👋 سلام!\n\n"
    "من ربات قیمت لحظه‌ای هستم:\n"
    "💵 دلار/یورو/پوند\n"
    "🥇 طلا، سکه امامی، بهار آزادی، نیم‌سکه، ربع‌سکه\n"
    "🪙 تتر داخلی\n"
    "🌐 رمزارزها (بیت‌کوین، اتریوم و ۵۰۰+ ارز)\n\n"
    "دستورات:\n"
    "/iran — قیمت‌های بازار ایران\n"
    "/crypto — رمزارزهای معروف\n"
    "/price BTC — قیمت یک ارز خاص\n"
    "/all — همه باهم\n"
    "/help — راهنما"
)


def _fmt(v) -> str:
    if isinstance(v, float) and v >= 100:
        return f"{v:,.0f}"
    if isinstance(v, float):
        return f"{v:.6f}".rstrip("0").rstrip(".")
    return f"{v:,}"


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME, parse_mode=None)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME, parse_mode=None)


async def cmd_iran(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = prices.iran_message()
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_crypto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ دارم قیمت‌ها رو می‌گیرم...")
    msg = prices.crypto_message(limit=15)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ دارم همه‌ی قیمت‌ها رو می‌گیرم...")
    txt = prices.iran_message() + "\n\n" + prices.crypto_message(limit=10)
    if len(txt) > 4000:
        txt = txt[:4000]
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)


async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("مثال: `/price BTC`", parse_mode=ParseMode.MARKDOWN)
        return
    sym = ctx.args[0].upper()
    await update.message.reply_text(f"⏳ قیمت {sym}...")
    # اول ایران، بعد کریپتو
    iran_map = {
        "USD": "dollar", "DOLLAR": "dollar", "EUR": "euro", "EURO": "euro",
        "GBP": "pound", "USDT": "usdt", "TETHER": "usdt",
        "GOLD18": "gold_18", "GOLD": "gold_18", "COIN": "coin_emami",
        "EMAMI": "coin_emami", "BAHAR": "coin_bahar", "HALF": "coin_half",
        "QUARTER": "coin_quarter", "GERAMI": "coin_gerami",
    }
    if sym in iran_map:
        p = prices.get_iran().get(iran_map[sym])
        if p:
            await update.message.reply_text(f"{IRAN_FA_LABEL(sym)}: `{p:,}` تومان", parse_mode=ParseMode.MARKDOWN)
            return
    msg = prices.crypto_message(symbol=sym)
    if "پیدا نشد" in msg or "not" in msg.lower():
        await update.message.reply_text(f"❌ {sym} پیدا نشد. مثال: BTC، ETH، SOL، TON")
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


def IRAN_FA_LABEL(sym):
    from prices import IRAN_FA
    import bot as _
    m = {
        "USD": "dollar", "EUR": "euro", "GBP": "pound", "USDT": "usdt",
        "GOLD": "gold_18", "COIN": "coin_emami", "EMAMI": "coin_emami",
        "BAHAR": "coin_bahar", "HALF": "coin_half", "QUARTER": "coin_quarter",
        "GERAMI": "coin_gerami",
    }
    key = m.get(sym)
    return prices.IRAN_FA.get(key, sym)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """اگه کاربر فقط یه ارز تایپ کنه (بدون دستور)."""
    t = update.message.text.strip().upper()
    known = {"USD", "EUR", "GBP", "USDT", "GOLD", "COIN", "EMAMI", "BAHAR", "BTC", "ETH", "SOL", "TON", "XRP", "DOGE", "TRX", "SHIB", "ADA", "BNB", "LTC"}
    if t in known:
        await cmd_price(update, ctx, args=[t]) if False else None
        # ساده‌تر: مستقیم قیمت بده
        if t in {"USD","EUR","GBP","USDT","GOLD","COIN","EMAMI","BAHAR"}:
            fake_args = [t]
            class FakeCtx:
                pass
            # می‌سازیم ساده
            m = prices.get_iran()
            keymap = {"USD":"dollar","EUR":"euro","GBP":"pound","USDT":"usdt","GOLD":"gold_18","COIN":"coin_emami","EMAMI":"coin_emami","BAHAR":"coin_bahar"}
            k = keymap.get(t)
            if k and k in m:
                await update.message.reply_text(f"{prices.IRAN_FA[k]}: `{m[k]:,}` تومان", parse_mode=ParseMode.MARKDOWN)
                return
        await cmd_price.__wrapped__ if hasattr(cmd_price, "__wrapped__") else None
        # کریپتو
        msg = prices.crypto_message(symbol=t)
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


def main():
    if not TOKEN:
        print("❌ متغیر محیطی BOT_TOKEN ست نشده.")
        raise SystemExit(1)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("iran", cmd_iran))
    app.add_handler(CommandHandler("crypto", cmd_crypto))
    app.add_handler(CommandHandler("all", cmd_all))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Bot started (polling)")
    app.run_polling()


if __name__ == "__main__":
    main()

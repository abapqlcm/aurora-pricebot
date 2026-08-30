"""
AuroraPriceBot v2 — ربات گفتگویی با کارت تصویری
کاربر تایپ می‌کنه: «دلار» → کارت قشنگ قیمت
کاربر تایپ می‌کنه: «125 دلار» → کارت محاسبه
هیچ دستوری لازم نیست.
"""
import os
import logging

from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import prices
import render
from render import parse_input, calc_message, single_message, render_calc_card, render_single_card, iran_rows, crypto_rows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ.get("BOT_TOKEN", "")

WELCOME = (
    "👋 سلام! خوش اومدی\n\n"
    "من قیمت لحظه‌ای همه‌چیز رو بلدم:\n\n"
    "💵 دلار، یورو، پوند، درهم، لیر و ۴۰+ ارز دیگه\n"
    "🥇 طلا، سکه امامی، بهار آزادی، نیم و ربع‌سکه\n"
    "🪙 تتر داخلی\n"
    "🌐 بیت‌کوین، اتریوم و ۵۰۰+ رمزارز\n\n"
    "✍️ *چطوری؟*\n"
    "فقط بنویس: `دلار`\n"
    "یا بپرس: `125 دلار چند تومنه؟`\n"
    "یا: `2 گرم طلا`\n\n"
    "همین! هیچ دستوری لازم نیست 😎"
)


async def send_card(update: Update, png: bytes, caption: str = ""):
    """ارسال کارت تصویری."""
    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    await update.message.reply_photo(photo=png, caption=caption, parse_mode=ParseMode.MARKDOWN)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """هندلر اصلی — هر پیام متنی."""
    text = update.message.text.strip()
    if not text:
        return

    # /start و /help
    if text.startswith("/start") or text.startswith("/help"):
        await update.message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)
        return

    # «همه» / «قیمت ها» / «قیمت‌ها»
    if text in {"همه", "قیمت ها", "قیمت‌ها", "همه قیمت ها", "همه قیمت‌ها", "لیست"}:
        await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
        rows = iran_rows()
        png = render.render_price_card(rows, title="بازار ایران", subtitle="قیمت لحظه‌ای")
        await update.message.reply_photo(photo=png)
        return

    # رمزارزها
    if text in {"کریپتو", "رمزارز", "رمزارزها", "ارز دیجیتال", "ارزهای دیجیتال"}:
        await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
        rows = crypto_rows(limit=12)
        png = render.render_price_card(rows, title="رمزارزها", subtitle="دلاری")
        await update.message.reply_photo(photo=png)
        return

    # پارس ورودی
    kind, data = parse_input(text)

    if kind == "single":
        key = data
        png = render_single_card(key)
        if png:
            await send_card(update, png)
            return
    elif kind == "calc":
        key, amount = data
        png = render_calc_card(key, amount)
        if png:
            await send_card(update, png)
            return
        # fallback متن
        msg = calc_message(key, amount)
        if msg:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
            return

    # نفهمید
    await update.message.reply_text(
        "🤔 نفهمیدم چی خواستی.\n\n"
        "مثال‌ها:\n"
        "• `دلار`\n"
        "• `یورو`\n"
        "• `طلا`\n"
        "• `سکه`\n"
        "• `بیت کوین`\n"
        "• `125 دلار`\n"
        "• `2 گرم طلا`",
        parse_mode=ParseMode.MARKDOWN,
    )


def main():
    if not TOKEN:
        print("❌ BOT_TOKEN ست نشده.")
        raise SystemExit(1)
    app = Application.builder().token(TOKEN).build()
    # هیچ CommandHandler نیست — همه‌چیز متن عادی
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.COMMAND, on_text))  # /start هم می‌گیره
    log.info("AuroraPriceBot v2 started (conversational)")
    app.run_polling()


if __name__ == "__main__":
    main()

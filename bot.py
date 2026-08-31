"""
AuroraPriceBot v5 — ربات گفتگویی کامل
کاربر تایپ می‌کنه: «دلار»، «طلا»، «بیت کوین»، «125 دلار»، «2 گرم طلا»...
ربات بنر تصویری حرفه‌ای می‌فرسته.
"""
import os
import logging

from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import catalog
import datafeeds
import banner
import render

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ.get("BOT_TOKEN", "")

WELCOME = (
    "👋 سلام! خوش اومدی\n\n"
    "من قیمت لحظه‌ای همه‌چیز رو بلدم:\n\n"
    "💵 دلار، یورو، پوند، درهم، لیر، دینار، فرانک و ۲۰+ ارز دیگه\n"
    "🥇 طلا، سکه امامی، بهار آزادی، نیم و ربع‌سکه\n"
    "🪙 تتر داخلی\n"
    "🌐 بیت‌کوین، اتریوم و ۳۰+ رمزارز\n\n"
    "✍️ *چطوری؟*\n"
    "فقط بنویس: `دلار` یا `طلا` یا `بیت کوین`\n"
    "یا بپرس: `125 دلار چند تومنه؟`\n"
    "یا: `2 گرم طلا`\n\n"
    "همین! هیچ دستور لازم نیست 😎"
)


async def send_card(update: Update, png: bytes, caption: str = ""):
    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    await update.message.reply_photo(photo=png, caption=caption, parse_mode=ParseMode.MARKDOWN)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        return

    # /start و /help
    if text.startswith("/start") or text.startswith("/help"):
        await update.message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)
        return

    # «همه» / «قیمت ها» → کارت کامل بازار ایران
    if text in {"همه", "قیمت ها", "قیمت‌ها", "همه قیمت ها", "همه قیمت‌ها", "لیست", "قیمت"}:
        await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
        rows = []
        for k, (name, _, _) in catalog.FIAT.items():
            d = datafeeds.get_banner_data(k)
            if d and d.get("price"):
                rows.append((name, f"{d['price']:,} تومان", None))
        png = render.render_price_card(rows, title="بازار ایران", subtitle="قیمت لحظه‌ای")
        if png:
            await update.message.reply_photo(photo=png)
            return

    # «کریپتو» / «رمزارز» → کارت رمزارزها
    if text in {"کریپتو", "رمزارز", "رمزارزها", "ارز دیجیتال", "ارزهای دیجیتال", "کریپتوها"}:
        await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
        rows = []
        for k, (name, _, _) in catalog.CRYPTO.items():
            d = datafeeds.get_banner_data(k)
            if d and d.get("price"):
                rows.append((name, f"${d['price']:,.2f}", None))
        png = render.render_price_card(rows[:12], title="رمزارزها", subtitle="دلاری")
        if png:
            await update.message.reply_photo(photo=png)
            return

    # پارس ورودی
    kind, data = render.parse_input(text)

    if kind == "single":
        key = data
        png = banner.render_banner(key)
        if png:
            await send_card(update, png)
            return
        await update.message.reply_text(
            f"❌ قیمت {key} پیدا نشد. مثال: `دلار`، `طلا`، `بیت کوین`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if kind == "calc":
        key, amount = data
        png = render.render_calc_card(key, amount)
        if png:
            await send_card(update, png)
            return
        # fallback متن
        msg = render.calc_message(key, amount)
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
        "• `2 گرم طلا`\n\n"
        "ارزهای پشتیبانی‌شده: دلار، یورو، پوند، درهم، لیر، فرانک، دینار، یوان، ین، روبل، تتر، طلا، سکه و ۳۰+ رمزارز",
        parse_mode=ParseMode.MARKDOWN,
    )


async def on_error(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """هر خطایی لاگ بشه + به کاربر بگم."""
    err = ctx.error
    log.error("handler error: %s", err)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ یه خطای داخلی پیش اومد. دوباره تلاش کن یا اسم ارز رو دقیق‌تر بفرست.",
            )
        except Exception:
            pass


    def main():
        if not TOKEN:
            print("❌ BOT_TOKEN ست نشده.")
            raise SystemExit(1)
        app = Application.builder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
        app.add_handler(MessageHandler(filters.COMMAND, on_text))
        app.add_error_handler(on_error)
        log.info("AuroraPriceBot v5 started (conversational)")
        app.run_polling()


if __name__ == "__main__":
    main()

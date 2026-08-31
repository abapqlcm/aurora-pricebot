"""
AuroraPriceBot v5 — ربات گفتگویی کامل
کاربر تایپ می‌کنه: «دلار»، «طلا»، «بیت کوین»، «125 دلار»، «2 گرم طلا»...
ربات بنر تصویری حرفه‌ای می‌فرسته.
"""
import os
import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import render
import banner
import datafeeds

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "")


async def on_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """دستور /start."""
    await update.message.reply_text(
        "سلام! 👋\n\n"
        "من **AuroraPriceBot** هستم — ربات قیمت لحظه‌ای ارزها و رمزارزها.\n\n"
        "**چطوری استفاده کنم:**\n"
        "• اسم ارز رو بنویس: `دلار`، `یورو`، `طلا`، `بیت‌کوین`\n"
        "• یا عدد + ارز: `125 دلار`، `2 گرم طلا`\n"
        "• من بنر قیمت تصویری برات می‌فرستم\n\n"
        "**ارزهای موجود:**\n"
        "💵 **دلار، یورو، پوند، درهم، لیر، فرانک، دینار...**\n"
        "🥇 **طلا (۱۸ و ۲۴)، سکه امامی، بهار، نیم، ربع، گرمی**\n"
        "💎 **تتر (USDT)**\n"
        "🪙 **بیت‌کوین، اتریوم، سولانا، تون، دوج، شیبا و ۲۴ کریپتوی دیگر**\n\n"
        "بیا شروع کن! 🚀",
        parse_mode="Markdown"
    )


async def _prefetch(ctx: ContextTypes.DEFAULT_TYPE, keys: list):
    """دیتای ارزهای محبوب رو از قبل بگیره تا جواب بعدی فوری باشه."""
    import asyncio
    def _job():
        for k in keys:
            try:
                datafeeds.get_banner_data(k)
            except Exception:
                pass
    asyncio.get_running_loop().run_in_executor(None, _job)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """کاربر متن فرستاد — پردازش و جواب."""
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    await update.message.chat.send_action("upload_photo")  # "uploading..."
    
    try:
        # پارس ورودی
        kind, data = render.parse_input(text)
        
        if kind is None:
            # ورودی نامعلوم
            import catalog
            all_names = list(catalog.FIAT.keys()) + list(catalog.GOLD.keys()) + list(catalog.STABLE.keys()) + list(catalog.CRYPTO.keys())
            reply = f"🤔 متوجه نشدم.\n\nمثال‌های معتبر:\n• دلار، یورو، طلا، بیت‌کوین\n• ۱۲۵ دلار، ۲ گرم طلا\n• ۰.۰۱ بیت‌کوین"
            await update.message.reply_text(reply)
            return
        
        if kind == "single":
            # اسم ارز تک — بنر + کپشن زنده در یک پیام
            key = data
            d = datafeeds.get_banner_data(key)
            png = banner.render_banner(key)
            if png and d:
                unit = d.get("unit", "تومان")
                price = d.get("price") or 0
                pct = d.get("change_pct") or 0
                
                if unit == "تومان" and key != "usdt":
                    # فیات/طلا/سکه (نه تتر)
                    cap = (
                        f"⭐️ 1 {d['name']} = *{render.fmt_num(price)} تومان*\n"
                        f"*{pct:+.2f}%*\n"
                        f"🕐 بروزرسانی: {render._now_fa()}"
                    )
                else:
                    # کریپتو یا تتر: قیمت + درصد + محدوده High/Low (24h)
                    ohlcv = d.get("ohlcv", [])
                    high_24 = max(x[1] for x in ohlcv) if ohlcv else price
                    low_24 = min(x[2] for x in ohlcv) if ohlcv else price
                    
                    # برای تتر: نمایش به تومان
                    if unit == "تومان" and key == "usdt":
                        cap = (
                            f"⭐️ 1 {d['name']} = *{render.fmt_num(int(price))} تومان*\n"
                            f"*{pct:+.2f}%*\n"
                            f"\n📊 **محدوده ۲۴ ساعت:**\n"
                            f"> 🔼 بالاترین: {render.fmt_num(int(high_24))} تومان\n"
                            f"> 🔽 پایین‌ترین: {render.fmt_num(int(low_24))} تومان\n"
                            f"\n🕐 بروزرسانی: {render._now_fa()}"
                        )
                    else:
                        # دیگر کریپتوها: USD
                        cap = (
                            f"⭐️ 1 {d['name']} = *${render.fmt_num(price)}*\n"
                            f"*{pct:+.2f}%*\n"
                            f"\n📊 **محدوده ۲۴ ساعت:**\n"
                            f"> 🔼 بالاترین: ${render.fmt_num(high_24)}\n"
                            f"> 🔽 پایین‌ترین: ${render.fmt_num(low_24)}\n"
                            f"\n🕐 بروزرسانی: {render._now_fa()}"
                        )
                await update.message.reply_photo(png, caption=cap, parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ نتونستم قیمت {key} رو بگیرم.")
            # دیتای بعدی از قبل آماده شه
            await _prefetch(ctx, ["dollar", "BTC", "gold_18", "usdt", "euro"])
        
        elif kind == "calc":
            # محاسبه: amount × ارز — بنر + کپشن (همه در یک پیام)
            key, amount = data
            d = datafeeds.get_banner_data(key)
            png = banner.render_banner(key)
            if png and d:
                unit = d.get("unit", "تومان")
                price = d.get("price") or 0
                total = amount * price
                if unit == "تومان":
                    cap = (
                        f"⭐️ 1 {d['name']} = {render.fmt_num(price)} تومان\n"
                        f"💱 {render.fmt_num(render._nice(amount))} {d['name']} = {render.fmt_num(int(total))} تومان\n"
                        f"🕐 بروزرسانی: {render._now_fa()}"
                    )
                else:
                    cap = (
                        f"⭐️ 1 {d['name']} = ${render.fmt_num(price)}\n"
                        f"💱 {render.fmt_num(render._nice(amount))} {d['name']} = ${render.fmt_num(round(total, 2))}\n"
                        f"🕐 بروزرسانی: {render._now_fa()}"
                    )
                await update.message.reply_photo(png, caption=cap)
            else:
                await update.message.reply_text(f"❌ نتونستم قیمت {key} رو بگیرم.")
    
    except Exception as e:
        log.error("on_text error: %s", e, exc_info=True)
        await update.message.reply_text(
            "⚠️ یه خطای داخلی پیش اومد. دوباره تلاش کن یا اسم ارز رو دقیق‌تر بفرست."
        )


async def on_error(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """هر خطایی لاگ بشه + به کاربر بگم."""
    err = ctx.error
    log.error("handler error: %s", err, exc_info=True)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ یه خطای داخلی پیش اومد. دوباره تلاش کن.",
            )
        except Exception:
            pass


def main():
    """شروع ربات."""
    if not TOKEN:
        print("❌ BOT_TOKEN ست نشده.")
        raise SystemExit(1)
    
    app = Application.builder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(MessageHandler(filters.COMMAND, on_start))  # /start + /help و...
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))  # متن عادی
    app.add_error_handler(on_error)
    
    log.info("🚀 AuroraPriceBot v5 started (conversational)")
    app.run_polling()


if __name__ == "__main__":
    main()

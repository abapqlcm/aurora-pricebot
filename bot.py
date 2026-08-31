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

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "")


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
            all_names = list(catalog.FIAT_FA.keys()) + list(catalog.GOLD_FA.keys()) + list(catalog.STABLE_FA.keys()) + list(catalog.CRYPTO_FA.keys())
            reply = f"🤔 متوجه نشدم.\n\nمثال‌های معتبر:\n• دلار، یورو، طلا، بیت‌کوین\n• ۱۲۵ دلار، ۲ گرم طلا\n• ۰.۰۱ بیت‌کوین"
            await update.message.reply_text(reply)
            return
        
        if kind == "single":
            # اسم ارز تک — بنر
            key = data
            png = banner.render_banner(key)
            if png:
                await update.message.reply_photo(png)
            else:
                await update.message.reply_text(f"❌ نتونستم بنر {key} رو بسازم.")
        
        elif kind == "calc":
            # محاسبه: amount × ارز
            key, amount = data
            # ۱) بنر
            png = banner.render_banner(key)
            if png:
                await update.message.reply_photo(png)
            else:
                await update.message.reply_text(f"❌ نتونستم بنر {key} رو بسازم.")
            
            # ۲) متن محاسبه
            msg = render.calc_message(key, amount)
            if msg:
                await update.message.reply_text(msg, parse_mode="Markdown")
    
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    
    log.info("🚀 AuroraPriceBot v5 started (conversational)")
    app.run_polling()


if __name__ == "__main__":
    main()

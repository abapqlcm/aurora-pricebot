"""
AuroraPriceBot v6 — ربات گفتگویی کامل (thread-safe)
کاربر تایپ می‌کنه: «دلار»، «طلا»، «بیت کوین»، «125 دلار»، «2 گرم طلا»...
ربات بنر تصویری حرفه‌ای می‌فرسته.
"""
import os
import logging
import time
import threading

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters

import render
import banner
import datafeeds

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "")


async def on_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """دستور /start."""
    # ۶. دکمه‌های کوتاه (Inline buttons)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 جستجو", callback_data="help_search"),
            InlineKeyboardButton("📊 کریپتو", callback_data="show_crypto"),
        ],
        [
            InlineKeyboardButton("🥇 طلا", callback_data="show_gold"),
            InlineKeyboardButton("💱 ارزها", callback_data="show_fiat"),
        ],
    ])
    
    await update.message.reply_text(
        "سلام! 👋\n\n"
        "من **AuroraPriceBot** هستم — ربات قیمت لحظه‌ای ارزها و رمزارزها.\n\n"
        "**چطوری استفاده کنم:**\n"
        "• اسم ارز رو بنویس: `دلار`، `یورو`، `طلا`، `بیت‌کوین`\n"
        "• یا عدد + ارز: `125 دلار`، `2 گرم طلا`\n"
        "• من بنر قیمت تصویری برات می‌فرستم\n\n"
        "**ارزهای موجود:**\n"
        "💵 **۶۵ ارز فیات** (دلار، یورو، پوند، درهم...)\n"
        "🥇 **طلا و سکه** (۱۸، ۲۴، امامی، بهار، نیم، ربع، گرمی)\n"
        "💎 **تتر (USDT)**\n"
        "🪙 **۲۹ کریپتو** (بیت‌کوین، اتریوم، سولانا، و...)\n\n"
        "بیا شروع کن! 🚀",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def on_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """دستور /ping — Real ping (TCP خالص) + Telegram ping (TLS+DNS)."""
    import asyncio
    import socket
    import ssl

    def _real_ping():
        # فقط زمان اتصال TCP (بدون DNS/TLS) — خالص‌ترین پینگ
        t0 = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect(("149.154.167.220", 443))  # سرور تلگرام
            return (time.time() - t0) * 1000
        except Exception:
            return None
        finally:
            s.close()

    def _telegram_ping():
        # TLS handshake + DNS lookup
        t0 = time.time()
        ctx = ssl.create_default_context()
        try:
            with socket.create_connection(("api.telegram.org", 443), timeout=5) as raw:
                with ctx.wrap_socket(raw, server_hostname="api.telegram.org") as s:
                    return (time.time() - t0) * 1000
        except Exception:
            return None

    try:
        loop = asyncio.get_running_loop()
        real, tg = await asyncio.gather(
            loop.run_in_executor(None, _real_ping),
            loop.run_in_executor(None, _telegram_ping)
        )
        msg = "⚡ Real ping: "
        msg += f"{real:.0f}ms" if real is not None else "N/A"
        msg += "\n\n⚡ Telegram ping: "
        msg += f"{tg:.0f}ms" if tg is not None else "N/A"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Ping failed: {e}")

async def _prefetch(ctx: ContextTypes.DEFAULT_TYPE, keys: list):
    """دیتای ارزهای محبوب رو از قبل بگیره تا جواب بعدی فوری باشه."""
    import asyncio
    def _job():
        for k in keys:
            try:
                datafeeds.get_banner_data(k)
                banner.render_banner(k)
            except Exception:
                pass
    asyncio.get_running_loop().run_in_executor(None, _job)


HOT_KEYS = ["dollar", "euro", "BTC", "usdt", "gold_18", "pound", "try", "aed", "SOL", "ETH"]

# ۱۲. قفل کلی برای دسترسی‌های هم‌زمان به کش‌ها/فایل‌ها (thread-safe)
_warm_lock = threading.Lock()


async def _warm_loop(ctx: ContextTypes.DEFAULT_TYPE):
    """هر ۱۰ ثانیه ارزهای محبوب رو از قبل رندر می‌کنه — جواب کاربر همیشه <1s.
    با lock + stagger: هر بار فقط یه key، بدون فشار به APIها."""
    import asyncio
    idx = 0
    while True:
        try:
            k = HOT_KEYS[idx % len(HOT_KEYS)]
            idx += 1

            def _job(key=k):
                if not _warm_lock.acquire(blocking=False):
                    return  # قبلی هنوز در حال اجراست — skip (بدون صف)
                try:
                    datafeeds.get_banner_data(key)
                    banner.render_banner(key)
                except Exception:
                    pass
                finally:
                    _warm_lock.release()

            await asyncio.get_running_loop().run_in_executor(None, _job)
        except Exception as e:
            log.warning("warm loop: %s", e)
        await asyncio.sleep(10)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """کاربر متن فرستاد — پردازش و جواب."""
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    log.info(f"input: {text}")
    
    # پینگ بدون اسلش هم کار کنه
    if text.lower() in ("ping", "پینگ", "پنگ"):
        await on_ping(update, ctx)
        return
    
    try:
        # پارس ورودی
        kind, data = render.parse_input(text)
        log.info(f"parsed: kind={kind}")
        
        if kind is None:
            # ورودی نامعلوم — فوری return (بدون fetch، بدون typing)
            log.info(f"unknown input, returning")
            return
        
        # فقط اگه ورودی معتبره: جواب (بدون typing indicator — Telegram خودش عکس رو نشون می‌ده)
        log.info(f"valid input, sending")
        
        # ۱۰. fetch+render در thread جدا — event loop بلاک نشه (سرعت)
        import asyncio
        loop = asyncio.get_running_loop()
        
        if kind == "single":
            # اسم ارز تک — بنر + کپشن + دکمه‌های کارت انتقالی
            key = data
            # ۵. ویدیو (نمودار متحرک) — اول امتحان کن، فیلد شد PNG
            import asyncio as _aio
            loop2 = _aio.get_running_loop()
            vid = await loop2.run_in_executor(None, banner.render_banner_video, key)
            if vid:
                d0 = await loop2.run_in_executor(None, datafeeds.get_banner_data, key)
                await update.message.reply_video(
                    vid,
                    caption=_caption_for(key, d0),
                    parse_mode="HTML",
                    reply_markup=_carousel_kb(key),
                    supports_streaming=True,
                )
            else:
                await send_price_card(update, key, edit=False)
            # دیتای بعدی از قبل آماده شه
            await _prefetch(ctx, ["dollar", "BTC", "gold_18", "usdt", "euro"])

        elif kind == "market":
            # ۱۰. کارت «بازار امروز» — گرید چند ارز
            loop_m = _aio.get_running_loop()
            mpng = await loop_m.run_in_executor(None, banner.render_market_card)
            if mpng:
                await update.message.reply_photo(mpng, caption="📊 <b>بازار امروز</b> — برگ برنده‌ها، طلای روز و کریپتو", parse_mode="HTML")
            else:
                await update.message.reply_text("❌ دیتای بازار در دسترس نیست.")
        
        elif kind == "calc":
            # محاسبه: amount × ارز — بنر + کپشن (همه در یک پیام)
            key, amount = data
            d = await loop.run_in_executor(None, datafeeds.get_banner_data, key)
            png = await loop.run_in_executor(None, banner.render_banner, key)
            if png and d:
                unit = d.get("unit", "تومان")
                price = d.get("price") or 0
                total = amount * price
                if unit == "تومان":
                    cap = (
                        f"⭐️ 1 {d['name']} = <b>{render.fmt_num(price)}</b>\n"
                        f"💱 {render.fmt_num(render._nice(amount))} {d['name']} = <b>{render.fmt_num(int(total))}</b>\n"
                        f"🕐 Update: {render._now_en()}"
                    )
                else:
                    cap = (
                        f"⭐️ 1 {d['name']} = <b>${render.fmt_num(price)}</b>\n"
                        f"💱 {render.fmt_num(render._nice(amount))} {d['name']} = <b>${render.fmt_num(round(total, 2))}</b>\n"
                        f"🕐 Update: {render._now_en()}"
                    )
                await update.message.reply_photo(png, caption=cap, parse_mode="HTML")
            else:
                await update.message.reply_text(f"❌ نتونستم قیمت {key} رو بگیرم.")
    
    except Exception as e:
        log.error("on_text error: %s", e, exc_info=True)
        await update.message.reply_text(
            "⚠️ یه خطای داخلی پیش اومد. دوباره تلاش کن یا اسم ارز رو دقیق‌تر بفرست."
        )


# ۱۵. کارت انتقالی — چرخه ارزهای محبوب برای دکمه‌های ◀️ ▶️
CAROUSEL = ["dollar", "euro", "pound", "usdt", "BTC", "ETH", "gold_18"]


def _carousel_kb(current: str):
    """دکمه‌های ◀️ ▶️ برای ورق‌زدن کارت‌ها."""
    try:
        i = CAROUSEL.index(current)
    except ValueError:
        i = 0
    prev = CAROUSEL[(i - 1) % len(CAROUSEL)]
    nxt = CAROUSEL[(i + 1) % len(CAROUSEL)]
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️", callback_data=f"card:{prev}"),
        InlineKeyboardButton(f"{i + 1}/{len(CAROUSEL)}", callback_data="card:noop"),
        InlineKeyboardButton("▶️", callback_data=f"card:{nxt}"),
    ]])


def _caption_for(key: str, d: dict | None) -> str:
    """کپشن مشترک برای ویدیو/بنر."""
    if not d:
        return "⭐️ AuroraPriceBot"
    unit = d.get("unit", "تومان")
    price = d.get("price") or 0
    pct = d.get("change_pct") or 0
    if unit != "تومان":
        ohlcv = d.get("ohlcv", [])
        high_24 = max(x[1] for x in ohlcv) if ohlcv else price
        low_24 = min(x[2] for x in ohlcv) if ohlcv else price
        return (
            f"⭐️ 1 {d['name']} = <b>${render.fmt_num(price)}</b>\n"
            f"<b>{pct:+.2f}%</b>\n"
            f"\n📊 <b>24H High & Low:</b>\n"
            f"<blockquote>🔼 High: ${render.fmt_num(high_24)}\n"
            f"🔽 Low: ${render.fmt_num(low_24)}</blockquote>\n"
            f"\n🕐 Update: {render._now_en()}"
        )
    if key == "usdt":
        ohlcv = d.get("ohlcv", [])
        high_24 = max(x[1] for x in ohlcv) if ohlcv else price
        low_24 = min(x[2] for x in ohlcv) if ohlcv else price
        return (
            f"⭐️ 1 {d['name']} = <b>{render.fmt_num(int(price))}</b>\n"
            f"<b>{pct:+.2f}%</b>\n"
            f"\n📊 <b>24H High & Low:</b>\n"
            f"<blockquote>🔼 High: {render.fmt_num(int(high_24))}\n"
            f"🔽 Low: {render.fmt_num(int(low_24))}</blockquote>\n"
            f"\n🕐 Update: {render._now_en()}"
        )
    return (
        f"⭐️ 1 {d['name']} = <b>{render.fmt_num(price)}</b>\n"
        f"<b>{pct:+.2f}%</b>\n"
        f"🕐 Update: {render._now_en()}"
    )


async def send_price_card(update_or_query, key: str, edit=False):
    """بنر + کپشن + دکمه‌های ورق‌زدن — برای پیام جدید یا ویرایش (transition)."""
    import asyncio
    loop = asyncio.get_running_loop()
    d = await loop.run_in_executor(None, datafeeds.get_banner_data, key)
    png = await loop.run_in_executor(None, banner.render_banner, key)
    if not png or not d:
        msg = f"❌ نتونستم قیمت {key} رو بگیرم."
        if edit and hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text(msg)
        else:
            await update_or_query.message.reply_text(msg)
        return
    cap = _caption_for(key, d)
    kb = _carousel_kb(key)
    if edit:
        try:
            media = InputMediaPhoto(png, caption=cap, parse_mode="HTML")
            await update_or_query.edit_message_media(media=media, reply_markup=kb)
        except Exception:
            # fallback: پیام جدید اگه ویرایش ممکن نبود
            await update_or_query.message.reply_photo(png, caption=cap, parse_mode="HTML", reply_markup=kb)
    else:
        await update_or_query.message.reply_photo(png, caption=cap, parse_mode="HTML", reply_markup=kb)


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


async def on_button_click(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """هندلر دکمه‌های Inline شروع + کارت انتقالی ◀️ ▶️."""
    query = update.callback_query
    
    # ۱۵. کارت انتقالی — ورق‌زدن کارت‌ها بدون پیام جدید
    if query.data and query.data.startswith("card:"):
        key = query.data[5:]
        if key == "noop":
            await query.answer()
            return
        await query.answer()  # لود indicator سریع
        try:
            await send_price_card(query, key, edit=True)
        except Exception as e:
            log.error("carousel edit: %s", e)
            try:
                await query.answer("⚠️ خطا — دوباره تلاش کن", show_alert=False)
            except Exception:
                pass
        return
    
    await query.answer()  # لود indicator
    
    if query.data == "show_crypto":
        # بنر کریپتو (محبوب‌ترین) — با کارت انتقالی
        await send_price_card(query, "BTC", edit=True)
    elif query.data == "show_gold":
        await send_price_card(query, "gold_18", edit=True)
    elif query.data == "show_fiat":
        await send_price_card(query, "dollar", edit=True)
    elif query.data == "help_search":
        await query.edit_message_text("🔍 جستجو: اسم ارز رو بنویس یا `شماره ارز`")


async def _post_init(application):
    """بعد از استارت: warm loop رو بنداز تو پس‌زمینه."""
    application.create_task(_warm_loop(application))


def main():
    """شروع ربات."""
    if not TOKEN:
        print("❌ BOT_TOKEN ست نشده.")
        raise SystemExit(1)
    
    app = Application.builder().token(TOKEN).post_init(_post_init).concurrent_updates(True).build()
    
    # Handlers
    app.add_handler(CommandHandler("ping", on_ping))  # /ping
    app.add_handler(CommandHandler("start", on_start))  # /start
    app.add_handler(CallbackQueryHandler(on_button_click))  # دکمه‌های Inline
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))  # متن عادی
    app.add_error_handler(on_error)
    
    log.info("🚀 AuroraPriceBot v6 started (fast warm-cache)")
    app.run_polling()


if __name__ == "__main__":
    main()

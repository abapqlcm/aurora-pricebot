"""
AuroraPriceBot v6 — ربات گفتگویی کامل (thread-safe)
کاربر تایپ می‌کنه: «دلار»، «طلا»، «بیت کوین»، «125 دلار»، «2 گرم طلا»...
ربات بنر تصویری حرفه‌ای می‌فرسته.
"""
import os
import logging
import time
import threading
import asyncio
import subprocess

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaAnimation
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters

import render
import banner
import datafeeds
import admin

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
                with ctx.wrap_socket(raw, server_hostname="api.telegram.org"):
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
                # ۲۸. انیمیشن هم گرم — اولین کلیک هم آنی
                banner.render_banner_video(k)
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
                    # ۲۸. ویدیو/انیمیشن هم گرم کن — جواب دکمه/بنر = آنی
                    banner.render_banner_video(key)
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

    # 📊 پنل ادمین: ثبت کاربر/گروه (سبک — فقط شمارنده)
    try:
        admin.track_user(update.message.from_user)
        admin.track_group(update.message.chat)
    except Exception as e:
        log.warning("track: %s", e)

    # 📢 حالت broadcast ادمین؟
    try:
        if await on_broadcast_text(update, ctx):
            return
    except Exception as e:
        log.warning("broadcast: %s", e)
    
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
            log.info("unknown input, returning")
            return
        
        # فقط اگه ورودی معتبره: جواب (بدون typing indicator — Telegram خودش عکس رو نشون می‌ده)
        log.info("valid input, sending")
        
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
                # ۲۶. قیمت مچ: قیمتِ لحظه‌ی رندر ویدیو (کپشن = بنر، بدون مغایرت)
                v_price = banner.get_last_video_price(key)
                d0 = await loop2.run_in_executor(None, datafeeds.get_banner_data, key)
                # ۲۹. کریپتو: قیمت تومانی هم تو کپشن (تتر تومانی × قیمت دلاری)
                _toman = datafeeds.usdt_toman() if d0 and d0.get("unit") != "تومان" else None
                # ۲۳. حالت GIF: reply_animation — اتوپلی + لوپ بی‌نهایت (بدون دکمه‌ی پخش)
                # نکته: با bytes خام باید filename بدیم وگرنه تلگرام application/octet-stream نشون می‌ده!
                try:
                    await update.message.reply_animation(
                        vid,
                        filename="aurora_banner.mp4",
                        duration=2,
                        width=900,
                        height=950,
                        caption=_caption_for(key, d0, price_override=v_price, toman=_toman),
                        parse_mode="HTML",
                        reply_markup=_carousel_kb(key),
                    )
                except Exception as e_anim:
                    log.warning("animation send failed (%s) → video fallback", e_anim)
                    await update.message.reply_video(
                        vid,
                        filename="aurora_banner.mp4",
                        caption=_caption_for(key, d0, price_override=v_price, toman=_toman),
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
            # محاسبه: amount × ارز — بنر GIF متحرک + کپشن (همه در یک پیام)
            key, amount = data
            d = await loop.run_in_executor(None, datafeeds.get_banner_data, key)
            if d:
                vid = await loop.run_in_executor(None, banner.render_banner_video, key)
            else:
                vid = None
            if vid and d:
                unit = d.get("unit", "تومان")
                price = d.get("price") or 0
                total = amount * price
                # BUG-2 فیکس: کریپتوی کوچک (SHIB) قبلاً «$0» می‌شد → دقت داینامیک
                if unit == "تومان":
                    cap = (
                        f"⭐️ 1 {d['name']} = <b>{render.fmt_num(price)}</b>\n"
                        f"💱 {render.fmt_num(render._nice(amount))} {d['name']} = <b>{render.fmt_num(int(total))}</b>\n"
                        f"🕐 Update: {render._now_en()}"
                    )
                else:
                    cap = (
                        f"⭐️ 1 {d['name']} = <b>${render.fmt_num(price)}</b>\n"
                        f"💱 {render.fmt_num(render._nice(amount))} {d['name']} = <b>${render.fmt_num(total)}</b>\n"
                        f"🕐 Update: {render._now_en()}"
                    )
                try:
                    await update.message.reply_animation(
                        vid,
                        filename="aurora_banner.mp4",
                        duration=2,
                        width=900,
                        height=950,
                        caption=cap,
                        parse_mode="HTML",
                    )
                except Exception as e_anim:
                    log.warning("calc animation failed (%s) → photo", e_anim)
                    png = await loop.run_in_executor(None, banner.render_banner, key)
                    if png:
                        await update.message.reply_photo(png, caption=cap, parse_mode="HTML")
            elif d:
                # ویدیو نبود → عکس ثابت (مسیر قبلی)
                png = await loop.run_in_executor(None, banner.render_banner, key)
                if png:
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
                            f"💱 {render.fmt_num(render._nice(amount))} {d['name']} = <b>${render.fmt_num(total)}</b>\n"
                            f"🕐 Update: {render._now_en()}"
                        )
                    await update.message.reply_photo(png, caption=cap, parse_mode="HTML")
                else:
                    await update.message.reply_text(f"❌ نتونستم قیمت {key} رو بگیرم.")
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


def _caption_for(key: str, d: dict | None, price_override=None, toman: float | None = None) -> str:
    """کپشن مشترک برای ویدیو/بنر. price_override → قیمت دقیق همون لحظه‌ی بنر.
    toman → قیمت تومانی (برای کریپتوهای دلاری — کاربر خواست)."""
    if not d:
        return "⭐️ AuroraPriceBot"
    unit = d.get("unit", "تومان")
    price = price_override if price_override is not None else (d.get("price") or 0)
    pct = d.get("change_pct") or 0
    if unit != "تومان":
        ohlcv = d.get("ohlcv", [])
        high_24 = max(x[1] for x in ohlcv) if ohlcv else price
        low_24 = min(x[2] for x in ohlcv) if ohlcv else price
        # ۲۹. خط تومانی برای کریپتو (قیمت لحظه‌ای تتر تومانی × قیمت دلاری)
        toman_line = ""
        if toman:
            toman_line = f"\n≈ <b>{render.fmt_num(int(round(price * toman)))} تومان</b>"
        return (
            f"⭐️ 1 {d['name']} = <b>${render.fmt_num(price)}</b>{toman_line}\n"
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
    """بنر GIF متحرک + کپشن + دکمه‌های ورق‌زدن — پیام جدید یا ویرایش (transition).
    همیشه animation می‌فرسته؛ فقط اگه ویدیو نبود عکس ثابت (fallback)."""
    import asyncio
    loop = asyncio.get_running_loop()
    d = await loop.run_in_executor(None, datafeeds.get_banner_data, key)
    vid = await loop.run_in_executor(None, banner.render_banner_video, key)
    if not d:
        msg = f"❌ نتونستم قیمت {key} رو بگیرم."
        if edit and hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text(msg)
        else:
            await update_or_query.message.reply_text(msg)
        return
    # ۲۶. قیمت مچ: کپشن = قیمتِ لحظه‌ی رندر ویدیو
    v_price = banner.get_last_video_price(key)
    # ۲۹. کریپتو: قیمت تومانی هم تو کپشن
    _toman = datafeeds.usdt_toman() if d.get("unit") != "تومان" else None
    cap = _caption_for(key, d, price_override=v_price, toman=_toman)
    kb = _carousel_kb(key)
    if vid:
        if edit:
            try:
                media = InputMediaAnimation(
                    vid,
                    filename="aurora_banner.mp4",
                    duration=2, width=900, height=950,
                    caption=cap, parse_mode="HTML",
                )
                await update_or_query.edit_message_media(media=media, reply_markup=kb)
                return
            except Exception as e_edit:
                log.warning("edit→animation failed (%s) → new msg", e_edit)
                # ویرایش ممکن نبود (مثلا پیام قبلی عکسه) → پیام جدید بفرست
        try:
            await update_or_query.message.reply_animation(
                vid,
                filename="aurora_banner.mp4",
                duration=2, width=900, height=950,
                caption=cap, parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception as e_anim:
            log.warning("animation send failed (%s) → photo", e_anim)
            png = await loop.run_in_executor(None, banner.render_banner, key)
            if edit:
                await update_or_query.message.reply_photo(png, caption=cap, parse_mode="HTML", reply_markup=kb)
            else:
                await update_or_query.message.reply_photo(png, caption=cap, parse_mode="HTML", reply_markup=kb)
        return
    # fallback: عکس ثابت
    png = await loop.run_in_executor(None, banner.render_banner, key)
    if not png:
        msg = f"❌ نتونستم قیمت {key} رو بگیرم."
        if edit and hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text(msg)
        else:
            await update_or_query.message.reply_text(msg)
        return
    if edit:
        try:
            media = InputMediaPhoto(png, caption=cap, parse_mode="HTML")
            await update_or_query.edit_message_media(media=media, reply_markup=kb)
            return
        except Exception:
            pass
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
        await query.edit_message_text("🔍 جستجو: اسم ارز رو بنویس، یا عدد و ارز مثل «125 دلار»")


async def _post_init(application):
    """بعد از استارت: warm loop رو بنداز تو پس‌زمینه."""
    application.create_task(_warm_loop(application))


# ================= پنل ادمین (فقط OWNER) =================

def _is_owner(update: Update) -> bool:
    u = update.effective_user
    return bool(u and u.id == admin.OWNER_ID)


def _admin_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 کاربران", callback_data="adm_users"),
         InlineKeyboardButton("👨‍👩‍👧‍👦 گروه‌ها", callback_data="adm_groups")],
        [InlineKeyboardButton("📈 نمودار ۷روز", callback_data="adm_chart"),
         InlineKeyboardButton("🏥 سلامت", callback_data="adm_health")],
        [InlineKeyboardButton("📢 ارسال همگانی", callback_data="adm_bc"),
         InlineKeyboardButton("🔄 بروزرسانی", callback_data="adm_main")],
    ])


async def on_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/admin — داشبورد اصلی."""
    if not _is_owner(update):
        await update.message.reply_text("⛔ این بخش فقط برای مالک رباته.")
        return
    s = admin.overview()
    txt = (
        "🛠 <b>پنل ادمین — AuroraPriceBot</b>\n\n"
        f"👥 کاربران: <b>{s['users']}</b>\n"
        f"🟢 فعال ۲۴ساعت: <b>{s['act24']}</b>\n"
        f"🟡 فعال ۷روز: <b>{s['act7']}</b>\n"
        f"👨‍👩‍👧‍👦 گروه‌ها: <b>{s['groups']}</b>\n\n"
        f"💬 پیام امروز: <b>{s['today_msgs']}</b> (دیروز: {s['yday_msgs']})\n"
        f" cumulative جمع کل پیام‌ها: <b>{s['total_msgs']}</b>\n"
        f"🕐 <i>{render._now_en()}</i>"
    )
    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=_admin_main_kb())


async def _admin_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE, query, data: str):
    """هندلر دکمه‌های پنل ادمین."""
    if data == "adm_main":
        s = admin.overview()
        txt = (
            "🛠 <b>پنل ادمین</b>\n\n"
            f"👥 کاربران: <b>{s['users']}</b> | 🟢 ۲۴س: <b>{s['act24']}</b> | 🟡 ۷ر: <b>{s['act7']}</b>\n"
            f"👨‍👩‍👧‍👦 گروه‌ها: <b>{s['groups']}</b>\n"
            f"💬 امروز: <b>{s['today_msgs']}</b> | جمع: <b>{s['total_msgs']}</b>"
        )
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=_admin_main_kb())

    elif data == "adm_users":
        chunk, total, has_more = admin.users_list(0)
        lines = ["👥 <b>کاربران (۱۰ آخر):</b>\n"]
        for uid, u in chunk:
            un = f"@{u['username']}" if u.get("username") else "—"
            lines.append(f"• <b>{u.get('name') or 'بی‌نام'}</b> ({un}) — {u.get('count', 0)} پیام")
        lines.append(f"\nجمع کل: <b>{total}</b>")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ برگشت", callback_data="adm_main")]])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)

    elif data == "adm_groups":
        gs = admin.groups_list()
        lines = [f"👨‍👩‍👧‍👦 <b>گروه‌ها ({len(gs)}):</b>\n"]
        for cid, g in gs[:15]:
            lines.append(f"• <b>{g.get('title') or 'بی‌نام'}</b> — {g.get('count', 0)} پیام")
        if not gs:
            lines.append("هنوز گروهی ثبت نشده.")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ برگشت", callback_data="adm_main")]])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)

    elif data == "adm_chart":
        s = admin.overview()
        daily = s["daily"]
        if daily:
            mx = max(daily.values()) or 1
            lines = ["📈 <b>پیام‌های ۷ روز اخیر:</b>\n"]
            for day, v in daily.items():
                bar = "▇" * max(1, int(v / mx * 22))
                lines.append(f"<code>{day[5:]}</code> {bar} <b>{v}</b>")
        else:
            lines = ["هنوز داده‌ای نیست."]
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ برگشت", callback_data="adm_main")]])
        await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)

    elif data == "adm_health":
        import asyncio
        import socket

        def _ping():
            t0 = time.time()
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(4)
                s.connect(("149.154.167.220", 443))
                s.close()
                return f"{(time.time() - t0) * 1000:.0f}ms"
            except Exception:
                return "N/A"

        loop = asyncio.get_running_loop()
        tg = await loop.run_in_executor(None, _ping)
        try:
            du = subprocess.run(["sh", "-c", "du -sh hist 2>/dev/null | cut -f1"], capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            du = "?"
        try:
            uptime_s = time.time() - _BOOT_TIME
            uptime = f"{int(uptime_s // 3600)}h {int(uptime_s % 3600 // 60)}m"
        except Exception:
            uptime = "?"
        txt = (
            "🏥 <b>سلامت ربات:</b>\n\n"
            f"⚡ پینگ تلگرام: <b>{tg}</b>\n"
            f"⏱ آپ‌تایم: <b>{uptime}</b>\n"
            f"💾 حجم hist: <b>{du}</b>\n"
            f"🧵 کش بنرها: <b>{len(banner._PNG_CACHE)}</b>\n"
            f"🎬 کش ویدیوها: <b>{len(banner._MP4_CACHE)}</b>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ برگشت", callback_data="adm_main")]])
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)

    elif data == "adm_bc":
        # شروع broadcast — منتظر متن بعدی از ادمین
        _BC_STATE[admin.OWNER_ID] = True
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="adm_cancel_bc")]])
        await query.edit_message_text(
            "📢 <b>ارسال همگانی</b>\n\nمتن پیام رو بفرست (همون پیام به همه‌ی کاربران می‌ره).\n"
            "برای انصراف دکمه‌ی زیر یا /cancel_bc.",
            parse_mode="HTML", reply_markup=kb)

    elif data == "adm_cancel_bc":
        _BC_STATE.pop(admin.OWNER_ID, None)
        await query.edit_message_text("✅ ارسال همگانی لغو شد.", reply_markup=_admin_main_kb())


_BC_STATE: dict = {}
_BOOT_TIME = time.time()


async def on_admin_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """CallbackQuery پنل ادمین."""
    query = update.callback_query
    if not _is_owner(update):
        await query.answer("⛔ فقط مالک", show_alert=True)
        return
    await query.answer()
    try:
        await _admin_cb(update, ctx, query, query.data)
    except Exception as e:
        log.error("admin cb: %s", e)
        try:
            await query.answer("⚠️ خطا — دوباره تلاش کن", show_alert=False)
        except Exception:
            pass


async def on_broadcast_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """اگه ادمین تو حالت broadcast هست، متن = پیام همگانی."""
    if not _BC_STATE.get(update.effective_user.id):
        return False
    _BC_STATE.pop(update.effective_user.id, None)
    msg = update.message
    targets = admin.all_user_ids()
    ok = fail = 0
    status = await msg.reply_text(f"📢 در حال ارسال به {len(targets)} کاربر...")
    for uid in targets:
        try:
            await ctx.bot.copy_message(chat_id=int(uid), from_chat_id=msg.chat_id, message_id=msg.message_id)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # rate-limit
    await status.edit_text(f"📢 تمام شد!\n✅ موفق: {ok}\n❌ ناموفق: {fail}")
    return True


async def on_cancel_bc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """BUG-4 فیکس: state همیشه پاک می‌شه حتی اگر reply خطا بده (lambda قبلی)."""
    _BC_STATE.pop(update.effective_user.id, None)
    try:
        await update.message.reply_text("✅ ارسال همگانی لغو شد.")
    except Exception:
        pass


def main():
    """شروع ربات."""
    if not TOKEN:
        print("❌ BOT_TOKEN ست نشده.")
        raise SystemExit(1)

    app = Application.builder().token(TOKEN).post_init(_post_init).concurrent_updates(True).build()

    # Handlers
    app.add_handler(CommandHandler("ping", on_ping))  # /ping
    app.add_handler(CommandHandler("start", on_start))  # /start
    app.add_handler(CommandHandler("admin", on_admin))  # 🛠 پنل ادمین (OWNER)
    app.add_handler(CommandHandler("cancel_bc", on_cancel_bc))
    # دکمه‌های ادمین — قبل از هندلر عمومی callback (group=-1 اولویت)
    app.add_handler(CallbackQueryHandler(on_admin_button, pattern="^adm_"))
    app.add_handler(CallbackQueryHandler(on_button_click))  # دکمه‌های Inline
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))  # متن عادی
    app.add_error_handler(on_error)

    log.info("🚀 AuroraPriceBot v6 started (fast warm-cache + admin panel)")
    app.run_polling()


if __name__ == "__main__":
    main()

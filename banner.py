"""
بنر حرفه‌ای قیمت — پس‌زمینه‌ی تار پرچم/لوگو + کارت شیشه‌ای + نمودار Area
تم: شیشه‌ای (glassmorphism) مشکی‌طلایی
"""
import io
import logging
import threading
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import catalog
import datafeeds

log = logging.getLogger("render")

FONT_DIR = "fonts"
GOLD = (212, 175, 55)
GOLD_BRIGHT = (255, 215, 0)
WHITE = (245, 245, 250)
GRAY = (185, 185, 195)
GREEN = (46, 204, 113)
RED = (235, 87, 87)
CARD_BG = (255, 255, 255, 235)

# ۱. رنگ‌های متغیر بر اساس نوع ارز (Dark Theme + Color Coding)
COLORS_BY_TYPE = {
    "fiat": {"bg": (15, 25, 40), "accent": (70, 150, 255), "text": (100, 180, 255)},  # آبی = ارز
    "gold": {"bg": (40, 35, 15), "accent": (255, 215, 0), "text": (255, 200, 0)},   # طلایی = طلا
    "crypto": {"bg": (25, 15, 35), "accent": (180, 100, 255), "text": (200, 150, 255)},  # بنفش = کریپتو
    "stable": {"bg": (20, 35, 25), "accent": (100, 255, 150), "text": (150, 255, 180)},  # سبز = تتر/stable
}

W, H = 900, 950


def _fa(text: str) -> str:
    """متن فارسی خام."""
    return str(text)


_RAQM = None  # کش وضعیت libraqm

def _rtl(s: str) -> str:
    """متن فارسی برای PIL:
    - با libraqm: خام بده (raqm خودش RTL + اتصال حروف رو انجام می‌ده)
    - بدون libraqm (Railway): reshape + bidi
    """
    global _RAQM
    if _RAQM is None:
        try:
            from PIL import features
            _RAQM = features.check("raqm")
        except Exception:
            _RAQM = False
    s = str(s)
    if _RAQM:
        return s
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s


_FONTS: dict = {}

def _font(size: int, weight: str = "m") -> ImageFont.FreeTypeFont:
    """فونت با کش — دیگه هر بار truetype باز نمی‌شه (سرعت)."""
    key = (size, weight)
    if key not in _FONTS:
        path = {"b": f"{FONT_DIR}/Vazir-Bold.ttf",
                "m": f"{FONT_DIR}/Vazir-Medium.ttf",
                "r": f"{FONT_DIR}/Vazir-Regular.ttf"}[weight]
        _FONTS[key] = ImageFont.truetype(path, size)
    return _FONTS[key]


def _fetch_bg_image(code: str) -> Optional[Image.Image]:
    """پرچم یا لوگوی رمزارز — با کش در assets/."""
    import os
    url, kind, key = catalog.asset_urls(code)
    if not url:
        return None
    os.makedirs("assets", exist_ok=True)
    path = f"assets/{key}.png"
    if not os.path.exists(path):
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            open(path, "wb").write(r.content)
        except Exception as e:
            log.warning("bg fetch %s: %s", url, e)
            return None
    try:
        return Image.open(path).convert("RGB")
    except Exception as e:
        log.warning("bg open %s: %s", path, e)
        return None


def _blurred_bg(img: Image.Image, color_type: str = "fiat") -> Image.Image:
    """پس‌زمینه: cover + blur شدید + تم تاریک رنگی."""
    # cover-crop به نسبت W×H
    sw, sh = img.size
    target = W / H
    src = sw / sh
    if src > target:
        nw = int(sh * target)
        x0 = (sw - nw) // 2
        img = img.crop((x0, 0, x0 + nw, sh))
    else:
        nh = int(sw / target)
        y0 = (sh - nh) // 2
        img = img.crop((0, y0, sw, y0 + nh))
    img = img.resize((W, H), Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(28))
    
    # ۲. تم تاریک با رنگ‌های متغیر
    colors = COLORS_BY_TYPE.get(color_type, COLORS_BY_TYPE["fiat"])
    base_color = colors["bg"]
    # دارک‌تر: overlay نیمه‌تنیده
    overlay = Image.new("RGB", (W, H), base_color)
    return Image.blend(img, overlay, 0.55)  # بیشتر تاریک شدند (۰.۵۵ به‌جای ۰.۴۵)


def _smooth(points, steps=None):
    """Catmull-Rom spline — خط نرم و یکدست (بدون تیکه‌تیکه)."""
    if len(points) < 3:
        return points
    pts = [(float(x), float(y)) for x, y in points]
    out = []
    n = len(pts)
    steps = steps or max(8, int((pts[-1][0] - pts[0][0]) / 2))
    for i in range(n - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[min(n - 1, i + 1)]
        p3 = pts[min(n - 1, i + 2)]
        for t in [j / steps for j in range(steps)]:
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def _area_chart(history, w: int, h: int, up: bool, ohlcv=None, candlestick: bool = False) -> Image.Image:
    """نمودار حرفه‌ای: خط smooth نوری + گرادیان + کندل‌های ظریف + محور قیمت داخل کادر.
    candlestick=True → کندل‌ها برجسته‌تر (بدنه‌ی پهن‌تر + گلو) وقتی ohlcv کافی هست."""
    PAD_T, PAD_B, PAD_X = 14, 10, 6
    if len(history) < 2:
        history = (history + [history[0]]) if history else [0, 0]
    mn, mx = min(history), max(history)
    if mx == mn:
        mx = mn * 1.001 + 1
    rng = mx - mn
    n = len(history)
    line_color = GREEN if up else RED

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    plot_h = h - PAD_T - PAD_B

    def y_of(v):
        return PAD_T + plot_h - (v - mn) / rng * plot_h

    # شبکه‌ی افقی ظریف (۴ خط داخل کادر)
    for i in range(1, 4):
        gy = PAD_T + int(plot_h * i / 4)
        d.line([(0, gy), (w, gy)], fill=(255, 255, 255, 16), width=1)

    # نقاط اصلی
    pts = []
    for i, v in enumerate(history):
        x = PAD_X + i / (n - 1) * (w - 2 * PAD_X)
        pts.append((x, y_of(v)))

    # گرادیان زیر خط (با ماسک smooth)
    smooth = _smooth(pts)
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for yy in range(h):
        alpha = max(0, int(100 * (1 - yy / h)))
        gd.line([(0, yy), (w, yy)], fill=(line_color[0], line_color[1], line_color[2], alpha))
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    poly = [(x, y) for x, y in smooth]
    poly += [(w - PAD_X, h), (PAD_X, h)]
    md.polygon(poly, fill=70)
    img.paste(grad, (0, 0), mask)

    # کندل‌ها (اگه OHLC داریم) — نیمه‌شفاف و باریک (پیش‌فرض) یا برجسته (candlestick=True)
    if ohlcv and 8 <= len(ohlcv) <= 120:
        show = ohlcv if len(ohlcv) <= 60 else ohlcv[::2]
        sstep = (w - 2 * PAD_X) / len(show)
        cw = max(3, min(8, int(sstep * 0.55))) if candlestick else max(2, min(6, int(sstep * 0.55)))
        body_a = 180 if candlestick else 110
        wick_a = 150 if candlestick else 80
        for i, (o, hi, lo, c) in enumerate(show):
            x = int(PAD_X + i * sstep + sstep / 2)
            col = GREEN if c >= o else RED
            yh = y_of(hi); yl = y_of(lo)
            yh = max(PAD_T, min(h - PAD_B, yh))
            yl = max(PAD_T, min(h - PAD_B, yl))
            d.line([(x, yh), (x, yl)], fill=col + (wick_a,), width=1)
            yo, yc = y_of(o), y_of(c)
            t, b = max(PAD_T, min(h - PAD_B, min(yo, yc))), max(PAD_T, min(h - PAD_B, max(yo, yc)))
            if b - t < 1.2:
                b = t + 1.2
            d.rounded_rectangle((x - cw // 2, t, x + cw // 2 + 1, b), radius=1, fill=col + (body_a,))
            # گلو دور بدنه‌ی کندل (فقط در حالت برجسته) — لایه‌ی محو زیر بدنه
            if candlestick:
                gr = cw + 5
                d.rounded_rectangle((x - gr // 2, t - 2, x + gr // 2 + 1, b + 2), radius=2,
                                    fill=col + (28,))

    # خط اصلی نرم + هاله‌ی نور (glow) — چند پاس با آلفا کم
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow)
    gd2.line(smooth, fill=line_color + (70,), width=9, joint="curve")
    gd2.line(smooth, fill=line_color + (110,), width=5, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(3))
    img.alpha_composite(glow)
    d.line(smooth, fill=(0, 0, 0, 60), width=2, joint="curve")
    d.line(smooth, fill=line_color + (255,), width=3, joint="curve")

    # نقطه‌ی درخشان آخر (داخل کادر) + Pulse (انیموشن ضعیف)
    ex, ey = smooth[-1]
    ey = max(PAD_T, min(h - PAD_B, ey))
    # ۵. Pulse: چندین لایه نورانی برای اثر تپش
    for r, a in [(16, 40), (11, 80), (6, 150), (2, 255)]:
        d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=line_color + (a,))

        # محور قیمت — حذف شد (خواست کاربر: اعداد سمت راست چارت نباشه)
    return img


def _fmt(v) -> str:
    """BUG-3 فیکس: قیمت‌های خیلی کوچک (<0.01 مثل SHIB) با 8 رقم دقت — 0.00000521 قبلاً 0.000005 می‌شد."""
    if isinstance(v, float) and v < 0.01 and v > 0:
        s = f"{v:,.10f}".rstrip("0").rstrip(".")
        # حداقل ۸ رقم معنادار بعد از صفرهای پیشرو
        if len(s.split(".")[-1]) < 8 and "." in s:
            s = f"{v:,.8f}".rstrip("0")
            if s.endswith("."):
                s = s[:-1]
    elif isinstance(v, float) and v < 10:
        s = f"{v:,.6f}".rstrip("0").rstrip(".")
    elif isinstance(v, float):
        s = f"{v:,.2f}".rstrip("0").rstrip(".")
    else:
        s = f"{v:,}"
    return s


def render_fa_num(v) -> str:
    """عدد انگلیسی → فارسی (برای چیپ خرید/فروش)."""
    fa = str(_fmt(v)).translate(str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹،"))
    return fa


_VIDEO_LOCK = threading.Lock()
_MP4_CACHE: dict = {}
# ۲۵. قیمت لحظه‌ی رندر هر ویدیو — برای مچ‌کردن کپشن با بنر (بدون مغایرت)
_LAST_VIDEO_PRICE: dict = {}


def get_last_video_price(code: str):
    """قیمتی که آخرین ویدیوی رندرشده‌ی این ارز روش ساخته شده (برای کپشن مچ)."""
    ck = catalog.resolve(code) or code
    return _LAST_VIDEO_PRICE.get(ck)


def render_banner_video(code: str, duration: float = 2.2, fps: int = 20) -> Optional[bytes]:
    """۵. نمودار متحرک MP4 — خط با انیمیشن کشیده می‌شه + نقطه‌ی pulse.
    خروجی bytes (mp4/h264). کش ۶۰ ثانیه. fallback: None → فراخوان از PNG استفاده کنه."""
    ck = catalog.resolve(code) or code
    import time
    now = time.time()
    hit = _MP4_CACHE.get(ck)
    if hit and now - hit[0] < 60:
        return hit[1]
    with _VIDEO_LOCK:
        hit = _MP4_CACHE.get(ck)
        now = time.time()
        if hit and now - hit[0] < 60:
            return hit[1]
        try:
            out = _render_video_uncached(code, ck, now, duration, fps)
            if out:
                # ثبت قیمتِ همون لحظه‌ی رندر (برای کپشن مچ)
                d = datafeeds.get_banner_data(code)
                if d:
                    _LAST_VIDEO_PRICE[ck] = d.get("price")
            return out
        except Exception as e:
            log.warning("video render %s: %s", code, e)
            return None


def _render_video_uncached(code: str, ck: str, now: float, duration: float, fps: int) -> Optional[bytes]:
    data = datafeeds.get_banner_data(code)
    if not data or not data.get("price"):
        return None
    hist = data.get("history") or []
    if len(hist) < 4:
        return None

    unit = data["unit"]
    pct = data.get("change_pct")
    up = (hist[-1] >= hist[0])
    line_color = GREEN if up else RED

    # رنگ تأکیدی (برای نئون/ذرات/روشنایی) بر اساس نوع ارز
    asset_type = _asset_type(code)
    accent_color = COLORS_BY_TYPE.get(asset_type, COLORS_BY_TYPE["fiat"])["accent"]

    # پس‌زمینه‌ی بنر **بدون نمودار** (خط static قدیمی حذف) — خط انیمیشنی تنها خطه
    # omit_price=True → قیمت هر فریم با roll-up کشیده می‌شه (ایده ۲) نه در پس‌زمینه
    base_png = render_banner_base_no_chart(code, omit_price=True)
    if not base_png:
        return None
    base_img = Image.open(io.BytesIO(base_png)).convert("RGB")
    Wv, Hv = base_img.size

    # موقعیت دقیق نمودار: بدون no_chart، y بعد از buy/sell chip روی self_chart_top میفته
    # بازتولید همون محاسبه: y = 36 + 110 (هدر) + 190 (قیمت) + 68/84 (chip) = ثابت‌ها
    # → مطمئن‌ترین راه: از همون توابع استفاده کن و y_chart رو حساب کن
    chart_x0 = 60 + 28
    chart_w = Wv - 60 - 28 - 60 - 28
    chart_h = 300
    # y شروع نمودار: هدر(36+110=146) + قیمت(+190=336) + chip(68 اگر buy/sell یا 84 اگر pct)
    # با no_chart رندر کردیم و y آخرین مقدار — دوباره محاسبه مثل _render_banner_uncached:
    y_calc = 36 + 110 + 190
    if data.get("buy") and data.get("sell") and data.get("buy") != data.get("sell"):
        y_calc += 68
    elif pct is not None:
        y_calc += 84
    chart_y0 = 50 + y_calc  # کارت در (card_margin, 50) کامپوزیت می‌شه

    n = len(hist)
    mn, mx = min(hist), max(hist)
    if mx == mn:
        mx = mn * 1.001 + 1
    rng = mx - mn

    PAD_T, PAD_B, PAD_X = 14, 10, 6
    plot_h = chart_h - PAD_T - PAD_B

    def y_of(v):
        return chart_y0 + PAD_T + plot_h - (v - mn) / rng * plot_h

    # نقاط smooth (همون Catmull-Rom بنر — خط شکسته نمی‌شه)
    raw_pts = []
    for i, v in enumerate(hist):
        x = chart_x0 + PAD_X + i / (n - 1) * (chart_w - 2 * PAD_X)
        raw_pts.append((x, y_of(v)))
    smooth_pts = _smooth(raw_pts, steps=12)

    # ۲۲. ffmpeg مستقیم با subprocess (imageio writer اینجا فایل خالی می‌سازه)
    # نکته: فریم‌ها با numpy array باعث OOM می‌شن (کپی 900x950×3 × ۴۴ فریم) →
    # به جاش از PIL مستقیم tobytes می‌فرستیم (RSS کم)
    import subprocess as _sp, tempfile, os as _os
    import imageio_ffmpeg
    _FF = imageio_ffmpeg.get_ffmpeg_exe()
    # ۲۴. ابعاد زوج — شرط تلگرام برای animation (اتوپلی GIF)
    w, h = (Wv // 2) * 2, (Hv // 2) * 2
    if (w, h) != (Wv, Hv):
        base_img = base_img.crop((0, 0, w, h))
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    try:
        proc = _sp.Popen(
            [_FF, "-y", "-threads", "1", "-f", "rawvideo", "-vcodec", "rawvideo",
             "-s", f"{w}x{h}",
             "-pix_fmt", "rgb24", "-r", str(fps), "-i", "-",
             "-an", "-vcodec", "libx264", "-preset", "veryfast", "-threads", "1",
             "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", "-crf", "23", tmp.name],
            stdin=_sp.PIPE, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        try:
            n_frames = int(duration * fps)
            import math
            total = len(smooth_pts)
            # موقعیت بج LIVE در بنر (کارت: margin 60، icon 28, y-10 → badge در 28+84+14=126, y+24)
            # توجه: بنر no_chart بج نداره → اینجا هر فریم با pulse بکش (blink واقعی)
            badge_x = 60 + 28 + 84 + 14
            badge_y = 50 + 36 + 24
            for f in range(n_frames):
                t = f / max(1, n_frames - 1)
                eased = 1 - (1 - t) ** 3
                img = base_img.copy()
                d = ImageDraw.Draw(img, "RGBA")
                # ایده ۴ (فیکس): نئون چرخشی — مستقیم روی لبه‌ی «کارت» (۶۰,۵۰ تا w-۶۰,h-۱۱۰)
                # قبلاً لبه‌ی تصویر کشیده می‌شد → دیده نمی‌شد و outline آبی ثابت می‌موند
                try:
                    _draw_card_neon(d, 60, 50, w - 60, h - 110, t)
                except Exception as e_nb:
                    log.warning("neon border frame: %s", e_nb)
                # ۰) بج LIVE چشمک‌زن — دوره‌ی ۲.۴s نرم (بجای ۱s تند)
                _draw_live_badge(d, badge_x, badge_y, pulse_t=(f / (fps * 2.4)) % 1.0)
                # ذرات نورانی (برگشت — کاربر خواست بمونه)
                try:
                    _draw_particles(d, w, h, t, accent_color, seed=42)
                except Exception as e_p:
                    log.warning("particles frame: %s", e_p)
                # ایده ۲: roll-up قیمت — ۴۰٪ اول انیمیت، بعد ثابت
                try:
                    _rollup_digits(img, w // 2, 50 + 36 + 110 + 56, data["price"],
                                   min(1.0, t / 0.4), unit=unit)
                except Exception as e_ru:
                    log.warning("rollup frame: %s", e_ru)
                # (ایده ۳ fade و ایده ۱ shine حذف شد — کاربر نخواست)
                # ۱) گرادیان زیر خط — فقط بخش کشیده‌شده، محدود به کادر نمودار
                idx_end = max(2, int(2 + (total - 2) * eased))
                pts = smooth_pts[:idx_end]
                if len(pts) >= 2:
                    chart_top = chart_y0
                    chart_bot = chart_y0 + chart_h - PAD_B
                    clip = (int(chart_x0), int(chart_top), int(chart_x0 + chart_w), int(chart_bot))
                    poly = list(pts) + [(pts[-1][0], chart_bot),
                                        (pts[0][0], chart_bot)]
                    mask = Image.new("L", (w, h), 0)
                    md = ImageDraw.Draw(mask)
                    md.polygon(poly, fill=52)
                    # clip ماسک به کادر نمودار (بیرون نزنه)
                    clip_img = Image.new("L", (w, h), 0)
                    ImageDraw.Draw(clip_img).rectangle(clip, fill=255)
                    from PIL import ImageChops as _ic
                    mask = _ic.composite(mask, Image.new("L", (w, h), 0), clip_img)
                    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                    gd4 = ImageDraw.Draw(grad)
                    yy0 = max(int(min(p[1] for p in pts)), int(chart_top))
                    for yy in range(yy0, int(chart_bot)):
                        alpha = max(0, int(80 * (1 - (yy - yy0) / max(1, chart_bot - yy0))))
                        gd4.line([(clip[0], yy), (clip[2], yy)], fill=line_color + (alpha,))
                    img.paste(grad, (0, 0), mask)
                    d2 = ImageDraw.Draw(img, "RGBA")
                    # ۲) گلو + خط smooth (نرم — بدون شکستگی)
                    d2.line(pts, fill=line_color + (70,), width=10, joint="curve")
                    d2.line(pts, fill=line_color + (120,), width=6, joint="curve")
                    d2.line(pts, fill=line_color + (255,), width=4, joint="curve")
                    # ۳) نقطه‌ی سر متحرک با pulse
                    ex, ey = pts[-1]
                    pr = 6 + 3 * math.sin(f / n_frames * math.pi * 4)
                    for r, a in [(int(pr * 2.2), 60), (int(pr * 1.5), 130), (int(pr), 255)]:
                        d2.ellipse((ex - r, ey - r, ex + r, ey + r), fill=line_color + (a,))
                proc.stdin.write(img.tobytes())  # بدون numpy — RSS کم
            proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.wait()
        out = open(tmp.name, "rb").read()
    finally:
        try:
            _os.unlink(tmp.name)
        except Exception:
            pass
    if not out or len(out) < 1000:
        return None
    _MP4_CACHE[ck] = (now, out)
    return out


def _code_ids(code: str):
    """(tgju_id، binance_symbol) برای کد."""
    std = catalog.resolve(code)
    if not std:
        return None, None
    if std in catalog.FIAT:
        return catalog.FIAT[std][2], None  # tgju_id
    if std in catalog.GOLD:
        return catalog.GOLD[std][1], None
    if std in catalog.STABLE:
        return catalog.STABLE[std][1], None
    if std in catalog.CRYPTO:
        return None, catalog.CRYPTO[std][1]
    return None, None


_PNG_CACHE: dict = {}
_RENDER_LOCK = threading.Lock()  # ۱۳. رندر هم‌زمان دوتا thread برای یه ارز → lock

def _asset_type(code: str) -> str:
    """نوع ارز برای رنگ‌بندی: fiat / gold / crypto / stable."""
    std = catalog.resolve(code) or code
    if std in catalog.FIAT:
        return "fiat"
    if std in catalog.GOLD:
        return "gold"
    if std in catalog.STABLE:
        return "stable"
    if std in catalog.CRYPTO:
        return "crypto"
    return "fiat"


def _gold_ingot_logo(size: int = 84) -> Optional[Image.Image]:
    """لوگوی شمش طلای سه‌بعدی با گرادیان — برای کادر آیکون طلا/سکه."""
    s4 = size * 4  # supersample برای لبه‌های نرم
    img = Image.new("RGBA", (s4, s4), (0, 0, 0, 0))

    def lerp(a, b, t):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

    top_c, mid_c, bot_c = (255, 236, 150), (250, 200, 60), (176, 128, 20)

    # بدنه‌ی شمش — ذوزنقه با گرادیان عمودی
    m = s4 * 0.14          # حاشیه
    th = s4 * 0.46         # ارتفاع بدنه
    top_in = s4 * 0.09     # فرو رفتن بالای ذوزنقه
    bx0, by0 = m, s4 * 0.30
    bx1, by1 = s4 - m, by0 + th
    body = Image.new("RGBA", (s4, s4), (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    bd.polygon([(bx0 + top_in, by0), (bx1 - top_in, by0), (bx1, by1), (bx0, by1)],
               fill=(255, 255, 255, 255))
    grad = Image.new("RGBA", (s4, s4), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for yy in range(int(by0), int(by1) + 1):
        t = (yy - by0) / max(1, th)
        c = lerp(top_c, bot_c, t) if t < 0.55 else lerp(mid_c, bot_c, (t - 0.55) / 0.45)
        gd.line([(0, yy), (s4, yy)], fill=c + (255,))
    img.paste(grad, (0, 0), body)

    # براقیت بالای شمش (هایلایت)
    hl = Image.new("RGBA", (s4, s4), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    hd.polygon([(bx0 + top_in + s4 * 0.05, by0 + s4 * 0.02),
                (bx1 - top_in - s4 * 0.05, by0 + s4 * 0.02),
                (bx1 - s4 * 0.16, by0 + th * 0.42),
                (bx0 + s4 * 0.16, by0 + th * 0.42)],
               fill=(255, 255, 255, 90))
    img = Image.alpha_composite(img, hl)

    # لبه‌ی پایین سایه
    sd = ImageDraw.Draw(img)
    sd.polygon([(bx0, by1), (bx1, by1), (bx1 - s4 * 0.03, by1 + s4 * 0.035),
                (bx0 + s4 * 0.03, by1 + s4 * 0.035)],
               fill=(120, 85, 10, 200))

    # درخشش دور شمش
    glow = Image.new("RGBA", (s4, s4), (0, 0, 0, 0))
    gld = ImageDraw.Draw(glow)
    gld.polygon([(bx0 + top_in, by0), (bx1 - top_in, by0), (bx1, by1), (bx0, by1)],
                outline=(255, 215, 0, 160), width=s4 // 28)
    glow = glow.filter(ImageFilter.GaussianBlur(s4 / 22))
    img = Image.alpha_composite(glow, img)

    return img.resize((size, size), Image.LANCZOS)


def _gold_lux_bg() -> Image.Image:
    """پس‌زمینه‌ی لوکس طلا — گرادیان تیره گرم + اشعه + bokeh طلایی + وینیت."""
    import random
    img = Image.new("RGB", (W, H), (14, 11, 4))
    d = ImageDraw.Draw(img, "RGBA")
    # گرادیان شعاعی مرکز-پایین (طلایی گرم)
    cx, cy = W // 2, int(H * 0.62)
    maxr = int((W ** 2 + H ** 2) ** 0.5 / 2)
    for r in range(maxr, 0, -12):
        t = r / maxr
        a = int(38 * (1 - t))
        d.ellipse((cx - r, cy - int(r * 1.15), cx + r, cy + int(r * 1.15)),
                  fill=(60, 44, 8, a))
    # اشعه‌های مورب ملایم
    ray = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ray)
    rnd = random.Random(7)
    for i in range(9):
        x = rnd.randint(-100, W + 100)
        wdt = rnd.randint(30, 90)
        rd.polygon([(x, 0), (x + wdt, 0), (x + wdt - 220, H), (x - 220, H)],
                   fill=(255, 200, 60, rnd.randint(5, 12)))
    ray = ray.filter(ImageFilter.GaussianBlur(22))
    img = Image.alpha_composite(img.convert("RGBA"), ray)
    # bokeh طلایی
    bk = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bk)
    for i in range(26):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        r = rnd.randint(6, 34)
        a = rnd.randint(14, 44)
        bd.ellipse((x - r, y - r, x + r, y + r), fill=(255, 210, 90, a))
    bk = bk.filter(ImageFilter.GaussianBlur(7))
    img = Image.alpha_composite(img, bk)
    # وینیت تیره دور کادر
    vin = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vin)
    vd.ellipse((-W * 0.25, -H * 0.25, W * 1.25, H * 1.25), fill=255)
    vin = vin.filter(ImageFilter.GaussianBlur(140))
    dark = Image.new("RGBA", (W, H), (6, 5, 2, 150))
    dark.putalpha(Image.eval(vin, lambda p: max(0, 150 - p // 2)))
    img = Image.alpha_composite(img, dark)
    return img.convert("RGB")


_GOLD_BG_CACHE: Optional[Image.Image] = None


def _get_gold_bg() -> Image.Image:
    global _GOLD_BG_CACHE
    if _GOLD_BG_CACHE is None:
        _GOLD_BG_CACHE = _gold_lux_bg()
    return _GOLD_BG_CACHE


def _draw_24h_range_bar(cd, x0, x1, y, low, high, price, accent):
    """۱۹. نوار موقعیت ۲۴ ساعته — قیمت الان کجای بازه Low–High است."""
    span = (high - low) or 1
    frac = max(0.0, min(1.0, (price - low) / span))
    bar_w = x1 - x0
    # ریل
    cd.rounded_rectangle((x0, y, x1, y + 10), radius=5, fill=(255, 255, 255, 28))
    # پرشدگی تا موقعیت فعلی
    pos_x = int(x0 + bar_w * frac)
    cd.rounded_rectangle((x0, y, pos_x, y + 10), radius=5, fill=accent + (230,))
    # نقطه‌ی موقعیت فعلی (درخشان)
    for r, a in [(9, 60), (6, 140), (3, 255)]:
        cd.ellipse((pos_x - r, y + 5 - r, pos_x + r, y + 5 + r), fill=accent + (a,))
    # لیبل‌های Low/High
    f_min = _font(20, "r")
    cd.text((x1, y + 22), _rtl(_fa(_fmt(high))), font=f_min, fill=GRAY, anchor="ra")
    cd.text((x0, y + 22), _rtl(_fa(_fmt(low))), font=f_min, fill=GRAY, anchor="la")


def _draw_card_neon(d, x0, y0, x1, y1, t: float):
    """ایده ۴ (نسخه نهایی): نئون دور کارت — فقط رنگ پیوسته عوض می‌شه (آبی→بنفش→طلایی→سبز).
    بدون قوس چرخان (کاربر نخواست)."""
    palette = [(70, 150, 255), (180, 100, 255), (255, 215, 0), (100, 255, 150)]
    n = len(palette)
    ph = t * n
    i0 = int(ph) % n
    i1 = (i0 + 1) % n
    ffrac = ph - int(ph)
    col = tuple(int(palette[i0][k] + (palette[i1][k] - palette[i0][k]) * ffrac) for k in range(3))
    d.rounded_rectangle((x0, y0, x1, y1), radius=36, outline=col + (200,), width=4)


def _draw_shine_sweep(cd, x0, y0, x1, y1, t: float, accent):
    """ایده ۱: نوار نور (shine) که روی کارت حرکت می‌کنه. t∈[0,1) موقعیت."""
    import math
    cx = x0 + (x1 - x0) * t
    w = (x1 - x0) * 0.16
    for i in range(int(w), 0, -2):
        a = int(90 * (1 - i / w))
        if a <= 0:
            continue
        xx = cx - i
        cd.rectangle((xx, y0, xx + 2, y1), fill=(255, 255, 255, a))
    # حلقه‌ی نرم روی لبه
    halo = max(2, int(w * 0.4))
    if 0 <= cx <= x1:
        cd.rectangle((cx - halo, y0, cx + halo, y1),
                     fill=(255, 255, 255, int(40 * (0.5 + 0.5 * math.sin(t * math.pi)))), width=0)


def _draw_neon_border(card, cw, ch, t: float, accent):
    """ایده ۴: حاشیه نئون با گرادیان چرخشی. t∈[0,1) فاز. در PNG از t=0 استفاده می‌شه."""
    # رنگ چرخشی بین آبی/بنفش/طلایی/سبز
    palette = [(70, 150, 255), (180, 100, 255), (255, 215, 0), (100, 255, 150)]
    n = len(palette)
    ph = t * n
    i0 = int(ph) % n
    i1 = (i0 + 1) % n
    f = ph - int(ph)
    col = tuple(int(palette[i0][k] + (palette[i1][k] - palette[i0][k]) * f) for k in range(3))
    glow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for gw, ga in [(8, 36), (5, 70), (3, 120)]:
        gd.rounded_rectangle((-gw // 2, -gw // 2, cw - 1 + gw // 2, ch - 1 + gw // 2),
                             radius=36 + gw // 2, outline=col + (ga,), width=gw)
    glow = glow.filter(ImageFilter.GaussianBlur(7))
    card.alpha_composite(glow)
    # حاشیه‌ی تیز روی خود کارت (بازگردوننده‌ی رنگ اصلی هم هست)
    cdraw = ImageDraw.Draw(card)
    cdraw.rounded_rectangle((1, 1, cw - 2, ch - 2), radius=36, outline=col + (220,), width=2)
    return col


def _draw_particles(cd, w, h, t: float, accent, seed=1):
    """ایده ۶: ذرات نورانی شناور (بالا می‌رن). t∈[0,1) فاز کلی."""
    import random
    rnd = random.Random(seed)
    for _ in range(14):
        px = rnd.randint(20, w - 20)
        speed = 0.05 + rnd.random() * 0.08
        base_y = rnd.randint(40, h - 40)
        phase = rnd.random()
        yy = (base_y - ((t + phase) % 1.0) * h * speed) % h
        r = rnd.randint(2, 5)
        a = int(120 * (1 - ((t + phase) % 1.0)))
        if a <= 0:
            continue
        cd.ellipse((px - r, int(yy) - r, px + r, int(yy) + r),
                  fill=accent[:3] + (max(0, a),))


def _draw_gold_ingot_divider(cd, x0, x1, y):
    """ایده ۸: جداکننده ردیف شمش‌های طلایی کوچیک (فقط طلا)."""
    n = max(3, int((x1 - x0) / 70))
    gap = (x1 - x0) / (n + 1)
    for i in range(n):
        cx = x0 + gap * (i + 1)
        cd.rounded_rectangle((cx - 22, y - 8, cx + 22, y + 8), radius=4,
                             fill=(255, 200, 60, 200), outline=(255, 230, 120, 255), width=1)


def _draw_progress_ring(cd, cx, cy, r, frac, accent):
    """ایده ۹: حلقه پیشرفت دور لوگو — frac∈[0,1] نشون‌دهنده موقعیت قیمت در بازه ۲۴س."""
    import math
    # پس‌زمینه
    cd.arc((cx - r, cy - r, cx + r, cy + r), 0, 360, fill=(255, 255, 255, 36), width=5)
    # پرشدگی از بالا شروع می‌شه
    start = -90
    end = start + 360 * max(0.0, min(1.0, frac))
    cd.arc((cx - r, cy - r, cx + r, cy + r), start, end, fill=accent + (235,), width=5)
    # نقطه‌ی انتهایی درخشان
    ang = math.radians(end)
    ex = cx + r * math.cos(ang)
    ey = cy + r * math.sin(ang)
    for rr, aa in [(9, 60), (5, 140), (3, 255)]:
        cd.ellipse((ex - rr, ey - rr, ex + rr, ey + rr), fill=accent + (aa,))


def _draw_surge_badge(cd, x, y, accent):
    """ایده ۷: بج جهش (🔺/🔻) وقتی |٪|≥۲ — روی کادر."""
    cd.rounded_rectangle((x, y, x + 120, y + 40), radius=20,
                         fill=(255, 60, 60, 50), outline=(255, 90, 90, 220), width=2)
    cd.text((x + 60, y + 20), "⚡ جهش", font=_font(22, "b"), fill=(255, 160, 160), anchor="mm")


def _rollup_digits(img, cx, cy, target, t, unit=""):
    """ایده ۲: انیمیشن roll-up عدد قیمت (فقط ویدیو). t∈[0,1) پیشرفت.
    فیکس زشتی: از ۹۲٪ قیمت شروع می‌شه و نرم به خودش می‌رسه (نه پرش از صفر) —
    فقط ۲-۳ رقم آخر می‌چرخن = اودومتر لوکس و آرام."""
    eased = 1 - (1 - t) ** 3
    # شروع از ۹۲٪ → ارقام بالا ثابت می‌مونن و فقط انتهای عدد رول می‌کنه
    cur = target * (0.92 + 0.08 * eased)
    d = ImageDraw.Draw(img)
    txt = f"{_fmt(cur)} {unit if unit == 'دلار' else ''}".strip()
    d.text((cx, cy), _rtl(_fa(txt)), font=_font(104, "b"), fill=GOLD_BRIGHT, anchor="mm")
    return img


def _draw_live_badge(cd, x, y, pulse_t: float = 0.0):
    """۲۰. بج LIVE — دایره سبز درخشان + متن. pulse_t∈[0,1) → تپش نرم."""
    import math
    if pulse_t > 0:
        blink = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(pulse_t * 2 * math.pi))
    else:
        blink = 1.0
    for r, a in [(9, int(60 * blink)), (6, int(130 * blink)), (4, int(255 * blink))]:
        cd.ellipse((x - r, y - r, x + r, y + r), fill=(46, 204, 113, min(255, a)))
    f_b = _font(22, "b")
    lv = blink if pulse_t > 0 else 1.0
    cd.text((x + 14, y), "LIVE", font=f_b,
            fill=(int(46 * lv), int(204 * lv), int(113 * lv)), anchor="lm")


def render_market_card() -> Optional[bytes]:
    """۲۱. کارت «بازار امروز» — گرید ۸ ارز + بیشترین رشد/افت."""
    import time
    now = time.time()
    hit = _PNG_CACHE.get("__market__")
    if hit and now - hit[0] < 20:
        return hit[1]
    with _RENDER_LOCK:
        hit = _PNG_CACHE.get("__market__")
        if hit and now - hit[0] < 20:
            return hit[1]
        try:
            m = datafeeds.market_overview()
        except Exception:
            m = None
        if not m or not m.get("rows"):
            return None

        W2, H2 = 900, 1100
        img = Image.new("RGB", (W2, H2), (12, 12, 16))
        d = ImageDraw.Draw(img)
        # گرادیان پس‌زمینه
        for yy in range(H2):
            t = yy / H2
            d.line([(0, yy), (W2, yy)], fill=(int(12 + 16 * t), int(12 + 12 * t), int(16 + 10 * t)))

        # هدر
        f_title = _font(46, "b")
        d.text((W2 // 2, 70), _rtl(_fa("📊 بازار امروز")), font=f_title, fill=GOLD_BRIGHT, anchor="mm")
        _draw_live_badge(d, W2 // 2 - 110, 70)
        from datetime import datetime, timezone, timedelta
        ir = timezone(timedelta(hours=3, minutes=30))
        now_fa = datetime.now(ir).strftime("%H:%M:%S")
        d.text((W2 // 2 + 130, 70), _rtl(_fa(now_fa)), font=_font(24, "r"), fill=GRAY, anchor="mm")

        # گرید ۲×۴
        cols, cw2 = 2, (W2 - 80) // 2
        rows_data = m["rows"][:8]
        rh = 150
        y0 = 140
        accent_map = {"fiat": (70, 150, 255), "gold": (255, 215, 0),
                      "crypto": (180, 100, 255), "stable": (100, 255, 150)}
        for i, r in enumerate(rows_data):
            col, row = i % cols, i // cols
            x0 = 40 + col * (cw2 + 20)
            y1 = y0 + row * (rh + 16)
            atype = _asset_type(r["key"])
            accent = accent_map.get(atype, (70, 150, 255))
            d.rounded_rectangle((x0, y1, x0 + cw2, y1 + rh), radius=22,
                                fill=(22, 22, 30, 200), outline=accent + (160,), width=2)
            # نام + قیمت + ٪
            d.text((x0 + cw2 - 20, y1 + 26), _rtl(_fa(r["name"])), font=_font(28, "b"),
                   fill=WHITE, anchor="ra")
            price_txt = f"{_fmt(r['price'])}" + ("" if r["unit"] == "تومان" else " $")
            d.text((x0 + cw2 - 20, y1 + 78), _rtl(_fa(price_txt)), font=_font(36, "b"),
                   fill=GOLD_BRIGHT, anchor="ra")
            if r["unit"] == "تومان":
                d.text((x0 + cw2 - 20, y1 + 122), _rtl(_fa("تومان")), font=_font(20, "r"),
                       fill=GRAY, anchor="ra")
            if r["pct"] is not None:
                c = GREEN if r["pct"] >= 0 else RED
                d.text((x0 + 20, y1 + 78), f"{r['pct']:+.2f}%", font=_font(26, "b"),
                       fill=c, anchor="lm")
            # اسپارک‌لاین کوچیک
            try:
                dd = datafeeds.get_banner_data(r["key"])
                h = (dd.get("history") or [])[-30:] if dd else []
                if len(h) >= 3:
                    mn, mx = min(h), max(h)
                    rng = (mx - mn) or 1
                    sw, sh = cw2 // 3, 34
                    sx0, sy0 = x0 + 20, y1 + rh - 58
                    pts = [(sx0 + i / (len(h) - 1) * sw, sy0 + sh - (v - mn) / rng * sh)
                           for i, v in enumerate(h)]
                    d.line(pts, fill=accent + (200,), width=2, joint="curve")
            except Exception:
                pass

        # بیشترین رشد/افت
        yb = y0 + 4 * (rh + 16) + 16
        f_b = _font(26, "b")
        if m.get("top"):
            n, p = m["top"]
            d.rounded_rectangle((40, yb, W2 // 2 - 10, yb + 56), radius=16,
                                fill=(46, 204, 113, 40), outline=GREEN + (200,), width=2)
            d.text((W2 // 4, yb + 28), _rtl(_fa(f"🔺 بیشترین رشد: {n} ({p:+.2f}%)")),
                   font=f_b, fill=GREEN, anchor="mm")
        if m.get("bottom"):
            n, p = m["bottom"]
            d.rounded_rectangle((W2 // 2 + 10, yb, W2 - 40, yb + 56), radius=16,
                                fill=(235, 87, 87, 40), outline=RED + (200,), width=2)
            d.text((W2 * 3 // 4, yb + 28), _rtl(_fa(f"🔻 بیشترین افت: {n} ({p:+.2f}%)")),
                   font=f_b, fill=RED, anchor="mm")

        # واترمارک
        d.text((W2 // 2, H2 - 30), _rtl(_fa("⭐ AuroraPriceBot · @iprez")),
               font=_font(22, "b"), fill=(230, 230, 235, 200), anchor="mm")

        buf = io.BytesIO()
        img.save(buf, "PNG")
        _PNG_CACHE["__market__"] = (now, buf.getvalue())
        return _PNG_CACHE["__market__"][1]


def render_banner(code: str) -> Optional[bytes]:
    import time
    ck = catalog.resolve(code) or code
    hit = _PNG_CACHE.get(ck)
    now = time.time()
    # کش ۲۰ ثانیه — warm loop هر ۱۰ ثانیه رفرش می‌کنه (جواب فوری)
    if hit and now - hit[0] < 20:
        return hit[1]

    # ۱۳. فقط یه thread در آن واحد رندر کنه (double-check بعد از lock)
    with _RENDER_LOCK:
        hit = _PNG_CACHE.get(ck)
        now = time.time()
        if hit and now - hit[0] < 20:
            return hit[1]
        return _render_banner_uncached(code, ck, now)


def render_banner_base_no_chart(code: str, omit_price: bool = False) -> Optional[bytes]:
    """بنر کامل بدون نمودار (پس‌زمینه‌ی ویدیوی انیمیشنی) — بدون کش (بلافاصله مصرف می‌شه).
    omit_price=True → قیمت و چیپ «تومان» کشیده نمی‌شه (ویدیو هر فریم خودش می‌کشه)."""
    import time
    ck = catalog.resolve(code) or code
    with _RENDER_LOCK:
        now = time.time()
        return _render_banner_uncached(code, ck, now, no_chart=True, omit_price=omit_price)


def _render_banner_uncached(code: str, ck: str, now: float, no_chart: bool = False,
                            omit_price: bool = False) -> Optional[bytes]:
    """رندر واقعی بنر — فقط از render_banner صدا زده شه (lock گرفته شده).
    no_chart=True → بنر بدون نمودار (برای پس‌زمینه‌ی ویدیوی انیمیشنی).
    omit_price=True → قیمت حذف، ولی y همون‌قدر (+190) جلو می‌ره (جای ویدیو)."""
    data = datafeeds.get_banner_data(code)
    if not data or not data.get("price"):
        return None

    tg_id, b_sym = _code_ids(code)
    # ثبت snapshot زنده (برای تاریخچه‌ی دقیقه‌ای آینده)
    if tg_id:
        datafeeds.record_snapshot(catalog.resolve(code), tgju_id=tg_id)
    elif b_sym:
        datafeeds.record_snapshot(catalog.resolve(code), binance_sym=b_sym)
    else:
        datafeeds.record_snapshot(catalog.resolve(code))

    price = data["price"]
    pct = data.get("change_pct")
    hist = data.get("history") or []
    # ارزهای er-api تاریخچه ندارن → خط تخت زنده بساز (از snapshotهای ربات)
    if len(hist) < 2 and price:
        from datafeeds import local_history
        lh = local_history(code)
        if len(lh) >= 2:
            hist = [p for _, p in lh]
        else:
            hist = [price * 0.999, price]

    # پس‌زمینه
    bg = _fetch_bg_image(code)
    kind = None
    asset_type = _asset_type(code)  # ۳. تعیین نوع ارز برای رنگ‌بندی
    if bg is None:
        _, kind, key = catalog.asset_urls(code)
    if asset_type == "gold" and bg is None:
        # ۲۷. طلا/سکه — پس‌زمینه‌ی لوکس طلایی (گرادیان + اشعه + bokeh)
        base = _get_gold_bg().copy()
    elif bg is not None:
        base = _blurred_bg(bg, color_type=asset_type)  # رنگ متغیر!
    else:
        # طلا/سکه/آیکون‌های گمشده — پس‌زمینه‌ی مشکی‌طلایی خالص
        base = Image.new("RGB", (W, H), (12, 12, 16))
        bd = ImageDraw.Draw(base)
        for y in range(H):
            t = y / H
            c = (int(12 + 20 * t), int(12 + 14 * t), int(16))
            bd.line([(0, y), (W, y)], fill=c)
        # لوگوی بزرگ‌تر در پس‌زمینه
        try:
            bd.ellipse((W//2-260, H//2-260, W//2+260, H//2+260), outline=(212, 175, 55), width=6)
            bd.ellipse((W//2-200, H//2-200, W//2+200, H//2+200), outline=(212, 175, 55, 120), width=2)
        except Exception:
            pass

    # ---- کارت شیشه‌ای ----
    card_margin = 60
    card = Image.new("RGBA", (W - card_margin * 2, H - card_margin * 2 - 40), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cw, ch = card.size

    # ۴. رنگ‌ها بر اساس نوع ارز
    colors = COLORS_BY_TYPE.get(asset_type, COLORS_BY_TYPE["fiat"])
    card_outline = colors["accent"]  # حاشیه رنگی
    
    # کارت نیمه‌شفاف + حاشیه رنگی — گلاس‌مورفیسم واقعی (شفاف‌تر)
    cd.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=36, fill=(16, 16, 24, 178),
                         outline=card_outline + (200,), width=3)  # width=3 برای نیون
    
    # ۱۴. نیون گلو — هاله‌ی نور دور کارت (چند لایه outline محو)
    glow_layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    gd3 = ImageDraw.Draw(glow_layer)
    for gw, ga in [(10, 40), (6, 70), (3, 110)]:
        gd3.rounded_rectangle((-gw // 2, -gw // 2, cw - 1 + gw // 2, ch - 1 + gw // 2),
                              radius=36 + gw // 2, outline=card_outline + (ga,), width=gw)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(6))
    card.alpha_composite(glow_layer)

    y = 36
    # --- عنوان + پرچم + بج LIVE ---
    f_title = _font(44, "b")
    title = data["name"]
    cd.text((cw - 36, y), _rtl(_fa(title)), font=f_title, fill=WHITE, anchor="ra")
    # ۲۰. بج LIVE گوشه‌ی چپ بالا (کنار آیکون)
    if not no_chart:
        _draw_live_badge(cd, 28 + 84 + 14, y + 24)

    # پرچم/آیکون دایره‌ای
    y_icon = y  # محل آیکون (برای حلقه‌ی پیشرفت طلا)
    icon_img = _fetch_bg_image(code)
    if icon_img is None and asset_type == "gold":
        # ۲۷. طلا/سکه — لوگوی شمش طلای سه‌بعدی (به‌جای متن Au)
        try:
            _ing = _gold_ingot_logo(84)
            card.alpha_composite(_ing, (28, y - 10))
        except Exception as e_gold:
            log.warning("gold ingot logo: %s", e_gold)
    elif icon_img is not None:
        s = 84
        ic = icon_img.resize((s, s), Image.LANCZOS)
        if ic.mode != "RGBA":
            ic = ic.convert("RGBA")
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, s, s), fill=255)
        card.paste(ic, (28, y - 10), mask)
    else:
        cd.ellipse((28, y - 6, 28 + 76, y + 70), outline=GOLD + (255,), width=3)
        f_icon = _font(40, "b")
        glyph = {"gold": "Au", "coin": "🪙", "usdt": "₮"}.get(kind or "", "★")
        cd.text((28 + 38, y + 32), glyph, font=f_icon, fill=GOLD_BRIGHT, anchor="mm")
    # ۹. حلقه‌ی پیشرفت دور لوگوی طلا — موقعیت قیمت در بازه ۲۴س
    if asset_type == "gold" and data.get("high_24") and data.get("low_24"):
        try:
            hi = data["high_24"]; lo = data["low_24"]
            if hi > lo:
                frac = (price - lo) / (hi - lo)
                _draw_progress_ring(cd, 28 + 42, y_icon + 32, 52, frac, GOLD_BRIGHT)
        except Exception:
            pass
    y += 110

    # --- قیمت اصلی (تایپوگرافی بزرگ‌تر + واحد در چیپ جدا) ---
    f_price = _font(104, "b")
    unit = data["unit"]
    if not omit_price:
        price_txt = f"{_fmt(price)} {unit if unit=='دلار' else ''}".strip()
        cd.text((cw // 2, y + 56), _rtl(_fa(price_txt)), font=f_price, fill=GOLD_BRIGHT, anchor="mm")
        if unit == "تومان":
            # ۹. واحد تو چیپ جدا
            chip_txt = "تومان"
            f_chip = _font(28, "b")
            chw = cd.textlength(_rtl(_fa(chip_txt)), font=f_chip)
            cx1 = cw // 2 - chw / 2 - 24
            cx2 = cw // 2 + chw / 2 + 24
            cd.rounded_rectangle((cx1, y + 122, cx2, y + 122 + 46), radius=23,
                                 fill=(255, 255, 255, 24), outline=GRAY + (120,), width=1)
            cd.text((cw // 2, y + 122 + 23), _rtl(_fa(chip_txt)), font=f_chip, fill=GRAY, anchor="mm")
    y += 190

    # ۱۶. بازه خرید/فروش صرافی (اگه Alanchand داره)
    y_chip = y  # محل چیپ — برای بج جهش (ایده ۷)
    buy_v = data.get("buy")
    sell_v = data.get("sell")
    if buy_v and sell_v and buy_v != sell_v:
        f_bs = _font(24, "b")
        bs_txt = f"فروش {render_fa_num(sell_v)}  ·  خرید {render_fa_num(buy_v)}"
        tw = cd.textlength(_rtl(_fa(bs_txt)), font=f_bs)
        bx1 = cw // 2 - tw / 2 - 26
        bx2 = cw // 2 + tw / 2 + 26
        cd.rounded_rectangle((bx1, y, bx2, y + 48), radius=24,
                             fill=(255, 255, 255, 20), outline=card_outline + (150,), width=2)
        cd.text((cw // 2, y + 24), _rtl(_fa(bs_txt)), font=f_bs, fill=WHITE, anchor="mm")
        y += 68
    elif pct is not None:
        up = pct >= 0
        color = GREEN if up else RED
        sign = "+" if up else ""
        label = f"{sign}{pct:.2f}٪  ۲۴س"
        f_chg = _font(30, "b")
        tw = cd.textlength(_rtl(_fa(label)), font=f_chg)
        bx1 = cw // 2 - tw / 2 - 28
        bx2 = cw // 2 + tw / 2 + 28
        cd.rounded_rectangle((bx1, y, bx2, y + 56), radius=28, fill=color + (46,),
                             outline=color + (220,), width=2)
        cd.text((cw // 2, y + 28), _rtl(_fa(label)), font=f_chg, fill=color, anchor="mm")
        y += 84

    # ۸. جداکننده‌ی شمش طلایی (فقط طلا) بین چیپ و نمودار
    if asset_type == "gold" and not no_chart:
        _draw_gold_ingot_divider(cd, 28, cw - 28, y)
        y += 18
    # ۷. بج جهش وقتی |٪|≥۲ — کنار چیپ
    if pct is not None and abs(pct) >= 2.0:
        _draw_surge_badge(cd, cw - 160, y_chip, card_outline)

    # --- نمودار ---
    chart_h = 300
    if len(hist) >= 3 and not no_chart:
        up = (hist[-1] >= hist[0])
        ohlcv_data = data.get("ohlcv")
        candlestick = ohlcv_data is not None and len(ohlcv_data) >= 8
        chart = _area_chart(hist, cw - 56, chart_h, up, ohlcv=ohlcv_data, candlestick=candlestick)
        card.paste(chart, (28, y), chart)
        y += chart_h + 20
        # کپشن نمودار + تاریخ آخرین آپدیت قیمت
        f_cap = _font(22, "r")
        if unit == "تومان":
            cap = "روند ۱۴ روز گذشته · آخرین بروزرسانی: " + data.get("updated", "")
        else:
            cap = "روند ۷ روز گذشته (ساعتی) · زنده"
        cd.text((cw // 2, y), _rtl(_fa(cap)), font=f_cap, fill=GRAY, anchor="mm")
        y += 48

    # ۱۹. نوار موقعیت ۲۴ ساعته (اگه high/low داریم) — در بنر ویدیویی نکش (ناحیه‌ی نمودار آزاد بمونه)
    h24 = data.get("high_24")
    l24 = data.get("low_24")
    if h24 and l24 and h24 > l24 and not no_chart:
        _draw_24h_range_bar(cd, 40, cw - 40, y, l24, h24, price, card_outline)
        f_rl = _font(20, "b")
        cd.text((cw // 2, y + 52), _rtl(_fa("موقعیت قیمت در بازه ۲۴ ساعت")),
                font=f_rl, fill=GRAY, anchor="mm")
        y += 84

    # ---- ترکیب نهایی ----
    out = base.convert("RGBA")
    out.alpha_composite(card, (card_margin, 50))

    od = ImageDraw.Draw(out)
    # (بج منبع حذف شد — کاربر نخواست)

    # ۸. لوگوی دایره‌ای گوشه‌ی پایین راست (بجای واترمارک متنی)
    try:
        import os
        logo_path = "assets/logo_circle.png"
        if not os.path.exists(logo_path) and os.path.exists("logo_pro.png"):
            lg = Image.open("logo_pro.png").convert("RGBA").resize((72, 72), Image.LANCZOS)
            mask2 = Image.new("L", (72, 72), 0)
            ImageDraw.Draw(mask2).ellipse((0, 0, 72, 72), fill=255)
            lg.putalpha(mask2)
            lg.save(logo_path)
        if os.path.exists(logo_path):
            lg = Image.open(logo_path).convert("RGBA")
            out.paste(lg, (W - 100, H - 100), lg)
    except Exception:
        pass

    # واترمارک متنی کنار لوگو
    f_wm = _font(24, "b")
    od.text((W - 115, H - 64), _rtl(_fa("AuroraPriceBot · @iprez")),
            font=f_wm, fill=(230, 230, 235, 200), anchor="rm")

    buf = io.BytesIO()
    out.convert("RGB").save(buf, "PNG")
    if no_chart:
        # بنر ویدیویی کش نمی‌شه (موقته) — فقط برگرد
        return buf.getvalue()
    _PNG_CACHE[ck] = (now, buf.getvalue())
    return _PNG_CACHE[ck][1]

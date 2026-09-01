"""
بنر حرفه‌ای قیمت — پس‌زمینه‌ی تار پرچم/لوگو + کارت شیشه‌ای + نمودار Area
تم: شیشه‌ای (glassmorphism) مشکی‌طلایی
"""
import io
import logging
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


def _area_chart(history, w: int, h: int, up: bool, ohlcv=None) -> Image.Image:
    """نمودار حرفه‌ای: خط smooth نوری + گرادیان + کندل‌های ظریف + محور قیمت داخل کادر."""
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

    # کندل‌های ظریف پشت خط (اگر OHLC داریم — نیمه‌شفاف و باریک)
    if ohlcv and 8 <= len(ohlcv) <= 120:
        show = ohlcv if len(ohlcv) <= 60 else ohlcv[::2]
        sstep = (w - 2 * PAD_X) / len(show)
        cw = max(2, min(6, int(sstep * 0.55)))
        for i, (o, hi, lo, c) in enumerate(show):
            x = int(PAD_X + i * sstep + sstep / 2)
            col = GREEN if c >= o else RED
            yh = y_of(hi); yl = y_of(lo)
            yh = max(PAD_T, min(h - PAD_B, yh))
            yl = max(PAD_T, min(h - PAD_B, yl))
            d.line([(x, yh), (x, yl)], fill=col + (80,), width=1)
            yo, yc = y_of(o), y_of(c)
            t, b = max(PAD_T, min(h - PAD_B, min(yo, yc))), max(PAD_T, min(h - PAD_B, max(yo, yc)))
            if b - t < 1.2:
                b = t + 1.2
            d.rounded_rectangle((x - cw // 2, t, x + cw // 2 + 1, b), radius=1, fill=col + (110,))

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
    if isinstance(v, float) and v < 10:
        s = f"{v:,.6f}".rstrip("0").rstrip(".")
    elif isinstance(v, float):
        s = f"{v:,.2f}".rstrip("0").rstrip(".")
    else:
        s = f"{v:,}"
    return s


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


def render_banner(code: str) -> Optional[bytes]:
    import time
    ck = catalog.resolve(code) or code
    hit = _PNG_CACHE.get(ck)
    now = time.time()
    # کش ۲۰ ثانیه — warm loop هر ۱۰ ثانیه رفرش می‌کنه (جواب فوری)
    if hit and now - hit[0] < 20:
        return hit[1]
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
    if bg is not None:
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
            f_big = _font(420, "b")
            emoji = {"gold": "🥇", "coin": "🪙", "usdt": "💵"}.get(key or kind, "💰")
            # PIL ایموجی رنگی ندارد → شکل هندسی
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
    
    # کارت نیمه‌شفاف + حاشیه رنگی (نه طلایی)
    cd.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=36, fill=(20, 20, 28, 216),
                         outline=card_outline + (200,), width=3)  # width=3 برای نیون

    y = 36
    # --- عنوان + پرچم ---
    f_title = _font(44, "b")
    title = data["name"]
    cd.text((cw - 36, y), _rtl(_fa(title)), font=f_title, fill=WHITE, anchor="ra")

    # پرچم/آیکون دایره‌ای
    icon_img = _fetch_bg_image(code)
    if icon_img is not None:
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
    y += 110

    # --- قیمت اصلی ---
    f_price = _font(88, "b")
    unit = data["unit"]
    price_txt = f"{_fmt(price)} {unit if unit=='دلار' else ''}".strip()
    cd.text((cw // 2, y + 50), _rtl(_fa(price_txt)), font=f_price, fill=GOLD_BRIGHT, anchor="mm")
    if unit == "تومان":
        f_unit = _font(30, "r")
        cd.text((cw // 2, y + 118), _rtl(_fa("تومان")), font=f_unit, fill=GRAY, anchor="mm")
    y += 160

    # --- باکس تغییرات ---
    if pct is not None:
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

    # --- نمودار ---
    chart_h = 300
    if len(hist) >= 3:
        up = (hist[-1] >= hist[0])
        chart = _area_chart(hist, cw - 56, chart_h, up, ohlcv=data.get("ohlcv"))
        card.paste(chart, (28, y), chart)
        y += chart_h + 20
        # کپشن نمودار + تاریخ آخرین آپدیت قیمت
        f_cap = _font(22, "r")
        if unit == "تومان":
            cap = "روند ۱۴ روز گذشته · آخرین بروزرسانی: " + data.get("updated", "")
        else:
            cap = "روند ۷ روز گذشته (ساعتی) · زنده"
        cd.text((cw // 2, y), _rtl(_fa(cap)), font=f_cap, fill=GRAY, anchor="mm")
        y += 40

    # ---- ترکیب نهایی ----
    out = base.convert("RGBA")
    out.alpha_composite(card, (card_margin, 50))

    # --- واترمارک ---
    od = ImageDraw.Draw(out)
    f_wm = _font(24, "b")
    od.text((W // 2, H - 36), _rtl(_fa("⭐ AuroraPriceBot · @iprez")),
            font=f_wm, fill=(230, 230, 235, 200), anchor="mm")

    buf = io.BytesIO()
    out.convert("RGB").save(buf, "PNG")
    _PNG_CACHE[ck] = (now, buf.getvalue())
    return _PNG_CACHE[ck][1]

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

W, H = 900, 950


def _fa(text: str) -> str:
    """متن فارسی خام — چون از direction='rtl' در PIL (libraqm) استفاده می‌کنیم."""
    return str(text)


def _font(size: int, weight: str = "m") -> ImageFont.FreeTypeFont:
    path = {"b": f"{FONT_DIR}/Vazir-Bold.ttf",
            "m": f"{FONT_DIR}/Vazir-Medium.ttf",
            "r": f"{FONT_DIR}/Vazir-Regular.ttf"}[weight]
    return ImageFont.truetype(path, size)


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


def _blurred_bg(img: Image.Image) -> Image.Image:
    """پس‌زمینه: cover + blur شدید + تیره‌سازی ملایم."""
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
    # تیره‌سازی برای خوانایی کارت
    overlay = Image.new("RGB", (W, H), (10, 10, 14))
    return Image.blend(img, overlay, 0.45)


def _area_chart(history, w: int, h: int, up: bool) -> Image.Image:
    """نمودار Area با گرادیان زیر خط."""
    if len(history) < 2:
        history = (history + [history[0]]) if history else [0, 0]
    mn, mx = min(history), max(history)
    rng = (mx - mn) or 1
    pts = []
    n = len(history)
    for i, v in enumerate(history):
        x = i / (n - 1) * (w - 8) + 4
        y = h - 8 - (v - mn) / rng * (h - 20)
        pts.append((x, y))
    # خطی‌سازی ملایم (میانگین متحرک) — بدون scipy
    line_color = GREEN if up else RED

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # گرادیان زیر نمودار
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(h):
        alpha = max(0, int(120 * (1 - y / h)))
        gd.line([(0, y), (w, y)], fill=(line_color[0], line_color[1], line_color[2], alpha))
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.polygon(pts + [(w - 4, h), (4, h)], fill=255)
    img.paste(grad, (0, 0), mask)

    # خط اصلی — smooth و با سایه
    d.line([(x+1, y+2) for x, y in pts], fill=(0,0,0,60), width=2, joint="curve")
    d.line(pts, fill=line_color + (255,), width=3, joint="curve")

    # نقطه‌ی آخر با هاله
    ex, ey = pts[-1]
    for r, a in [(16, 60), (10, 110), (5, 255)]:
        d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=line_color + (a,))
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
        return catalog.FIAT[std][2], None
    if std in catalog.GOLD:
        return catalog.GOLD[std][1], None
    if std in catalog.STABLE:
        return catalog.STABLE[std][1], None
    if std in catalog.CRYPTO:
        return None, catalog.CRYPTO[std][1]
    return None, None


def render_banner(code: str) -> Optional[bytes]:
    data = datafeeds.get_banner_data(code)
    if not data or not data.get("price"):
        return None

    tg_id, b_sym = _code_ids(code)
    # ثبت snapshot زنده (برای تاریخچه‌ی دقیقه‌ای آینده)
    if tg_id:
        datafeeds.record_snapshot(catalog.resolve(code), tgju_id=tg_id)
    elif b_sym:
        datafeeds.record_snapshot(catalog.resolve(code), binance_sym=b_sym)

    price = data["price"]
    pct = data.get("change_pct")
    hist = data.get("history") or []

    # پس‌زمینه
    bg = _fetch_bg_image(code)
    kind = None
    if bg is None:
        _, kind, key = catalog.asset_urls(code)
    if bg is not None:
        base = _blurred_bg(bg)
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

    # کارت نیمه‌شفاف + حاشیه طلایی
    cd.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=36, fill=(20, 20, 28, 216),
                         outline=GOLD + (200,), width=2)

    y = 36
    # --- عنوان + پرچم ---
    f_title = _font(44, "b")
    title = data["name"]
    cd.text((cw - 36, y), _fa(title), font=f_title, fill=WHITE, anchor="ra", direction='rtl')

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
    cd.text((cw // 2, y + 50), _fa(price_txt), font=f_price, fill=GOLD_BRIGHT, anchor="mm", direction='rtl')
    if unit == "تومان":
        f_unit = _font(30, "r")
        cd.text((cw // 2, y + 118), _fa("تومان"), font=f_unit, fill=GRAY, anchor="mm", direction='rtl')
    y += 160

    # --- باکس تغییرات ---
    if pct is not None:
        up = pct >= 0
        color = GREEN if up else RED
        sign = "+" if up else ""
        label = f"{sign}{pct:.2f}٪  ۲۴س"
        f_chg = _font(30, "b")
        tw = cd.textlength(_fa(label), font=f_chg)
        bx1 = cw // 2 - tw / 2 - 28
        bx2 = cw // 2 + tw / 2 + 28
        cd.rounded_rectangle((bx1, y, bx2, y + 56), radius=28, fill=color + (46,),
                             outline=color + (220,), width=2)
        cd.text((cw // 2, y + 28), _fa(label), font=f_chg, fill=color, anchor="mm", direction='rtl')
        y += 84

    # --- نمودار ---
    chart_h = 300
    if len(hist) >= 3:
        up = (hist[-1] >= hist[0])
        chart = _area_chart(hist, cw - 56, chart_h, up)
        card.paste(chart, (28, y), chart)
        y += chart_h + 20
        # کپشن نمودار
        f_cap = _font(22, "r")
        cap = "روند ۱۴ روز گذشته" if unit == "تومان" else "روند ۷ روز گذشته (ساعتی)"
        cd.text((cw // 2, y), _fa(cap), font=f_cap, fill=GRAY, anchor="mm", direction='rtl')
        y += 40

    # ---- ترکیب نهایی ----
    out = base.convert("RGBA")
    out.alpha_composite(card, (card_margin, 50))

    # --- واترمارک ---
    od = ImageDraw.Draw(out)
    f_wm = _font(24, "b")
    od.text((W // 2, H - 36), _fa("⭐ AuroraPriceBot · @iprez"),
            font=f_wm, fill=(230, 230, 235, 200), anchor="mm", direction='rtl')

    buf = io.BytesIO()
    out.convert("RGB").save(buf, "PNG", optimize=True)
    return buf.getvalue()

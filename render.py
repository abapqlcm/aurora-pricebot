"""
Rendering güzel تصویر قیمت‌ها با Pillow — تم مشکی طلایی (Aurora style)
"""
import io
import re
from typing import Optional, List, Tuple

from PIL import Image, ImageDraw, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display

from prices import get_iran, get_crypto, IRAN_FA, CRYPTO_FA, fmt_toman

FONT_DIR = "fonts"
F_BOLD = f"{FONT_DIR}/Vazir-Bold.ttf"
F_MED = f"{FONT_DIR}/Vazir-Medium.ttf"
F_REG = f"{FONT_DIR}/Vazir-Regular.ttf"

# رنگ‌ها — تم مشکی‌طلایی
BG = (12, 12, 16)
CARD = (22, 22, 30)
GOLD = (212, 175, 55)
GOLD_BRIGHT = (255, 215, 0)
WHITE = (240, 240, 245)
GRAY = (150, 150, 160)
GREEN = (62, 207, 142)
RED = (235, 87, 87)

W = 720  # عرض تصویر


def _fa(text: str) -> str:
    """آماده‌سازی متن فارسی برای PIL (reshape + bidi)."""
    return get_display(arabic_reshaper.reshape(str(text)))


def _fa_num(n) -> str:
    """تبدیل اعداد به فرمت خوانا با جداکننده."""
    if isinstance(n, float):
        s = f"{n:,.4f}".rstrip("0").rstrip(".")
    else:
        s = f"{n:,}"
    return s


def _load_font(size: int, weight: str = "med"):
    from PIL import ImageFont
    path = {"b": F_BOLD, "m": F_MED, "r": F_REG}[weight]
    return ImageFont.truetype(path, size)


def _rrect(draw: ImageDraw.ImageDraw, xy, r, fill):
    draw.rounded_rectangle(xy, radius=r, fill=fill)


def _header(img: ImageDraw.ImageDraw, title: str, subtitle: str = ""):
    """هدر بالای تصویر."""
    # لوگو/عنوان
    f_title = _load_font(52, "b")
    f_sub = _load_font(24, "r")
    img.text((W // 2, 90), _fa(title), font=f_title, fill=GOLD_BRIGHT, anchor="mm")
    if subtitle:
        img.text((W // 2, 145), _fa(subtitle), font=f_sub, fill=GRAY, anchor="mm")
    # خط تزئینی
    img.line([(80, 185), (W - 80, 185)], fill=(212, 175, 55, 100), width=2)


def _footer(img: ImageDraw.ImageDraw, img_h: int):
    f = _load_font(20, "r")
    img.text((W // 2, img_h - 45), _fa("⭐ AuroraPriceBot · @iprez"),
             font=f, fill=GRAY, anchor="mm")


def render_price_card(
    rows: List[Tuple[str, str, Optional[str]]],
    title: str = "قیمت لحظه‌ای",
    subtitle: str = "",
) -> bytes:
    """
    rows = [(نام, مقدار نمایشی, تغییر٪ یا None), ...]
    خروجی: بایت‌های PNG
    """
    pad = 28
    row_h = 78
    header_h = 210
    footer_h = 80
    H = header_h + footer_h + len(rows) * row_h + pad

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # پس‌زمینه‌ی گرادیانی ملایم — بالا کمی روشن‌تر
    for y in range(H):
        t = y / H
        c = tuple(int(BG[i] + 10 * (1 - t)) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)

    _header(d, title, subtitle)

    y = header_h
    f_name = _load_font(30, "b")
    f_val = _load_font(30, "m")
    f_unit = _load_font(20, "r")
    f_chg = _load_font(22, "b")

    for name, value, change in rows:
        # کارت هر ردیف
        _rrect(d, (pad, y, W - pad, y + row_h - 12), 16, CARD)
        # نوار طلایی سمت راست (RTL)
        d.rounded_rectangle((W - pad - 6, y + 8, W - pad - 2, y + row_h - 20), radius=2, fill=GOLD)
        # نام (راست)
        d.text((W - pad - 24, y + (row_h - 12) // 2), _fa(name),
               font=f_name, fill=WHITE, anchor="rm")
        # مقدار (چپ)
        d.text((pad + 20, y + (row_h - 12) // 2 - 8), _fa(value),
               font=f_val, fill=GOLD_BRIGHT, anchor="lm")
        # تغییر٪ (سمت چپ پایین)
        if change:
            color = GREEN if not change.startswith("-") else RED
            d.text((pad + 20, y + row_h - 26), _fa(change),
                   font=f_chg, fill=color, anchor="lm")
        y += row_h

    _footer(d, H)

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def iran_rows() -> List[Tuple[str, str, Optional[str]]]:
    p = get_iran()
    rows = []
    for key in ["dollar", "euro", "pound", "usdt", "gold_18", "gold_24",
                "coin_emami", "coin_bahar", "coin_half", "coin_quarter", "coin_gerami"]:
        if key in p:
            label = IRAN_FA[key]
            rows.append((label, _fa_num(p[key]) + " تومان", None))
    return rows


def crypto_rows(limit: int = 10) -> List[Tuple[str, str, Optional[str]]]:
    m = get_crypto(limit=limit)
    rows = []
    for k, v in list(m.items())[:limit]:
        label = f"{CRYPTO_FA.get(k, k)} ({k})"
        rows.append((label, "$" + _fa_num(v), None))
    return rows


# ============================================================
# پارس ورودی کاربر — ماشین‌حساب و اسم ارز
# ============================================================

FA_TO_KEY = {
    "دلار": "dollar", "دلارامریکا": "dollar", "دولار": "dollar", "usd": "dollar", "دلار آمریکا": "dollar",
    "یورو": "euro", "eur": "euro", "يورو": "euro",
    "پوند": "pound", "gbp": "pound", "پوند انگلیس": "pound",
    "تتر": "usdt", "usdt": "usdt", "تِتِر": "usdt",
    "طلا": "gold_18", "طلای18": "gold_18", "طلای 18": "gold_18", "طلای۱۸": "gold_18",
    "طلا۱۸": "gold_18", "طلای۲۴": "gold_24", "طلای 24": "gold_24",
    "سکه": "coin_emami", "سکه امامی": "coin_emami", "امامی": "coin_emami",
    "بهار": "coin_bahar", "بهار آزادی": "coin_bahar", "بهارازادی": "coin_bahar",
    "نیم سکه": "coin_half", "نیم‌سکه": "coin_half", "نیمسکه": "coin_half",
    "ربع سکه": "coin_quarter", "ربع‌سکه": "coin_quarter", "ربعسکه": "coin_quarter",
    "گرمی": "coin_gerami", "سکه گرمی": "coin_gerami",
    "بیت کوین": "BTC", "بیتکوین": "BTC", "btc": "BTC", "bitcoin": "BTC",
    "اتریوم": "ETH", "eth": "ETH", "ethereum": "ETH",
    "سولانا": "SOL", "sol": "SOL",
    "تون": "TON", "ton": "TON", "تونکوین": "TON",
    "دوج": "DOGE", "دوجکوین": "DOGE", "doge": "DOGE",
    "شیبا": "SHIB", "shib": "SHIB",
    "ریپل": "XRP", "xrp": "XRP",
}

# نام فارسی → نمایش
DISPLAY_FA = {
    "dollar": "دلار آمریکا", "euro": "یورو", "pound": "پوند انگلیس",
    "usdt": "تتر", "gold_18": "طلای ۱۸ عیار", "gold_24": "طلای ۲۴ عیار",
    "coin_emami": "سکه امامی", "coin_bahar": "سکه بهار آزادی",
    "coin_half": "نیم‌سکه", "coin_quarter": "ربع‌سکه", "coin_gerami": "سکه گرمی",
}


def parse_input(text: str):
    """
    ورودی کاربر را می‌فهمد:
    - "دلار" → ('single', 'dollar')
    - "125 دلار" / "دلار 125" → ('calc', ('dollar', 125))
    - "12.5 دلار" / "0.5 بیت کوین" → اعشار هم قبوله
    خروجی: (نوع, داده)
    """
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)

    # عدد در ابتدا یا انتها (اعشار هم پشتیبانی می‌شود)
    m_num_start = re.match(r"^(\d+(?:[.,]\d+)?)\s*(.+)$", t)
    m_num_end = re.match(r"^(.+?)\s*(\d+(?:[.,]\d+)?)$", t)

    for pattern, num_group, name_group in [
        (m_num_start, 1, 2),
        (m_num_end, 2, 1),
    ]:
        if pattern:
            num_str = pattern.group(num_group).replace(",", "")
            name = pattern.group(name_group).strip()
            try:
                num = float(num_str)
            except ValueError:
                continue
            # اسم ارز را پیدا کن
            key = _resolve_name(name)
            if key:
                return ("calc", (key, num))

    # فقط اسم ارز
    key = _resolve_name(t)
    if key:
        return ("single", key)
    return (None, None)


def _resolve_name(name: str):
    """اسم فارسی/انگلیسی → کلید داخلی."""
    n = name.strip().lower()
    n = re.sub(r"\s+", " ", n)
    # جستجوی دقیق
    if n in FA_TO_KEY:
        return FA_TO_KEY[n]
    # حذف کلمات اضافه (ولی "ریال" و "گرم" را نگه می‌داریم برای تشخیص)
    for stop in ["به", "چند", "تومان", "چنده", "قیمت", "چنده؟", "؟", "چی", "دانه", "عدد", "یک"]:
        n = n.replace(f" {stop} ", " ").replace(stop, "").strip()
    if not n:
        return None
    if n in FA_TO_KEY:
        return FA_TO_KEY[n]
    # "گرم" → طلا (مثل "2 گرم")
    if n == "گرم" or n == "grams" or n == "gram":
        return "gold_18"
    # "ریال" → دلار (کاربر منظورش دلار آمریکا — ریال ایران نداریم به عنوان واحد معامله)
    # نه، ریال = ۱۰ تومان — پس تقسیم بر ۱۰ می‌کنیم بعداً. فعلاً پشتیبانی نمی‌کنیم
    if n == "ریال" or n == "ریال ایران":
        return "rial"
    # جستجوی جزئی
    for k, v in FA_TO_KEY.items():
        if k in n or n in k:
            return v
    return None


def get_price_for(key: str):
    """قیمت یک ارز به تومان (ایرانی) یا دلار (کریپتو)."""
    iran = get_iran()
    # ریال = تومان × ۱۰ → پس قیمت دلار به ریال = dollar×۱۰
    if key == "rial":
        # قیمت دلار به ریال — کاربر «1000 ریال» می‌گه یعنی ۱۰۰ ریال دلار
        d = iran.get("dollar")
        if d:
            return ("rial_usd", d * 10)  # قیمت دلار به ریال
        return (None, None)
    if key in iran:
        return ("toman", iran[key])
    crypto = get_crypto(symbol=key)
    if crypto:
        return ("usd", list(crypto.values())[0])
    return (None, None)


def calc_message(key: str, amount: float) -> Optional[str]:
    """متن ماشین‌حساب — مثلا 125 دلار = 25,751,250 تومان."""
    unit, price = get_price_for(key)
    if price is None:
        return None
    total = amount * price
    name = DISPLAY_FA.get(key, CRYPTO_FA.get(key, key))
    if unit == "toman":
        return (
            f"🧮 *محاسبه*\n\n"
            f"{_fa_num(amount)} {name} = *{_fa_num(int(total))} تومان*\n\n"
            f"قیمت واحد: {_fa_num(price)} تومان"
        )
    if unit == "rial_usd":
        return (
            f"🧮 *محاسبه*\n\n"
            f"{_fa_num(amount)} دلار = *{_fa_num(int(total))} ریال*\n\n"
            f"قیمت واحد: {_fa_num(int(price))} ریال"
        )
    return (
        f"🧮 *محاسبه*\n\n"
        f"{_fa_num(amount)} {name} = *${_fa_num(total)}*\n\n"
        f"قیمت واحد: ${_fa_num(price)}"
    )


def single_message(key: str) -> Optional[str]:
    """متن قیمت یک ارز."""
    unit, price = get_price_for(key)
    if price is None:
        return None
    name = DISPLAY_FA.get(key, CRYPTO_FA.get(key, key))
    if unit == "toman":
        return f"{name}: *{_fa_num(price)} تومان*"
    return f"{name}: *${_fa_num(price)}*"


def render_calc_card(key: str, amount: float) -> bytes:
    """کارت محاسبه — 125 دلار = X تومان."""
    unit, price = get_price_for(key)
    name = DISPLAY_FA.get(key, CRYPTO_FA.get(key, key))
    if price is None:
        return None
    total = amount * price
    if unit == "toman":
        rows = [
            (f"{_fa_num(amount)} {name}", f"{_fa_num(int(total))} تومان", None),
            ("قیمت واحد", f"{_fa_num(price)} تومان", None),
        ]
        return render_price_card(rows, title="محاسبه", subtitle="تبدیل به تومان")
    if unit == "rial_usd":
        rows = [
            (f"{_fa_num(amount)} دلار", f"{_fa_num(int(total))} ریال", None),
            ("قیمت واحد", f"{_fa_num(int(price))} ریال", None),
        ]
        return render_price_card(rows, title="محاسبه", subtitle="تبدیل به ریال")
    rows = [
        (f"{_fa_num(amount)} {name}", f"${_fa_num(total)}", None),
        ("قیمت واحد", f"${_fa_num(price)}", None),
    ]
    return render_price_card(rows, title="محاسبه", subtitle="تبدیل به دلار")


def render_single_card(key: str) -> bytes:
    """کارت قیمت یک ارز."""
    unit, price = get_price_for(key)
    name = DISPLAY_FA.get(key, CRYPTO_FA.get(key, key))
    if price is None:
        return None
    if unit == "toman":
        rows = [(name, f"{_fa_num(price)} تومان", None)]
        return render_price_card(rows, title="قیمت لحظه‌ای")
    rows = [(name, f"${_fa_num(price)}", None)]
    return render_price_card(rows, title="قیمت لحظه‌ای")

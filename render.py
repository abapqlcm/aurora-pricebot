"""
parse_input — پارس ورودی کاربر با کمک catalog (یه منبع واحد)
"""
import re
from typing import Optional, Tuple, Any
import catalog
import datafeeds

# ساخت FA_TO_KEY خودکار از catalog
FA_TO_KEY = {}
# ارزهای فیات
for k, (name, *_rest) in catalog.FIAT.items():
    FA_TO_KEY[name] = k
    FA_TO_KEY[k] = k
# طلا/سکه
for k, (name, _, _) in catalog.GOLD.items():
    FA_TO_KEY[name] = k
    FA_TO_KEY[k] = k
# تتر
for k, (name, _, _) in catalog.STABLE.items():
    FA_TO_KEY[name] = k
    FA_TO_KEY[k] = k
# رمزارزها
for k, (name, _, _) in catalog.CRYPTO.items():
    FA_TO_KEY[name] = k
    FA_TO_KEY[k.lower()] = k

# آلیاس‌های اضافی
EXTRA = {
    "دلار": "dollar", "دلار آمریکا": "dollar", "دولار": "dollar", "usd": "dollar",
    "یورو": "euro", "eur": "euro", "پوند": "pound", "gbp": "pound",
    "تتر": "usdt", "usdt": "usdt", "تِتِر": "usdt",
    "طلا": "gold_18", "طلای ۱۸": "gold_18", "طلای۱۸": "gold_18", "طلای 24": "gold_24", "طلای۲۴": "gold_24",
    "سکه": "coin_emami", "امامی": "coin_emami", "سکه امامی": "coin_emami",
    "بهار": "coin_bahar", "بهار آزادی": "coin_bahar",
    "نیم سکه": "coin_half", "نیم‌سکه": "coin_half", "نیمسکه": "coin_half",
    "ربع سکه": "coin_quarter", "ربع‌سکه": "coin_quarter",
    "گرمی": "coin_gerami", "سکه گرمی": "coin_gerami",
    "بیت کوین": "BTC", "بیتکوین": "BTC", "btc": "BTC", "بیت": "BTC",
    "اتریوم": "ETH", "eth": "ETH", "اتری": "ETH",
    "سولانا": "SOL", "sol": "SOL",
    "تون": "TON", "ton": "TON", "تونکوین": "TON",
    "دوج": "DOGE", "دوجکوین": "DOGE", "doge": "DOGE",
    "شیبا": "SHIB", "shib": "SHIB",
    "ریپل": "XRP", "xrp": "XRP",
    "آربی": "ARB", "arb": "ARB", "آربیتروم": "ARB",
    "اپتیمیزم": "OP", "op": "OP",
    "پولکادات": "DOT", "dot": "DOT",
    "لایت کوین": "LTC", "litecoin": "LTC",
    "ترون": "TRX", "tron": "TRX",
    "آوالانچ": "AVAX", "avax": "AVAX",
    "چین‌لینک": "LINK", "link": "LINK",
    "کاردانو": "ADA", "cardano": "ADA",
    "فایل کوین": "FIL", "filecoin": "FIL",
    "یونی": "UNI", "uni": "UNI",
    "اتریوم کلاسیک": "ETC",
    "کازموس": "ATOM",
    "نیر": "NEAR", "near": "NEAR",
    "استلار": "XLM", "stellar": "XLM",
    "بیت کوین کش": "BCH",
    "سندباکس": "SAND", "دیسنترالند": "MANA",
    "آپتوس": "APT", "پپه": "PEPE",
    "درهم": "aed", "درهم امارات": "aed",
    "لیر": "try", "لیر ترکیه": "try",
    "فرانک": "chf", "فرانک سوئیس": "chf",
    "یوان": "cny", "یوان چین": "cny",
    "ین": "jpy", "ین ژاپن": "jpy",
    "روبل": "rub", "روبل روسیه": "rub",
    "دینار": "kwd", "دینار کویت": "kwd",
    "ریال عربستان": "sar", "سعودی": "sar",
    "روپیه": "inr", "روپیه هند": "inr",
    "پاکستان": "pkr",
    "رینگیت": "myr", "مالزی": "myr",
    "دینار عراق": "iqd", "عراق": "iqd",
    "ریال عمان": "omr", "عمان": "omr",
    "ریال قطر": "qar", "قطر": "qar",
    "دینار بحرین": "bhd", "بحرین": "bhd",
    "دلار استرالیا": "aud", "دلار کانادا": "cad",
    "روبلی": "rub",
    "طلای آب شده": "gold_melted", "طلای آب‌شده": "gold_melted", "آب شده": "gold_melted",
    "گرم طلا": "gold_18",
    "کرون سوئد": "sek", "کرون": "sek", "سوئد": "sek",
    "کرون نروژ": "nok", "نروژ": "nok",
    "کرون دانمارک": "dkk", "دانمارک": "dkk",
    "افغانی": "afn", "افغانستان": "afn",
    "وون": "krw", "کره جنوبی": "krw",
    "بات": "thb", "تایلند": "thb",
    "رئال": "brl", "برزیل": "brl",
    "پزو": "mxn", "مکزیک": "mxn",
    "رند": "zar", "آفریقای جنوبی": "zar",
    "سنگاپور": "sgd", "هنگ کنگ": "hkd", "نیوزیلند": "nzd",
    "شکل": "ils", "زلوتی": "pln", "لهستان": "pln",
    "منات": "azn", "آذربایجان": "azn",
    "درام": "amd", "ارمنستان": "amd", "لاری": "gel", "گرجستان": "gel",
    "تنگه": "kzt", "قزاقستان": "kzt", "سوم": "uzs", "ازبکستان": "uzs",
    "نایرا": "ngn", "نیجریه": "ngn", "بر": "etb", "اتیوپی": "etb",
    "پوند مصر": "egp", "مصر": "egp", "دینار لیبی": "lyd", "لیبی": "lyd",
    "دینار اردن": "jod", "اردن": "jod", "پوند لبنان": "lbp", "لبنان": "lbp",
    "لیره سوریه": "syp", "سوریه": "syp", "ریال یمن": "yer", "یمن": "yer",
    "درهم مراکش": "mad", "مراکش": "mad", "دینار الجزایر": "dzd", "الجزایر": "dzd",
    "دینار تونس": "tnd", "تونس": "tnd", "پوند سودان": "sdp", "سودان": "sdp",
    "روپیه سریلانکا": "lkr", "سریلانکا": "lkr", "تاکا": "bdt", "بنگلادش": "bdt",
    "کیات": "mmk", "میانمار": "mmk", "دونگ": "vnd", "ویتنام": "vnd",
    "پزو فیلیپین": "php", "فیلیپین": "php", "روپیه اندونزی": "idr", "اندونزی": "idr",
    "پزو آرژانتین": "ars", "آرژانتین": "ars", "پزو شیلی": "clp", "شیلی": "clp",
    "پزو کلمبیا": "cop", "کلمبیا": "cop", "سول": "pen", "پرو": "pen",
}
FA_TO_KEY.update(EXTRA)

# حذف کلمات اضافه از ورودی
STOP = re.compile(r"\b(به|چند|چنده|قیمت|چی|هست|میشه|می‌شه|روی|از|با|در|برای|؟)\b")


def _clean(s: str) -> str:
    s = STOP.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_input(text: str) -> Tuple[Optional[str], Any]:
    t = text.strip()
    tc = t.lower()
    tc = re.sub(r"\s+", " ", tc)
    tc_clean = _clean(tc)

    # فقط پیام‌های کوتاه و مستقیم قبول کن (جلوگیری از گیجی در گپ)
    # 1) عدد + ارز: "125 دلار"
    # 2) تک ارز: "دلار"
    # 3) اسم کامل: "پوند انگلیس"
    words = tc.split()
    if len(words) > 3:
        return (None, None)  # جمله طولانی → خاموش

    # شماره + ارز
    nums = re.findall(r"[\d]+(?:[.,]\d+)?", t)
    text_no_nums = re.sub(r"[\d]+(?:[.,]\d+)?", "", t).strip()
    text_no_nums_clean = _clean(text_no_nums)

    # تلاش با عدد اول
    if nums:
        n = nums[0].replace(",", "")
        try:
            amount = float(n)
        except ValueError:
            amount = None
        if amount:
            key = FA_TO_KEY.get(tc_clean) or FA_TO_KEY.get(tc) or _resolve_text(text_no_nums_clean or text_no_nums)
            if key:
                return ("calc", (key, amount))
            key = _resolve_text(text_no_nums)
            if key:
                return ("calc", (key, amount))

    # فقط متن
    key = FA_TO_KEY.get(tc_clean) or FA_TO_KEY.get(tc) or _resolve_text(tc)
    if key:
        return ("single", key)
    key = _resolve_text(t)
    if key:
        return ("single", key)

    return (None, None)


def _resolve_text(t: str):
    """جستجوی جزئی + resolve از catalog — فقط برای عبارات کامل."""
    t = _clean(t.lower())
    # دقیق
    if t in FA_TO_KEY:
        return FA_TO_KEY[t]
    # resolve catalog
    from catalog import resolve
    r = resolve(t)
    if r:
        return r
    # جستجوی جزئی (a in b) — حذف شد (خطرناک برای false positive)
    return None


def fmt_num(v) -> str:
    if isinstance(v, float) and v < 10:
        return f"{v:,.6f}".rstrip("0").rstrip(".")
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{int(v):,}"


def _nice(v) -> str:
    """عدد تمیز برای نمایش (حذف صفرهای اضافی)."""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def _now_en() -> str:
    """Current time in English — HH:MM:SS."""
    from datetime import datetime, timezone, timedelta
    ir = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(ir).strftime("%H:%M:%S")


def _now_fa() -> str:
    """زمان فعلی به وقت ایران — HH:MM:SS."""
    from datetime import datetime, timezone, timedelta
    ir = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(ir).strftime("%H:%M:%S")


# نمایش‌ها
DISPLAY_FA = {}
for k, (n, *_) in catalog.FIAT.items(): DISPLAY_FA[k] = n
for k, (n, *_) in catalog.GOLD.items(): DISPLAY_FA[k] = n
for k, (n, *_) in catalog.STABLE.items(): DISPLAY_FA[k] = n
for k, (n, *_) in catalog.CRYPTO.items(): DISPLAY_FA[k] = n

# بزرگ‌ترین ارزها برای پاس سریع
KNOWN_CODES = set(FA_TO_KEY.values())


# ============================================================
# کارت‌های ساده (fallback) — از banner برای رندر استفاده می‌کنیم
# ============================================================

def render_price_card(rows, title="", subtitle=""):
    """کارت ساده‌ی چندردیفه — برای «همه» و «کریپتو»."""
    def _rtl_f(s):
        """RTL: با libraqm خام، بدون libraqm reshape+bidi."""
        try:
            from PIL import features
            if features.check("raqm"):
                return str(s)
        except Exception:
            pass
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            return get_display(arabic_reshaper.reshape(str(s)))
        except Exception:
            return str(s)

    import io
    from PIL import Image, ImageDraw, ImageFont
    W = 720
    row_h = 64
    header_h = 150
    footer_h = 60
    H = header_h + footer_h + len(rows) * row_h + 20
    img = Image.new("RGB", (W, H), (12, 12, 16))
    d = ImageDraw.Draw(img)
    f_title = ImageFont.truetype("fonts/Vazir-Bold.ttf", 40)
    f_row = ImageFont.truetype("fonts/Vazir-Medium.ttf", 26)
    f_sub = ImageFont.truetype("fonts/Vazir-Regular.ttf", 20)
    d.text((W//2, 60), _rtl_f(title), font=f_title, fill=(255,215,0), anchor="mm")
    if subtitle:
        d.text((W//2, 105), _rtl_f(subtitle), font=f_sub, fill=(150,150,160), anchor="mm")
    y = header_h
    for name, value, _ in rows:
        d.rounded_rectangle((20, y, W-20, y+row_h-10), radius=14, fill=(22,22,30))
        d.text((W-36, y+(row_h-10)//2), _rtl_f(name), font=f_row, fill=(240,240,245), anchor="rm")
        d.text((36, y+(row_h-10)//2), str(value), font=f_row, fill=(255,215,0), anchor="lm")
        y += row_h
    d.text((W//2, H-35), "⭐ AuroraPriceBot · @iprez", font=f_sub, fill=(150,150,160), anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def render_calc_card(key, amount):
    """کارت محاسبه — بنر اصلی + مقدار محاسبه‌شده."""
    import banner as _banner
    d = datafeeds.get_banner_data(key)
    if not d or not d.get("price"):
        return None
    price = d["price"]
    total = amount * price
    unit = d["unit"]
    name = d["name"]
    if unit == "تومان":
        caption = f"{fmt_num(amount)} {name} = {fmt_num(int(total))} تومان"
    else:
        caption = f"{fmt_num(amount)} {name} = ${fmt_num(total)}"
    png = _banner.render_banner(key)
    return png


def calc_message(key, amount):
    """متن محاسبه — fallback وقتی بنر نیست."""
    d = datafeeds.get_banner_data(key)
    if not d or not d.get("price"):
        return None
    price = d["price"]
    total = amount * price
    name = d["name"]
    unit = d["unit"]
    if unit == "تومان":
        return f"🧮 {fmt_num(amount)} {name} = *{fmt_num(int(total))} تومان*"
    return f"🧮 {fmt_num(amount)} {name} = *${fmt_num(total)}*"

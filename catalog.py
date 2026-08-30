"""
Catalog — نقشه‌ی کامل ارزها: کد داخلی → نام فارسی، پرچم/لوگو، منبع قیمت
پرچم‌ها از flagcdn.com (کد کشوری ۲ حرفی)
لوگوی رمزارز از cryptocurrency-icons (spothq) — fallback: binance symbol
"""
from typing import Optional

# نماد ایموجی پرچم برای کپشن تلگرام
FLAG_EMOJI = {
    "us": "🇺🇸", "eu": "🇪🇺", "gb": "🇬🇧", "ae": "🇦🇪", "tr": "🇹🇷",
    "ch": "🇨🇭", "ca": "🇨🇦", "au": "🇦🇺", "cn": "🇨🇳", "jp": "🇯🇵",
    "ru": "🇷🇺", "kw": "🇰🇼", "sa": "🇸🇦", "om": "🇴🇲", "qa": "🇶🇦",
    "bh": "🇧🇭", "in": "🇮🇳", "pk": "🇵🇰", "az": "🇦🇿", "my": "🇲🇾",
    "iq": "🇮🇶", "ir": "🇮🇷",
}

# ارزهای فیات بازار ایران (TGJU) — کد → (نام فارسی، کد کشور پرچم، tgju_id)
FIAT = {
    "dollar":   ("دلار آمریکا",        "us", "price_dollar_rl"),
    "euro":     ("یورو",               "eu", "price_eur"),
    "pound":    ("پوند انگلیس",        "gb", "price_gbp"),
    "aed":      ("درهم امارات",        "ae", "price_aed"),
    "try":      ("لیر ترکیه",          "tr", "price_try"),
    "chf":      ("فرانک سوئیس",        "ch", "price_chf"),
    "cad":      ("دلار کانادا",        "ca", "price_cad"),
    "aud":      ("دلار استرالیا",      "au", "price_aud"),
    "cny":      ("یوان چین",           "cn", "price_cny"),
    "jpy":      ("ین ژاپن",            "jp", "price_jpy"),
    "rub":      ("روبل روسیه",         "ru", "price_rub"),
    "kwd":      ("دینار کویت",         "kw", "price_kwd"),
    "sar":      ("ریال عربستان",       "sa", "price_sar"),
    "omr":      ("ریال عمان",          "om", "price_omr"),
    "qar":      ("ریال قطر",           "qa", "price_qar"),
    "bhd":      ("دینار بحرین",        "bh", "price_bhd"),
    "inr":      ("روپیه هند",          "in", "price_inr"),
    "pkr":      ("روپیه پاکستان",      "pk", "price_pkr"),
    "myr":      ("رینگیت مالزی",       "my", "price_myr"),
    "iqd":      ("دینار عراق",         "iq", "price_iqd"),
}

# طلا و سکه (TGJU) — کد → (نام فارسی، tgju_id، آیکون)
GOLD = {
    "gold_18":     ("طلای ۱۸ عیار",      "geram18",   "gold"),
    "gold_24":     ("طلای ۲۴ عیار",      "geram24",   "gold"),
    "coin_emami":  ("سکه امامی",          "sekee",     "coin"),
    "coin_bahar":  ("سکه بهار آزادی",     "sekeb",     "coin"),
    "coin_half":   ("نیم‌سکه",            "nim",       "coin"),
    "coin_quarter":("ربع‌سکه",            "rob",       "coin"),
    "coin_gerami": ("سکه گرمی",           "gerami",    "coin"),
    "gold_melted": ("طلای آب‌شده",        "gold_17",   "gold"),
}

# تتر داخلی
STABLE = {
    "usdt": ("تتر", "usdt-irr", "usdt"),
}

# رمزارزهای محبوب — کد → (نام فارسی، symbol binance، آیکون)
CRYPTO = {
    "BTC":  ("بیت‌کوین",   "BTCUSDT",  "btc"),
    "ETH":  ("اتریوم",     "ETHUSDT",  "eth"),
    "BNB":  ("بایننس کوین","BNBUSDT",  "bnb"),
    "SOL":  ("سولانا",     "SOLUSDT",  "sol"),
    "XRP":  ("ریپل",       "XRPUSDT",  "xrp"),
    "ADA":  ("کاردانو",    "ADAUSDT",  "ada"),
    "DOGE": ("دوج‌کوین",   "DOGEUSDT", "doge"),
    "TON":  ("تون‌کوین",   "TONUSDT",  "ton"),
    "TRX":  ("ترون",       "TRXUSDT",  "trx"),
    "SHIB": ("شیبا اینو",  "SHIBUSDT", "shib"),
    "DOT":  ("پولکادات",   "DOTUSDT",  "dot"),
    "LTC":  ("لایت‌کوین",  "LTCUSDT",  "ltc"),
    "AVAX": ("آوالانچ",    "AVAXUSDT", "avax"),
    "LINK": ("چین‌لینک",   "LINKUSDT", "link"),
    "MATIC":("پالیگان",    "MATICUSDT","matic"),
    "ATOM": ("کازموس",     "ATOMUSDT", "atom"),
    "NEAR": ("نیر",        "NEARUSDT", "near"),
    "XLM":  ("استلار",     "XLMUSDT",  "xlm"),
    "BCH":  ("بیت‌کوین کش","BCHUSDT",  "bcc"),
    "FIL":  ("فایل‌کوین",  "FILUSDT",  "fil"),
    "UNI":  ("یونی‌سواپ",   "UNIUSDT",  "uni"),
    "ETC":  ("اتریوم کلاسیک","ETCUSDT","etc"),
    "ARB":  ("آربیتروم",   "ARBUSDT",  "arbitrum"),
    "OP":   ("اپتیمیزم",   "OPUSDT",   "optimism"),
    "PEPE": ("پپه",        "PEPEUSDT", "pepe"),
    "SAND": ("سندباکس",    "SANDUSDT", "sand"),
    "MANA": ("دیسنترالند", "MANAUSDT", "mana"),
    "AXS":  ("اکسی اینفینیتی","AXSUSDT","axs"),
    "Apt":  ("آپتوس",      "APTUSDT",  "apt"),
}

# آیکون‌های ویژه‌ی طلا/سکه/تتر که لوگوی رمزارزی ندارن → ایموجی بزرگ می‌کشیم
SPECIAL_ICON = {
    "gold": "🥇", "coin": "🪙", "usdt": "💵",
}


# آلیاس‌های رایج کاربران → کد استاندارد
ALIASES = {
    "eur": "euro", "usd": "dollar", "gbp": "pound", "uah": None,
    "درهم": "aed", "لیر": "try", "روبل": "rub", "یوان": "cny",
    "دینار": "kwd", "فرانک": "chf", "ریال سعودی": "sar", "عربستان": "sar",
    "بیت": "BTC", "اتری": "ETH", "atom coin": "ATOM",
    "grams": "gold_18", "gram": "gold_18",
}


def resolve(code: str) -> Optional[str]:
    """کد ورودی را به کد استاندارد تبدیل می‌کند."""
    if code in FIAT or code in GOLD or code in STABLE or code in CRYPTO:
        return code
    if code in ALIASES and ALIASES[code]:
        return ALIASES[code]
    low = code.lower()
    if low in ALIASES and ALIASES[low]:
        return ALIASES[low]
    return None


def asset_urls(code: str):
    """(آدرس تصویر پس‌زمینه، نوع) — flag یا crypto icon."""
    if code in FIAT:
        _, cc, _ = FIAT[code]
        return f"https://flagcdn.com/w1280/{cc}.png", "flag", cc
    if code in CRYPTO:
        _, _, icon = CRYPTO[code]
        return (f"https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/{icon}.png",
                "crypto", icon)
    if code in GOLD:
        kind = GOLD[code][2]
        return None, kind, kind
    if code in STABLE:
        return "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/usdt.png", "crypto", "usdt"
    return None, None, None

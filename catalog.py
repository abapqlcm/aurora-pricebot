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

# ارزهای فیات بازار ایران — کد → (نام فارسی، کد کشور پرچم، tgju_id، بایننس FX)
# قیمت لایو = تتر تومانی (والکس) × نرخ جهانی ارز/دلار (بایننس)
FIAT = {
    "dollar":   ("دلار آمریکا",        "us", "price_dollar_rl", None),   # = تتر
    "euro":     ("یورو",               "eu", "price_eur",        None),
    "pound":    ("پوند انگلیس",        "gb", "price_gbp",        None),
    "aed":      ("درهم امارات",        "ae", "price_aed",        None),   # بایننس نداره → دلار×3.6725 ثابت
    "try":      ("لیر ترکیه",          "tr", "price_try",        "TRYUSDT"),
    "chf":      ("فرانک سوئیس",        "ch", "price_chf",        None),
    "cad":      ("دلار کانادا",        "ca", "price_cad",        None),
    "aud":      ("دلار استرالیا",      "au", "price_aud",        None),
    "cny":      ("یوان چین",           "cn", "price_cny",        None),
    "jpy":      ("ین ژاپن",            "jp", "price_jpy",        None),
    "rub":      ("روبل روسیه",         "ru", "price_rub",        None),
    "kwd":      ("دینار کویت",         "kw", "price_kwd",        None),
    "sar":      ("ریال عربستان",       "sa", "price_sar",        None),
    "omr":      ("ریال عمان",          "om", "price_omr",        None),
    "qar":      ("ریال قطر",           "qa", "price_qar",        None),
    "bhd":      ("دینار بحرین",        "bh", "price_bhd",        None),
    "inr":      ("روپیه هند",          "in", "price_inr",        None),
    "pkr":      ("روپیه پاکستان",      "pk", "price_pkr",        None),
    "myr":      ("رینگیت مالزی",       "my", "price_myr",        None),
    "iqd":      ("دینار عراق",         "iq", "price_iqd",        None),
    "sek":     ("کرون سوئد",       "se", None, None),

    "nok":     ("کرون نروژ",        "no", None, None),
    "dkk":     ("کرون دانمارک",     "dk", None, None),
    "afn":     ("افغانی",           "af", None, None),
    "krw":     ("وون کره جنوبی",    "kr", None, None),
    "thb":     ("بات تایلند",       "th", None, None),
    "brl":     ("رئال برزیل",       "br", None, None),
    "mxn":     ("پزو مکزیک",        "mx", None, None),
    "zar":     ("رند آفریقای جنوبی","za", None, None),
    "sgd":     ("دلار سنگاپور",     "sg", None, None),
    "hkd":     ("دلار هنگ‌کنگ",     "hk", None, None),
    "nzd":     ("دلار نیوزیلند",    "nz", None, None),
    "ils":     ("شکل اسرائیل",      "il", None, None),
    "pln":     ("زلوتی لهستان",     "pl", None, None),
    "czk":     ("کرون چک",          "cz", None, None),
    "huf":     ("فورینت مجارستان",  "hu", None, None),
    "ron":     ("لئو رومانی",       "ro", None, None),
    "azn":     ("منات آذربایجان",   "az", None, None),
    "amd":     ("درام ارمنستان",    "am", None, None),
    "gel":     ("لاری گرجستان",     "ge", None, None),
    "kzt":     ("تنگه قزاقستان",    "kz", None, None),
    "uzs":     ("سوم ازبکستان",     "uz", None, None),
    "etb":     ("بر اتیوپی",        "et", None, None),
    "ngn":     ("نایرا نیجریه",     "ng", None, None),
    "egp":     ("پوند مصر",         "eg", None, None),
    "lyd":     ("دینار لیبی",       "ly", None, None),
    "jod":     ("دینار اردن",       "jo", None, None),
    "lbp":     ("پوند لبنان",       "lb", None, None),
    "syp":     ("لیره سوریه",       "sy", None, None),
    "yer":     ("ریال یمن",         "ye", None, None),
    "mad":     ("درهم مراکش",       "ma", None, None),
    "dzd":     ("دینار الجزایر",    "dz", None, None),
    "tnd":     ("دینار تونس",       "tn", None, None),
    "sdp":     ("پوند سودان",       "sd", None, None),
    "lkr":     ("روپیه سری‌لانکا",  "lk", None, None),
    "bdt":     ("تاکا بنگلادش",     "bd", None, None),
    "mmk":     ("کیات میانمار",     "mm", None, None),
    "vnd":     ("دونگ ویتنام",      "vn", None, None),
    "php":     ("پزو فیلیپین",      "ph", None, None),
    "idr":     ("روپیه اندونزی",    "id", None, None),
    "uyu":     ("پزو اروگوئه",      "uy", None, None),
    "ars":     ("پزو آرژانتین",     "ar", None, None),
    "clp":     ("پزو شیلی",         "cl", None, None),
    "cop":     ("پزو کلمبیا",       "co", None, None),
    "pen":     ("سول پرو",          "pe", None, None),
}

# نرخ‌های ثابت جهانی برای ارزهای بدون جفت بایننس (تقریبی — fallback TGJU بهتره)
# در عمل: اگه بایننس جفت نداشت → مستقیم TGJU (قیمت ریالی روزانه)

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
    "APT":  ("آپتوس",      "APTUSDT",  "apt"),
    "TON":  ("گرم",        "GRAMUSDT",  "gram"),
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
        _, cc = FIAT[code][0], FIAT[code][1]
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

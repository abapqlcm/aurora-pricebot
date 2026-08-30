"""
AuroraPriceBot — ربات قیمت لحظه‌ای ارز، طلا، سکه و رمزارز
منابع داده:
  - TGJU (call1.tgju.org/ajax.json) → دلار/یورو/طلا/سکه/تتر ریالی + رمزارزهای ایرانی
  - Binance API → همه‌ی رمزارزهای جهانی (USDT جفت)
"""
import json
import re
import time
import logging
from typing import Dict, Optional

import requests

log = logging.getLogger("prices")

TGJU_URL = "https://call1.tgju.org/ajax.json"
BINANCE_ALL = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_ONE = "https://api.binance.com/api/v3/ticker/price"

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

# کش ساده با TTL
_cache: Dict[str, tuple] = {}
CACHE_TTL = 60  # ثانیه


def _get(url: str, timeout: int = 12):
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r


# ============================================================
# TGJU — ارزهای ایران
# ============================================================
def _tgju() -> dict:
    key = "tgju"
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]
    r = _get(TGJU_URL)
    data = r.json().get("current", {})
    _cache[key] = (now, data)
    return data


def _tgju_p(c: dict, key: str) -> Optional[int]:
    v = c.get(key, {}).get("p")
    if v is None:
        return None
    v = str(v).replace(",", "").strip()
    return int(float(v)) if v else None


def get_iran() -> dict:
    """قیمت‌های ایرانی (تومان = ریال/۱۰)."""
    c = _tgju()
    out = {}

    def add(name, key, toman=True):
        p = _tgju_p(c, key)
        if p:
            out[name] = p // 10 if toman else p

    add("dollar", "price_dollar_rl")
    add("euro", "price_eur")
    add("pound", "price_gbp")
    add("usdt", "usdt-irr")            # تتر بازار داخلی (ریال)
    add("gold_18", "geram18")           # طلای ۱۸ عیار / گرم / تومان
    add("gold_24", "geram24")
    add("mesghal", "mesghal") if "mesghal" in c else None
    add("coin_emami", "sekee")          # سکه امامی
    add("coin_emami_retail", "retail_sekee")
    add("coin_bahar", "sekeb")          # بهار آزادی
    add("coin_bahar_retail", "retail_sekeb")
    add("coin_half", "retail_nim")      # نیم‌سکه
    add("coin_quarter", "retail_rob")   # ربع‌سکه
    add("coin_gerami", "retail_gerami") # سکه گرمی
    return {k: v for k, v in out.items() if v}


# ============================================================
# Binance — رمزارزهای جهانی
# ============================================================
def _binance_all() -> dict:
    key = "bin"
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]
    r = _get(BINANCE_ALL)
    m = {}
    for x in r.json():
        sym = x.get("symbol", "")
        if sym.endswith("USDT"):
            try:
                m[sym[:-4].upper()] = float(x["lastPrice"])
            except Exception:
                pass
    _cache[key] = (now, m)
    return m


# نام نمایشی معروف‌ها
CRYPTO_FA = {
    "BTC": "بیت‌کوین", "ETH": "اتریوم", "USDT": "تتر", "BNB": "بایننس‌کوین",
    "SOL": "سولانا", "XRP": "ریپل", "ADA": "کاردانو", "DOGE": "دوج‌کوین",
    "TRX": "ترون", "TON": "تون‌کوین", "SHIB": "شیبا", "DOT": "پولکادات",
    "MATIC": "پالیگان", "LTC": "لایت‌کوین", "AVAX": "آوالانچ", "LINK": "چین‌لینک",
    "ATOM": "کازموس", "XLM": "استلار", "NEAR": "نیر", "ARB": "آربیتروم",
    "OP": "اپتیمیزم", "PEPE": "پپه", "FIL": "فایل‌کوین", "ETC": "اتریوم کلاسیک",
    "BCH": "بیت‌کوین کش", "SAND": "سندباکس", "MANA": "دیسنترالند", "AXS": "اکسی اینفینیتی",
}


def get_crypto(symbol: str = None, limit: int = 20) -> dict:
    """قیمت دلاری رمزارزها. symbol=None → لیست پرحجم‌ها."""
    m = _binance_all()
    if symbol:
        s = symbol.upper().strip()
        if s in m:
            return {s: m[s]}
        return {}
    # مرتب بر اساس |change| یا حجم نمی‌دونیم، پس فقط معروف‌ها به ترتیب
    ordered = [s for s in CRYPTO_FA if s in m]
    rest = [s for s in m if s not in CRYPTO_FA][:limit]
    keys = (ordered + [s for s in rest if s not in ordered])[:limit]
    return {k: m[k] for k in keys}


def fmt_toman(v: int) -> str:
    """قیمت تومانی خوانا."""
    if v >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f} میلیارد"
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f} میلیون"
    if v >= 1_000:
        return f"{v/1_000:.0f} هزار"
    return str(v)


IRAN_FA = {
    "dollar": "💵 دلار آمریکا",
    "euro": "💶 یورو",
    "pound": "💷 پوند انگلیس",
    "usdt": "🪙 تتر (بازار داخلی)",
    "gold_18": "🟡 طلای ۱۸ عیار (گرم)",
    "gold_24": "🟨 طلای ۲۴ عیار (گرم)",
    "coin_emami": "🥇 سکه امامی",
    "coin_emami_retail": "🥇 سکه امامی (خرده‌فروشی)",
    "coin_bahar": "🥇 سکه بهار آزادی",
    "coin_bahar_retail": "🥇 سکه بهار آزادی (خرده‌فروشی)",
    "coin_half": "🥈 نیم‌سکه",
    "coin_quarter": "🥈 ربع‌سکه",
    "coin_gerami": "🥉 سکه گرمی",
}


def iran_message() -> str:
    prices = get_iran()
    if not prices:
        return "⚠️ دریافت قیمت‌ها ناموفق بود — بعداً دوباره امتحان کن."
    lines = ["🇮🇷 *قیمت‌های بازار ایران*", ""]
    for k, label in IRAN_FA.items():
        if k in prices:
            lines.append(f"{label}: `{prices[k]:,}` تومان")
    return "\n".join(lines)


def crypto_message(symbol: str = None, limit: int = 15) -> str:
    m = get_crypto(symbol, limit)
    if not m:
        return f"⚠️ قیمت {symbol or 'رمزارزها'} پیدا نشد."
    if symbol:
        s = list(m.keys())[0]
        v = list(m.values())[0]
        name = CRYPTO_FA.get(s, s)
        return f"{name} ({s}) = *${v:,.2f}*"
    lines = ["🌐 *رمزارزها (دلاری)*", ""]
    for k, v in list(m.items())[:limit]:
        name = CRYPTO_FA.get(k, k)
        if v >= 100:
            lines.append(f"{name} ({k}): `${v:,.0f}`")
        elif v >= 1:
            lines.append(f"{name} ({k}): `${v:,.2f}`")
        else:
            lines.append(f"{name} ({k}): `${v:.6f}`")
    return "\n".join(lines)

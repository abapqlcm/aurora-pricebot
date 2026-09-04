"""
Alanchand — قیمت لحظه‌ای بازار آزاد (خرید/فروش)
منبع: https://alanchand.com/ (SSR — قیمت‌ها داخل HTML)
"""
import re
import time
import logging

import requests

log = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TTL = 3  # ثانیه — هماهنگ با کش اصلی برای قیمت لایو

# نقشه نام‌های سایت → کدهای ربات
NAME_TO_CODE = {
    "دلار آمریکا": "dollar",
    "دلار استانبول": "dollar_ist",
    "یورو": "euro",
    "درهم": "aed",
    "لیر ترکیه": "try",
    "پوند انگلیس": "pound",
    "یوان چین": "cny",
    "دلار کانادا": "cad",
    "دلار استرالیا": "aud",
    "روبل روسیه": "rub",
    "صد دینار عراق": "iqd",
    "رینگیت مالزی": "myr",
    "لاری گرجستان": "gel",
    "منات آذربایجان": "azn",
    "صد درام ارمنستان": "amd",
    "بات تایلند": "thb",
    "ریال عمان": "omr",
    "روپیه هند": "inr",
    "صد ین ژاپن": "jpy",
    "افغانی": "afn",
}

FA_NUMS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _to_en(s: str) -> str:
    return s.translate(FA_NUMS).replace(",", "").strip()


def _fetch():
    """گرفتن و پارس قیمت‌ها از alanchand."""
    r = requests.get("https://alanchand.com/", timeout=10,
                     headers={"User-Agent": "Mozilla/5.0"})
    html = r.text
    result = {}
    for tr in html.split("<tr"):
        if "currName" not in tr:
            continue
        cidx = tr.find('class="currName"')
        if cidx < 0:
            continue
        seg = tr[cidx:tr.find("buyPrice")]
        name_m = re.search(r">\s*([^<>]+?)\s*</td>", seg)
        if not name_m:
            continue
        name = name_m.group(1).strip()
        if not name:
            continue
        buy_m = re.search(r'buyPrice[^"]*">\s*([\d,۰-۹]+)', tr)
        sell_m = re.search(r'sellPrice[^"]*">\s*([\d,۰-۹]+)', tr)
        if not buy_m or not sell_m:
            continue
        buy = _to_en(buy_m.group(1))
        sell = _to_en(sell_m.group(1))
        code = NAME_TO_CODE.get(name)
        if code:
            result[code] = {"buy": int(buy), "sell": int(sell), "name": name}
    return result


def get_prices() -> dict:
    """قیمتهای بازار روز (با کش ۳ ثانیه)."""
    now = time.time()
    if _CACHE and now - _CACHE.get("_t", 0) < _CACHE_TTL:
        return _CACHE
    try:
        data = _fetch()
        if data:
            data["_t"] = now
            _CACHE.clear()
            _CACHE.update(data)
            return dict(_CACHE)
    except Exception as e:
        log.warning("alanchand fetch error: %s", e)
    return dict(_CACHE)


def get_price(code: str) -> dict:
    """قیمت خرید/فروش برای یک ارز."""
    prices = get_prices()
    return prices.get(code)

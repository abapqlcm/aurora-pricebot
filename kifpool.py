"""
Kifpool — قیمت لحظه‌ای بازار آزاد
منبع: https://kifpool.me/live/currency (HTML — قیمت داخل span)
"""
import re
import time
import logging
import requests

log = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TTL = 20  # ثانیه

NAME_TO_CODE = {
    "دلار آمریکا": "dollar",
    "یورو اروپا": "euro",
    "درهم امارات": "aed",
}

FA_NUMS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

def _to_en(s: str) -> str:
    return s.translate(FA_NUMS).replace(",", "").strip()

def _fetch():
    """گرفتن قیمت‌ها از kifpool."""
    r = requests.get("https://kifpool.me/live/currency", timeout=10,
                     headers={"User-Agent": "Mozilla/5.0"})
    html = r.text
    result = {}
    # هر ارز داخل یک chunk با کلاس p-2 flex هست — فقط همون chunk رو match کن
    # chunk آخر متن صفحه رو هم داره ("دلار" تو متن مقاله) پس باید دقیق عنوان ارز رو پیدا کنیم
    chunks = html.split("p-2 flex")
    for chunk in chunks[1:]:
        # عنوان ارز داخل chunk دقیقاً بعد از کلاس border هست، قبل از قیمت
        # پس فقط 500 کاراکتر اول chunk که هدره رو چک کن
        header = chunk[:600]
        for fa_name, code in NAME_TO_CODE.items():
            if fa_name in header:
                m = re.search(r'<span class="inline-block">([\d,۰-۹]+)</span><span>تومان', chunk)
                if m:
                    val = _to_en(m.group(1))
                    try:
                        price = int(val)
                        result[code] = {"price": price, "name": fa_name}
                    except ValueError:
                        pass
                break
    return result

def get_prices() -> dict:
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
        log.warning("kifpool fetch error: %s", e)
    return dict(_CACHE)

def get_price(code: str) -> dict:
    prices = get_prices()
    return prices.get(code)

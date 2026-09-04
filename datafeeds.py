"""
داده‌های بنر: قیمت لحظه‌ای + درصد تغییر ۲۴h + تاریخچه برای نمودار
منابع:
  - TGJU ajax (قیمت لحظه‌ای ایران) + TGJU indicator API (تاریخچه)
  - Binance klines (تاریخچه + تغییر 24h کریپتو)
"""
import re
import time
import logging
from typing import List, Optional, Tuple

import requests

import catalog

log = logging.getLogger("data")

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
_cache = {}
CACHE_TTL = 3  # کش خیلی کوتاه — قیمت واقعاً لایو (تغییرات سریع دیده بشه)


def _get(url, timeout=12):
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r


def _cached(key, fn):
    now = time.time()
    # تبدیل کلید به رشته برای اطمینان از کارکرد صحیح کش
    key_str = str(key) if not isinstance(key, str) else key
    if key_str in _cache and now - _cache[key_str][0] < CACHE_TTL:
        return _cache[key_str][1]
    v = fn()
    _cache[key_str] = (now, v)
    return v


# ---------------- TGJU ----------------

def _tgju_now() -> dict:
    def fetch():
        return _get("https://call1.tgju.org/ajax.json").json().get("current", {})
    return _cached("tgju", fetch)


def tgju_quote(tgju_id: str) -> Tuple[Optional[int], Optional[float], Optional[int]]:
    """(قیمت تومان، درصد تغییر، تغییر ریالی) — از فیلدهای p/dp/d."""
    c = _tgju_now()
    rec = c.get(tgju_id, {})
    p = rec.get("p")
    if p is None:
        return None, None, None
    p = int(float(str(p).replace(",", "")))
    dp = rec.get("dp")
    try:
        dp = float(dp)
    except (TypeError, ValueError):
        dp = None
    d = rec.get("d")
    try:
        d = int(float(str(d).replace(",", "")))
    except (TypeError, ValueError):
        d = None
    return p, dp, d


_hist_cache: dict = {}

def tgju_history(tgju_id: str, days: int = 14) -> List[float]:
    """بسته‌شدن‌های روزانه از indicator API — کش 1 ساعته (روزانه‌ست، زود عوض نمی‌شه).
    خطا هم ۵ دقیقه کش می‌شه تا قطعی API باعث کندی زنجیره‌ای نشه."""
    key = f"h14_{tgju_id}"
    import time as _t
    hit = _hist_cache.get(key)
    if hit and _t.time() - hit[0] < (3600 if hit[1] else 300):
        return hit[1]
    def fetch():
        try:
            r = _get(f"https://api.tgju.org/v1/market/indicator/summary-table-data/{tgju_id}", timeout=15)
            data = r.json().get("data", [])
            if not data:
                _hist_cache[key] = (_t.time(), [])
                return []
            rows = data[:days]
            closes = []
            for row in rows:
                if len(row) < 4:
                    continue
                close = row[3]  # [open, low, high, close, ...]
                closes.append(float(str(close).replace(",", "")))
            v = list(reversed(closes))
            _hist_cache[key] = (_t.time(), v)
            return v
        except Exception as e:
            log.warning("tgju history %s: %s", tgju_id, e)
            # کش منفی ۵ دقیقه‌ای — جلوی تلاش مجدد هر ثانیه رو می‌گیره
            _hist_cache[key] = (_t.time(), [])
            return []
    return fetch()


# ---------------- Binance ----------------

def binance_klines(symbol: str, interval: str = "15m", limit: int = 96) -> List[float]:
    """کندل‌های اخیر — close prices، قدیمی→جدید."""
    ohlcv = binance_ohlcv(symbol, interval, limit)
    return [c[3] for c in ohlcv] if ohlcv else []


def binance_ohlcv(symbol: str, interval: str = "15m", limit: int = 96) -> List[list]:
    """کندل‌های اخیر — [open, high, low, close]، قدیمی→جدید."""
    def fetch():
        try:
            r = _get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}")
            return [[float(k[1]), float(k[2]), float(k[3]), float(k[4])] for k in r.json()]
        except Exception as e:
            log.warning("binance ohlcv %s: %s", symbol, e)
            return []
    return _cached(("ohlc", symbol), fetch)


def binance_24h_change(symbol: str) -> Optional[float]:
    """درصد تغییر 24 ساعته از ticker."""
    def fetch():
        try:
            r = _get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}")
            return float(r.json()["priceChangePercent"])
        except Exception as e:
            log.warning("binance 24h %s: %s", symbol, e)
            return None
    return _cached(("c", symbol), fetch)


# ---------------- Wallex (بازار آزاد ایران — لایو) ----------------

def _wallex_otc(side: str = "SELL") -> Optional[float]:
    """قیمت لحظهای OTC والکس — شاخص wPrice (همون قیمت بخش خرید/فروش، لایو).
    ۱. coin-market-list?baseAsset=USDT → quotes.TMN.wPrice (شاخص خام OTC — منبع dailyHigh/Low)
    ۲. fallback: /v1/otc/price?side=SELL
    هر دو خام هستن — بدون سود ۰.۵٪."""
    now = time.time()
    key = f"wallex_otc_{side}"

    def _from_index():
        try:
            r = _get("https://api.wallex.ir/v1/coin-market-list?baseAsset=USDT&fields=baseAsset,quotes.TMN.wPrice,quotes.TMN.dailyHighPrice,quotes.TMN.dailyLowPrice", timeout=8)
            for m in r.json().get("result", {}).get("markets", []):
                if m.get("baseAsset") == "USDT":
                    w = m.get("quotes", {}).get("TMN", {}).get("wPrice")
                    return float(w) if w else None
        except Exception as e:
            log.warning("wallex index: %s", e)
        return None

    def _from_otc_api():
        try:
            r = _get(f"https://api.wallex.ir/v1/otc/price?symbol=USDTTMN&side={side}", timeout=8)
            p = r.json().get("result", {}).get("price")
            return float(p) if p else None
        except Exception as e:
            log.warning("wallex otc %s: %s", side, e)
            return None

    hit = _cache.get(key)
    if hit and now - hit[0] < 3:  # ۳ ثانیه — کوچکترین نوسان هم دیده شه
        return hit[1]
    # فالبک BUY هم از شاخص (فقط کوتیشن SELL رو ضرب‌در اسپرد میکنه — نمایشی)
    v = _from_index() if side == "SELL" else _from_otc_api()
    if v:
        _cache[key] = (now, v)
    return v


def wallex_buy_quote() -> Tuple[Optional[float], Optional[float]]:
    """(قیمت خرید والکس، تغییر ۲۴h٪) — همون عدد بخش «خرید ارز» (price، لایو).
    این قیمت خودش حاشیه والکس رو داره — بدون سود اضافه."""
    def fetch():
        try:
            r = _get("https://api.wallex.ir/v1/coin-market-list?baseAsset=USDT&fields=baseAsset,quotes.TMN.price,quotes.TMN.percentChange24h", timeout=8)
            for m in r.json().get("result", {}).get("markets", []):
                if m.get("baseAsset") == "USDT":
                    t = m.get("quotes", {}).get("TMN", {})
                    p = float(t.get("price") or 0) or None
                    ch = float(t.get("percentChange24h") or 0)
                    return (p, ch)
        except Exception as e:
            log.warning("wallex buy: %s", e)
        return (None, None)
    return _cached("wallex_buy", fetch)


def wallex_index_high_low() -> Tuple[Optional[float], Optional[float]]:
    """سقف/کف ۲۴ ساعته‌ی شاخص OTC والکس — کاملا خام (بدون سود ۰.۵٪).
    منبع رسمی: quotes.TMN.dailyHighPrice / dailyLowPrice از coin-market-list."""
    def fetch():
        try:
            r = _get("https://api.wallex.ir/v1/coin-market-list?baseAsset=USDT&fields=baseAsset,quotes.TMN.dailyHighPrice,quotes.TMN.dailyLowPrice", timeout=8)
            for m in r.json().get("result", {}).get("markets", []):
                if m.get("baseAsset") == "USDT":
                    t = m.get("quotes", {}).get("TMN", {})
                    hi = float(t.get("dailyHighPrice") or 0) or None
                    lo = float(t.get("dailyLowPrice") or 0) or None
                    return (hi, lo)
        except Exception as e:
            log.warning("wallex hi/lo: %s", e)
        return (None, None)
    return _cached("wallex_hilo", fetch)

def _wallex_markets() -> dict:
    """نمادهای والکس — کش ۵ ثانیهای (لایو)."""
    def fetch():
        r = _get("https://api.wallex.ir/v1/markets", timeout=12)
        return r.json().get("result", {}).get("symbols", {})
    return _cached("wallex", fetch)


def wallex_quote(symbol: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """(آخرین قیمت تومانی، تغییر ۲۴h٪، بالاترین ۲۴h) از والکس."""
    syms = _wallex_markets()
    rec = syms.get(symbol)
    if not rec:
        return None, None, None
    st = rec.get("stats", {})
    def _f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    last = _f(st.get("lastPrice"))
    if last is None:
        last = _f(st.get("bidPrice")) or _f(st.get("askPrice"))
    ch = _f(st.get("24h_ch"))
    return last, ch, _f(st.get("24h_highPrice"))


def usdt_toman() -> float:
    """قیمت لحظهای تتر تومانی — OTC والکس (همون قیمت سایت wallex.ir، لایو ۵ثانیه).
    fallback: markets lastPrice اگر OTC در دسترس نبود."""
    p = _wallex_otc("SELL")
    if p:
        return p
    last, _, _ = wallex_quote("USDTTMN")
    return last or 0.0


# ---------------- Binance FX (نرخ جهانی ارزها) ----------------

def binance_fx_rate(usd_pair: str) -> Optional[float]:
    """نرخ دلاری ارز (مثل EURUSDT) از بایننس."""
    def fetch():
        try:
            r = _get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={usd_pair}")
            return float(r.json()["lastPrice"])
        except Exception as e:
            log.warning("binance fx %s: %s", usd_pair, e)
            return None
    return _cached(("fx", usd_pair), fetch)




# ---------------- ER-API (166 ارز جهانی — یک کال) ----------------

_fx_rates_cache = {"t": 0, "rates": {}}

def erapi_rates() -> dict:
    """نرخ جهانی همه‌ی ارزها نسبت به دلار — کش 10 دقیقه."""
    import time
    now = time.time()
    if _fx_rates_cache["rates"] and now - _fx_rates_cache["t"] < 600:
        return _fx_rates_cache["rates"]
    try:
        r = _get("https://open.er-api.com/v6/latest/USD", timeout=12)
        rates = r.json().get("rates", {})
        if rates:
            _fx_rates_cache["t"] = now
            _fx_rates_cache["rates"] = rates
        return rates
    except Exception as e:
        log.warning("erapi: %s", e)
        # بازگشت کش قدیمی حتی اگر خالی باشد (جلوگیری از کرش در fx_to_usd)
        return _fx_rates_cache["rates"] if _fx_rates_cache["rates"] else {}


def fx_to_usd(ccy: str) -> Optional[float]:
    """1 واحد از این ارز چند دلار؟ (مثل SEK → 0.104)"""
    rates = erapi_rates()
    v = rates.get(ccy.upper())
    if not v:
        return None
    return 1.0 / v


# ---------------- واحد یکپارچه ----------------

# کد داخلی → کد ISO واقعی برای er-api
_FIAT_ISO = {
    "dollar": "USD", "euro": "EUR", "pound": "GBP",
    "aed": "AED", "try": "TRY", "chf": "CHF", "cad": "CAD", "aud": "AUD",
    "cny": "CNY", "jpy": "JPY", "rub": "RUB", "kwd": "KWD", "sar": "SAR",
    "omr": "OMR", "qar": "QAR", "bhd": "BHD", "inr": "INR", "pkr": "PKR",
    "myr": "MYR", "iqd": "IQD",
}


def get_banner_data(code: str) -> Optional[dict]:
    """
    برای هر کد داخل catalog، داده‌ی کامل بنر را می‌سازد:
    {name, price(تومان), change_pct, change_abs, history[], source}
    """
    code = catalog.resolve(code)
    if not code:
        return None
    if code in catalog.FIAT:
        name, _, tg_id, fx_sym = catalog.FIAT[code]
        # Wallex لایو OTC (۵ثانیه — همون wallex.ir) + ۰.۵٪ سود بازار — قیمت اصلی
        usdt_t = usdt_toman()
        if usdt_t:
            usdt_t = round(usdt_t * 1.005)
        price = None
        pct = None
        if code == "dollar":
            price = round(usdt_t) if usdt_t else None
            _, pct, _ = wallex_quote("USDTTMN")
        elif fx_sym:
            rate = binance_fx_rate(fx_sym)
            if usdt_t and rate:
                price = round(usdt_t * rate)
            else:
                # بایننس جفت نداشت → er-api
                iso = _FIAT_ISO.get(code)
                v = fx_to_usd(iso) if iso else None
                if usdt_t and v:
                    price = round(usdt_t * v)
        else:
            iso = _FIAT_ISO.get(code)
            v = fx_to_usd(iso) if iso else None
            if usdt_t and v:
                price = round(usdt_t * v)
        if price is None:
            # فالبک نهایی: TGJU
            p, dp, d = tgju_quote(tg_id)
            hist_rial = tgju_history(tg_id)
            hist = [x / 10 for x in hist_rial]
            return {
                "name": name, "price": (p // 10 if p else None), "change_pct": dp,
                "change_abs": (d // 10 if d else None),
                "history": hist, "unit": "تومان", "source": "TGJU",
            }
        return {
            "name": name, "price": price, "change_pct": pct,
            "change_abs": None,
            "history": ([x / 10 for x in tgju_history(tg_id)] if tg_id else []),
            "unit": "تومان", "source": "Wallex+Binance (لایو +۰.۵٪)",
        }

    if code in catalog.GOLD:
        name, tg_id, _ = catalog.GOLD[code]
        p, dp, d = tgju_quote(tg_id)
        hist_rial = tgju_history(tg_id)
        hist = [x / 10 for x in hist_rial]
        return {
            "name": name, "price": (p // 10 if p else None), "change_pct": dp,
            "change_abs": (d // 10 if d else None),
            "history": hist, "unit": "تومان", "source": "TGJU",
        }

    if code in catalog.STABLE:
        name, tg_id, _ = catalog.STABLE[code]
        # تتر = قیمت «خرید ارز» والکس (price — لایو، همون عددی که کاربر تو بخش خرید میبینه)
        # + شاخص wPrice و های/لو ۲۴h خام برای کپشن
        buy_p, ch = wallex_buy_quote()      # قیمت خرید لایو (۲۱۸k) — بدون سود اضافه
        otc = usdt_toman()                  # شاخص wPrice خام (۲۱۶k)
        hi_i, lo_i = wallex_index_high_low()
        last = round(buy_p) if buy_p else None
        if last and hi_i and lo_i:
            high_24, low_24 = round(hi_i), round(lo_i)  # خام — بدون سود
            ohlcv = [
                [low_24, high_24, low_24, low_24],
                [low_24, high_24, low_24, last],
                [last, high_24, low_24, last]
            ]
            return {
                "name": name, "price": last, "change_pct": ch,
                "change_abs": None,
                "high_24": high_24, "low_24": low_24,
                "index_price": otc,  # شاخص wPrice — برای کپشن (تفاوت با خرید)
                "history": [x / 10 for x in tgju_history(tg_id)],
                "ohlcv": ohlcv,
                "unit": "تومان", "source": "Wallex خرید (لایو)",
            }
        if last:
            # از همان quote کشدار high/low بگیر (بدون درخواست تکراری)
            try:
                syms = _wallex_markets()
                usdt_data = syms.get('USDTTMN', {})
                stats = usdt_data.get('stats', {})
                # های/لو ۲۴h خام والکس — بدون سود ۰.۵٪ (همون که سایت wallex.ir نشون میده)
                high_24 = round(float(stats.get('24h_highPrice', last))) if stats.get('24h_highPrice') else last
                low_24 = round(float(stats.get('24h_lowPrice', last))) if stats.get('24h_lowPrice') else last
                # fake ohlcv برای chart — ساختار [open, high, low, close] مثل بایننس
                ohlcv = [
                    [low_24, high_24, low_24, low_24],
                    [low_24, high_24, low_24, last],
                    [last, high_24, low_24, last]
                ]
            except Exception as e:
                log.warning("wallex USDTTMN stats: %s", e)
                high_24 = low_24 = last
                ohlcv = []

            return {
                "name": name, "price": round(last), "change_pct": ch,
                "change_abs": None,
                "high_24": high_24, "low_24": low_24,  # ۱۷. برای نوار موقعیت ۲۴س
                "history": [x / 10 for x in tgju_history(tg_id)],
                "ohlcv": ohlcv,
                "unit": "تومان", "source": "Wallex (لایو)",
            }
        # fallback
        p, dp, d = tgju_quote(tg_id)
        hist = [x / 10 for x in tgju_history(tg_id)]
        return {
            "name": name, "price": (p // 10 if p else None), "change_pct": dp,
            "change_abs": (d // 10 if d else None),
            "history": hist, "unit": "تومان", "source": "TGJU",
        }

    if code in catalog.CRYPTO:
        name, sym, _ = catalog.CRYPTO[code]
        ohlcv = binance_ohlcv(sym)
        if not ohlcv:
            return None
        klines = [c[3] for c in ohlcv]
        price_usd = klines[-1]
        # ۲۸. سرعت: pct از خود کندل‌ها (کندل ۲۴h قبل) — بدون درخواست دوم به Binance
        p_24 = klines[-25] if len(klines) >= 25 else klines[0]
        # محاسبه تغییرات ۲۴ ساعته با جلوگیری از تقسیم بر صفر
        pct = round((price_usd - p_24) / p_24 * 100, 2) if p_24 and p_24 != 0 else None
        # تاریخچه‌ی ۲۴h به تومان تبدیل می‌کنیم (دلار × تتر داخلی) تا همه چیز تومانی باشه؟
        # نه — کریپتو را دلاری نشان می‌دهیم، استانداردتر است
        ch_abs = price_usd - p_24 if p_24 else 0.0
        # ۱۷. high/low واقعی ۲۴h از کندل‌های ۱۵ دقیقه‌ای اخیر (۹۶ کندل = ۲۴ ساعت)
        h24 = ohlcv[-96:] if len(ohlcv) >= 96 else ohlcv
        high_24 = max((x[1] for x in h24), default=price_usd) if h24 else price_usd
        low_24 = min((x[2] for x in h24), default=price_usd) if h24 else price_usd
        return {
            "name": name, "price": price_usd, "change_pct": pct,
            "change_abs": ch_abs, "history": klines, "ohlcv": ohlcv,
            "high_24": high_24, "low_24": low_24,  # برای نوار موقعیت ۲۴س
            "unit": "دلار", "source": "Binance",
        }

    return None


# ۱۸. کارت «بازار امروز» — گرید چند ارز + بیشترین رشد/افت
MARKET_KEYS = ["dollar", "euro", "pound", "usdt", "gold_18", "coin_emami", "BTC", "ETH"]


def market_overview() -> dict:
    """دیتای خلاصه برای کارت بازار: قیمت + ٪تغییر هر ارز محبوب.
    خروجی: {"rows": [(name, price, pct, unit)], "top": (name,pct)|None, "bottom": (name,pct)|None}
    """
    rows = []
    for k in MARKET_KEYS:
        try:
            d = get_banner_data(k)
        except Exception:
            d = None
        if not d or not d.get("price"):
            continue
        rows.append({
            "key": k, "name": d["name"], "price": d["price"],
            "pct": d.get("change_pct"), "unit": d.get("unit", "تومان"),
        })
    top = bottom = None
    with_pct = [r for r in rows if r["pct"] is not None]
    if with_pct:
        sorted_r = sorted(with_pct, key=lambda r: r["pct"], reverse=True)
        # فقط اگر بیشترین مقدار مثبت باشد top را تنظیم کن
        if sorted_r[0]["pct"] > 0:
            top = (sorted_r[0]["name"], sorted_r[0]["pct"])
        # فقط اگر کمترین مقدار منفی باشد bottom را تنظیم کن
        if sorted_r[-1]["pct"] < 0:
            bottom = (sorted_r[-1]["name"], sorted_r[-1]["pct"])
    return {"rows": rows, "top": top, "bottom": bottom}


# ---------------- Local minute history (self-recorded) ----------------
import json as _json
import os as _os

HIST_DIR = "hist"
TTL_MIN = 60  # نگه‌داشتن ۶۰ نقطه‌ی اخیر


def _hist_path(key: str) -> str:
    _os.makedirs(HIST_DIR, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
    return _os.path.join(HIST_DIR, f"{safe}.json")


def record_snapshot(code: str, tgju_id: str = None, binance_sym: str = None):
    """قیمت لحظه‌ای را در تاریخچه‌ی محلی ثبت می‌کند — هر بار که بنر خواسته شه."""
    import time as _t
    # ۱۱. جلوگیری از ثبت تکراری در <55 ثانیه (warm loop نباید history رو شلوغ کنه)
    path = _hist_path(f"local_{code}")
    try:
        now = int(_t.time())
        data = []
        if _os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = _json.load(f)
            except Exception:
                data = []
        # اگه آخرین snapshot تازه‌ست (<55s)، ثبت نکن (بدون duplicate و بدون fetch اضافه)
        if data and now - data[-1][0] < 55:
            return
        price = None
        if not tgju_id and not binance_sym:
            d = get_banner_data(code)
            price = d.get("price") if d else None
        if tgju_id:
            p, _, _ = tgju_quote(tgju_id)
            price = p // 10 if p else None  # تومان
        elif binance_sym:
            try:
                price = float(_get(f"https://api.binance.com/api/v3/ticker/price?symbol={binance_sym}").json()["price"])
            except Exception:
                price = None
        if not price:
            return
        data.append([now, price])
        # حذف نقاط قدیمی‌تر از ۶۰ نقطه یا ۲۴ ساعت
        data = [x for x in data if now - x[0] < 86400][-60:]
        with open(path, "w") as f:
            _json.dump(data, f)
    except Exception as e:
        log.warning("record_snapshot %s: %s", code, e)


def local_history(code: str) -> list:
    """تاریخچه‌ی محلی ثبت‌شده (may be short)."""
    path = _hist_path(f"local_{code}")
    try:
        return _json.load(open(path))
    except Exception:
        return []


def smart_history(code: str, tgju_id: str = None, binance_sym: str = None) -> Tuple[list, str]:
    """
    هوشمندانه‌ترین تاریخچه:
    - اگر تاریخچه‌ی محلی ≥ ۱۰ نقطه → همون (برچسب: 'X دقیقه اخیر')
    - وگرنه تاریخچه‌ی رسمی (TGJU روزانه / Binance ساعتی)
    خروجی: (مقادیر، برچسب)
    """
    local = local_history(code)
    if len(local) >= 10:
        span_min = round((local[-1][0] - local[0][0]) / 60)
        label = f"روند {span_min} دقیقه اخیر (زنده)"
        return [x[1] for x in local], label
    # fallback رسمی
    if tgju_id:
        hist = tgju_history(tgju_id)
        if hist:
            return [x / 10 for x in hist], "روند ۱۴ روز گذشته"
    if binance_sym:
        k = binance_klines(binance_sym)
        if k:
            return k, "روند ۲۴ ساعت گذشته"
    return [], ""

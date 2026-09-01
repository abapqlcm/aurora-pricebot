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
import alanchand

log = logging.getLogger("data")

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
_cache = {}
CACHE_TTL = 15  # کش کوتاه برای سرعت (قیمت هنوز کاملاً زنده)


def _get(url, timeout=12):
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r


def _cached(key, fn):
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]
    v = fn()
    _cache[key] = (now, v)
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
    """بسته‌شدن‌های روزانه از indicator API — کش 1 ساعته (روزانه‌ست، زود عوض نمی‌شه)."""
    key = ("h14", tgju_id)
    import time as _t
    hit = _hist_cache.get(key)
    if hit and _t.time() - hit[0] < 3600:
        return hit[1]
    def fetch():
        try:
            r = _get(f"https://api.tgju.org/v1/market/indicator/summary-table-data/{tgju_id}", timeout=15)
            rows = r.json()["data"][:days]
            closes = []
            for row in rows:
                close = row[3]  # [open, low, high, close, ...]
                closes.append(float(str(close).replace(",", "")))
            v = list(reversed(closes))
            _hist_cache[key] = (_t.time(), v)
            return v
        except Exception as e:
            log.warning("tgju history %s: %s", tgju_id, e)
            return []
    return _cached(("hist", tgju_id), fetch)


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

def _wallex_markets() -> dict:
    """نمادهای والکس — کش ۲۰ ثانیه‌ای (لایو ولی نه هر ثانیه)."""
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
    """قیمت لحظه‌ای تتر تومانی (بازار آزاد = نرخ واقعی دلار)."""
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
        return _fx_rates_cache["rates"]


def fx_to_usd(ccy: str) -> Optional[float]:
    """1 واحد از این ارز چند دلار؟ (مثل SEK → 0.104)"""
    rates = erapi_rates()
    v = rates.get(ccy.upper())
    if not v:
        return None
    return 1.0 / v


# ---------------- واحد یکپارچه ----------------

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
        # ۱) اول بازار روز از Alanchand (خرید/فروش صرافی)
        al = alanchand.get_price(code)
        if al:
            return {
                "name": name, "price": al["sell"], "change_pct": None,
                "change_abs": None,
                "buy": al["buy"], "sell": al["sell"],  # ۱۶. بازه خرید/فروش برای بنر
                "history": ([x / 10 for x in tgju_history(tg_id)] if tg_id else []),
                "unit": "تومان", "source": "Alanchand (بازار روز)",
            }
        # ۲) fallback: Wallex + Binance (لایو)
        usdt_t = usdt_toman()
        price = None
        pct = None
        if code == "dollar":
            # دلار = تتر تومانی (بازار آزاد)
            price = round(usdt_t) if usdt_t else None
            _, pct, _ = wallex_quote("USDTTMN")
        elif tg_id is None:
            # ارزهای بدون TGJU → er-api (نرخ جهانی) × تتر تومانی
            v = fx_to_usd(code)
            if usdt_t and v:
                price = round(usdt_t * v)
        elif usdt_t and fx_sym:
            rate = binance_fx_rate(fx_sym)
            if rate:
                price = round(usdt_t * rate)
        if price is None:
            # fallback: TGJU (ممکنه کند باشه)
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
            "unit": "تومان", "source": "Wallex+Binance (لایو)",
        }

    if code in catalog.GOLD:
        name, tg_id, _ = catalog.GOLD[code]
        p, dp, d = tgju_quote(tg_id)
        hist_rial = tgju_history(tg_id)
        hist = [x / 10 for x in hist_rial]
        return {
            "name": name, "price": p // 10, "change_pct": dp,
            "change_abs": (d // 10 if d else None),
            "history": hist, "unit": "تومان", "source": "TGJU",
        }

    if code in catalog.STABLE:
        name, tg_id, _ = catalog.STABLE[code]
        # تتر داخلی = USDTTMN والکس (لایو)
        last, ch, _ = wallex_quote("USDTTMN")
        if last:
            # از Wallex 24h high/low بگیر
            try:
                r = _get("https://api.wallex.ir/v1/markets?symbol=USDTTMN", timeout=8)
                stats = r.json()['result']['symbols']['USDTTMN']['stats']
                high_24 = float(stats.get('24h_highPrice', last))
                low_24 = float(stats.get('24h_lowPrice', last))
                # fake ohlcv برای chart — ساختار [open, high, low, close] مثل بایننس
                ohlcv = [
                    [low_24, high_24, low_24, low_24],
                    [low_24, high_24, low_24, last],
                    [last, high_24, low_24, last]
                ]
            except:
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
        pct = round((price_usd - p_24) / p_24 * 100, 2) if p_24 else None
        # تاریخچه‌ی ۲۴h به تومان تبدیل می‌کنیم (دلار × تتر داخلی) تا همه چیز تومانی باشه؟
        # نه — کریپتو را دلاری نشان می‌دهیم، استانداردتر است
        ch_abs = price_usd - p_24
        if pct is None:
            pct = round((price_usd - p_24) / p_24 * 100, 2)
        # ۱۷. high/low واقعی ۲۴h از کندل‌های ۱۵ دقیقه‌ای اخیر (۹۶ کندل = ۲۴ ساعت)
        h24 = ohlcv[-96:] if len(ohlcv) >= 96 else ohlcv
        high_24 = max(x[1] for x in h24)
        low_24 = min(x[2] for x in h24)
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
        if sorted_r[0]["pct"] > 0:
            top = (sorted_r[0]["name"], sorted_r[0]["pct"])
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
                data = _json.load(open(path))
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
        _json.dump(data, open(path, "w"))
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

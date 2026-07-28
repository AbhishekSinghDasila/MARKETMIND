"""
Deterministic market data + technical analysis tools.

IMPORTANT: every number in this file (support/resistance levels, RSI, MACD,
moving averages) is computed with real math on real historical price data
via yfinance + pandas + ta. The LLM agents are only ever given these
already-computed numbers to reason about and explain — they never invent
a price level themselves. Getting this wrong is not just "unhelpful" the
way a vague research report is; a hallucinated price level is actively
dangerous, so the boundary between "computed" and "narrated" is a hard
rule in this project.
"""

import time

import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import AverageTrueRange

# Representative large-cap baskets per sector. yfinance doesn't reliably
# expose every NSE sectoral index under a simple ticker, so each sector's
# "view" is derived from the average momentum of its basket instead.
SECTOR_TICKERS = {
    "BANKING": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "IT": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS"],
    "OIL_GAS": ["RELIANCE.NS", "ONGC.NS", "IOC.NS", "BPCL.NS", "GAIL.NS"],
    "PHARMA": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "LUPIN.NS"],
}

INDEX_TICKERS = {"NIFTY50": "^NSEI", "SENSEX": "^BSESN"}

# Reverse lookup: TICKER_SECTOR["RELIANCE.NS"] -> "OIL_GAS"
TICKER_SECTOR = {t: sector for sector, tickers in SECTOR_TICKERS.items() for t in tickers}


# ---------------------------------------------------------------------------
# Simple in-memory TTL cache. Cuts down how many times we actually hit
# Yahoo Finance — the live chart polls every 30s, the portfolio re-fetches
# prices on every view, and repeated analyses of the same stock are common
# during testing/demoing. Reusing a recent fetch instead of re-hitting
# Yahoo every time both speeds up the app and reduces the chance of
# tripping Yahoo's rate limiting in the first place.
# ---------------------------------------------------------------------------
_CACHE: dict = {}


def _cache_get(key, ttl: float):
    entry = _CACHE.get(key)
    if entry and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None


def _cache_set(key, value):
    _CACHE[key] = (time.time(), value)


def _retry(fn, *args, retries: int = 3, base_delay: float = 1.5, **kwargs):
    """Yahoo Finance occasionally rate-limits or briefly hiccups on a request —
    retry with backoff before giving up, instead of failing the whole pipeline
    on one transient error."""
    last_err = None
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(base_delay * (attempt + 1))
    raise last_err


def get_price_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV history for a symbol.

    Tries yf.Ticker(...).history() first (retried with backoff). If that
    still comes back empty — which happens more often for index tickers
    like ^NSEI than individual stocks, and more often under Yahoo rate
    limiting — falls back to yf.download(), which goes through a different
    internal code path in yfinance and often succeeds when .history() alone
    doesn't. Only raises if BOTH approaches fail.

    Cached briefly (see _CACHE above) so repeated calls for the same
    symbol/period/interval within a short window reuse the last fetch
    instead of hitting Yahoo again.
    """
    ttl = 20 if interval != "1d" else 90  # intraday data goes stale faster than daily bars
    cache_key = ("history", symbol, period, interval)
    cached = _cache_get(cache_key, ttl)
    if cached is not None:
        return cached

    try:
        df = _retry(lambda: yf.Ticker(symbol).history(period=period, interval=interval), retries=3, base_delay=2.0)
        if df is not None and not df.empty:
            _cache_set(cache_key, df)
            return df
    except Exception as e:
        print(f"[data.py] Ticker.history() failed for {symbol}: {type(e).__name__}: {e}")

    try:
        df = _retry(
            lambda: yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True),
            retries=3, base_delay=2.0,
        )
        if df is not None and not df.empty:
            # yf.download can return MultiIndex columns even for one ticker; flatten if so.
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            _cache_set(cache_key, df)
            return df
    except Exception as e:
        print(f"[data.py] yf.download() fallback also failed for {symbol}: {type(e).__name__}: {e}")

    raise ValueError(f"No price data returned for {symbol} — check the symbol is correct")


def sector_momentum(sector: str) -> dict:
    """Average % change over 5 days and 1 month across a sector's basket.

    Fetches the whole basket in ONE batched request (yf.download with
    multiple tickers) rather than one request per stock — fewer requests
    means less chance of hitting Yahoo's rate limiting mid-pipeline.
    threads=False on purpose: concurrent per-ticker requests are more
    likely to look bot-like to Yahoo and get individually throttled than
    one sequential batch call.
    """
    tickers = SECTOR_TICKERS[sector]
    cache_key = ("sector_momentum", sector)
    cached = _cache_get(cache_key, ttl=90)
    if cached is not None:
        return cached

    data = _retry(
        lambda: yf.download(tickers, period="2mo", group_by="ticker", threads=False, progress=False, auto_adjust=True)
    )

    changes_5d, changes_1m, per_stock = [], [], []
    for t in tickers:
        close = None
        try:
            close = data[t]["Close"].dropna()
        except Exception:
            close = None

        # If this ticker came back empty in the batch (Yahoo occasionally
        # drops one ticker from a multi-ticker request), retry it alone
        # before giving up on it entirely.
        if close is None or close.empty:
            try:
                solo = _retry(lambda t=t: yf.Ticker(t).history(period="2mo"))
                close = solo["Close"].dropna()
            except Exception:
                continue

        try:
            if close.empty:
                continue
            last = close.iloc[-1]
            c5 = (last / close.iloc[-6] - 1) * 100 if len(close) > 6 else 0.0
            c1m = (last / close.iloc[0] - 1) * 100
            changes_5d.append(c5)
            changes_1m.append(c1m)
            per_stock.append({"ticker": t, "last_price": round(float(last), 2), "change_5d_pct": round(float(c5), 2)})
        except Exception:
            continue

    result = {
        "sector": sector,
        "avg_change_5d_pct": round(float(np.mean(changes_5d)), 2) if changes_5d else 0.0,
        "avg_change_1m_pct": round(float(np.mean(changes_1m)), 2) if changes_1m else 0.0,
        "stocks": per_stock,
    }
    _cache_set(cache_key, result)
    return result


def _find_swing_points(series: pd.Series, window: int = 3) -> list[float]:
    """A point is a swing high/low if it's the max/min within +/- window days."""
    points = []
    for i in range(window, len(series) - window):
        segment = series.iloc[i - window : i + window + 1]
        if series.iloc[i] == segment.max() or series.iloc[i] == segment.min():
            points.append(float(series.iloc[i]))
    return points


def _cluster_levels(points: list[float], current_price: float, tolerance_pct: float = 1.2) -> list[dict]:
    """Group nearby swing points into zones; more touches = stronger level."""
    if not points:
        return []
    points = sorted(points)
    clusters: list[list[float]] = []
    for p in points:
        if clusters and abs(p - clusters[-1][-1]) / clusters[-1][-1] * 100 <= tolerance_pct:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    levels = [{"price": round(float(np.mean(c)), 2), "touches": len(c)} for c in clusters]
    return sorted(levels, key=lambda l: -l["touches"])


def intraday_history(symbol: str) -> dict:
    """Recent intraday candles (5-min bars) for a live-updating chart.

    If the market is closed, yfinance still returns the most recent
    session's data, so this degrades gracefully to "last session" rather
    than erroring out.
    """
    cache_key = ("intraday", symbol)
    cached = _cache_get(cache_key, ttl=20)
    if cached is not None:
        return cached

    df = None
    try:
        df = _retry(lambda: yf.Ticker(symbol).history(period="2d", interval="5m"), retries=3, base_delay=2.0)
    except Exception:
        df = None

    if df is None or df.empty:
        try:
            df = _retry(
                lambda: yf.download(symbol, period="2d", interval="5m", progress=False, auto_adjust=True),
                retries=3, base_delay=2.0,
            )
            if df is not None and isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
        except Exception:
            df = None

    if df is None or df.empty:
        raise ValueError(f"No intraday data returned for {symbol}")
    recent = df.tail(96)  # last ~8 hours of 5-min bars
    points = [
        {"time": idx.strftime("%H:%M"), "close": round(float(row["Close"]), 2)}
        for idx, row in recent.iterrows()
    ]
    last = float(df["Close"].iloc[-1])
    prev_close = float(df["Close"].iloc[0])
    result = {
        "symbol": symbol,
        "points": points,
        "last_price": round(last, 2),
        "change_pct": round((last / prev_close - 1) * 100, 2) if prev_close else 0.0,
    }
    _cache_set(cache_key, result)
    return result


def index_quotes() -> dict:
    """Fast, LLM-free current price + day-change for Nifty & Sensex, for a ticker tape."""
    cached = _cache_get(("index_quotes",), ttl=30)
    if cached is not None:
        return cached

    quotes = {}
    for name, ticker in INDEX_TICKERS.items():
        try:
            df = get_price_history(ticker, period="5d", interval="1d")
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2]) if len(df) > 1 else last
            change_pct = round((last / prev - 1) * 100, 2) if prev else 0.0
            quotes[name] = {"price": round(last, 2), "change_pct": change_pct}
        except Exception:
            quotes[name] = None
    _cache_set(("index_quotes",), quotes)
    return quotes


def technical_snapshot_safe(symbol: str) -> dict:
    """Same as technical_snapshot(), but never raises.

    Used specifically for the Nifty/Sensex lookups inside index_agent(),
    which run on EVERY single request (market overview or stock analysis)
    regardless of what the user actually asked about. A transient Yahoo
    Finance hiccup on the index data shouldn't take down the entire
    pipeline when it's only auxiliary context — degrade gracefully with a
    null snapshot instead, and let the Index Agent's prompt handle nulls.
    """
    try:
        return technical_snapshot(symbol)
    except Exception as e:
        return {
            "symbol": symbol, "current_price": None, "trend": "unknown",
            "sma20": None, "sma50": None, "sma200": None, "rsi_14": None,
            "macd_line": None, "macd_signal": None, "macd_bias": "unknown",
            "resistance_levels": [], "support_levels": [], "price_history": [],
            "atr_14": None, "volatility_pct": None, "risk_label": "unknown",
            "suggested_position_qty": None, "reference_capital": REFERENCE_CAPITAL,
            "risk_pct_per_trade": RISK_PCT_PER_TRADE * 100,
            "data_unavailable": True, "error": str(e),
        }


def get_last_price(symbol: str) -> float:
    """Lightweight current-price lookup for portfolio valuation and paper trades."""
    df = get_price_history(symbol, period="5d", interval="1d")
    return round(float(df["Close"].iloc[-1]), 2)


REFERENCE_CAPITAL = 100000  # ₹1,00,000 — a clearly-labeled illustrative amount, not tied to the paper portfolio's actual cash
RISK_PCT_PER_TRADE = 0.01   # 1% — the standard "fixed-fractional" risk-per-trade rule used in real risk management


def technical_snapshot(symbol: str) -> dict:
    """Compute support/resistance, trend, RSI, MACD, volatility, and a
    position-sizing suggestion for one symbol. All real math."""
    df = get_price_history(symbol, period="9mo")
    close = df["Close"]
    current_price = float(close.iloc[-1])

    swing_points = _find_swing_points(close, window=4)
    clustered = _cluster_levels(swing_points, current_price)
    resistance = sorted(
        [l for l in clustered if l["price"] > current_price], key=lambda l: l["price"]
    )[:3]
    support = sorted(
        [l for l in clustered if l["price"] < current_price], key=lambda l: -l["price"]
    )[:3]

    sma20 = SMAIndicator(close, window=20).sma_indicator().iloc[-1]
    sma50 = SMAIndicator(close, window=50).sma_indicator().iloc[-1]
    sma200 = SMAIndicator(close, window=200).sma_indicator().iloc[-1] if len(close) >= 200 else None
    rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
    macd_ind = MACD(close)
    macd_line = macd_ind.macd().iloc[-1]
    macd_signal = macd_ind.macd_signal().iloc[-1]

    if sma200 is not None and not np.isnan(sma200):
        trend = "uptrend" if current_price > sma50 > sma200 else (
            "downtrend" if current_price < sma50 < sma200 else "sideways/mixed"
        )
    else:
        trend = "uptrend" if current_price > sma50 else "downtrend"

    # Last ~90 trading days of closes, for the frontend to draw an actual
    # price chart with the support/resistance levels overlaid.
    recent = df.tail(90)
    price_history = [
        {"date": idx.strftime("%Y-%m-%d"), "close": round(float(row["Close"]), 2)}
        for idx, row in recent.iterrows()
    ]

    # --- Volatility + position sizing (standard fixed-fractional risk rule) ---
    atr = AverageTrueRange(df["High"], df["Low"], df["Close"], window=14).average_true_range().iloc[-1]
    atr_14 = float(atr) if not np.isnan(atr) else None
    volatility_pct = round(atr_14 / current_price * 100, 2) if atr_14 else None
    if volatility_pct is None:
        risk_label = "unknown"
    elif volatility_pct < 1.5:
        risk_label = "low"
    elif volatility_pct < 3.0:
        risk_label = "medium"
    else:
        risk_label = "high"

    stop_distance = atr_14 * 1.5 if atr_14 else None
    suggested_qty = (
        int((REFERENCE_CAPITAL * RISK_PCT_PER_TRADE) // stop_distance) if stop_distance and stop_distance > 0 else None
    )

    return {
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "trend": trend,
        "sma20": round(float(sma20), 2) if not np.isnan(sma20) else None,
        "sma50": round(float(sma50), 2) if not np.isnan(sma50) else None,
        "sma200": round(float(sma200), 2) if sma200 is not None and not np.isnan(sma200) else None,
        "rsi_14": round(float(rsi), 2) if not np.isnan(rsi) else None,
        "macd_line": round(float(macd_line), 2) if not np.isnan(macd_line) else None,
        "macd_signal": round(float(macd_signal), 2) if not np.isnan(macd_signal) else None,
        "macd_bias": "bullish" if macd_line > macd_signal else "bearish",
        "resistance_levels": resistance,
        "support_levels": support,
        "price_history": price_history,
        "atr_14": round(atr_14, 2) if atr_14 else None,
        "volatility_pct": volatility_pct,
        "risk_label": risk_label,
        "suggested_position_qty": suggested_qty,
        "reference_capital": REFERENCE_CAPITAL,
        "risk_pct_per_trade": RISK_PCT_PER_TRADE * 100,
    }

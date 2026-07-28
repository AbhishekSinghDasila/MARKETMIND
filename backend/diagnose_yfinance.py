"""
Run this directly to see the REAL error yfinance is hitting, with nothing
else (no FastAPI, no retries, no fallback logic) in the way:

    python diagnose_yfinance.py

This will tell us definitively what's actually wrong.
"""

import yfinance as yf

print(f"yfinance version: {yf.__version__}\n")

try:
    import curl_cffi
    print(f"curl_cffi version: {curl_cffi.__version__}")
except ImportError:
    print("curl_cffi is NOT installed (yfinance will fall back to plain requests)")
except Exception as e:
    print(f"curl_cffi import error: {e}")

print("\n--- Test 1: a well-known US stock (AAPL) ---")
try:
    df = yf.Ticker("AAPL").history(period="5d")
    print("SUCCESS, got", len(df), "rows" if not df.empty else "an EMPTY result")
    print(df.tail(2))
except Exception as e:
    print(f"FAILED with: {type(e).__name__}: {e}")

print("\n--- Test 2: an NSE stock (TCS.NS) ---")
try:
    df = yf.Ticker("TCS.NS").history(period="5d")
    print("SUCCESS, got", len(df), "rows" if not df.empty else "an EMPTY result")
    print(df.tail(2))
except Exception as e:
    print(f"FAILED with: {type(e).__name__}: {e}")

print("\n--- Test 3: yf.download() instead of Ticker().history() ---")
try:
    df = yf.download("TCS.NS", period="5d", progress=False)
    print("SUCCESS, got", len(df), "rows" if not df.empty else "an EMPTY result")
    print(df.tail(2))
except Exception as e:
    print(f"FAILED with: {type(e).__name__}: {e}")

print("\nDone. Copy this whole output back to Claude.")

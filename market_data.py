"""
Market Data Engine
==================
Fetches real-time market data via yfinance with IST market hours awareness.
Market timings: 9:15 AM to 3:30 PM IST (Monday to Friday).

Features:
- Automatic market hours detection
- 5-minute interval polling during market hours
- Price data caching in SQLite
- Multi-stock watchlist support
"""

import time
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import pytz
import database as db

# IST timezone
IST = pytz.timezone("Asia/Kolkata")

# Market hours
MARKET_OPEN_TIME = 9  # 9:00 AM IST (pre-open)
MARKET_START_TIME = 9  # 9:15 AM IST (actual start)
MARKET_START_MINUTE = 15
MARKET_CLOSE_TIME = 15  # 3:30 PM IST
MARKET_CLOSE_MINUTE = 30

# Polling interval
POLL_INTERVAL_SECONDS = 60  # 1 minute polling for real-time feel


def is_market_open():
    """Check if the Indian stock market is currently open."""
    now_ist = datetime.now(IST)
    # Weekend check
    if now_ist.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    # Time check: 9:15 AM to 3:30 PM
    market_open = now_ist.replace(hour=MARKET_START_TIME, minute=MARKET_START_MINUTE, second=0, microsecond=0)
    market_close = now_ist.replace(hour=MARKET_CLOSE_TIME, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)

    return market_open <= now_ist <= market_close


def is_pre_market():
    """Check if we're in pre-market hours (9:00-9:15 AM)."""
    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return False
    pre_open = now_ist.replace(hour=9, minute=0, second=0, microsecond=0)
    market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    return pre_open <= now_ist < market_open


def get_market_status() -> str:
    """Get a human-readable market status string."""
    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return "Weekend (Market Closed)"

    market_open = now_ist.replace(hour=MARKET_START_TIME, minute=MARKET_START_MINUTE, second=0, microsecond=0)
    market_close = now_ist.replace(hour=MARKET_CLOSE_TIME, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)

    if now_ist < market_open:
        diff = market_open - now_ist
        minutes = int(diff.total_seconds() / 60)
        return f"Pre-Market (Opens in {minutes} min)"

    if now_ist > market_close:
        return "Market Closed"

    remaining = market_close - now_ist
    hours = int(remaining.total_seconds() / 3600)
    minutes = int((remaining.total_seconds() % 3600) / 60)
    return f"Market Open ({hours}h {minutes}m remaining)"


def get_next_market_open() -> datetime:
    """Get the next market opening time."""
    now_ist = datetime.now(IST)
    # Start from tomorrow
    next_day = now_ist + timedelta(days=1)
    # Find next weekday
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day.replace(hour=MARKET_START_TIME, minute=MARKET_START_MINUTE, second=0, microsecond=0)


def fetch_live_price(symbol: str) -> dict:
    """
    Fetch live price data for a given symbol using yfinance.
    Returns dict with price, high, low, volume, and indicators.
    """
    try:
        ticker = yf.Ticker(symbol)
        # Get current trading data with 5m interval
        df = ticker.history(period="2d", interval="5m")

        if df.empty:
            # Fallback: try 1d
            df = ticker.history(period="1d")

        if df.empty:
            return None

        # Get last row
        last = df.iloc[-1]
        current_price = float(last["Close"])
        high = float(last["High"])
        low = float(last["Low"])
        volume = int(last["Volume"])

        # Get previous day close for daily change
        prev_close = float(df.iloc[-2]["Close"]) if len(df) > 1 else current_price
        day_change = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0

        return {
            "symbol": symbol,
            "price": current_price,
            "high": high,
            "low": low,
            "open": float(last["Open"]),
            "volume": volume,
            "prev_close": prev_close,
            "day_change": round(day_change, 2),
            "timestamp": datetime.now(IST).isoformat(),
        }
    except Exception as e:
        print(f"[MARKET DATA] Error fetching {symbol}: {e}")
        return None


def fetch_quick_price(symbol: str) -> float:
    """
    Lighter/faster live price fetch for bulk watchlist checks.
    Uses the fast quote endpoint instead of a full history download.
    Falls back to fetch_live_price() if the fast path fails.
    Returns the price as float, or None.
    """
    try:
        ticker = yf.Ticker(symbol)
        price = float(ticker.fast_info["last_price"])
        if price and price > 0:
            return price
    except Exception:
        pass
    try:
        data = fetch_live_price(symbol)
        if data and data.get("price"):
            return float(data["price"])
    except Exception:
        pass
    return None


def fetch_historical_data(symbol: str, period: str = "1mo", interval: str = "5m") -> pd.DataFrame:
    """
    Fetch historical data for a symbol.
    Uses 5-minute candles by default for intraday analysis.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if not df.empty:
            # Flatten MultiIndex columns if needed
            if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
                df.columns = df.columns.droplevel(1)
        return df
    except Exception as e:
        print(f"[MARKET DATA] Error fetching history for {symbol}: {e}")
        return pd.DataFrame()


def fetch_batch_prices(symbols: list) -> dict:
    """Fetch live prices for multiple symbols in batch."""
    results = {}
    for symbol in symbols:
        data = fetch_live_price(symbol)
        if data:
            results[symbol] = data
            # Store in DB
            db.record_price(symbol, data["price"], data["high"], data["low"], data["volume"])
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    return results


def poll_market_cycle(watchlist: list = None):
    """
    Run a single market data polling cycle.
    Fetches prices, stores in DB, and returns the data.
    """
    if watchlist is None:
        watchlist = db.get_watchlist()

    if not watchlist:
        print("[MARKET DATA] No watchlist configured.")
        return {}

    # Check if market is open
    if not is_market_open():
        status = get_market_status()
        print(f"[MARKET DATA] {status}. Skipping fetch.")
        return {}

    # Limit to first 15 stocks for performance
    active_watchlist = watchlist[:15]
    print(f"[MARKET DATA] Polling {len(active_watchlist)} stocks...")

    results = fetch_batch_prices(active_watchlist)
    print(f"[MARKET DATA] Fetched {len(results)} prices.")

    return results


def get_market_summary(watchlist: list = None) -> pd.DataFrame:
    """Get a summary DataFrame of current market prices."""
    if watchlist is None:
        watchlist = db.get_watchlist()

    results = fetch_batch_prices(watchlist[:15])

    if not results:
        return pd.DataFrame()

    rows = []
    for symbol, data in results.items():
        rows.append({
            "Symbol": symbol.replace(".NS", ""),
            "LTP": data["price"],
            "Day Change %": data["day_change"],
            "High": data["high"],
            "Low": data["low"],
            "Volume": data["volume"],
        })

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    print(f"[MARKET DATA] Market Status: {get_market_status()}")
    print(f"[MARKET DATA] Market open: {is_market_open()}")

    watchlist = db.get_watchlist()[:5]
    print(f"[MARKET DATA] Watchlist: {watchlist}")

    if is_market_open():
        data = poll_market_cycle(watchlist)
        print(f"[MARKET DATA] Sample data: {list(data.keys())}")
    else:
        print("[MARKET DATA] Using cached/offline data.")
        # Fetch some recent data for offline testing
        for sym in watchlist[:3]:
            hist = fetch_historical_data(sym, period="5d", interval="5m")
            print(f"[MARKET DATA] {sym}: {len(hist)} candles fetched")

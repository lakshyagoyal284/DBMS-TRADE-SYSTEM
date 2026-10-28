"""
Stock Analysis Script
======================
Uses TA-Lib + yfinance to analyze stocks classified by volatility.
Calculates total profit %, annualised return (CAGR), and annualised profit %.

Usage:
    python stock_analysis.py
"""

import numpy as np
import pandas as pd
import talib
import yfinance as yf
from datetime import datetime
import warnings
import os

warnings.filterwarnings("ignore")

# Set UTF-8 encoding for output
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# --- Configuration -----------------------------------------------------------
STOCKS = {
    "Non-Volatile": [
        "SPY",   # S&P 500 ETF
        "BND",   # Vanguard Total Bond Market ETF
        "JNJ",   # Johnson & Johnson
        "PG",    # Procter & Gamble
        "KO",    # Coca-Cola
    ],
    "Volatile": [
        "TSLA",  # Tesla
        "MARA",  # Marathon Digital
        "NVDA",  # NVIDIA
        "GME",   # GameStop
        "AMZN",  # Amazon
    ],
}

PERIOD = "2y"


# --- Metrics Calculation ----------------------------------------------------
def compute_metrics(df: pd.DataFrame, ticker: str) -> dict:
    """Calculate all required metrics from price data."""
    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values

    # Basic Returns
    total_return = (close[-1] - close[0]) / close[0]
    total_profit_pct = total_return * 100

    # Annualised Return (CAGR)
    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25
    if years > 0 and total_return > -1:
        cagr = (1 + total_return) ** (1 / years) - 1
        annualised_return_pct = cagr * 100
    else:
        annualised_return_pct = -100.0 if total_return <= -1 else 0.0
    annualised_profit_pct = annualised_return_pct

    # Daily Returns
    daily_returns = np.diff(close) / close[:-1]

    # TA-Lib Volatility Indicators
    atr = talib.ATR(high, low, close, timeperiod=14)
    atr_current = atr[-1] / close[-1] * 100 if not np.isnan(atr[-1]) else 0

    natr = talib.NATR(high, low, close, timeperiod=14)
    natr_current = natr[-1] if not np.isnan(natr[-1]) else 0

    upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    bb_width = (upper - lower) / middle * 100
    bb_width_current = bb_width[-1] if not np.isnan(bb_width[-1]) else 0

    rsi = talib.RSI(close, timeperiod=14)
    rsi_current = rsi[-1] if not np.isnan(rsi[-1]) else 50

    log_returns = np.diff(np.log(close))
    hist_vol = np.std(log_returns[-20:]) * np.sqrt(252) * 100 if len(log_returns) >= 20 else 0

    vol_score = (natr_current + bb_width_current / 5 + hist_vol / 10) / 3

    return {
        "ticker": ticker,
        "total_profit_pct": round(total_profit_pct, 2),
        "annualised_return_pct": round(annualised_return_pct, 2),
        "annualised_profit_pct": round(annualised_profit_pct, 2),
        "atr_pct": round(atr_current, 2),
        "natr_pct": round(natr_current, 2),
        "bb_width_pct": round(bb_width_current, 2),
        "hist_vol_pct": round(hist_vol, 2),
        "rsi": round(rsi_current, 1),
        "vol_score": round(vol_score, 2),
        "avg_daily_return_pct": round(np.mean(daily_returns) * 100, 3),
        "daily_volatility_pct": round(np.std(daily_returns) * 100, 3),
        "start_price": round(close[0], 2),
        "end_price": round(close[-1], 2),
        "days": days,
    }


# --- Analysis Runner --------------------------------------------------------
def analyze_stocks():
    """Fetch data & compute metrics for all stocks across categories."""
    all_results = []

    print("=" * 100)
    print("  TA-LIB STOCK ANALYSIS -- VOLATILITY & RETURN METRICS")
    print("=" * 100)
    print()
    print(f"  Period: {PERIOD} (ending {datetime.now().strftime('%Y-%m-%d')})")
    print()
    print(f"  CAGR = Compound Annual Growth Rate (annualised return)")
    print()

    for category, tickers in STOCKS.items():
        print(f"  {'-' * 60}")
        print(f"  [ {category.upper()} STOCKS ]")
        print(f"  {'-' * 60}")
        print()

        for ticker in tickers:
            try:
                print(f"  Fetching {ticker}...", end=" ", flush=True)
                df = yf.download(ticker, period=PERIOD, progress=False, auto_adjust=True)
                if df.empty or len(df) < 30:
                    print(f"[SKIP] Insufficient data ({len(df)} days)")
                    continue

                # Flatten MultiIndex columns (newer yfinance versions)
                if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
                    df.columns = df.columns.droplevel(1)

                metrics = compute_metrics(df, ticker)
                all_results.append(metrics)
                print("[OK]")

            except Exception as e:
                print(f"[ERROR] {e}")

    print()
    print("=" * 100)

    if not all_results:
        print("\n  No results to display.\n")
        return all_results

    results_df = pd.DataFrame(all_results)

    # Separate by category
    results_df["category"] = results_df["ticker"].apply(
        lambda t: next(
            (cat for cat, tkrs in STOCKS.items() if t in tkrs),
            "Unknown",
        )
    )

    print()
    print("  " + "=" * 95)
    print("  RESULTS SUMMARY")
    print("  " + "=" * 95)
    print()

    display_cols = [
        "ticker", "category", "total_profit_pct", "annualised_return_pct",
        "annualised_profit_pct", "hist_vol_pct", "atr_pct", "bb_width_pct",
        "rsi", "vol_score", "start_price", "end_price", "days",
    ]

    display_df = results_df[display_cols].copy()
    display_df.columns = [
        "Ticker", "Category", "Total Profit %", "Ann. Return %",
        "Ann. Profit %", "Hist Vol %", "ATR %", "BB Width %",
        "RSI", "Vol Score", "Start $", "End $", "Days",
    ]

    pd.set_option("display.max_columns", 20)
    pd.set_option("display.width", 120)
    pd.set_option("display.colheader_justify", "right")

    print(display_df.to_string(index=False))
    print()

    # Category Averages
    print("  " + "-" * 95)
    print("  CATEGORY AVERAGES")
    print("  " + "-" * 95)
    print()

    avg_cols = [
        "total_profit_pct", "annualised_return_pct", "annualised_profit_pct",
        "hist_vol_pct", "atr_pct", "bb_width_pct", "rsi", "vol_score",
    ]
    avg_labels = [
        "Total Profit %", "Ann. Return %", "Ann. Profit %",
        "Hist Vol %", "ATR %", "BB Width %", "RSI", "Vol Score",
    ]

    for category in ["Non-Volatile", "Volatile"]:
        cat_df = results_df[results_df["category"] == category]
        if cat_df.empty:
            continue
        print(f"  [{category}]")
        for col, label in zip(avg_cols, avg_labels):
            vals = cat_df[col]
            avg = vals.mean()
            print(f"    {label:20s} : {avg:>8.2f}")
        print()

    # Final Comparison
    non_vol = results_df[results_df["category"] == "Non-Volatile"]
    vol = results_df[results_df["category"] == "Volatile"]

    print("  " + "-" * 95)
    print("  VOLATILITY COMPARISON")
    print("  " + "-" * 95)
    print()

    if not non_vol.empty and not vol.empty:
        nv_vol = non_vol["hist_vol_pct"].mean()
        v_vol = vol["hist_vol_pct"].mean()
        nv_ret = non_vol["annualised_return_pct"].mean()
        v_ret = vol["annualised_return_pct"].mean()

        print(f"    Metric                       Non-Volatile    Volatile    Ratio")
        print(f"    {'-' * 67}")
        print(f"    Historical Volatility (%)       {nv_vol:>8.2f}     {v_vol:>8.2f}     {v_vol/nv_vol:>6.2f}x")
        print(f"    ATR (%)                         {non_vol['atr_pct'].mean():>8.2f}     {vol['atr_pct'].mean():>8.2f}     {vol['atr_pct'].mean()/non_vol['atr_pct'].mean():>6.2f}x")
        print(f"    BB Width (%)                    {non_vol['bb_width_pct'].mean():>8.2f}     {vol['bb_width_pct'].mean():>8.2f}     {vol['bb_width_pct'].mean()/non_vol['bb_width_pct'].mean():>6.2f}x")
        print(f"    Ann. Return (%)                 {nv_ret:>8.2f}     {v_ret:>8.2f}     {v_ret/nv_ret if nv_ret != 0 else 0:>6.2f}x")
        print(f"    Ann. Profit (%)                 {non_vol['annualised_profit_pct'].mean():>8.2f}     {vol['annualised_profit_pct'].mean():>8.2f}     {vol['annualised_profit_pct'].mean()/non_vol['annualised_profit_pct'].mean():>6.2f}x")
        print()

    return results_df


# --- Main --------------------------------------------------------------------
if __name__ == "__main__":
    results = analyze_stocks()
    print("  [Done]")

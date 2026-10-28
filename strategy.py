"""
Trading Strategy Engine
=======================
Generates buy/sell signals using TA-Lib technical indicators.
Real-time, unbiased, data-driven strategy.

Core Strategy: RSI + Bollinger Bands Mean Reversion with Volume Confirmation

Entry Rules:
  BUY  - RSI(14) < 30 (oversold) AND price near/lower BB(20,2) AND Volume > 1.2x avg
  SELL - RSI(14) > 70 (overbought) AND price near/upper BB(20,2) AND Volume > 1.2x avg

Exit Rules:
  - Stop Loss: 3% below entry
  - Take Profit: RSI crosses back above 50 (for buy) or below 50 (for sell)
  - Trailing Stop: 2% trailing after 3% profit
"""

import numpy as np
import pandas as pd
import talib
from datetime import datetime
import pytz
import database as db

IST = pytz.timezone("Asia/Kolkata")


def compute_indicators(df: pd.DataFrame) -> dict:
    """
    Compute all TA-Lib indicators for a given price DataFrame.
    Returns the latest indicator values.
    """
    if df.empty or len(df) < 30:
        return {}

    close = df["Close"].values.astype(np.float64)
    high = df["High"].values.astype(np.float64)
    low = df["Low"].values.astype(np.float64)
    volume = df["Volume"].values.astype(np.float64)

    # --- RSI ---
    rsi = talib.RSI(close, timeperiod=14)
    rsi_current = rsi[-1] if not np.isnan(rsi[-1]) else 50.0
    rsi_prev = rsi[-2] if len(rsi) > 1 and not np.isnan(rsi[-2]) else rsi_current

    # --- Bollinger Bands ---
    upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    bb_upper = upper[-1] if not np.isnan(upper[-1]) else close[-1]
    bb_middle = middle[-1] if not np.isnan(middle[-1]) else close[-1]
    bb_lower = lower[-1] if not np.isnan(lower[-1]) else close[-1]

    # Price position within Bollinger Bands (0 = lower, 100 = upper, 50 = middle)
    bb_range = bb_upper - bb_lower
    bb_position_pct = ((close[-1] - bb_lower) / bb_range) * 100 if bb_range > 0 else 50
    bb_width_pct = ((bb_upper - bb_lower) / bb_middle) * 100

    # --- Volume Analysis ---
    volume_sma = talib.SMA(volume, timeperiod=20)
    vol_sma_current = volume_sma[-1] if not np.isnan(volume_sma[-1]) else volume[-1]
    volume_ratio = volume[-1] / vol_sma_current if vol_sma_current > 0 else 1.0

    # --- ATR for volatility ---
    atr = talib.ATR(high, low, close, timeperiod=14)
    atr_current = atr[-1] if not np.isnan(atr[-1]) else 0

    # --- Moving Averages ---
    sma_20 = talib.SMA(close, timeperiod=20)
    sma_50 = talib.SMA(close, timeperiod=50)
    sma_20_current = sma_20[-1] if not np.isnan(sma_20[-1]) else close[-1]
    sma_50_current = sma_50[-1] if not np.isnan(sma_50[-1]) else close[-1]

    # --- MACD ---
    macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    macd_current = macd[-1] if not np.isnan(macd[-1]) else 0
    macd_signal_current = macd_signal[-1] if not np.isnan(macd_signal[-1]) else 0

    # Price relative to MAs
    price_above_sma20 = close[-1] > sma_20_current
    price_above_sma50 = close[-1] > sma_50_current if not np.isnan(sma_50_current) else True

    return {
        "close": close[-1],
        "rsi": rsi_current,
        "rsi_prev": rsi_prev,
        "bb_upper": bb_upper,
        "bb_middle": bb_middle,
        "bb_lower": bb_lower,
        "bb_position_pct": bb_position_pct,
        "bb_width_pct": bb_width_pct,
        "volume_ratio": volume_ratio,
        "atr": atr_current,
        "atr_pct": (atr_current / close[-1]) * 100 if close[-1] > 0 else 0,
        "sma_20": sma_20_current,
        "sma_50": sma_50_current,
        "price_above_sma20": price_above_sma20,
        "price_above_sma50": price_above_sma50,
        "macd": macd_current,
        "macd_signal": macd_signal_current,
        "macd_histogram": macd_hist[-1] if len(macd_hist) > 0 and not np.isnan(macd_hist[-1]) else 0,
    }


def evaluate_signal(indicators: dict, symbol: str) -> dict:
    """
    Evaluate trading signal based on indicators.

    Returns a dict with signal info, or None if no signal.
    """
    if not indicators:
        return None

    close = indicators["close"]
    rsi = indicators["rsi"]
    bb_position = indicators["bb_position_pct"]
    volume_ratio = indicators["volume_ratio"]
    atr_pct = indicators["atr_pct"]
    price_above_sma20 = indicators["price_above_sma20"]
    price_above_sma50 = indicators["price_above_sma50"]
    macd = indicators["macd"]
    macd_signal = indicators["macd_signal"]

    signal = None
    signal_type = None
    strength = 0
    reasons = []

    # --- BUY Signal Conditions ---
    buy_score = 0

    # Condition 1: RSI Oversold (< 30)
    if rsi < 30:
        buy_score += 30
        reasons.append(f"RSI oversold ({rsi:.1f})")
    elif rsi < 35:
        buy_score += 15
        reasons.append(f"RSI near oversold ({rsi:.1f})")

    # Condition 2: Price near lower Bollinger Band (below 30% of band)
    if bb_position < 20:
        buy_score += 25
        reasons.append(f"Price at lower BB ({bb_position:.0f}%)")
    elif bb_position < 35:
        buy_score += 12
        reasons.append(f"Price near lower BB ({bb_position:.0f}%)")

    # Condition 3: Volume confirmation
    if volume_ratio > 1.5:
        buy_score += 20
        reasons.append(f"High volume ({volume_ratio:.1f}x avg)")
    elif volume_ratio > 1.2:
        buy_score += 10
        reasons.append(f"Above avg volume ({volume_ratio:.1f}x avg)")

    # Condition 4: MACD bullish crossover (or near)
    if macd > macd_signal and macd < 0:
        buy_score += 15
        reasons.append("MACD turning bullish")
    elif macd > macd_signal:
        buy_score += 8

    # Condition 5: Price above SMA20 (trend context)
    if price_above_sma20:
        buy_score += 5

    # Condition 6: Low volatility (safer entry)
    if atr_pct < 3:
        buy_score += 5

    # Total buy strength
    if buy_score >= 50:
        signal_type = "BUY"
        strength = buy_score

    # --- SELL Signal Conditions ---
    sell_score = 0
    sell_reasons = []

    # Condition 1: RSI Overbought (> 70)
    if rsi > 70:
        sell_score += 30
        sell_reasons.append(f"RSI overbought ({rsi:.1f})")
    elif rsi > 65:
        sell_score += 15
        sell_reasons.append(f"RSI near overbought ({rsi:.1f})")

    # Condition 2: Price near upper Bollinger Band (above 70% of band)
    if bb_position > 80:
        sell_score += 25
        sell_reasons.append(f"Price at upper BB ({bb_position:.0f}%)")
    elif bb_position > 65:
        sell_score += 12
        sell_reasons.append(f"Price near upper BB ({bb_position:.0f}%)")

    # Condition 3: Volume confirmation
    if volume_ratio > 1.5:
        sell_score += 20
        sell_reasons.append(f"High volume ({volume_ratio:.1f}x avg)")
    elif volume_ratio > 1.2:
        sell_score += 10
        sell_reasons.append(f"Above avg volume ({volume_ratio:.1f}x avg)")

    # Condition 4: MACD bearish crossover
    if macd < macd_signal and macd > 0:
        sell_score += 15
        sell_reasons.append("MACD turning bearish")
    elif macd < macd_signal:
        sell_score += 8

    # Condition 5: High volatility (risky to hold)
    if atr_pct > 4:
        sell_score += 5

    if sell_score >= 50:
        # Only override buy if sell is stronger
        if signal_type is None or sell_score > buy_score:
            signal_type = "SELL"
            strength = sell_score
            reasons = sell_reasons

    # Determine BB position label
    if bb_position < 30:
        bb_pos_label = "lower"
    elif bb_position > 70:
        bb_pos_label = "upper"
    else:
        bb_pos_label = "middle"

    if signal_type:
        signal = {
            "symbol": symbol,
            "signal_type": signal_type,
            "strength": float(strength),
            "price": float(close),
            "rsi": float(rsi),
            "bb_position": bb_pos_label,
            "volume_ratio": float(volume_ratio),
            "reason": "; ".join(reasons),
            "timestamp": datetime.now(IST).isoformat(),
        }

    return signal


def scan_symbol(symbol: str, period: str = "5d", interval: str = "5m") -> dict:
    """
    Scan a single symbol for trading signals.
    Fetches recent data, computes indicators, and evaluates signals.
    """
    from market_data import fetch_historical_data

    df = fetch_historical_data(symbol, period=period, interval=interval)
    if df.empty or len(df) < 30:
        return None

    indicators = compute_indicators(df)
    if not indicators:
        return None

    signal = evaluate_signal(indicators, symbol)

    if signal:
        # Record the signal in the database
        signal_id = db.record_signal(
            symbol=signal["symbol"],
            signal_type=signal["signal_type"],
            price=signal["price"],
            strength=signal["strength"],
            rsi=signal["rsi"],
            bb_position=signal["bb_position"],
            volume_ratio=signal["volume_ratio"],
            reason=signal["reason"],
        )
        signal["id"] = signal_id
        print(f"[STRATEGY] {signal['signal_type']} signal for {symbol} "
              f"(strength: {signal['strength']:.0f}, RSI: {signal['rsi']:.1f})")
        print(f"[STRATEGY]   Reason: {signal['reason']}")

    return signal


def scan_watchlist(watchlist: list = None) -> list:
    """
    Scan entire watchlist for trading signals.
    Returns list of signals found.
    """
    if watchlist is None:
        watchlist = db.get_watchlist()

    if not watchlist:
        print("[STRATEGY] Empty watchlist.")
        return []

    signals = []
    # Limit to first 15 for performance
    for symbol in watchlist[:15]:
        signal = scan_symbol(symbol)
        if signal:
            signals.append(signal)

    print(f"[STRATEGY] Scan complete. {len(signals)} signals generated.")
    return signals


def get_exit_signal(holding_symbol: str, entry_price: float,
                    entry_rsi: float, current_rsi: float,
                    current_price: float, indicators: dict) -> dict:
    """
    Check if we should exit an existing position.

    Returns exit signal dict or None.
    """
    if not indicators:
        return None

    exit_reason = None

    # 1. Stop Loss: 3% below entry
    stop_loss_pct = float(db.get_config("stop_loss_pct"))
    stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
    if current_price <= stop_loss_price:
        exit_reason = f"Stop loss hit ({stop_loss_pct:.0f}%)"

    # 2. Take Profit: RSI mean reversion
    # If we bought at RSI < 30 and it crossed back above 50
    if entry_rsi < 35 and current_rsi > 55:
        exit_reason = f"RSI mean reversion ({entry_rsi:.0f} -> {current_rsi:.0f})"

    # 3. Take Profit: fixed target
    take_profit_pct = float(db.get_config("take_profit_pct"))
    take_profit_price = entry_price * (1 + take_profit_pct / 100)
    if current_price >= take_profit_price:
        exit_reason = f"Take profit target ({take_profit_pct:.0f}%)"

    # 4. Trailing stop: if price went up 3%, trail by 2%
    gain_pct = ((current_price - entry_price) / entry_price) * 100
    if gain_pct > 3:
        # Simple trailing: if dropped 2% from peak
        trailing_stop = entry_price * (1 + gain_pct / 100 - 0.02)
        if current_price <= trailing_stop:
            exit_reason = f"Trailing stop hit (gain {gain_pct:.1f}% -> drop)"

    if exit_reason:
        return {
            "symbol": holding_symbol,
            "signal_type": "EXIT",
            "strength": 80,
            "price": current_price,
            "reason": exit_reason,
            "timestamp": datetime.now(IST).isoformat(),
        }

    return None


if __name__ == "__main__":
    print("[STRATEGY] Running strategy scan...")
    signals = scan_watchlist(db.get_watchlist()[:5])
    print(f"[STRATEGY] Found {len(signals)} signals.")
    for s in signals:
        print(f"  {s['signal_type']} {s['symbol']} @ {s['price']:.2f} (strength: {s['strength']:.0f})")
        print(f"    Reason: {s['reason']}")

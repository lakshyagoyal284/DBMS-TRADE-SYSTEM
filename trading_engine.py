"""
Trading Engine
==============
Executes paper trades based on signals from the strategy engine.
Manages portfolio: buying, selling, position sizing, risk management.

Real-world features:
- Slippage simulation (0.1% per trade)
- Market hours only trading
- Position sizing (max 15% of capital per position)
- Max 5 concurrent positions
- Stop loss and take profit management
- Email notifications on buy/sell
"""

import time
import numpy as np
import pandas as pd
from datetime import datetime
import pytz
import database as db
from market_data import is_market_open, fetch_live_price, fetch_quick_price, get_market_status
from strategy import scan_symbol, compute_indicators, get_exit_signal
from market_data import fetch_historical_data
import email_notifier
import whatsapp_notifier

IST = pytz.timezone("Asia/Kolkata")


def get_position_size(symbol: str, price: float) -> tuple:
    """
    Calculate position size based on available capital and risk.

    Returns (shares_to_buy, investment_amount)
    """
    cash = db.get_cash_balance()
    max_position_pct = float(db.get_config("max_position_pct"))
    max_positions = float(db.get_config("max_positions"))

    # Check current number of open positions
    current_positions = db.get_holdings()
    if not current_positions.empty:
        if len(current_positions) >= max_positions:
            print(f"[TRADING] Max positions ({max_positions}) reached. Cannot open new.")
            return (0, 0)

    # Max investment per position
    max_investment = cash * (max_position_pct / 100)

    # Limit to 15% of available cash
    position_capital = min(max_investment, cash * 0.15)

    # Calculate shares (round down to nearest integer)
    shares = int(position_capital / price)

    # Minimum trade value (at least Rs. 500)
    min_trade_value = 500
    if shares * price < min_trade_value:
        return (0, 0)

    return (shares, round(shares * price, 2))


def execute_buy(symbol: str, price: float, signal_id: int = None,
                reason: str = "Strategy Signal") -> dict:
    """
    Execute a buy trade (paper trading).
    Returns trade result dict or None if failed.
    """
    if not is_market_open():
        status = get_market_status()
        print(f"[TRADING] Cannot execute buy - {status}")
        return {"success": False, "reason": f"Market closed: {status}"}

    cash = db.get_cash_balance()

    # Calculate position size
    shares, investment = get_position_size(symbol, price)

    if shares <= 0 or investment <= 0:
        return {"success": False, "reason": "Insufficient capital or position too small"}

    if cash < investment:
        return {"success": False, "reason": f"Insufficient cash (need Rs.{investment:.0f}, have Rs.{cash:.0f})"}

    # Apply realistic slippage (0.1%)
    slippage = price * 0.001
    exec_price = price + slippage
    trade_value = round(shares * exec_price, 2)

    # Update cash
    new_cash = cash - trade_value
    db.update_cash_balance(new_cash)

    # Get entry RSI from signal
    entry_rsi = None
    if signal_id:
        conn = db.get_connection()
        sig = conn.execute("SELECT rsi FROM signals WHERE id = ?", (signal_id,)).fetchone()
        if sig and sig["rsi"]:
            entry_rsi = sig["rsi"]
        conn.close()
    
    # Update holdings
    db.update_holding(symbol, shares, exec_price, entry_rsi=entry_rsi)

    # Record trade
    db.record_trade(
        symbol=symbol, side="BUY", quantity=shares,
        price=exec_price, realized_pnl=0, realized_pnl_pct=0,
        reason=reason, signal_id=signal_id
    )

    result = {
        "success": True,
        "symbol": symbol,
        "side": "BUY",
        "shares": shares,
        "price": exec_price,
        "investment": trade_value,
        "slippage": round(slippage, 2),
        "remaining_cash": new_cash,
        "reason": reason,
        "timestamp": datetime.now(IST).isoformat(),
    }

    print(f"[TRADING] BUY {shares} {symbol} @ Rs.{exec_price:.2f} = Rs.{trade_value:.0f}")

    # Send notifications
    email_notifier.send_buy_notification(result)
    whatsapp_notifier.send_trade_notification(result)

    return result


def execute_sell(symbol: str, price: float, quantity: int = None,
                 signal_id: int = None, reason: str = "Strategy Signal") -> dict:
    """
    Execute a sell trade (paper trading).
    If quantity is None, sells entire position.
    """
    if not is_market_open():
        status = get_market_status()
        print(f"[TRADING] Cannot execute sell - {status}")
        return {"success": False, "reason": f"Market closed: {status}"}

    # Get current holding
    holdings = db.get_holdings()
    holding = holdings[holdings["symbol"] == symbol]

    if holding.empty:
        return {"success": False, "reason": f"No holdings for {symbol}"}

    holding = holding.iloc[0]
    current_qty = int(holding["quantity"])
    avg_price = float(holding["avg_buy_price"])

    if quantity is None or quantity > current_qty:
        quantity = current_qty

    if quantity <= 0:
        return {"success": False, "reason": "Invalid quantity"}

    # Apply realistic slippage (0.1%)
    slippage = price * 0.001
    exec_price = price - slippage
    trade_value = round(quantity * exec_price, 2)

    # Calculate realized P&L
    buy_cost = quantity * avg_price
    realized_pnl = trade_value - buy_cost
    realized_pnl_pct = ((exec_price - avg_price) / avg_price) * 100

    # Update cash
    cash = db.get_cash_balance()
    new_cash = cash + trade_value
    db.update_cash_balance(new_cash)

    # Update holdings
    new_qty = current_qty - quantity
    if new_qty <= 0:
        db.remove_holding(symbol)
        db.clear_alert_price(symbol)
    else:
        db.update_holding(symbol, -quantity, exec_price)

    # Record trade
    db.record_trade(
        symbol=symbol, side="SELL", quantity=quantity,
        price=exec_price, realized_pnl=round(realized_pnl, 2),
        realized_pnl_pct=round(realized_pnl_pct, 2),
        reason=reason, signal_id=signal_id
    )

    result = {
        "success": True,
        "symbol": symbol,
        "side": "SELL",
        "shares": quantity,
        "price": exec_price,
        "trade_value": trade_value,
        "realized_pnl": round(realized_pnl, 2),
        "realized_pnl_pct": round(realized_pnl_pct, 2),
        "slippage": round(slippage, 2),
        "remaining_cash": new_cash,
        "reason": reason,
        "timestamp": datetime.now(IST).isoformat(),
    }

    print(f"[TRADING] SELL {quantity} {symbol} @ Rs.{exec_price:.2f} = "
          f"Rs.{trade_value:.0f} (P&L: Rs.{realized_pnl:.0f}, {realized_pnl_pct:.1f}%)")

    # Send notifications
    email_notifier.send_sell_notification(result)
    whatsapp_notifier.send_trade_notification(result)

    return result


def update_holdings_prices():
    """Update current market prices for all open holdings."""
    holdings = db.get_holdings()
    if holdings.empty:
        return

    for _, holding in holdings.iterrows():
        symbol = holding["symbol"]
        price_data = fetch_live_price(symbol)
        if price_data:
            current_price = price_data["price"]
            db.update_holding(symbol, 0, current_price)


def check_price_rises():
    """
    Check all holdings for price rises and send email alerts.
    Only sends alerts if:
      - Email rise alerts are enabled
      - Price has risen above the last notified price by the configured threshold
      - Price is above the buy price (positive movement)
    """
    holdings = db.get_holdings()
    if holdings.empty:
        return

    if not email_notifier.is_rise_alert_enabled():
        return

    threshold_pct = email_notifier.get_rise_alert_threshold()
    stop_loss_pct = float(db.get_config("stop_loss_pct"))
    take_profit_pct = float(db.get_config("take_profit_pct"))

    for _, holding in holdings.iterrows():
        symbol = holding["symbol"]
        avg_buy_price = float(holding["avg_buy_price"])
        current_price = float(holding["current_price"])
        quantity = int(holding["quantity"])
        buy_value = float(holding["buy_value"])
        current_value = float(holding["current_value"])
        unrealized_pnl = float(holding["unrealized_pnl"])
        unrealized_pnl_pct = float(holding["unrealized_pnl_pct"])

        # Only alert if price is above buy price (positive movement)
        if current_price <= avg_buy_price:
            continue

        # Get last notified price
        last_notified = db.get_last_alert_price(symbol)

        # Calculate rise since last notification
        if last_notified > 0:
            rise_since_last = ((current_price - last_notified) / last_notified) * 100
        else:
            # First notification for this symbol
            rise_since_last = threshold_pct + 1  # Force send

        # Only send if price has risen by at least the threshold from last notification
        if rise_since_last < threshold_pct:
            continue

        # Get current RSI from recent indicators
        current_rsi = "N/A"
        try:
            from market_data import fetch_historical_data
            df = fetch_historical_data(symbol, period="2d", interval="5m")
            if not df.empty:
                from strategy import compute_indicators
                indicators = compute_indicators(df)
                if indicators and "rsi" in indicators:
                    current_rsi = f"{indicators['rsi']:.1f}"
        except Exception:
            pass

        # Get entry RSI
        entry_rsi = holding["entry_rsi"]
        entry_rsi_str = f"{entry_rsi:.1f}" if entry_rsi else "N/A"

        # Calculate stop loss and take profit prices
        stop_loss_price = avg_buy_price * (1 - stop_loss_pct / 100)
        take_profit_price = avg_buy_price * (1 + take_profit_pct / 100)

        # Build plan details
        plan_details = (
            f"🟢 <b>Strategy:</b> RSI + Bollinger Bands Mean Reversion\n"
            f"• Entered at Rs.{avg_buy_price:.2f} (RSI: {entry_rsi_str})\n"
            f"• Current RSI: {current_rsi} — {'Bullish' if current_rsi != 'N/A' and float(current_rsi) > 50 else 'Neutral/Bearish' if current_rsi != 'N/A' else 'Unknown'}\n"
            f"• Stop Loss: Rs.{stop_loss_price:.2f} ({stop_loss_pct:.0f}% below entry)\n"
            f"• Take Profit: Rs.{take_profit_price:.2f} ({take_profit_pct:.0f}% above entry)\n"
            f"• RSI Exit: When RSI crosses back above 50 (mean reversion complete)\n"
            f"• Trailing Stop: 2% trail activates after 3% gain"
        )

        holding_data = {
            "symbol": symbol,
            "quantity": quantity,
            "avg_buy_price": avg_buy_price,
            "current_price": current_price,
            "buy_value": buy_value,
            "current_value": current_value,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "entry_rsi": entry_rsi_str,
            "current_rsi": current_rsi,
            "stop_loss_price": round(stop_loss_price, 2),
            "take_profit_price": round(take_profit_price, 2),
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "plan_details": plan_details,
        }

        # Send the price rise alert
        email_notifier.send_price_rise_notification(holding_data)

        # Update the last notified price
        db.update_last_alert_price(symbol, current_price)

        print(f"[PRICE ALERT] {symbol} rose to Rs.{current_price:.2f} "
              f"(+{unrealized_pnl_pct:.1f}%, profit: Rs.{unrealized_pnl:,.0f}). Email sent.")



def check_watchlist_price_rises(batch_size: int = 25):
    """
    Watchlist-wide price rise alerts (holdings excluded - covered elsewhere).

    To avoid hammering Yahoo with 475 requests per cycle, symbols are checked
    in round-robin batches: `batch_size` symbols per trading cycle, so the whole
    watchlist is swept roughly every (watchlist_size / batch_size) cycles.

    Anti-spam rules:
      * First sight of a symbol only records the baseline price (no email),
        so a fresh install doesn't flood the inbox.
      * After that, an email fires only when the price rises >= threshold %
        above the last alerted price (same 1%-step throttle as holdings).
    """
    if db.get_config("watchlist_rise_alerts") == "false":
        return
    if not email_notifier.is_rise_alert_enabled():
        return

    threshold_pct = email_notifier.get_rise_alert_threshold()
    watchlist = db.get_watchlist()
    if not watchlist:
        return

    # Skip symbols we already hold (those are covered by check_price_rises)
    holdings = db.get_holdings()
    held = set(holdings["symbol"]) if not holdings.empty else set()
    watchlist = [s for s in watchlist if s not in held]
    if not watchlist:
        return

    # Round-robin cursor so each symbol is checked eventually
    try:
        cursor = int(float(db.get_config("watchlist_alert_cursor") or "0"))
    except Exception:
        cursor = 0
    cursor = cursor % len(watchlist)
    batch = [watchlist[(cursor + i) % len(watchlist)] for i in range(min(batch_size, len(watchlist)))]
    db.set_config("watchlist_alert_cursor", str((cursor + batch_size) % len(watchlist)))

    for symbol in batch:
        try:
            current_price = fetch_quick_price(symbol)
        except Exception:
            current_price = None
        if not current_price or current_price <= 0:
            continue

        last_notified = db.get_last_alert_price(symbol)
        if last_notified <= 0:
            # First time seeing this symbol - set the baseline, don't email.
            db.update_last_alert_price(symbol, current_price)
            continue

        rise_pct = ((current_price - last_notified) / last_notified) * 100
        if rise_pct >= threshold_pct:
            email_notifier.send_watchlist_rise_notification(
                symbol, current_price, rise_pct, last_notified
            )
            db.update_last_alert_price(symbol, current_price)
            print(f"[WATCHLIST ALERT] {symbol} rose to Rs.{current_price:.2f} "
                  f"(+{rise_pct:.1f}% since last alert). Email sent.")


def check_exit_conditions():
    """
    Check all open positions for exit conditions (stop loss, take profit).
    Returns list of exit trades executed.
    """
    holdings = db.get_holdings()
    exits = []

    if holdings.empty:
        return exits

    for _, holding in holdings.iterrows():
        symbol = holding["symbol"]
        entry_price = float(holding["avg_buy_price"])
        entry_rsi = float(holding["entry_rsi"]) if holding["entry_rsi"] else 30.0
        current_price = float(holding["current_price"])

        # Fetch recent data for indicators
        df = fetch_historical_data(symbol, period="2d", interval="5m")
        if df.empty:
            continue

        indicators = None
        try:
            from strategy import compute_indicators
            indicators = compute_indicators(df)
        except:
            pass

        current_rsi = indicators.get("rsi", 50) if indicators else 50

        # Check exit signal with REAL entry RSI, not hardcoded 30
        exit_sig = get_exit_signal(symbol, entry_price, entry_rsi,
                                     current_rsi,
                                     current_price, indicators or {})

        if exit_sig:
            result = execute_sell(symbol, current_price, reason=exit_sig["reason"])
            if result["success"]:
                exits.append(result)

    return exits


def process_signals():
    """
    Main trading cycle: scan for signals and execute trades.
    Runs during market hours.
    """
    if not is_market_open():
        return {"status": "closed", "message": get_market_status()}

    print("\n" + "=" * 60)
    print(f"[TRADING] Trading cycle at {datetime.now(IST).strftime('%H:%M:%S')} IST")
    print("=" * 60)

    results = {"buys": [], "sells": [], "signals_processed": 0}

    # 1. Update current prices for holdings
    update_holdings_prices()

    # 1b. Check for price rises and send email alerts (held stocks)
    check_price_rises()

    # 1c. Watchlist-wide price rise alerts (round-robin batches)
    check_watchlist_price_rises()

    # 2. Check exit conditions first
    exits = check_exit_conditions()
    results["sells"] = exits
    for exit_trade in exits:
        print(f"[TRADING] Exited {exit_trade['symbol']}: {exit_trade['reason']}")

    # 3. Scan for new buy signals
    from strategy import scan_watchlist
    signals = scan_watchlist()
    results["signals_processed"] = len(signals)

    # 4. Execute buy signals
    max_positions = int(float(db.get_config("max_positions")))
    current_positions = db.get_holdings()

    for signal in signals:
        if signal["signal_type"] == "BUY":
            # Check if we already have this symbol
            if not current_positions.empty and signal["symbol"] in current_positions["symbol"].values:
                print(f"[TRADING] Already holding {signal['symbol']}. Skipping.")
                continue

            # Check max positions
            if len(current_positions) >= max_positions:
                print(f"[TRADING] Max positions ({max_positions}) reached.")
                break

            # Execute buy
            result = execute_buy(
                symbol=signal["symbol"],
                price=signal["price"],
                signal_id=signal.get("id"),
                reason=signal["reason"]
            )
            if result["success"]:
                results["buys"].append(result)
                current_positions = db.get_holdings()

    # 5. Record portfolio snapshot
    summary = db.get_dashboard_summary()
    db.record_portfolio_snapshot(
        cash=summary["cash_balance"],
        invested=summary["invested_value"],
        unrealized_pnl=summary["unrealized_pnl"],
        realized_pnl=summary["realized_pnl"],
        day_pnl=0  # Will calculate properly in full implementation
    )

    # 6. Send periodic portfolio summaries (every N minutes)
    email_notifier.maybe_send_summary_email()
    whatsapp_notifier.maybe_send_summary()

    return results


def run_trading_loop(interval_seconds: int = 300):
    """
    Run the main trading loop.
    Polls for signals and executes trades every N seconds during market hours.
    
    Args:
        interval_seconds: Time between trading cycles (default 300 = 5 min)
    """
    print("=" * 60)
    print("  REAL-TIME TRADING ENGINE STARTED")
    print(f"  Market: NSE (9:15 AM - 3:30 PM IST)")
    print(f"  Check interval: {interval_seconds}s")
    print("=" * 60)

    while True:
        try:
            if is_market_open():
                results = process_signals()
                summary = db.get_dashboard_summary()
                print(f"\n[TRADING] Cycle complete:")
                print(f"  Buys: {len(results['buys'])} | Sells: {len(results['sells'])}")
                print(f"  Portfolio: Rs.{summary['total_portfolio_value']:.0f} "
                      f"(P&L: Rs.{summary['total_pnl']:.0f}, {summary['total_returns_pct']:.1f}%)")
                print(f"  Open positions: {summary['num_open_positions']} | Cash: Rs.{summary['cash_balance']:.0f}")
            else:
                status = get_market_status()
                print(f"[TRADING] {status}. Waiting for market open...", end="\r")

            # Wait for next cycle
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n[TRADING] Stopped by user.")
            break
        except Exception as e:
            print(f"\n[TRADING] Error in trading loop: {e}")
            time.sleep(interval_seconds)


if __name__ == "__main__":
    # Initialize DB
    db.init_db()

    # Run a single cycle
    results = process_signals()
    print(f"\n[TRADING] Cycle results:")
    print(f"  Buy trades: {len(results['buys'])}")
    print(f"  Sell trades: {len(results['sells'])}")
    print(f"  Signals processed: {results['signals_processed']}")

    # Show portfolio summary
    summary = db.get_dashboard_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")

"""
Stock Trading Dashboard
=======================
Real-time trading dashboard built with Streamlit.
Features:
- Live portfolio tracking with auto-refresh
- P&L analysis (realized, unrealized, daily)
- Open positions with entry/current prices
- Trade history with win/loss breakdown
- Trading signals from TA-Lib strategy
- Equity curve and performance charts
- Market hours indicator (IST)
- SQLite database for persistent data
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
import time
import sys
import os

# Fix encoding for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (OSError, AttributeError):
        # stdout may not support reconfigure in some terminals
        pass

# Ensure the current directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from market_data import (
    get_market_status, is_market_open, fetch_live_price, 
    get_market_summary, fetch_historical_data, poll_market_cycle
)
from strategy import scan_symbol
from trading_engine import (
    execute_buy, execute_sell, process_signals,
    update_holdings_prices
)
import email_notifier
import whatsapp_notifier

# --- Page Config ---
st.set_page_config(
    page_title="Live Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #3a3a5e;
    }
    .profit { color: #00ff88; font-weight: bold; }
    .loss { color: #ff4444; font-weight: bold; }
    .neutral { color: #888888; }
    .market-open { color: #00ff88; }
    .market-closed { color: #ff4444; }
    .header-text { color: #e0e0e0; font-size: 1.1em; }
    .card-title { color: #888; font-size: 0.85em; text-transform: uppercase; }
    .card-value { font-size: 1.8em; font-weight: bold; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- Initialize ---
if "initialized" not in st.session_state:
    db.init_db()
    st.session_state.initialized = True
    st.session_state.last_refresh = datetime.now()
    st.session_state.auto_refresh = False
    # Load trading active state from DB (persistent across restarts)
    trading_state = db.get_config("trading_active")
    st.session_state.trading_active = (trading_state == "true")
    if st.session_state.trading_active:
        st.session_state.auto_refresh = True


def format_currency(val):
    """Format value as currency."""
    if val >= 0:
        return f"Rs.{val:,.2f}"
    return f"-Rs.{abs(val):,.2f}"


def format_pnl(val):
    """Format P&L with color indicator."""
    if val > 0:
        return f'<span class="profit">+Rs.{val:,.2f}</span>'
    elif val < 0:
        return f'<span class="loss">-Rs.{abs(val):,.2f}</span>'
    return f'<span class="neutral">Rs.{val:,.2f}</span>'


# --- Sidebar ---
with st.sidebar:
    st.title("📈 Trading Dashboard")
    st.markdown("---")

    # Market Status
    market_status = get_market_status()
    is_open = is_market_open()
    status_icon = "🟢" if is_open else "🔴"
    status_class = "market-open" if is_open else "market-closed"
    st.markdown(f"<h3 class='{status_class}'>{status_icon} {market_status}</h3>", 
                unsafe_allow_html=True)

    st.markdown("---")

    # Trading Engine Controls
    st.subheader("🤖 Trading Engine")

    trading_active = st.session_state.trading_active
    is_open = is_market_open()

    if trading_active:
        # STOP button - red/warning styling
        st.markdown('<div style="background: #2a1a1a; border: 1px solid #ff4444; border-radius: 10px; padding: 10px; margin-bottom: 10px;">'
                    '<span style="color: #00ff88;">🟢 </span><b>Trading Active</b>'
                    '<br><span style="color: #aaa; font-size: 0.85em;">Buying & selling on every cycle</span></div>',
                    unsafe_allow_html=True)
        if st.button("🛑 STOP TRADING", use_container_width=True,
                     type="secondary"):
            st.session_state.trading_active = False
            st.session_state.auto_refresh = False
            db.set_config("trading_active", "false")
            st.success("Trading stopped.")
            st.rerun()
    else:
        # START button - green/prominent styling
        st.markdown('<div style="background: #1a2a1a; border: 1px solid #444; border-radius: 10px; padding: 10px; margin-bottom: 10px;">'
                    '<span style="color: #ff4444;">🔴 </span><b>Trading Stopped</b>'
                    '<br><span style="color: #aaa; font-size: 0.85em;">Click Start to begin automated trading</span></div>',
                    unsafe_allow_html=True)
        start_disabled = not is_open
        if start_disabled:
            st.caption("Market is closed. Trading will start when market opens.")
        if st.button("🚀 START TRADING", use_container_width=True,
                     disabled=start_disabled,
                     type="primary"):
            st.session_state.trading_active = True
            st.session_state.auto_refresh = True
            db.set_config("trading_active", "true")
            st.success("Trading started!")
            st.rerun()

    st.markdown("---")

    # Controls
    st.subheader("Controls")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    with col2:
        auto_label = "⏸️ Pause Auto" if st.session_state.auto_refresh else "▶️ Auto Refresh"
        if st.button(auto_label, use_container_width=True):
            st.session_state.auto_refresh = not st.session_state.auto_refresh

    # Auto-refresh every 15s
    if st.session_state.auto_refresh:
        st.caption("Auto-refreshing every 15s...")

    st.markdown("---")

    # Portfolio Summary Card
    st.subheader("💰 Portfolio Snapshot")
    summary = db.get_dashboard_summary()

    st.markdown(
        f'<div class="metric-card">'
        f'<div class="card-title">Total Portfolio Value</div>'
        f'<div class="card-value">{format_currency(summary["total_portfolio_value"])}</div>'
        f'<div style="margin-top: 10px;">'
        f'<div class="card-title">Total P&L</div>'
        f'<div style="font-size: 1.4em;">{format_pnl(summary["total_pnl"])}</div>'
        f'<div style="font-size: 0.9em;">Returns: <b>{summary["total_returns_pct"]:.2f}%</b></div>'
        f'</div></div>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    # Quick Stats
    st.subheader("📊 Quick Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Cash Balance", f"Rs.{summary['cash_balance']:,.0f}")
        st.metric("Open Positions", summary["num_open_positions"])
    with col2:
        st.metric("Total Trades", summary["total_trades"])
        st.metric("Win Rate", f"{summary['win_rate']:.1f}%")

    st.markdown("---")
    st.caption(f"Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
    st.caption("Data source: Yahoo Finance (NSE)")
    st.caption("Market: NSE (9:15 AM - 3:30 PM IST)")


# --- Main Content ---
# Run trading cycle only when trading is active AND auto-refresh is on
if st.session_state.trading_active and st.session_state.auto_refresh and is_open:
    process_signals()
elif st.session_state.trading_active and not is_open:
    # Trading is active but market closed - just update holdings prices
    update_holdings_prices()

# Send periodic portfolio summaries (every N minutes, default 15) when auto-refresh is on
if st.session_state.auto_refresh:
    email_notifier.maybe_send_summary_email()
    whatsapp_notifier.maybe_send_summary()

# ---- Tabs ----
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard", "💼 Holdings", "📜 Trade History", 
    "🔔 Signals", "⚙️ Settings & Strategy"
])

# ================
# TAB 1: DASHBOARD
# ================
with tab1:
    st.header("Real-Time Trading Dashboard")

    # Top row: Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Total Portfolio Value",
            f"Rs.{summary['total_portfolio_value']:,.0f}",
            delta=f"{summary['total_returns_pct']:.1f}%",
        )
    with col2:
        st.metric(
            "Total P&L",
            f"Rs.{summary['total_pnl']:,.0f}",
            delta=f"{summary['total_returns_pct']:.1f}%",
            delta_color="normal",
        )
    with col3:
        st.metric(
            "Realized P&L",
            f"Rs.{summary['realized_pnl']:,.0f}",
        )
    with col4:
        st.metric(
            "Unrealized P&L",
            f"Rs.{summary['unrealized_pnl']:,.0f}",
        )
    with col5:
        st.metric(
            "Total Returns %",
            f"{summary['total_returns_pct']:.2f}%",
        )

    # Second row: Position summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Bought Shares", f"{summary['total_bought_shares']:,}")
    with col2:
        st.metric("Total Sold Shares", f"{summary['total_sold_shares']:,}")
    with col3:
        st.metric("Shares in Holdings", f"{summary['held_shares']:,}")
    with col4:
        st.metric("Win/Loss", f"{summary['winning_trades']}W / {summary['losing_trades']}L")

    st.markdown("---")

    # Market Watch
    st.subheader("📋 Live Market Watch")

    watchlist = db.get_watchlist()
    market_df = get_market_summary(watchlist[:10])

    if not market_df.empty:
        # Color the Day Change column
        def color_change(val):
            if val > 0:
                return f'<span style="color: #00ff88;">+{val:.2f}%</span>'
            elif val < 0:
                return f'<span style="color: #ff4444;">{val:.2f}%</span>'
            return f'<span>{val:.2f}%</span>'

        market_df["Day Change %"] = market_df["Day Change %"].apply(
            lambda x: f'+{x:.2f}%' if x > 0 else f'{x:.2f}%'
        )
        st.dataframe(market_df, use_container_width=True, hide_index=True)
    else:
        st.info("Market data unavailable. Market may be closed.")

    st.markdown("---")

    # Equity Curve
    st.subheader("📈 Portfolio Equity Curve")
    portfolio_hist = db.get_portfolio_history(limit=500)

    if not portfolio_hist.empty:
        portfolio_hist["timestamp"] = pd.to_datetime(portfolio_hist["timestamp"])

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            row_heights=[0.7, 0.3],
            subplot_titles=("Portfolio Value", "Daily P&L"),
        )

        fig.add_trace(
            go.Scatter(
                x=portfolio_hist["timestamp"],
                y=portfolio_hist["total_value"],
                mode="lines",
                name="Portfolio Value",
                line=dict(color="#00ff88", width=2),
                fill="tozeroy",
                fillcolor="rgba(0, 255, 136, 0.1)",
            ),
            row=1, col=1,
        )

        fig.add_trace(
            go.Bar(
                x=portfolio_hist["timestamp"],
                y=portfolio_hist["day_pnl"],
                name="Day P&L",
                marker_color=[
                    "#00ff88" if v >= 0 else "#ff4444" 
                    for v in portfolio_hist["day_pnl"]
                ],
            ),
            row=2, col=1,
        )

        fig.update_layout(
            height=500,
            template="plotly_dark",
            showlegend=False,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        fig.update_xaxes(title_text="", row=1, col=1)
        fig.update_xaxes(title_text="Time", row=2, col=1)
        fig.update_yaxes(title_text="Value (Rs.)", row=1, col=1)
        fig.update_yaxes(title_text="P&L (Rs.)", row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No portfolio history yet. Start trading to see your equity curve.")


# ================
# TAB 2: HOLDINGS
# ================
with tab2:
    st.header("💼 Current Holdings / Open Positions")

    holdings = db.get_holdings()

    if not holdings.empty:
        # Summary metrics
        total_invested = holdings["buy_value"].sum()
        total_current = holdings["current_value"].sum()
        total_unrealized_pnl = holdings["unrealized_pnl"].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Invested", f"Rs.{total_invested:,.0f}")
        col2.metric("Current Value", f"Rs.{total_current:,.0f}")
        col3.metric("Unrealized P&L", f"Rs.{total_unrealized_pnl:,.0f}",
                    delta=f"{(total_unrealized_pnl/total_invested*100):.1f}%" if total_invested > 0 else "0%")

        st.markdown("---")

        for _, holding in holdings.iterrows():
            symbol = holding["symbol"]
            col1, col2, col3, col4, col5, col6 = st.columns(6)

            with col1:
                st.markdown(f"**{symbol.replace('.NS', '')}**")
                st.caption(f"Since {holding['entry_date'][:10]}")
            with col2:
                st.metric("Quantity", int(holding["quantity"]))
            with col3:
                st.metric("Avg Buy", f"Rs.{holding['avg_buy_price']:.2f}")
            with col4:
                st.metric("Current", f"Rs.{holding['current_price']:.2f}")
            with col5:
                pnl = holding["unrealized_pnl"]
                pnl_pct = holding["unrealized_pnl_pct"]
                delta_color = "normal" if pnl >= 0 else "inverse"
                st.metric(
                    "Unrealized P&L",
                    f"Rs.{pnl:,.0f}",
                    delta=f"{pnl_pct:.1f}%",
                    delta_color=delta_color,
                )
            with col6:
                if st.button(f"Sell All {symbol.replace('.NS', '')}", 
                             key=f"sell_{symbol}_{holding['id']}"):
                    if is_market_open():
                        result = execute_sell(symbol, holding["current_price"])
                        if result["success"]:
                            st.success(f"Sold {symbol}: P&L = Rs.{result['realized_pnl']:.0f}")
                            st.rerun()
                        else:
                            st.error(f"Sell failed: {result.get('reason', 'Unknown')}")
                    else:
                        st.warning("Market is closed. Can only trade during market hours.")

            st.divider()
    else:
        st.info("No open positions. The strategy will automatically open positions when trading signals are found during market hours.")

    st.markdown("---")

    # Top Holdings Performance Chart
    if not holdings.empty:
        st.subheader("Holdings Performance")
        
        fig = go.Figure()
        for _, holding in holdings.iterrows():
            symbol = holding["symbol"].replace(".NS", "")
            pnl_pct = holding["unrealized_pnl_pct"]
            color = "#00ff88" if pnl_pct >= 0 else "#ff4444"

            fig.add_trace(go.Bar(
                name=symbol,
                x=[symbol],
                y=[pnl_pct],
                marker_color=color,
                text=f"{pnl_pct:.1f}%",
                textposition="outside",
            ))

        fig.update_layout(
            title="Position-wise Returns (%)",
            template="plotly_dark",
            height=400,
            yaxis_title="Return %",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)


# ================
# TAB 3: TRADE HISTORY
# ================
with tab3:
    st.header("📜 Trade History")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Trades", summary["total_trades"])
    with col2:
        st.metric("Winning Trades", summary["winning_trades"])
    with col3:
        st.metric("Losing Trades", summary["losing_trades"])

    trades = db.get_trades(limit=200)

    if not trades.empty:
        # Format for display
        display_trades = trades.copy()
        display_trades["timestamp"] = pd.to_datetime(display_trades["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        display_trades["symbol"] = display_trades["symbol"].str.replace(".NS", "")
        display_trades["trade_value"] = display_trades["trade_value"].apply(lambda x: f"Rs.{x:,.0f}")

        # Color P&L
        def color_pnl(val):
            if val > 0:
                return f'<span style="color: #00ff88;">+Rs.{val:,.0f}</span>'
            elif val < 0:
                return f'<span style="color: #ff4444;">-Rs.{abs(val):,.0f}</span>'
            return f'<span>Rs.0</span>'

        display_trades["realized_pnl_display"] = display_trades["realized_pnl"].apply(color_pnl)

        col_order = ["timestamp", "symbol", "side", "quantity", "price", 
                      "trade_value", "realized_pnl_display", "reason"]
        col_labels = ["Time", "Symbol", "Side", "Qty", "Price", "Value", "P&L", "Reason"]

        display_df = display_trades[col_order].copy()
        display_df.columns = col_labels

        st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)

        # P&L Distribution
        st.subheader("P&L Distribution")
        fig = px.histogram(
            trades[trades["realized_pnl"] != 0],
            x="realized_pnl",
            nbins=20,
            color_discrete_sequence=["#00ff88"],
            labels={"realized_pnl": "Realized P&L (Rs.)"},
        )
        fig.update_layout(template="plotly_dark", height=300, showlegend=False)
        fig.add_vline(x=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)

        # Cumulative P&L
        st.subheader("Cumulative Realized P&L")
        trades_sorted = trades.sort_values("timestamp")
        trades_sorted["cumulative_pnl"] = trades_sorted["realized_pnl"].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(trades_sorted["timestamp"]),
            y=trades_sorted["cumulative_pnl"],
            mode="lines",
            name="Cumulative P&L",
            line=dict(color="#00ff88", width=2),
            fill="tozeroy",
            fillcolor="rgba(0, 255, 136, 0.1)",
        ))
        fig.update_layout(
            title="Cumulative Realized P&L Over Time",
            template="plotly_dark",
            height=400,
            yaxis_title="P&L (Rs.)",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trades yet. Trades will appear here once the strategy executes them.")


# ================
# TAB 4: SIGNALS
# ================
with tab4:
    st.header("🔔 Trading Signals")

    # Manual scan button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Scan Now", use_container_width=True):
            with st.spinner("Scanning watchlist for signals..."):
                from strategy import scan_watchlist
                signals = scan_watchlist()
                st.success(f"Scan complete! {len(signals)} signals found.")
                st.rerun()

    st.markdown("---")

    signals = db.get_recent_signals(limit=100)

    if not signals.empty:
        # Format for display
        display_signals = signals.copy()
        display_signals["timestamp"] = pd.to_datetime(display_signals["timestamp"]).dt.strftime("%H:%M:%S")
        display_signals["symbol"] = display_signals["symbol"].str.replace(".NS", "")

        # Color by type
        def color_signal_type(val):
            if val == "BUY":
                return f'<span style="color: #00ff88; font-weight: bold;">BUY</span>'
            elif val == "SELL":
                return f'<span style="color: #ff4444; font-weight: bold;">SELL</span>'
            return f'<span style="color: #ffaa00; font-weight: bold;">{val}</span>'

        display_signals["signal_display"] = display_signals["signal_type"].apply(color_signal_type)
        display_signals["executed_display"] = display_signals["executed"].apply(
            lambda x: "✅" if x else "⏳"
        )

        display_signals["strength_bar"] = display_signals["strength"].apply(
            lambda x: f"{'█' * int(x/10)}{'░' * (10 - int(x/10))} ({x:.0f})"
        )

        col_order = ["timestamp", "symbol", "signal_display", "price", 
                      "rsi", "bb_position", "strength_bar", "reason", "executed_display"]
        col_labels = ["Time", "Symbol", "Signal", "Price", "RSI", "BB Pos", 
                       "Strength", "Reason", "Executed"]

        display_df = display_signals[col_order].copy()
        display_df.columns = col_labels

        st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)

        # Signal strength chart
        st.subheader("Signal Strength Overview")
        signal_counts = signals["signal_type"].value_counts()
        fig = px.pie(
            values=signal_counts.values,
            names=signal_counts.index,
            color=signal_counts.index,
            color_discrete_map={"BUY": "#00ff88", "SELL": "#ff4444", "EXIT": "#ffaa00"},
            title="Signal Distribution",
        )
        fig.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("No signals generated yet. Signals appear when the strategy detects trading opportunities.")


# ================
# TAB 5: SETTINGS
# ================
with tab5:
    st.header("⚙️ Settings & Strategy Configuration")

    st.subheader("📋 Watchlist Management")
    current_watchlist = db.get_watchlist()
    watchlist_str = ", ".join([s.replace(".NS", "") for s in current_watchlist])

    st.text_area(
        "NSE Stock Symbols (comma separated)",
        value=watchlist_str,
        height=150,
        key="watchlist_input",
    )

    if st.button("💾 Save Watchlist", use_container_width=True):
        symbols = st.session_state.watchlist_input
        # Clean and add .NS suffix
        clean_symbols = []
        for s in symbols.split(","):
            s = s.strip().upper()
            if s:
                if not s.endswith(".NS"):
                    s += ".NS"
                clean_symbols.append(s)
        db.set_config("watchlist", ",".join(clean_symbols))
        st.success(f"Watchlist updated with {len(clean_symbols)} symbols!")
        st.rerun()

    st.markdown("---")

    st.subheader("💰 Capital & Risk Settings")

    col1, col2 = st.columns(2)
    with col1:
        initial_capital = float(db.get_config("initial_capital"))
        new_capital = st.number_input(
            "Initial Capital (Rs.)",
            min_value=10000,
            max_value=100000000,
            value=int(initial_capital),
            step=10000,
        )
        if new_capital != initial_capital:
            db.set_config("initial_capital", str(new_capital))
            st.success(f"Initial capital updated to Rs.{new_capital:,.0f}")

    with col2:
        current_cash = db.get_cash_balance()
        st.metric("Current Cash Balance", f"Rs.{current_cash:,.0f}")
        if st.button("Reset Cash to Initial", use_container_width=True):
            db.update_cash_balance(initial_capital)
            st.success(f"Cash reset to Rs.{initial_capital:,.0f}")
            st.rerun()

    col1, col2, col3 = st.columns(3)
    with col1:
        max_pos = int(float(db.get_config("max_positions")))
        new_max_pos = st.number_input("Max Concurrent Positions", 1, 20, max_pos)
        if new_max_pos != max_pos:
            db.set_config("max_positions", str(new_max_pos))
    with col2:
        max_pos_pct = float(db.get_config("max_position_pct"))
        new_max_pct = st.slider("Max Position Size (% of capital)", 5, 50, int(max_pos_pct))
        if new_max_pct != max_pos_pct:
            db.set_config("max_position_pct", str(new_max_pct))
    with col3:
        stop_loss = float(db.get_config("stop_loss_pct"))
        new_stop = st.slider("Stop Loss (%)", 1, 10, int(stop_loss))
        if new_stop != stop_loss:
            db.set_config("stop_loss_pct", str(new_stop))

    col1, col2 = st.columns(2)
    with col1:
        take_profit = float(db.get_config("take_profit_pct"))
        new_tp = st.slider("Take Profit (%)", 2, 20, int(take_profit))
        if new_tp != take_profit:
            db.set_config("take_profit_pct", str(new_tp))

    st.markdown("---")

    # =================
    # EMAIL NOTIFICATIONS
    # =================
    st.subheader("📧 Email Notifications")
    st.markdown(
        "Get real-time email alerts when the bot buys or sells shares. "
        "Configure your SMTP settings below."
    )

    # Load current email config
    email_enabled = db.get_config("email_enabled") == "true"
    email_smtp_server = db.get_config("email_smtp_server") or "smtp.gmail.com"
    email_smtp_port = int(db.get_config("email_smtp_port") or "587")
    email_sender = db.get_config("email_sender") or ""
    email_password = db.get_config("email_password") or ""
    email_recipient = db.get_config("email_recipient") or ""

    # Email toggle
    email_enabled = st.toggle("🔔 Enable Email Notifications", value=email_enabled,
                              help="Send email alerts on every buy/sell trade")
    db.set_config("email_enabled", "true" if email_enabled else "false")

    if email_enabled:
        st.markdown("""
        <div style="background: #1a2a1a; border: 1px solid #00ff8833; border-radius: 8px; padding: 12px; margin: 8px 0;">
            <b>💡 Tip:</b> For Gmail, you need to use an
            <a href="https://support.google.com/accounts/answer/185833" target="_blank" style="color: #58a6ff;">
            App Password</a> (not your regular password).
            Enable 2-Factor Authentication first, then generate an App Password.
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📧 Email Settings", expanded=not bool(email_sender)):
            col1, col2 = st.columns(2)

            with col1:
                new_smtp = st.text_input("SMTP Server", value=email_smtp_server,
                                          help="Gmail: smtp.gmail.com, Outlook: smtp.office365.com")
                if new_smtp != email_smtp_server:
                    db.set_config("email_smtp_server", new_smtp)

                new_sender = st.text_input("Sender Email", value=email_sender,
                                           placeholder="your.email@gmail.com",
                                           help="The email address that sends notifications")
                if new_sender != email_sender:
                    db.set_config("email_sender", new_sender)

                new_password = st.text_input(
                    "App Password",
                    type="password",
                    value=email_password if email_password else "",
                    placeholder="Enter 16-char app password",
                    help="Gmail App Password (16 characters, no spaces)",
                )
                if new_password != email_password:
                    db.set_config("email_password", new_password)

            with col2:
                new_port = st.number_input("SMTP Port", min_value=1, max_value=65535,
                                            value=email_smtp_port,
                                            help="Gmail: 587 (TLS), Outlook: 587")
                if new_port != email_smtp_port:
                    db.set_config("email_smtp_port", str(new_port))

                new_recipient = st.text_input("Recipient Email", value=email_recipient,
                                               placeholder="you@example.com",
                                               help="The email address that receives notifications")
                if new_recipient != email_recipient:
                    db.set_config("email_recipient", new_recipient)

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("📨 Send Test Email", use_container_width=True,
                             type="primary"):
                    with st.spinner("Sending test email..."):
                        result = email_notifier.send_test_email()
                        if result["success"]:
                            st.success(result["message"])
                        else:
                            st.error(result["message"])

        # Show config status
        config = email_notifier.get_email_config()
        configured = email_notifier.is_email_configured()

        if configured:
            st.markdown(
                f'<div style="background: #1a2a1a; border: 1px solid #00ff88; border-radius: 8px; '
                f'padding: 10px; margin: 8px 0;">'
                f'<span style="color: #00ff88;">✅ </span><b>Email configured</b> — '
                f'Sending from <code>{config["sender"]}</code> to <code>{config["recipient"]}</code>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div style="background: #2a1a1a; border: 1px solid #ff4444; border-radius: 8px; '
                f'padding: 10px; margin: 8px 0;">'
                f'<span style="color: #ff4444;">⚠️ </span><b>Email not configured</b> — '
                f'Please fill in all fields: Sender, Password, and Recipient'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.info("📧 Email notifications are disabled. Toggle the switch above to enable them.")

    st.markdown("---")

    # =================
    # WHATSAPP NOTIFICATIONS
    # =================
    st.subheader("💬 WhatsApp Notifications")
    st.markdown(
        "Get real-time buy/sell alerts and the periodic portfolio summary directly "
        "on your WhatsApp — **free** via the CallMeBot API, no business account needed."
    )

    # Load current WhatsApp config
    wa_enabled = db.get_config("whatsapp_enabled") == "true"
    wa_phone = db.get_config("whatsapp_phone") or ""
    wa_apikey = db.get_config("whatsapp_apikey") or ""

    # WhatsApp toggle
    wa_enabled = st.toggle("💬 Enable WhatsApp Notifications", value=wa_enabled,
                           help="Send buy/sell alerts and portfolio summaries to your WhatsApp")
    db.set_config("whatsapp_enabled", "true" if wa_enabled else "false")

    if wa_enabled:
        st.markdown("""
        <div style="background: #1a2a1a; border: 1px solid #25d36655; border-radius: 8px; padding: 12px; margin: 8px 0;">
            <b>🛠️ One-time setup (takes ~1 minute):</b><br>
            <b>1.</b> Add the bot number <code style="color:#25d366;">+34 644 596 804</code> to your phone contacts.<br>
            <b>2.</b> Send <i>"I allow callmebot to send me messages"</i> to it from WhatsApp.<br>
            <b>3.</b> The bot replies with your <b>APIKEY</b>. Enter it below with your phone number.
        </div>
        """, unsafe_allow_html=True)

        with st.expander("💬 WhatsApp Settings", expanded=not bool(wa_phone)):
            col1, col2 = st.columns(2)

            with col1:
                new_phone = st.text_input(
                    "Your WhatsApp Number (with country code)",
                    value=wa_phone,
                    placeholder="+91XXXXXXXXXX",
                    help="Your own number in international format, e.g. +91XXXXXXXXXX",
                )
                if new_phone != wa_phone:
                    db.set_config("whatsapp_phone", new_phone)

            with col2:
                new_apikey = st.text_input(
                    "CallMeBot API Key",
                    type="password",
                    value=wa_apikey,
                    placeholder="Enter the APIKEY from the bot",
                    help="The APIKEY the CallMeBot bot sent you after activation",
                )
                if new_apikey != wa_apikey:
                    db.set_config("whatsapp_apikey", new_apikey)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📨 Send Test WhatsApp", use_container_width=True,
                         type="primary"):
                with st.spinner("Sending test message..."):
                    result = whatsapp_notifier.send_test_message()
                    if result["success"]:
                        st.success(result["message"])
                    else:
                        st.error(result["message"])

        # Show config status
        wa_configured = whatsapp_notifier.is_whatsapp_configured()
        if wa_configured:
            st.markdown(
                f'<div style="background: #1a2a1a; border: 1px solid #25d366; border-radius: 8px; '
                f'padding: 10px; margin: 8px 0;">'
                f'<span style="color: #25d366;">✅ </span><b>WhatsApp configured</b> — '
                f'Messages will go to <code>{wa_phone}</code>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div style="background: #2a1a1a; border: 1px solid #ff4444; border-radius: 8px; '
                f'padding: 10px; margin: 8px 0;">'
                f'<span style="color: #ff4444;">⚠️ </span><b>WhatsApp not configured</b> — '
                f'Please enter your phone number and API key'
                f'</div>',
                unsafe_allow_html=True
            )

        # Periodic summary section
        st.markdown("---")
        st.subheader("⏰ Periodic Portfolio Summary on WhatsApp")
        wa_summary_enabled = db.get_config("whatsapp_summary_enabled") != "false"
        wa_summary_enabled = st.toggle(
            "📊 Enable Periodic Summary Messages",
            value=wa_summary_enabled,
            help="Send the full portfolio summary (profit, loss, returns, shares held) on an interval",
        )
        db.set_config("whatsapp_summary_enabled", "true" if wa_summary_enabled else "false")

        if wa_summary_enabled:
            wa_interval = float(db.get_config("whatsapp_summary_interval_min") or "1")
            new_wa_interval = st.slider(
                "Send every (minutes)",
                min_value=1,
                max_value=60,
                value=int(wa_interval),
                step=1,
                key="wa_interval_slider",
                help="How often to send the portfolio summary. Minimum 1 minute.",
            )
            if new_wa_interval != int(wa_interval):
                db.set_config("whatsapp_summary_interval_min", str(new_wa_interval))

            last_wa_ts = float(db.get_config("last_whatsapp_summary_at") or "0")
            if last_wa_ts > 0:
                from datetime import datetime as _dt2
                last_wa_str = _dt2.fromtimestamp(last_wa_ts).strftime("%H:%M:%S")
                st.caption(f"🕒 Last summary sent at {last_wa_str}")
            else:
                st.caption("🕒 No summary sent yet. One will be sent at the next cycle.")

            st.markdown(
                f'<div style="background: #1a1a2a; border: 1px solid #25d36655; border-radius: 8px; '
                f'padding: 12px; margin: 8px 0;">'
                f'<b>💬 What you\'ll get every {int(new_wa_interval)} minute(s):</b><br>'
                f'• <b>Total Profit</b> & <b>Total Loss</b><br>'
                f'• <b>Realized & Unrealized P&L</b><br>'
                f'• <b>Total Returns %</b> & Portfolio Value<br>'
                f'• <b>Shares in holdings</b> + per-position breakdown'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("📊 Periodic WhatsApp summaries are disabled.")
    else:
        st.info("💬 WhatsApp notifications are disabled. Toggle the switch above to enable them.")

    # =================
    # PRICE RISE ALERTS
    # =================
    if email_enabled and configured:
        st.markdown("---")
        st.subheader("📈 Price Rise Alerts")
        st.markdown(
            "Get notified when a stock you hold rises in price — even a little! "
            "The email includes current price, profit if sold now, and the bot's exit plan."
        )

        rise_enabled = db.get_config("email_rise_alerts") == "true"
        rise_threshold = float(db.get_config("rise_alert_threshold_pct") or "1.0")

        rise_enabled = st.toggle(
            "🔔 Enable Price Rise Alerts",
            value=rise_enabled,
            help="Send email alert when a held stock's price rises (even a little)",
        )
        db.set_config("email_rise_alerts", "true" if rise_enabled else "false")

        if rise_enabled:
            new_threshold = st.slider(
                "Minimum Price Rise (%) to Trigger Alert",
                min_value=0.1,
                max_value=5.0,
                value=rise_threshold,
                step=0.1,
                help="How much the price must rise (from last alert) to send a new notification. "
                     "Lower values = more frequent emails. Recommended: 0.5%",
                format="%.1f%%",
            )
            if new_threshold != rise_threshold:
                db.set_config("rise_alert_threshold_pct", str(new_threshold))

            st.markdown(
                f'<div style="background: #1a2a1a; border: 1px solid #ffaa0055; border-radius: 8px; '
                f'padding: 12px; margin: 8px 0;">'
                f'<b>📈 Example:</b> If you hold a stock bought at Rs.100 and it rises to Rs.{100 + new_threshold:.1f} '
                f'(<b>{new_threshold:.1f}%</b> from last alert), you\'ll get a detailed email.'
                f'</div>',
                unsafe_allow_html=True
            )

            # Show what the email contains
            with st.expander("📧 Preview: What the Price Rise Email Looks Like"):
                st.markdown("""
                **📋 Position Summary:**
                - Symbol, Quantity, Buy Price, Current Price
                - Total Invested vs Current Value

                **💰 If You Sell Now:**
                - Unrealized P&L (Rs. and %)
                - Entry RSI & Current RSI

                **🤖 Bot's Exit Plan:**
                - 🔴 **Stop Loss:** Sells if price drops to X% below entry
                - 🟢 **Take Profit:** Sells when price hits target
                - 📊 **RSI Exit:** Sells when RSI crosses back above 50
                - 📈 **Trailing Stop:** Locks in gains after 3%+ rise

                > 🔄 Alerts are sent at most once per threshold interval to avoid flooding.
                """)
        else:
            st.info("📈 Price rise alerts are disabled. Toggle the switch above to get notified on every upward move.")

        st.markdown("---")
        st.subheader("📊 Watchlist Price Rise Alerts")
        st.markdown(
            "Get an email when **any** stock in your watchlist rises — even if you don't hold it. "
            "Stocks are checked in rotation (~25 per cycle) so the whole watchlist is swept "
            "every few minutes."
        )

        wl_rise_enabled = db.get_config("watchlist_rise_alerts") != "false"
        wl_rise_enabled = st.toggle(
            "🔔 Enable Watchlist Price Rise Alerts",
            value=wl_rise_enabled,
            help="Email me when any watchlist stock rises by the threshold above its last alert price",
        )
        db.set_config("watchlist_rise_alerts", "true" if wl_rise_enabled else "false")

        if wl_rise_enabled:
            st.markdown(
                f'<div style="background: #1a1a2a; border: 1px solid #00ff8855; border-radius: 8px; '
                f'padding: 12px; margin: 8px 0;">'
                f'<b>📈 How it works:</b> Each watchlist stock is checked in rotation. '
                f'An email fires when a stock rises <b>{rise_threshold:.1f}%</b> above its last alert '
                f'price (same threshold as holding alerts, adjustable above). '
                f'First sight of a stock only sets the baseline — no flood of emails on startup.'
                f'</div>',
                unsafe_allow_html=True
            )

    # =================
    # PERIODIC SUMMARY EMAIL
    # =================
    if email_enabled and configured:
        st.markdown("---")
        st.subheader("⏰ Periodic Portfolio Summary")
        st.markdown(
            "Get a full portfolio summary email on a fixed interval (default every 15 minutes) — "
            "total profit, total loss, realized/unrealized P&L, total returns, shares in holdings, "
            "and a live breakdown of every open position."
        )

        summary_enabled = db.get_config("summary_email_enabled") != "false"
        summary_enabled = st.toggle(
            "📧 Enable Periodic Summary Emails",
            value=summary_enabled,
            help="Send a full portfolio summary email on a fixed interval",
        )
        db.set_config("summary_email_enabled", "true" if summary_enabled else "false")

        if summary_enabled:
            interval_min = float(db.get_config("summary_email_interval_min") or "15")
            new_interval = st.slider(
                "Send every (minutes)",
                min_value=1,
                max_value=60,
                value=int(interval_min),
                step=1,
                help="How often to send the portfolio summary email. Minimum 1 minute.",
            )
            if new_interval != int(interval_min):
                db.set_config("summary_email_interval_min", str(new_interval))

            last_sent_ts = float(db.get_config("last_summary_email_at") or "0")
            if last_sent_ts > 0:
                from datetime import datetime as _dt
                last_sent_str = _dt.fromtimestamp(last_sent_ts).strftime("%H:%M:%S")
                st.caption(f"🕒 Last summary email sent at {last_sent_str}")
            else:
                st.caption("🕒 No summary email sent yet. One will be sent at the next cycle.")

            st.markdown(
                f'<div style="background: #1a1a2a; border: 1px solid #58a6ff55; border-radius: 8px; '
                f'padding: 12px; margin: 8px 0;">'
                f'<b>📧 What you\'ll get every {int(new_interval)} minute(s):</b><br>'
                f'• <b>Total Profit</b> (winning trades) & <b>Total Loss</b> (losing trades)<br>'
                f'• <b>Realized P&L</b> and <b>Unrealized P&L</b><br>'
                f'• <b>Total Returns %</b> and Portfolio Value<br>'
                f'• <b>Total shares in holdings</b> with per-position breakdown'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("⏰ Periodic summary emails are disabled. Toggle the switch above to enable them.")

    st.markdown("---")

    st.subheader("🎯 Trading Strategy: RSI + BB Mean Reversion")
    st.markdown("""
    **Entry Rules (BUY):**
    - RSI(14) < 30 (oversold) — strong signal
    - Price near lower Bollinger Band(20,2) — mean reversion setup
    - Volume > 1.2x average — confirmation
    - MACD turning bullish — momentum alignment

    **Entry Rules (SELL):**
    - RSI(14) > 70 (overbought) — strong signal
    - Price near upper Bollinger Band(20,2) — mean reversion setup
    - Volume > 1.2x average — confirmation
    - MACD turning bearish — momentum alignment

    **Exit Rules:**
    - Stop Loss: 3% below entry price (configurable)
    - Take Profit: 5% above entry price (configurable)
    - RSI Mean Reversion: Exit when RSI crosses back above 50 (for buys)
    - Trailing Stop: 2% trail after 3% gain

    **Risk Management:**
    - Max 5 concurrent positions
    - Max 15% of capital per position
    - 0.1% slippage per trade (realistic)
    - No short selling (long-only for safety)
    """)

    st.markdown("---")

    st.subheader("🗄️ Database Management")
    if st.button("🧹 Reset All Trading Data", type="secondary", use_container_width=True):
        import os
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)
            db.init_db()
            db.set_config("current_cash", str(initial_capital))
            st.success("Database reset! All trades cleared.")
            st.rerun()

    st.caption("⚠️ Reset clears all trades, holdings, signals, and portfolio history. Watchlist and settings are preserved.")


# --- Auto-refresh logic (15 second interval) ---
if st.session_state.auto_refresh:
    status_text = "🟢 Trading Active" if st.session_state.trading_active else "🔄 Auto-refresh ON"
    status_color = "#00ff88" if st.session_state.trading_active else "#8888ff"
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="15">
        <div style="position: fixed; bottom: 10px; right: 10px; 
                    background: #1e1e2e; padding: 5px 10px; border-radius: 5px;
                    border: 1px solid #3a3a5e; font-size: 0.8em; color: {status_color};">
            {status_text} (15s)
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    # The app runs via `streamlit run dashboard.py`
    pass

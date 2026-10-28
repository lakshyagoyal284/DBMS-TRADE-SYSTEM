"""
Email Notifier
==============
Sends trade notifications via SMTP email.
Supports Gmail, Outlook, and custom SMTP servers.

Configuration is stored in the database (config table) with these keys:
  - email_enabled: "true" or "false"
  - email_smtp_server: e.g. smtp.gmail.com
  - email_smtp_port: e.g. 587
  - email_sender: sender email address
  - email_password: sender email app password
  - email_recipient: recipient email address
  - email_rise_alerts: "true" or "false"
  - rise_alert_threshold_pct: e.g. "1.0"
  - summary_email_enabled: "true" or "false"
  - summary_email_interval_min: e.g. "15" (send portfolio summary every N minutes)
  - last_summary_email_at: epoch timestamp of last summary email (internal)
"""

import smtplib
import ssl
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import database as db

# Default SMTP settings
DEFAULT_SMTP_SERVER = "smtp.gmail.com"
DEFAULT_SMTP_PORT = "587"


def get_email_config() -> dict:
    """Retrieve email configuration from the database."""
    return {
        "enabled": db.get_config("email_enabled") == "true",
        "smtp_server": db.get_config("email_smtp_server") or DEFAULT_SMTP_SERVER,
        "smtp_port": int(db.get_config("email_smtp_port") or DEFAULT_SMTP_PORT),
        "sender": db.get_config("email_sender") or "",
        "password": db.get_config("email_password") or "",
        "recipient": db.get_config("email_recipient") or "",
    }


def is_email_configured() -> bool:
    """Check if email is properly configured with all required fields."""
    config = get_email_config()
    return all([
        config["enabled"],
        config["sender"],
        config["password"],
        config["recipient"],
    ])


def is_rise_alert_enabled() -> bool:
    """Check if price rise alerts are enabled."""
    return db.get_config("email_rise_alerts") == "true"


def get_rise_alert_threshold() -> float:
    """Get the minimum price rise percentage to trigger an alert."""
    return float(db.get_config("rise_alert_threshold_pct") or "1.0")


def is_summary_email_enabled() -> bool:
    """Check if the periodic portfolio summary email is enabled."""
    return db.get_config("summary_email_enabled") != "false"


def get_summary_email_interval() -> int:
    """Get the summary email interval in seconds (default 15 minutes)."""
    minutes = float(db.get_config("summary_email_interval_min") or "15")
    return max(60, int(minutes * 60))


def send_email(subject: str, body_html: str) -> bool:
    """
    Send an email notification using the configured SMTP settings.

    Args:
        subject: Email subject line
        body_html: HTML body content

    Returns:
        True if sent successfully, False otherwise
    """
    if not is_email_configured():
        print("[EMAIL] Notifications disabled or not configured. Skipping email.")
        return False

    config = get_email_config()

    try:
        # Build message
        msg = MIMEMultipart("alternative")
        msg["From"] = config["sender"]
        msg["To"] = config["recipient"]
        msg["Subject"] = subject

        # Attach HTML body
        html_part = MIMEText(body_html, "html")
        msg.attach(html_part)

        # Connect to SMTP server
        context = ssl.create_default_context()
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            server.starttls(context=context)
            server.login(config["sender"], config["password"])
            server.sendmail(config["sender"], config["recipient"], msg.as_string())

        print(f"[EMAIL] Notification sent: {subject}")
        return True

    except smtplib.SMTPAuthenticationError:
        print(f"[EMAIL] Authentication failed. Check your email/password.")
        print(f"[EMAIL] For Gmail, use an App Password (not your regular password).")
        return False
    except smtplib.SMTPException as e:
        print(f"[EMAIL] SMTP error: {e}")
        return False
    except Exception as e:
        print(f"[EMAIL] Failed to send email: {e}")
        return False


def send_buy_notification(trade_data: dict) -> bool:
    """
    Send a buy trade notification email.

    Args:
        trade_data: Dict with keys - symbol, shares, price, investment, reason, timestamp
    """
    symbol = trade_data.get("symbol", "Unknown").replace(".NS", "")
    shares = trade_data.get("shares", 0)
    price = trade_data.get("price", 0)
    investment = trade_data.get("investment", 0)
    reason = trade_data.get("reason", "Strategy Signal")
    timestamp = trade_data.get("timestamp", datetime.now().isoformat()[:19])

    subject = f"🟢 BUY ALERT: Bought {shares} shares of {symbol} @ Rs.{price:.2f}"

    body_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #161b22; border-radius: 12px;
                        border: 1px solid #30363d; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%); padding: 20px;
                      text-align: center; }}
            .header h1 {{ margin: 0; color: #0d1117; font-size: 24px; }}
            .header .subtitle {{ color: #003d1f; margin-top: 5px; font-size: 14px; }}
            .body {{ padding: 24px; }}
            .trade-details {{ background: #0d1117; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 8px 0;
                          border-bottom: 1px solid #21262d; }}
            .detail-row:last-child {{ border-bottom: none; }}
            .label {{ color: #8b949e; font-size: 14px; }}
            .value {{ color: #e6edf3; font-size: 14px; font-weight: bold; }}
            .value.positive {{ color: #00ff88; }}
            .reason-box {{ background: #0d1117; border-radius: 8px; padding: 16px;
                          border-left: 4px solid #00ff88; margin-top: 16px; }}
            .reason-box h3 {{ margin: 0 0 8px 0; color: #00ff88; font-size: 14px; }}
            .reason-box p {{ margin: 0; color: #c9d1d9; font-size: 13px; line-height: 1.5; }}
            .footer {{ text-align: center; padding: 16px; color: #484f58; font-size: 12px;
                       border-top: 1px solid #21262d; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🟢 BUY EXECUTED</h1>
                <div class="subtitle">New position opened in your trading portfolio</div>
            </div>
            <div class="body">
                <div class="trade-details">
                    <div class="detail-row">
                        <span class="label">Symbol</span>
                        <span class="value">{symbol}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Quantity</span>
                        <span class="value">{shares:,} shares</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Buy Price</span>
                        <span class="value">Rs.{price:.2f}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Total Investment</span>
                        <span class="value positive">Rs.{investment:,.2f}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Timestamp</span>
                        <span class="value">{timestamp}</span>
                    </div>
                </div>
                <div class="reason-box">
                    <h3>📊 Reason for Purchase</h3>
                    <p>{reason}</p>
                </div>
            </div>
            <div class="footer">
                Auto-generated by your TA-Lib Trading Bot &bull; {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(subject, body_html)


def send_sell_notification(trade_data: dict) -> bool:
    """
    Send a sell trade notification email.

    Args:
        trade_data: Dict with keys - symbol, shares, price, trade_value,
                    realized_pnl, realized_pnl_pct, reason, timestamp
    """
    symbol = trade_data.get("symbol", "Unknown").replace(".NS", "")
    shares = trade_data.get("shares", 0)
    price = trade_data.get("price", 0)
    trade_value = trade_data.get("trade_value", 0)
    realized_pnl = trade_data.get("realized_pnl", 0)
    realized_pnl_pct = trade_data.get("realized_pnl_pct", 0)
    reason = trade_data.get("reason", "Strategy Signal")
    timestamp = trade_data.get("timestamp", datetime.now().isoformat()[:19])

    is_profit = realized_pnl >= 0
    emoji = "🟢" if is_profit else "🔴"
    pnl_color = "#00ff88" if is_profit else "#ff4444"
    pnl_text = f"+Rs.{realized_pnl:,.2f}" if is_profit else f"-Rs.{abs(realized_pnl):,.2f}"
    pnl_pct_text = f"+{realized_pnl_pct:.2f}%" if is_profit else f"{realized_pnl_pct:.2f}%"

    subject = f"{emoji} SELL ALERT: Sold {shares} {symbol} @ Rs.{price:.2f} (P&L: {pnl_text})"

    body_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #161b22; border-radius: 12px;
                        border: 1px solid #30363d; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, {'#00ff88' if is_profit else '#ff4444'} 0%, {'#00cc6a' if is_profit else '#cc2222'} 100%); padding: 20px;
                      text-align: center; }}
            .header h1 {{ margin: 0; color: #0d1117; font-size: 24px; }}
            .header .subtitle {{ color: {'#003d1f' if is_profit else '#4a0000'}; margin-top: 5px; font-size: 14px; }}
            .body {{ padding: 24px; }}
            .trade-details {{ background: #0d1117; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 8px 0;
                          border-bottom: 1px solid #21262d; }}
            .detail-row:last-child {{ border-bottom: none; }}
            .label {{ color: #8b949e; font-size: 14px; }}
            .value {{ color: #e6edf3; font-size: 14px; font-weight: bold; }}
            .value.positive {{ color: #00ff88; }}
            .value.negative {{ color: #ff4444; }}
            .pnl-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px;
                         background: {pnl_color}22; border: 1px solid {pnl_color}; margin: 8px 0; }}
            .pnl-big {{ font-size: 22px; font-weight: bold; color: {pnl_color}; }}
            .pnl-pct {{ font-size: 14px; color: {pnl_color}; }}
            .reason-box {{ background: #0d1117; border-radius: 8px; padding: 16px;
                          border-left: 4px solid {pnl_color}; margin-top: 16px; }}
            .reason-box h3 {{ margin: 0 0 8px 0; color: {pnl_color}; font-size: 14px; }}
            .reason-box p {{ margin: 0; color: #c9d1d9; font-size: 13px; line-height: 1.5; }}
            .footer {{ text-align: center; padding: 16px; color: #484f58; font-size: 12px;
                       border-top: 1px solid #21262d; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{'🟢 SELL EXECUTED - PROFIT' if is_profit else '🔴 SELL EXECUTED - LOSS'}</h1>
                <div class="subtitle">Position closed in your trading portfolio</div>
            </div>
            <div class="body">
                <div style="text-align: center; margin-bottom: 16px;">
                    <div class="pnl-badge">
                        <div class="pnl-big">{pnl_text}</div>
                        <div class="pnl-pct">{pnl_pct_text}</div>
                    </div>
                </div>
                <div class="trade-details">
                    <div class="detail-row">
                        <span class="label">Symbol</span>
                        <span class="value">{symbol}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Quantity Sold</span>
                        <span class="value">{shares:,} shares</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Sell Price</span>
                        <span class="value">Rs.{price:.2f}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Total Value</span>
                        <span class="value">Rs.{trade_value:,.2f}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Realized P&L</span>
                        <span class="value {'positive' if is_profit else 'negative'}">{pnl_text} ({pnl_pct_text})</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Timestamp</span>
                        <span class="value">{timestamp}</span>
                    </div>
                </div>
                <div class="reason-box">
                    <h3>📊 Reason for Sale</h3>
                    <p>{reason}</p>
                </div>
            </div>
            <div class="footer">
                Auto-generated by your TA-Lib Trading Bot &bull; {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(subject, body_html)


def send_price_rise_notification(holding_data: dict) -> bool:
    """
    Send a price rise alert email when a held stock price has appreciated.

    Args:
        holding_data: Dict with keys:
            - symbol: stock symbol
            - quantity: shares held
            - avg_buy_price: average purchase price
            - current_price: current market price
            - buy_value: total amount invested
            - current_value: current total value
            - unrealized_pnl: unrealized profit amount
            - unrealized_pnl_pct: unrealized profit percentage
            - entry_rsi: RSI at entry time
            - current_rsi: current RSI value
            - stop_loss_price: stop loss trigger price
            - take_profit_price: take profit trigger price
            - stop_loss_pct: stop loss percentage
            - take_profit_pct: take profit percentage
            - plan_details: human-readable strategy plan
    """
    symbol = holding_data.get("symbol", "Unknown").replace(".NS", "")
    quantity = holding_data.get("quantity", 0)
    buy_price = holding_data.get("avg_buy_price", 0)
    current_price = holding_data.get("current_price", 0)
    buy_value = holding_data.get("buy_value", 0)
    current_value = holding_data.get("current_value", 0)
    unrealized_pnl = holding_data.get("unrealized_pnl", 0)
    unrealized_pnl_pct = holding_data.get("unrealized_pnl_pct", 0)
    stop_loss_price = holding_data.get("stop_loss_price", 0)
    take_profit_price = holding_data.get("take_profit_price", 0)
    stop_loss_pct = holding_data.get("stop_loss_pct", 3)
    take_profit_pct = holding_data.get("take_profit_pct", 5)
    entry_rsi = holding_data.get("entry_rsi", "N/A")
    current_rsi = holding_data.get("current_rsi", "N/A")
    plan_details = holding_data.get("plan_details", "Strategy: RSI + Bollinger Bands Mean Reversion")

    price_change_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
    pnl_text = f"+Rs.{unrealized_pnl:,.2f}" if unrealized_pnl >= 0 else f"-Rs.{abs(unrealized_pnl):,.2f}"

    subject = f"📈 PRICE RISE: {symbol} up {price_change_pct:.1f}% → Rs.{current_price:.2f} (Profit: {pnl_text})"

    body_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; padding: 20px; }}
            .container {{ max-width: 620px; margin: 0 auto; background: #161b22; border-radius: 12px;
                        border: 1px solid #30363d; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #ffaa00 0%, #ff8800 100%); padding: 20px;
                      text-align: center; }}
            .header h1 {{ margin: 0; color: #0d1117; font-size: 24px; }}
            .header .subtitle {{ color: #4a2a00; margin-top: 5px; font-size: 14px; }}
            .body {{ padding: 24px; }}
            .section-title {{ color: #ffaa00; font-size: 16px; font-weight: bold; margin: 16px 0 8px 0;
                             border-bottom: 1px solid #30363d; padding-bottom: 4px; }}
            .price-change-badge {{ text-align: center; padding: 16px; margin-bottom: 16px;
                                 background: linear-gradient(135deg, #ffaa0011, #ff880011);
                                 border: 1px solid #ffaa0055; border-radius: 12px; }}
            .price-change-big {{ font-size: 28px; font-weight: bold; color: #00ff88; }}
            .price-change-sub {{ font-size: 14px; color: #8b949e; }}
            .details-grid {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }}
            .detail-card {{ background: #0d1117; border-radius: 8px; padding: 12px; flex: 1; min-width: 120px; }}
            .detail-card .label {{ color: #8b949e; font-size: 11px; text-transform: uppercase; }}
            .detail-card .value {{ color: #e6edf3; font-size: 16px; font-weight: bold; }}
            .detail-card .value.positive {{ color: #00ff88; }}
            .detail-card .value.negative {{ color: #ff4444; }}
            .detail-card .value.warning {{ color: #ffaa00; }}
            .plan-box {{ background: #0d1117; border-radius: 8px; padding: 16px;
                         border-left: 4px solid #ffaa00; margin-top: 16px; }}
            .plan-box h3 {{ margin: 0 0 8px 0; color: #ffaa00; font-size: 14px; }}
            .plan-box p {{ margin: 4px 0; color: #c9d1d9; font-size: 13px; line-height: 1.5; white-space: pre-wrap; }}
            .plan-box .plan-em {{ color: #ffaa00; font-weight: bold; }}
            .footer {{ text-align: center; padding: 16px; color: #484f58; font-size: 12px;
                       border-top: 1px solid #21262d; }}
            .divider {{ border-top: 1px solid #21262d; margin: 12px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📈 PRICE RISE ALERT</h1>
                <div class="subtitle">A stock in your portfolio is climbing!</div>
            </div>
            <div class="body">
                <!-- Price Change Highlight -->
                <div class="price-change-badge">
                    <div class="price-change-big">+{price_change_pct:.2f}%</div>
                    <div class="price-change-sub">
                        Rs.{buy_price:.2f} → <b style="color: #00ff88;">Rs.{current_price:.2f}</b>
                    </div>
                    <div class="price-change-sub">
                        Unrealized Profit: <b style="color: #00ff88;">{pnl_text} ({unrealized_pnl_pct:.2f}%)</b>
                    </div>
                </div>

                <!-- Position Details -->
                <div class="section-title">📋 Position Summary</div>
                <div class="details-grid">
                    <div class="detail-card">
                        <div class="label">Symbol</div>
                        <div class="value">{symbol}</div>
                    </div>
                    <div class="detail-card">
                        <div class="label">Quantity</div>
                        <div class="value">{quantity:,} shares</div>
                    </div>
                    <div class="detail-card">
                        <div class="label">Buy Price</div>
                        <div class="value">Rs.{buy_price:.2f}</div>
                    </div>
                    <div class="detail-card">
                        <div class="label">Current Price</div>
                        <div class="value positive">Rs.{current_price:.2f}</div>
                    </div>
                    <div class="detail-card">
                        <div class="label">Total Invested</div>
                        <div class="value">Rs.{buy_value:,.2f}</div>
                    </div>
                    <div class="detail-card">
                        <div class="label">Current Value</div>
                        <div class="value positive">Rs.{current_value:,.2f}</div>
                    </div>
                </div>

                <!-- Profit If Sold Now -->
                <div class="section-title">💰 If You Sell Now</div>
                <div class="details-grid">
                    <div class="detail-card">
                        <div class="label">Unrealized P&L</div>
                        <div class="value {'positive' if unrealized_pnl >= 0 else 'negative'}">{pnl_text}</div>
                    </div>
                    <div class="detail-card">
                        <div class="label">Return %</div>
                        <div class="value {'positive' if unrealized_pnl >= 0 else 'negative'}">{'+' if unrealized_pnl >= 0 else ''}{unrealized_pnl_pct:.2f}%</div>
                    </div>
                    <div class="detail-card">
                        <div class="label">Entry RSI</div>
                        <div class="value">{entry_rsi}</div>
                    </div>
                    <div class="detail-card">
                        <div class="label">Current RSI</div>
                        <div class="value warning">{current_rsi}</div>
                    </div>
                </div>

                <!-- Bot's Plan -->
                <div class="section-title">🤖 Trading Bot's Plan</div>
                <div class="plan-box">
                    <h3>📊 Exit Strategy for {symbol}</h3>
                    <p>{plan_details}</p>
                    <div class="divider"></div>
                    <p>🔴 <span class="plan-em">Stop Loss:</span> If price drops to <b>Rs.{stop_loss_price:.2f}</b> ({stop_loss_pct:.0f}% below entry), bot will sell to limit losses.</p>
                    <p>🟢 <span class="plan-em">Take Profit Target:</span> If price reaches <b>Rs.{take_profit_price:.2f}</b> ({take_profit_pct:.0f}% above entry), bot will book profits.</p>
                    <p>📊 <span class="plan-em">RSI Exit:</span> If RSI crosses back above 50 (currently {current_rsi}), the bot will exit for mean reversion profit.</p>
                    <p>📈 <span class="plan-em">Trailing Stop:</span> After 3%+ gain, bot trails a 2% stop to lock in gains if price reverses.</p>
                </div>
            </div>
            <div class="footer">
                Auto-generated by your TA-Lib Trading Bot &bull; {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(subject, body_html)


def send_watchlist_rise_notification(symbol: str, current_price: float,
                                      rise_pct: float, last_price: float) -> bool:
    """
    Send a simple price-rise alert for a watchlist stock (not held).

    Args:
        symbol: stock symbol
        current_price: current market price
        rise_pct: % rise since the last alert price
        last_price: the price at which the last alert was sent
    """
    sym = symbol.replace(".NS", "")
    subject = f"📈 WATCHLIST ALERT: {sym} up {rise_pct:.1f}% to Rs.{current_price:.2f}"

    body_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; padding: 20px; }}
            .container {{ max-width: 560px; margin: 0 auto; background: #161b22; border-radius: 12px;
                        border: 1px solid #30363d; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%); padding: 20px;
                      text-align: center; }}
            .header h1 {{ margin: 0; color: #0d1117; font-size: 22px; }}
            .header .subtitle {{ color: #003d1f; margin-top: 5px; font-size: 13px; }}
            .body {{ padding: 24px; text-align: center; }}
            .symbol {{ font-size: 32px; font-weight: bold; color: #e6edf3; margin: 8px 0; }}
            .price-big {{ font-size: 30px; font-weight: bold; color: #00ff88; margin: 4px 0; }}
            .details {{ background: #0d1117; border-radius: 8px; padding: 14px; margin: 16px 0;
                       text-align: left; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 6px 0;
                          border-bottom: 1px solid #21262d; }}
            .detail-row:last-child {{ border-bottom: none; }}
            .label {{ color: #8b949e; font-size: 13px; }}
            .value {{ color: #e6edf3; font-size: 13px; font-weight: bold; }}
            .value.positive {{ color: #00ff88; }}
            .note {{ color: #8b949e; font-size: 12px; }}
            .footer {{ text-align: center; padding: 14px; color: #484f58; font-size: 12px;
                       border-top: 1px solid #21262d; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📈 PRICE RISE ALERT</h1>
                <div class="subtitle">Watchlist stock moving up</div>
            </div>
            <div class="body">
                <div class="symbol">{sym}</div>
                <div class="price-big">+{rise_pct:.2f}%</div>
                <div class="note">Rs.{last_price:.2f} → <b style="color:#00ff88;">Rs.{current_price:.2f}</b></div>
                <div class="details">
                    <div class="detail-row"><span class="label">Current Price</span><span class="value positive">Rs.{current_price:.2f}</span></div>
                    <div class="detail-row"><span class="label">Price at Last Alert</span><span class="value">Rs.{last_price:.2f}</span></div>
                    <div class="detail-row"><span class="label">Rise Since Last Alert</span><span class="value positive">+{rise_pct:.2f}%</span></div>
                </div>
                <div class="note">This stock is on your watchlist (not currently held).</div>
            </div>
            <div class="footer">
                Auto-generated by your TA-Lib Trading Bot &bull; {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(subject, body_html)


def send_portfolio_summary_email(summary: dict = None) -> bool:
    """
    Send a full portfolio summary email with all key metrics:
    total profit, total loss, realized P&L, unrealized P&L, total returns,
    total shares in holdings, open positions, win rate, and holdings breakdown.

    Args:
        summary: Optional dict from db.get_dashboard_summary(). If None, it is fetched.

    Returns:
        True if sent successfully, False otherwise
    """
    if summary is None:
        summary = db.get_dashboard_summary()

    total_profit = db.get_total_profit()
    total_loss = db.get_total_loss()
    now = datetime.now()

    subject = f"📊 Portfolio Summary | P&L: {format_rs(summary['total_pnl'])} | {now.strftime('%d %b %H:%M')}"

    # Helper formatting
    def money(v, sign=True):
        return (("+" if v > 0 else "-") if sign else "") + f"Rs.{abs(v):,.2f}"

    def pct(v, sign=True):
        return ("+" if sign and v > 0 else "") + f"{v:.2f}%"

    pnl_color = lambda v: "#00ff88" if v >= 0 else "#ff4444"

    # Holdings table rows
    holdings_rows = ""
    holdings = db.get_holdings()
    if not holdings.empty:
        for _, h in holdings.iterrows():
            sym = str(h["symbol"]).replace(".NS", "")
            pnl = float(h["unrealized_pnl"])
            pnl_pct = float(h["unrealized_pnl_pct"])
            row_color = pnl_color(pnl)
            holdings_rows += f"""
            <tr>
                <td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#e6edf3;">{sym}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#e6edf3;">{int(h['quantity']):,}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#e6edf3;">Rs.{float(h['avg_buy_price']):,.2f}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #21262d;color:#e6edf3;">Rs.{float(h['current_price']):,.2f}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #21262d;color:{row_color};font-weight:bold;">{money(pnl)} ({pct(pnl_pct)})</td>
            </tr>"""
    else:
        holdings_rows = (
            '<tr><td colspan="5" style="padding:12px;color:#8b949e;text-align:center;">'
            'No open positions</td></tr>'
        )

    body_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; padding: 20px; }}
            .container {{ max-width: 640px; margin: 0 auto; background: #161b22; border-radius: 12px;
                        border: 1px solid #30363d; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #58a6ff 0%, #1f6feb 100%); padding: 20px;
                      text-align: center; }}
            .header h1 {{ margin: 0; color: #0d1117; font-size: 22px; }}
            .header .subtitle {{ color: #d0e4ff; margin-top: 5px; font-size: 13px; }}
            .body {{ padding: 24px; }}
            .section-title {{ color: #58a6ff; font-size: 15px; font-weight: bold; margin: 20px 0 10px 0;
                             border-bottom: 1px solid #30363d; padding-bottom: 4px; }}
            .metrics-grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
            .metric-card {{ background: #0d1117; border-radius: 10px; padding: 14px; flex: 1;
                           min-width: 130px; border: 1px solid #21262d; }}
            .metric-card .label {{ color: #8b949e; font-size: 11px; text-transform: uppercase;
                                   letter-spacing: 0.5px; }}
            .metric-card .value {{ color: #e6edf3; font-size: 17px; font-weight: bold; margin-top: 4px; }}
            .positive {{ color: #00ff88 !important; }}
            .negative {{ color: #ff4444 !important; }}
            .neutral {{ color: #e6edf3 !important; }}
            .big-pnl {{ font-size: 26px; font-weight: bold; text-align: center; margin: 8px 0 4px 0; }}
            .big-pnl-sub {{ text-align: center; color: #8b949e; font-size: 13px; margin-bottom: 8px; }}
            .pnl-badge {{ display: inline-block; padding: 6px 14px; border-radius: 20px; font-size: 13px;
                         font-weight: bold; }}
            .table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
            .table th {{ text-align: left; padding: 8px 12px; color: #8b949e; font-size: 11px;
                        text-transform: uppercase; border-bottom: 1px solid #30363d; }}
            .footer {{ text-align: center; padding: 16px; color: #484f58; font-size: 12px;
                       border-top: 1px solid #21262d; }}
            .footer .note {{ color: #6e7681; font-size: 11px; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 PORTFOLIO SUMMARY</h1>
                <div class="subtitle">{now.strftime('%A, %d %B %Y at %H:%M:%S')}</div>
            </div>
            <div class="body">
                <!-- Headline P&L -->
                <div class="big-pnl" style="color:{pnl_color(summary['total_pnl'])};">
                    {money(summary['total_pnl'])}
                </div>
                <div class="big-pnl-sub">
                    Total P&L ({pct(summary['total_returns_pct'])} returns) &bull; {summary['num_open_positions']} open position(s)
                </div>

                <!-- Key metrics -->
                <div class="section-title">💰 Key Metrics</div>
                <div class="metrics-grid">
                    <div class="metric-card"><div class="label">Total Profit</div><div class="value positive">{money(total_profit)}</div></div>
                    <div class="metric-card"><div class="label">Total Loss</div><div class="value negative">-{money(total_loss, sign=False)}</div></div>
                    <div class="metric-card"><div class="label">Realized P&L</div><div class="value {'positive' if summary['realized_pnl'] >= 0 else 'negative'}">{money(summary['realized_pnl'])}</div></div>
                    <div class="metric-card"><div class="label">Unrealized P&L</div><div class="value {'positive' if summary['unrealized_pnl'] >= 0 else 'negative'}">{money(summary['unrealized_pnl'])}</div></div>
                    <div class="metric-card"><div class="label">Total Returns</div><div class="value {'positive' if summary['total_returns_pct'] >= 0 else 'negative'}">{pct(summary['total_returns_pct'])}</div></div>
                    <div class="metric-card"><div class="label">Portfolio Value</div><div class="value neutral">Rs.{summary['total_portfolio_value']:,.2f}</div></div>
                    <div class="metric-card"><div class="label">Cash Balance</div><div class="value neutral">Rs.{summary['cash_balance']:,.2f}</div></div>
                    <div class="metric-card"><div class="label">Shares in Holdings</div><div class="value neutral">{summary['held_shares']:,}</div></div>
                    <div class="metric-card"><div class="label">Total Trades</div><div class="value neutral">{summary['total_trades']}</div></div>
                    <div class="metric-card"><div class="label">Win Rate</div><div class="value neutral">{summary['win_rate']:.1f}%</div></div>
                </div>

                <!-- Holdings breakdown -->
                <div class="section-title">📈 Current Holdings ({summary['held_shares']:,} shares)</div>
                <table class="table">
                    <tr>
                        <th>Symbol</th><th>Qty</th><th>Avg Buy</th><th>Current</th><th>Unrealized P&L</th>
                    </tr>
                    {holdings_rows}
                </table>
            </div>
            <div class="footer">
                Auto-generated by your TA-Lib Trading Bot &bull; every {db.get_config('summary_email_interval_min') or '15'} minute(s)<br>
                <span class="note">Total Profit = winning trades, Total Loss = losing trades (realized)</span>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(subject, body_html)


def maybe_send_summary_email() -> bool:
    """
    Send the periodic portfolio summary email if the interval has elapsed.
    Tracks the last sent time in the database to avoid spamming.

    Returns True if an email was sent, False otherwise (disabled, not due, or failed).
    """
    if not is_email_configured() or not is_summary_email_enabled():
        return False

    interval = get_summary_email_interval()
    last_sent = float(db.get_config("last_summary_email_at") or "0")

    # Send if never sent, or interval has elapsed
    if time.time() - last_sent < interval:
        return False

    summary = db.get_dashboard_summary()
    success = send_portfolio_summary_email(summary)
    if success:
        db.set_config("last_summary_email_at", str(time.time()))
        print(f"[EMAIL] Portfolio summary sent (interval {interval // 60} min).")
    return success


def format_rs(val: float) -> str:
    """Format a value as a compact Rs. string with sign."""
    return ("+" if val >= 0 else "-") + f"Rs.{abs(val):,.0f}"


def send_test_email() -> dict:
    """
    Send a test email to verify the configuration is working.

    Returns:
        Dict with 'success' bool and 'message' string
    """
    config = get_email_config()

    if not config["sender"] or not config["password"] or not config["recipient"]:
        return {
            "success": False,
            "message": "Email not fully configured. Please fill in all fields."
        }

    subject = "✅ TA-Lib Trading Bot - Test Notification"
    body_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; padding: 20px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: #161b22; border-radius: 12px;
                        border: 1px solid #30363d; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #58a6ff, #1f6feb); padding: 20px;
                      text-align: center; }}
            .header h1 {{ margin: 0; color: #0d1117; font-size: 20px; }}
            .body {{ padding: 24px; text-align: center; }}
            .body p {{ color: #c9d1d9; font-size: 14px; line-height: 1.6; }}
            .check {{ font-size: 48px; margin: 16px 0; }}
            .footer {{ text-align: center; padding: 16px; color: #484f58; font-size: 12px;
                       border-top: 1px solid #21262d; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Test Notification</h1>
            </div>
            <div class="body">
                <div class="check">📨</div>
                <h2 style="color: #e6edf3; margin: 0 0 8px 0;">Email Configuration Works!</h2>
                <p>
                    Your TA-Lib Trading Bot email notifications are working correctly.<br>
                    You will now receive real-time alerts for all buy and sell trades.
                </p>
                <p style="color: #8b949e; font-size: 12px;">
                    Sending from: {config["sender"]}<br>
                    Delivering to: {config["recipient"]}
                </p>
            </div>
            <div class="footer">
                Auto-generated by your TA-Lib Trading Bot &bull; {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </div>
        </div>
    </body>
    </html>
    """

    success = send_email(subject, body_html)
    if success:
        return {"success": True, "message": "Test email sent successfully! Check your inbox."}
    else:
        return {"success": False, "message": "Failed to send test email. Check your SMTP settings."}

"""
WhatsApp Notifier
=================
Sends WhatsApp notifications to your own phone number using the free
CallMeBot WhatsApp API (https://www.callmebot.com) — no registration,
no business account required. Best for personal alerts.

Setup (one-time, ~1 minute):
1. Add the CallMeBot bot number +34 644 596 804 to your phone contacts.
2. Send the message "I allow callmebot to send me messages" to that contact
   from your WhatsApp.
3. The bot replies with your unique APIKEY. Save that key and your phone
   number (with country code, e.g. +91XXXXXXXXXX) in the dashboard settings.

Configuration is stored in the database (config table) with these keys:
  - whatsapp_enabled: "true" or "false"
  - whatsapp_phone: recipient phone number with country code (e.g. +9198...)
  - whatsapp_apikey: APIKEY received from the CallMeBot bot
  - whatsapp_summary_enabled: "true" or "false"
  - whatsapp_summary_interval_min: e.g. "1" (send portfolio summary every N minutes)
  - last_whatsapp_summary_at: epoch timestamp of last summary (internal)
"""

import time
from datetime import datetime
import requests
import database as db

# CallMeBot API endpoint
CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"

# Bot number users must message to activate their API key
CALLMEBOT_BOT_NUMBER = "+34 644 596 804"

# When CallMeBot rate-limits us (HTTP 503, daily cap reached), wait this long
# before trying to send anything again, to avoid aggravating the throttling.
RATE_LIMIT_COOLDOWN_SECONDS = 60 * 60  # 1 hour
_rate_limited_until = 0.0  # epoch timestamp; 0 means not rate limited


# --- Configuration helpers ---

def get_whatsapp_config() -> dict:
    """Retrieve WhatsApp configuration from the database."""
    return {
        "enabled": db.get_config("whatsapp_enabled") == "true",
        "phone": db.get_config("whatsapp_phone") or "",
        "apikey": db.get_config("whatsapp_apikey") or "",
    }


def is_whatsapp_enabled() -> bool:
    """Check if WhatsApp notifications are enabled."""
    return db.get_config("whatsapp_enabled") == "true"


def is_whatsapp_configured() -> bool:
    """Check if WhatsApp is properly configured (enabled + phone + apikey)."""
    config = get_whatsapp_config()
    return all([config["enabled"], config["phone"], config["apikey"]])


def is_summary_enabled() -> bool:
    """Check if the periodic portfolio summary on WhatsApp is enabled."""
    return db.get_config("whatsapp_summary_enabled") != "false"


def get_summary_interval() -> int:
    """Get the summary interval in seconds (default 1 minute)."""
    minutes = float(db.get_config("whatsapp_summary_interval_min") or "1")
    return max(60, int(minutes * 60))


# --- Core send ---

def send_whatsapp_message(text: str) -> bool:
    """
    Send a plain-text WhatsApp message via the free CallMeBot API.

    Args:
        text: The message text (WhatsApp formatting like *bold* is allowed).

    Returns:
        True if the message was accepted by the API, False otherwise.
    """
    if not is_whatsapp_configured():
        print("[WHATSAPP] Notifications disabled or not configured. Skipping message.")
        return False

    global _rate_limited_until
    if time.time() < _rate_limited_until:
        print("[WHATSAPP] Still in CallMeBot rate-limit cooldown. Skipping message.")
        return False

    config = get_whatsapp_config()

    try:
        response = requests.get(
            CALLMEBOT_URL,
            params={
                "phone": config["phone"],
                "text": text,
                "apikey": config["apikey"],
            },
            timeout=15,
        )

        # CallMeBot returns HTTP 201 on BOTH success and error; errors are
        # distinguished by an "ERROR:" prefix in the response body.
        body = response.text or ""
        if response.status_code in (200, 201) and "error" not in body.lower():
            print(f"[WHATSAPP] Message sent to {config['phone']}.")
            return True

        if response.status_code == 503 or "too many requests" in body.lower():
            # Free CallMeBot has a daily message cap; once hit, further calls
            # get HTTP 503. Avoid hammering: wait out a cooldown before retrying.
            _rate_limited_until = time.time() + RATE_LIMIT_COOLDOWN_SECONDS
            print("[WHATSAPP] Rate limited by CallMeBot (daily message cap reached). "
                  f"Pausing WhatsApp sends for {RATE_LIMIT_COOLDOWN_SECONDS // 60} min.")
        else:
            print(f"[WHATSAPP] API error (HTTP {response.status_code}): {body[:200]}")
        return False
    except Exception as e:
        print(f"[WHATSAPP] Failed to send message: {e}")
        return False


# --- Message builders ---

def _fmt_money(v: float) -> str:
    """Format a value as a compact Rs. string with sign (unsigned for zero)."""
    if v > 0:
        return f"+Rs.{v:,.0f}"
    if v < 0:
        return f"-Rs.{abs(v):,.0f}"
    return f"Rs.{v:,.0f}"


def send_trade_notification(trade_data: dict) -> bool:
    """
    Send a WhatsApp notification for a buy or sell trade.

    Args:
        trade_data: Dict with keys - symbol, side, shares, price, investment
                    (or trade_value), realized_pnl, reason
    """
    symbol = str(trade_data.get("symbol", "Unknown")).replace(".NS", "")
    side = str(trade_data.get("side", "TRADE")).upper()
    shares = trade_data.get("shares", 0)
    price = trade_data.get("price", 0)
    reason = trade_data.get("reason", "Strategy Signal")

    if side == "BUY":
        investment = trade_data.get("investment", 0)
        header = "🟢 *BUY ALERT*"
        detail = f"Bought {shares:,} shares of {symbol} @ Rs.{price:.2f}"
        footer = f"Investment: Rs.{investment:,.2f}"
    else:
        realized_pnl = trade_data.get("realized_pnl", 0)
        pnl_text = _fmt_money(realized_pnl)
        header = "🔴 *SELL ALERT*" if realized_pnl < 0 else "🟢 *SELL ALERT (PROFIT)*"
        detail = f"Sold {shares:,} shares of {symbol} @ Rs.{price:.2f}"
        footer = f"Realized P&L: {pnl_text}"
        subject = f"🔴 SELL {symbol} x{shares} ({pnl_text})"

    message = (
        f"{header}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{detail}\n"
        f"{footer}\n"
        f"📊 Reason: {reason}\n"
        f"🕒 {datetime.now().strftime('%d %b %H:%M:%S')}"
    )

    return send_whatsapp_message(message)


def send_portfolio_summary(summary: dict = None) -> bool:
    """
    Send a WhatsApp message with the full portfolio summary:
    total profit, total loss, realized/unrealized P&L, total returns,
    shares in holdings, and a per-position breakdown.

    Args:
        summary: Optional dict from db.get_dashboard_summary().
    """
    if summary is None:
        summary = db.get_dashboard_summary()

    total_profit = db.get_total_profit()
    total_loss = db.get_total_loss()
    now = datetime.now()

    lines = [
        "📊 *PORTFOLIO SUMMARY*",
        f"🕒 {now.strftime('%A, %d %b %Y at %H:%M:%S')}",
        "━━━━━━━━━━━━━━━",
        f"💰 Total P&L: *{_fmt_money(summary['total_pnl'])}* ({('+' if summary['total_returns_pct'] >= 0 else '')}{summary['total_returns_pct']:.2f}%)",
        "━━━━━━━━━━━━━━━",
        f"🟢 Total Profit: *{_fmt_money(total_profit)}*",
        f"🔴 Total Loss: *-Rs.{total_loss:,.0f}*",
        f"✅ Realized P&L: *{_fmt_money(summary['realized_pnl'])}*",
        f"📈 Unrealized P&L: *{_fmt_money(summary['unrealized_pnl'])}*",
        f"📉 Total Returns: *{('+' if summary['total_returns_pct'] >= 0 else '')}{summary['total_returns_pct']:.2f}%*",
        f"🏦 Portfolio Value: *Rs.{summary['total_portfolio_value']:,.0f}*",
        f"💵 Cash Balance: *Rs.{summary['cash_balance']:,.0f}*",
        f"📦 Shares in Holdings: *{summary['held_shares']:,}*",
        f"🧾 Total Trades: *{summary['total_trades']}* (Win rate: {summary['win_rate']:.1f}%)",
    ]

    # Position breakdown
    holdings = db.get_holdings()
    if not holdings.empty:
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("📌 *Open Positions*")
        for _, h in holdings.iterrows():
            sym = str(h["symbol"]).replace(".NS", "")
            pnl = float(h["unrealized_pnl"])
            arrow = "🟢" if pnl >= 0 else "🔴"
            lines.append(
                f"• {sym}: {int(h['quantity'])} sh @ Rs.{float(h['avg_buy_price']):,.2f} "
                f"→ Rs.{float(h['current_price']):,.2f} ({arrow} {_fmt_money(pnl)})"
            )

    lines.append("━━━━━━━━━━━━━━━")
    lines.append("🤖 Your TA-Lib Trading Bot")

    return send_whatsapp_message("\n".join(lines))


def maybe_send_summary() -> bool:
    """
    Send the periodic portfolio summary on WhatsApp if the interval has elapsed.
    Tracks the last sent time in the database to avoid spamming.

    Returns True if a message was sent, False otherwise.
    """
    if not is_whatsapp_configured() or not is_summary_enabled():
        return False

    interval = get_summary_interval()
    last_sent = float(db.get_config("last_whatsapp_summary_at") or "0")

    if time.time() - last_sent < interval:
        return False

    success = send_portfolio_summary()
    if success:
        db.set_config("last_whatsapp_summary_at", str(time.time()))
        print(f"[WHATSAPP] Portfolio summary sent (interval {interval // 60} min).")
    return success


def send_test_message() -> dict:
    """
    Send a test WhatsApp message to verify the configuration works.

    Returns:
        Dict with 'success' bool and 'message' string
    """
    config = get_whatsapp_config()

    if not config["phone"] or not config["apikey"]:
        return {
            "success": False,
            "message": "WhatsApp not fully configured. Please fill in phone number and API key."
        }

    message = (
        "✅ *TA-Lib Trading Bot - Test Notification*\n"
        "Your WhatsApp notifications are working!\n"
        f"🕒 {datetime.now().strftime('%d %b %Y %H:%M:%S')}"
    )

    success = send_whatsapp_message(message)
    if success:
        return {"success": True, "message": "Test WhatsApp message sent! Check your phone."}
    else:
        return {"success": False, "message": "Failed to send test message. Check your settings and try again."}


if __name__ == "__main__":
    # Quick manual test: python whatsapp_notifier.py
    result = send_test_message()
    print(result["message"])

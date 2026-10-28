"""
Trading Dashboard REST API
==========================
JSON API for the native Android app.

Serves portfolio data, holdings, trades, signals and trading controls
from the same SQLite database the dashboard uses.

Security:
  * Every /api/* endpoint (except /health) requires a Bearer token.
  * The token is the same 6-digit PIN used by the remote control panel
    (dashboard_control_pin.txt), auto-generated on first run.
  * Use secrets.compare_digest to avoid timing attacks.

Run it (Python 3.10 - the interpreter that has Streamlit/FastAPI):
    py -3.10 api_server.py

It binds 0.0.0.0:8000 so the phone can reach it over Tailscale:
    http://<pc-tailscale-ip>:8000/api/summary
"""

import os
import time
import secrets
import uvicorn
from datetime import datetime

import database as db
from market_data import get_market_status, is_market_open

HERE = os.path.dirname(os.path.abspath(__file__))
PIN_FILE = os.path.join(HERE, "dashboard_control_pin.txt")

API_PORT = 8000

# Brute-force protection (same policy as dashboard_control.py):
# max 5 failed attempts per client IP, then a 60s lockout.
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60
_failures = {}  # client ip -> {"count": int, "locked_until": float}

# --------------------------------------------------------------------------
# PIN / auth (shared with dashboard_control.py so it stays one PIN)
# --------------------------------------------------------------------------
def load_or_create_pin() -> str:
    pin = ""
    if os.path.exists(PIN_FILE):
        with open(PIN_FILE, "r", encoding="utf-8") as f:
            pin = f.read().strip()
    if not pin:
        pin = "".join(secrets.choice("0123456789") for _ in range(6))
        with open(PIN_FILE, "w", encoding="utf-8") as f:
            f.write(pin)
    return pin


PIN = load_or_create_pin()


# --------------------------------------------------------------------------
# Helpers to convert pandas rows into JSON-safe dicts
# --------------------------------------------------------------------------
def _nan_to_none(v):
    """Sanitize a single value so JSON stays clean:
    NaN/None -> None, and corrupted bytes (e.g. null bytes that
    ended up in old portfolio_history rows) -> None."""
    try:
        import math
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
    except Exception:
        pass
    if isinstance(v, (bytes, bytearray)):
        # old corrupted BLOB rows (null bytes) -> None
        if b"\x00" in v:
            return None
        try:
            return v.decode("utf-8")
        except Exception:
            return None
    if isinstance(v, str):
        if "\x00" in v:  # corrupted value in the DB
            return None
        try:
            return v.encode("utf-8").decode("utf-8")
        except Exception:
            return None
    return v


def df_to_list(df) -> list:
    if df is None or df.empty:
        return []
    return [{k: _nan_to_none(v) for k, v in row.items()} for row in df.to_dict("records")]


# --------------------------------------------------------------------------
# Trading controls (shared state with the dashboard via DB config)
# --------------------------------------------------------------------------
def is_trading_active() -> bool:
    return db.get_config("trading_active") == "true"


def set_trading_active(active: bool):
    db.set_config("trading_active", "true" if active else "false")


# --------------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------------
from fastapi import FastAPI, Header, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Trading Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_token(request: Request, authorization: str = Header(default="")) -> None:
    """Auth dependency: Bearer token must match the PIN, with per-IP
    rate limiting so a 6-digit PIN can't be brute-forced."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    entry = _failures.get(client_ip, {"count": 0, "locked_until": 0.0})
    if now < entry["locked_until"]:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {int(entry['locked_until'] - now) + 1}s.",
        )

    expected = f"Bearer {PIN}"
    if secrets.compare_digest(authorization.strip(), expected):
        _failures.pop(client_ip, None)
        return

    entry["count"] += 1
    if entry["count"] >= _MAX_FAILED_ATTEMPTS:
        entry["locked_until"] = now + _LOCKOUT_SECONDS
        entry["count"] = 0
    _failures[client_ip] = entry
    raise HTTPException(status_code=401, detail="Invalid or missing token")


class ConfigUpdate(BaseModel):
    key: str
    value: str


class WatchlistUpdate(BaseModel):
    symbols: list


# --- public endpoints -----------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "trading_active": is_trading_active(),
    }


# --- authenticated endpoints ---------------------------------------------
@app.get("/api/summary", dependencies=[Depends(require_token)])
def summary():
    return db.get_dashboard_summary()


@app.get("/api/market", dependencies=[Depends(require_token)])
def market():
    return {
        "status": get_market_status(),
        "open": is_market_open(),
        "time": datetime.now().isoformat(),
    }


@app.get("/api/holdings", dependencies=[Depends(require_token)])
def holdings():
    """Holdings with the bot's exit plan (stop loss / take profit levels)."""
    stop_loss_pct = float(db.get_config("stop_loss_pct") or 3)
    take_profit_pct = float(db.get_config("take_profit_pct") or 5)
    rows = df_to_list(db.get_holdings())
    for r in rows:
        avg = r.get("avg_buy_price") or 0
        r["stop_loss_pct"] = stop_loss_pct
        r["take_profit_pct"] = take_profit_pct
        if avg > 0:
            r["stop_loss_price"] = round(avg * (1 - stop_loss_pct / 100), 2)
            r["take_profit_price"] = round(avg * (1 + take_profit_pct / 100), 2)
        else:
            r["stop_loss_price"] = 0
            r["take_profit_price"] = 0
    return rows


@app.get("/api/trades", dependencies=[Depends(require_token)])
def trades(limit: int = Query(100, ge=1, le=500)):
    return df_to_list(db.get_trades(limit=limit))


@app.get("/api/signals", dependencies=[Depends(require_token)])
def signals(limit: int = Query(100, ge=1, le=500)):
    return df_to_list(db.get_recent_signals(limit=limit))


@app.get("/api/portfolio-history", dependencies=[Depends(require_token)])
def portfolio_history(limit: int = Query(300, ge=10, le=1000)):
    df = db.get_portfolio_history(limit=limit)
    return df_to_list(df)


@app.get("/api/config", dependencies=[Depends(require_token)])
def config():
    keys = [
        "initial_capital", "current_cash", "max_position_pct",
        "stop_loss_pct", "take_profit_pct", "max_positions",
        "email_enabled", "email_smtp_server", "email_smtp_port",
        "email_sender", "email_password", "email_recipient",
        "email_rise_alerts", "rise_alert_threshold_pct",
        "watchlist_rise_alerts",
        "summary_email_enabled", "summary_email_interval_min",
        "whatsapp_enabled",
    ]
    cfg = {k: (db.get_config(k) or "") for k in keys}
    cfg["watchlist"] = db.get_watchlist()
    cfg["trading_active"] = is_trading_active()
    return cfg


@app.post("/api/config", dependencies=[Depends(require_token)])
def update_config(update: ConfigUpdate):
    allowed = {
        "max_position_pct", "stop_loss_pct", "take_profit_pct", "max_positions",
        "email_enabled", "email_smtp_server", "email_smtp_port",
        "email_sender", "email_password", "email_recipient",
        "email_rise_alerts", "rise_alert_threshold_pct",
        "watchlist_rise_alerts",
        "summary_email_enabled", "summary_email_interval_min",
    }
    if update.key not in allowed:
        raise HTTPException(status_code=400, detail=f"Key '{update.key}' is read-only")
    db.set_config(update.key, str(update.value))
    return {"ok": True, "key": update.key, "value": update.value}


@app.post("/api/email/test", dependencies=[Depends(require_token)])
def test_email():
    """Send a test email to verify the SMTP configuration."""
    from email_notifier import send_test_email
    return send_test_email()


@app.post("/api/watchlist", dependencies=[Depends(require_token)])
def update_watchlist(update: WatchlistUpdate):
    clean = []
    for s in update.symbols:
        s = s.strip().upper()
        if s:
            if not s.endswith(".NS"):
                s += ".NS"
            clean.append(s)
    db.set_config("watchlist", ",".join(clean))
    return {"ok": True, "count": len(clean), "symbols": clean}


@app.post("/api/trading/start", dependencies=[Depends(require_token)])
def start_trading():
    set_trading_active(True)
    return {"ok": True, "trading_active": True}


@app.post("/api/trading/stop", dependencies=[Depends(require_token)])
def stop_trading():
    set_trading_active(False)
    return {"ok": True, "trading_active": False}


@app.post("/api/trading/cycle", dependencies=[Depends(require_token)])
def run_cycle():
    """Run one manual trading scan cycle (signal scan + execution)."""
    from trading_engine import process_signals
    try:
        result = process_signals()
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cycle failed: {e}")


if __name__ == "__main__":
    db.init_db()
    print(f"[API] Trading Dashboard API starting on port {API_PORT}")
    print(f"[API] Auth token (PIN): {PIN}")
    print(f"[API] Reachable at: http://<pc-tailscale-ip>:{API_PORT}/api/health")
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level="info")

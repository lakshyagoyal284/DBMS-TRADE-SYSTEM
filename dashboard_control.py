"""
Dashboard Control Server
========================
A tiny, zero-dependency web control panel that lets you start and stop the
TA-Lib Trading Dashboard (Streamlit) from your phone.

How it works:
  * Runs on port 8765 on your PC, reachable from your phone via Tailscale
    (or home Wi-Fi).
  * Shows big START / STOP buttons and the live status of the dashboard.
  * Locks the controls behind a 6-digit PIN (saved in dashboard_control_pin.txt).
  * Uses only the Python standard library - no packages to install.

Run it (use Python 3.10, the interpreter that has Streamlit installed):
    py -3.10 dashboard_control.py

It auto-starts when you log in to Windows via the Startup folder
(dashboard_control_start.vbs).
"""

import os
import sys
import time
import socket
import string
import hashlib
import secrets
import subprocess
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(HERE, "dashboard_control.pid")  # dashboard PID
API_PID_FILE = os.path.join(HERE, "api_server.pid")     # API server PID
PIN_FILE = os.path.join(HERE, "dashboard_control_pin.txt")
LOG_FILE = os.path.join(HERE, "dashboard_control.log")

CONTROL_PORT = 8765
DASHBOARD_PORT = 8501
API_PORT = 8000
PYTHON = sys.executable  # the Python 3.10 interpreter running this server

COOKIE_NAME = "dc_session"
COOKIE_SALT = "ta-lib-dashboard-control"


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# --------------------------------------------------------------------------
# PIN handling (auto-generated on first run)
# --------------------------------------------------------------------------
def load_or_create_pin() -> str:
    pin = ""
    if os.path.exists(PIN_FILE):
        with open(PIN_FILE, "r", encoding="utf-8") as f:
            pin = f.read().strip()
    if not pin:
        pin = "".join(secrets.choice(string.digits) for _ in range(6))
        with open(PIN_FILE, "w", encoding="utf-8") as f:
            f.write(pin)
        log("Generated new PIN (saved to dashboard_control_pin.txt)")
    return pin


PIN = load_or_create_pin()


def pin_hash(pin: str) -> str:
    return hashlib.sha256((pin + COOKIE_SALT).encode()).hexdigest()


def cookie_value() -> str:
    return pin_hash(PIN)


# Simple brute-force protection for the PIN page
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60
_failures = {}  # client ip -> {"count": int, "locked_until": float}


# --------------------------------------------------------------------------
# Dashboard process management
# --------------------------------------------------------------------------
def pid_from_file(path: str = None):
    path = path or PID_FILE
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None


def pid_alive(pid):
    if not pid:
        return False
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == str(pid) and parts[1].isdigit():
                return True
        return False
    except Exception:
        return False


def is_dashboard_running() -> bool:
    """True if the dashboard is actually serving requests on its port."""
    if pid_alive(pid_from_file()):
        return True
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{DASHBOARD_PORT}/_stcore/health", timeout=2
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_dashboard() -> str:
    if is_dashboard_running():
        return "already-running"

    try:
        logfile = open(os.path.join(HERE, "dashboard_run.log"), "a", encoding="utf-8")
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(
            [
                PYTHON, "-m", "streamlit", "run", "dashboard.py",
                "--server.address", "0.0.0.0",
                "--server.port", str(DASHBOARD_PORT),
                "--server.headless", "true",
            ],
            cwd=HERE,
            stdout=logfile,
            stderr=logfile,
            creationflags=flags,
        )
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
        log(f"Dashboard start requested (PID {proc.pid})...")
        return "started"
    except Exception as e:
        log(f"Failed to start dashboard: {e}")
        return "error"


def stop_dashboard() -> bool:
    killed = False

    # 1) Kill the process tree we recorded (if any)
    pid = pid_from_file()
    if pid_alive(pid):
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, timeout=15,
        )
        killed = True
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass

    # 2) Kill anything else still listening on the dashboard port
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=15
        ).stdout
        pids = set()
        port = f":{DASHBOARD_PORT}"
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(port) and parts[3] == "LISTENING":
                if parts[4].isdigit() and parts[4] != "0":
                    pids.add(parts[4])
        for p in pids:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", p],
                capture_output=True, timeout=15,
            )
            killed = True
    except Exception:
        pass

    if killed:
        log("Dashboard stopped.")
    return killed


def is_api_running() -> bool:
    """True if the API server is actually serving requests on its port."""
    if pid_alive(pid_from_file(API_PID_FILE)):
        return True
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{API_PORT}/api/health", timeout=2
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_api() -> str:
    """Start the FastAPI server (port 8000) the phone app talks to."""
    if is_api_running():
        return "already-running"
    try:
        logfile = open(os.path.join(HERE, "api_server.log"), "a", encoding="utf-8")
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(
            [PYTHON, os.path.join(HERE, "api_server.py")],
            cwd=HERE,
            stdout=logfile,
            stderr=logfile,
            creationflags=flags,
        )
        with open(API_PID_FILE, "w") as f:
            f.write(str(proc.pid))
        log(f"API server start requested (PID {proc.pid})...")
        return "started"
    except Exception as e:
        log(f"Failed to start API server: {e}")
        return "error"


def stop_api() -> bool:
    """Stop the API server (recorded PID + anything on port 8000)."""
    killed = False
    pid = pid_from_file(API_PID_FILE)
    if pid_alive(pid):
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, timeout=15,
        )
        killed = True
    try:
        if os.path.exists(API_PID_FILE):
            os.remove(API_PID_FILE)
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=15
        ).stdout
        port = f":{API_PORT}"
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(port) and parts[3] == "LISTENING":
                if parts[4].isdigit() and parts[4] != "0":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", parts[4]],
                        capture_output=True, timeout=15,
                    )
                    killed = True
    except Exception:
        pass
    if killed:
        log("API server stopped.")
    return killed


def start_all() -> dict:
    """Start both the dashboard and the API server."""
    return {"dashboard": start_dashboard(), "api": start_api()}


def stop_all() -> dict:
    """Stop both the dashboard and the API server."""
    return {"dashboard": stop_dashboard(), "api": stop_api()}

def get_hostname() -> str:
    return socket.gethostname()


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# Tailscale IP is cached (the 3s page auto-refresh shouldn't re-run the CLI)
_tailscale_ip_cache = {"ip": "", "at": 0.0}


def get_tailscale_ip() -> str:
    """This PC's Tailscale IP (100.x) - reachable from your phone from anywhere.
    Browsers don't force HTTPS on IP addresses, so this URL avoids the
    "can't provide a secure connection" error on the phone."""
    if time.time() - _tailscale_ip_cache["at"] < 300:
        return _tailscale_ip_cache["ip"]
    ts = r"C:\Program Files\Tailscale\tailscale.exe"
    found = ""
    try:
        out = subprocess.run(
            [ts, "ip", "-4"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
        for line in out.splitlines():
            ip = line.strip()
            if ip.startswith("100."):
                found = ip
                break
    except Exception:
        pass
    _tailscale_ip_cache["ip"] = found
    _tailscale_ip_cache["at"] = time.time()
    return found


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
       background: #0f172a; color: #e2e8f0; min-height: 100vh;
       display: flex; align-items: center; justify-content: center; padding: 16px; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 20px;
        padding: 32px 24px; max-width: 420px; width: 100%;
        box-shadow: 0 20px 60px rgba(0,0,0,.5); text-align: center; }
h1 { font-size: 1.5rem; margin-bottom: 4px; }
.sub { color: #94a3b8; font-size: .85rem; margin-bottom: 20px; }
.pill { display: inline-block; padding: 8px 18px; border-radius: 999px;
        font-weight: 700; font-size: .95rem; margin-bottom: 24px; }
.pill.on { background: #052e16; color: #4ade80; border: 1px solid #16a34a55; }
.pill.off { background: #450a0a; color: #f87171; border: 1px solid #dc262655; }
.btn { display: block; width: 100%; border: none; border-radius: 14px;
       font-size: 1.15rem; font-weight: 700; padding: 18px; margin: 10px 0;
       cursor: pointer; color: #fff; text-decoration: none; }
.btn:disabled { opacity: .4; cursor: not-allowed; }
.svc { background: #0f172a; border: 1px solid #334155; border-radius: 14px;
       padding: 14px; margin: 10px 0; text-align: left; }
.svc-head { display: flex; justify-content: space-between; align-items: center;
            gap: 8px; margin-bottom: 10px; }
.svc-title { font-weight: 700; font-size: 1.05rem; }
.svc-actions { display: flex; gap: 10px; }
.svc-actions form { flex: 1; }
.svc-actions .btn { margin: 0; padding: 12px; font-size: .95rem; }
.svc .btn.open { margin-top: 10px; }
.start { background: linear-gradient(135deg, #16a34a, #15803d); }
.stop { background: linear-gradient(135deg, #dc2626, #b91c1c); }
.open { background: linear-gradient(135deg, #2563eb, #1d4ed8); }
.info { margin-top: 18px; font-size: .8rem; color: #94a3b8; line-height: 1.6;
        word-break: break-all; }
.lock { font-size: 2.6rem; margin-bottom: 8px; }
input[type=password] { width: 100%; padding: 16px; font-size: 1.3rem;
       text-align: center; letter-spacing: .4em; border-radius: 12px;
       border: 1px solid #334155; background: #0f172a; color: #e2e8f0;
       margin: 16px 0; }
.err { color: #f87171; font-size: .85rem; margin-top: 8px; }
"""


def render_control_page(auth_ok: bool, error: str = "") -> str:
    if not auth_ok:
        err = f'<div class="err">{error}</div>' if error else ""
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Dashboard Remote - Locked</title><style>" + CSS + "</style></head><body>"
            "<div class='card'><div class='lock'>🔒</div><h1>Dashboard Remote</h1>"
            "<div class='sub'>Enter your 6-digit PIN</div>"
            "<form method='post' action='/unlock'>"
            "<input type='password' name='pin' inputmode='numeric' "
            "autocomplete='off' autofocus required>"
            "<button class='btn start' type='submit'>Unlock</button></form>"
            + err + "</div></body></html>"
        )

    dash_running = is_dashboard_running()
    api_running = is_api_running()

    def status_row(emoji: str, title: str, key: str, running: bool, extra: str = ""):
        state = ('<span class="pill on">● RUNNING</span>' if running
                 else '<span class="pill off">● STOPPED</span>')
        act_start = ('' if running else
                     f'<form method="post" action="/start-{key}">'
                     f'<button class="btn start" type="submit">▶ Start</button></form>')
        act_stop = (f'<form method="post" action="/stop-{key}">'
                    f'<button class="btn stop" type="submit">⏹ Stop</button></form>'
                    if running else '')
        return (
            f'<div class="svc">'
            f'<div class="svc-head"><span class="svc-title">{emoji} {title}</span>{state}</div>'
            f'<div class="svc-actions">{act_start}{act_stop}</div>'
            + extra +
            '</div>'
        )

    host = get_hostname()
    lan = get_lan_ip()
    ts = get_tailscale_ip()  # 100.x IP - works from anywhere via Tailscale
    remote = ts or lan or host

    dash_extra = (f'<a class="btn open" href="http://{remote}:{DASHBOARD_PORT}" '
                  f'target="_blank">📈 Open Dashboard</a>' if dash_running else "")
    api_extra = (f'<a class="btn open" href="http://{remote}:{API_PORT}/api/health" '
                 f'target="_blank">⚙️ API Health</a>' if api_running else "")

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta http-equiv='refresh' content='3'>"
        "<title>Dashboard Remote</title><style>" + CSS + "</style></head><body>"
        "<div class='card'><h1>📈 Trading Dashboard</h1>"
        "<div class='sub'>Remote control · auto-updates every 3s</div>"
        + status_row("📈", "Dashboard", "dashboard", dash_running, dash_extra)
        + status_row("⚙️", "API Server", "api", api_running, api_extra)
        + '<div class="svc-actions">'
        '<form method="post" action="/start-all">'
        '<button class="btn start" type="submit">▶ START ALL</button></form>'
        '<form method="post" action="/stop-all">'
        '<button class="btn stop" type="submit">⏹ STOP ALL</button></form>'
        '</div>' +
        "<div class='info'>"
        "<b>Direct links</b> (open on your phone):<br>"
        f"Control panel: <b>http://{remote}:{CONTROL_PORT}</b><br>"
        f"Dashboard: <b>http://{remote}:{DASHBOARD_PORT}</b><br>"
        f"API: <b>http://{remote}:{API_PORT}/api/health</b><br>"
        f"Home Wi-Fi only: <b>http://{lan}:{DASHBOARD_PORT}</b><br>"
        "Tip: type the full <b>http://</b> URL on your phone, and ignore the "
        "\"Not Secure\" label - Tailscale already encrypts everything."
        "</div></div></body></html>"
    )


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: str, extra_headers=None, set_cookie=None):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str):
        self._send(303, "", extra_headers={"Location": location})

    def _auth_ok(self) -> bool:
        cookies = self.headers.get("Cookie") or ""
        for part in cookies.split(";"):
            part = part.strip()
            if part.startswith(COOKIE_NAME + "="):
                return part.split("=", 1)[1] == cookie_value()
        return False

    def _set_auth_cookie(self) -> str:
        return (f"{COOKIE_NAME}={cookie_value()}; Path=/; HttpOnly; "
                "SameSite=Lax; Max-Age=2592000")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, render_control_page(self._auth_ok()))
        elif path == "/healthz":
            self._send(200, "ok")
        else:
            self._send(404, "<h1>Not found</h1>")

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/unlock":
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8", "replace")
            pin = (parse_qs(body).get("pin") or [""])[0].strip()

            client_ip = self.client_address[0]
            now = time.time()
            entry = _failures.get(client_ip, {"count": 0, "locked_until": 0.0})
            if now < entry["locked_until"]:
                wait = int(entry["locked_until"] - now) + 1
                self._send(200, render_control_page(
                    False, f"Too many attempts. Try again in {wait}s."))
                return

            if secrets.compare_digest(pin, PIN):
                _failures.pop(client_ip, None)
                self._send(200, render_control_page(True),
                           set_cookie=self._set_auth_cookie())
            else:
                entry["count"] += 1
                if entry["count"] >= _MAX_FAILED_ATTEMPTS:
                    entry["locked_until"] = now + _LOCKOUT_SECONDS
                    entry["count"] = 0
                    msg = (f"Too many wrong attempts. Locked for "
                           f"{_LOCKOUT_SECONDS}s.")
                else:
                    msg = (f"Wrong PIN. "
                           f"{_MAX_FAILED_ATTEMPTS - entry['count']} attempts left.")
                _failures[client_ip] = entry
                self._send(200, render_control_page(False, msg))
            return

        if not self._auth_ok():
            self._redirect("/")
            return

        if path in ("/start-dashboard", "/start"):
            start_dashboard()
            self._redirect("/")
        elif path in ("/stop-dashboard", "/stop"):
            stop_dashboard()
            self._redirect("/")
        elif path == "/start-api":
            start_api()
            self._redirect("/")
        elif path == "/stop-api":
            stop_api()
            self._redirect("/")
        elif path == "/start-all":
            start_all()
            self._redirect("/")
        elif path == "/stop-all":
            stop_all()
            self._redirect("/")
        else:
            self._send(404, "<h1>Not found</h1>")

    def log_message(self, fmt, *args):
        # quiet the default request logging
        pass


# --------------------------------------------------------------------------
# Auto-start installer (writes a hidden launcher into the Windows Startup folder)
# --------------------------------------------------------------------------
def install_autostart() -> str:
    try:
        pythonw = os.path.join(os.path.dirname(PYTHON), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = PYTHON
        startup = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
        )
        if not os.path.isdir(startup):
            return f"Startup folder not found: {startup}"

        vbs = (
            "Set shell = CreateObject(\"WScript.Shell\")\r\n"
            "shell.CurrentDirectory = \"" + HERE.replace("\\", "\\\\") + "\"\r\n"
            "shell.Run \"" + pythonw.replace("\\", "\\\\") + "\" \"" +
            os.path.join(HERE, "dashboard_control.py").replace("\\", "\\\\") +
            "\", 0, False\r\n"
        )
        target = os.path.join(startup, "DashboardControl.vbs")
        with open(target, "w", encoding="utf-8") as f:
            f.write(vbs)
        log(f"Auto-start installed -> {target}")
        return target
    except Exception as e:
        log(f"Auto-start install failed: {e}")
        return f"error: {e}"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
if __name__ == "__main__":
    if "--install" in sys.argv:
        print(install_autostart())
    else:
        log(f"Dashboard Control Server starting on port {CONTROL_PORT}")
        # Auto-start both services so everything is up right after the PC boots.
        results = start_all()
        log(f"Auto-start results: dashboard={results['dashboard']}, api={results['api']}")
        server = ThreadingHTTPServer(("0.0.0.0", CONTROL_PORT), Handler)
        server.daemon_threads = True
        server.serve_forever()

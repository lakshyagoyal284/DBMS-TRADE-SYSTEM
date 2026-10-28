"""
WoL Relay
=========
A tiny, zero-dependency server that lets you wake the trading PC **from
anywhere**. It runs on ANY always-on device that is on the same home Wi-Fi/LAN
as the PC (e.g. an old Android phone via Termux, a Raspberry Pi, a mini PC, or
a router that can run scripts). Put Tailscale on that device so your phone can
reach it from outside, then set its URL in the Trading App's WoL settings.

  GET /wake   -> sends the magic packet to the trading PC (via Tailscale from anywhere)
  GET /health -> "ok"

Run it (any Python 3):
    python wol_relay.py
"""

import socket
import http.server
from urllib.parse import urlparse, parse_qs

# --- Configure for YOUR network -------------------------------------------
PC_MAC = "38:A7:46:43:8B:06"   # trading PC's NIC MAC (use the Ethernet MAC for reliability)
PC_IP = "10.20.4.180"          # trading PC's LAN IP (used as a fallback target)
BROADCAST = "10.20.4.255"      # home LAN broadcast address (last octet .255)
PORT = 8099
WAKE_KEY = "change-me-123"     # shared secret - put it in the app's relay URL as ?key=...
# --------------------------------------------------------------------------


def magic_packet(mac: str) -> bytes:
    mac = mac.replace(":", "").replace("-", "").replace(" ", "")
    mac_bytes = bytes.fromhex(mac)
    return b"\xff" * 6 + mac_bytes * 16


def send_wol() -> None:
    pkt = magic_packet(PC_MAC)
    for addr in (BROADCAST, PC_IP):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(pkt, (addr, 9))
            s.sendto(pkt, (addr, 9))  # twice for reliability
            s.close()
            print(f"  magic packet sent to {addr}:9")
        except Exception as e:
            print(f"  failed to send to {addr}: {e}")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path.startswith("/wake"):
            # Require the shared secret so strangers can't wake the PC.
            if qs.get("key", [""])[0] != WAKE_KEY:
                self.send_response(403)
                body = b"forbidden"
            else:
                send_wol()
                self.send_response(200)
                body = b"wake sent"
        elif parsed.path.startswith("/health"):
            self.send_response(200)
            body = b"ok"
        else:
            self.send_response(404)
            body = b""
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep it quiet


if __name__ == "__main__":
    print(f"WoL relay listening on port {PORT} -> waking {PC_MAC} (broadcast {BROADCAST})")
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

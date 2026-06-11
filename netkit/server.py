#!/usr/bin/env python3
"""NET KIT - Daily Internet Usage Tracker. Belongs to J. Servo LLC Smart Tech Stack.

Cross-platform (macOS / Linux / Windows). Stdlib only. Serves a single-file
dashboard plus a small JSON API. OS-specific data sources live in probes.py;
the daily ledger comes from vnStat when present, otherwise a built-in SQLite
poller (ledger.py) so the core feature works everywhere.

Config via env: NETKIT_HOST (default 127.0.0.1), NETKIT_PORT (default 8787),
NETKIT_DATA (default ~/.netkit).
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import probes
from .ledger import BuiltinLedger

try:
    from importlib.resources import files as _res_files
except ImportError:  # pragma: no cover - py<3.9
    _res_files = None

HOST = os.environ.get("NETKIT_HOST", "127.0.0.1")
PORT = int(os.environ.get("NETKIT_PORT", "8787"))
DATA_DIR = Path(os.environ.get("NETKIT_DATA", Path.home() / ".netkit"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SPEED_HISTORY = DATA_DIR / "speedtests.jsonl"
IP_HISTORY = DATA_DIR / "ip_history.jsonl"

_isp_cache = {"ts": 0, "data": None}
_speed_lock = threading.Lock()

# Built-in ledger runs always; on macOS/Linux with vnStat we prefer vnStat's
# richer DB for queries but still keep the builtin warm as a portable fallback.
_LEDGER = BuiltinLedger(DATA_DIR / "netkit.db", probes.iface_counters)
_HAS_VNSTAT = probes.vnstat_json() is not None


def _asset(name):
    """Read a packaged asset whether running from source, an installed wheel,
    or a zipapp .pyz."""
    if _res_files is not None:
        return (_res_files(__package__) / name).read_bytes()
    return (Path(__file__).resolve().parent / name).read_bytes()  # fallback


def ledger_json():
    if _HAS_VNSTAT:
        data = probes.vnstat_json()
        if data:
            return data
    return _LEDGER.to_vnstat_json()


def get_isp():
    import urllib.request
    if _isp_cache["data"] and time.time() - _isp_cache["ts"] < 600:
        return _isp_cache["data"]
    data = None
    for url in ("https://ifconfig.co/json", "https://ipinfo.io/json"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NETKIT/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                j = json.load(r)
            data = {"ip": j.get("ip"), "isp": j.get("asn_org") or j.get("org"),
                    "asn": j.get("asn"), "city": j.get("city"),
                    "country": j.get("country"),
                    "timezone": j.get("time_zone") or j.get("timezone"),
                    "source": url.split("/")[2]}
            break
        except Exception:
            continue
    if data:
        _isp_cache.update(ts=time.time(), data=data)
    return data or {"error": "ISP lookup unreachable"}


def _read_jsonl(path, n):
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    return [json.loads(x) for x in lines[-n:]][::-1]


def ip_watch():
    while True:
        data = get_isp()
        ip = data.get("ip")
        if ip:
            last = _read_jsonl(IP_HISTORY, 1)
            if not last or last[0]["ip"] != ip:
                with open(IP_HISTORY, "a") as f:
                    f.write(json.dumps({"ts": int(time.time()), "ip": ip,
                                        "isp": data.get("isp"),
                                        "asn": data.get("asn")}) + "\n")
        time.sleep(601)


def run_speedtest():
    rec = probes.run_speedtest()
    with open(SPEED_HISTORY, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/speedtest":
            if not _speed_lock.acquire(blocking=False):
                self._send(409, "application/json",
                           json.dumps({"error": "test already running"}).encode())
                return
            try:
                self._send(200, "application/json",
                           json.dumps(run_speedtest()).encode())
            except Exception as e:
                self._send(500, "application/json",
                           json.dumps({"error": str(e)}).encode())
            finally:
                _speed_lock.release()
        else:
            self._send(404, "text/plain", b"not found")

    def do_GET(self):
        try:
            if self.path.startswith("/api/ifstats"):
                c = probes.iface_counters()
                body = ({"ts": time.time(), "rx": c[1], "tx": c[2]} if c
                        else {"ts": time.time(), "rx": 0, "tx": 0, "error": "no interface"})
                self._send(200, "application/json", json.dumps(body).encode())
            elif self.path == "/api/isp":
                self._send(200, "application/json", json.dumps(get_isp()).encode())
            elif self.path == "/api/speedtest/history":
                self._send(200, "application/json",
                           json.dumps(_read_jsonl(SPEED_HISTORY, 10)).encode())
            elif self.path == "/api/ip/history":
                self._send(200, "application/json",
                           json.dumps(_read_jsonl(IP_HISTORY, 10)).encode())
            elif self.path.startswith("/api/live"):
                self._send(200, "application/json",
                           json.dumps(probes.live_connections()).encode())
            elif self.path.startswith("/api"):
                self._send(200, "application/json",
                           json.dumps(ledger_json()).encode())
            elif self.path == "/logo.png":
                self._send(200, "image/png", _asset("logo.png"))
            elif self.path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", _asset("index.html"))
            else:
                self._send(404, "text/plain", b"not found")
        except Exception as e:
            self._send(500, "application/json",
                       json.dumps({"error": str(e)}).encode())

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    threading.Thread(target=ip_watch, daemon=True).start()
    threading.Thread(target=_LEDGER.run, daemon=True).start()
    src = "vnStat" if _HAS_VNSTAT else "built-in SQLite ledger"
    print(f"NET KIT [{probes.SYS}] on http://{HOST}:{PORT}  (ledger: {src})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

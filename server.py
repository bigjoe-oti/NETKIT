#!/usr/bin/env python3
"""NET KIT - Daily Internet Usage Tracker. Belongs to J. Servo LLC Smart Tech Stack.

Serves the single-file UI and two data endpoints, stdlib only:
  /api       -> `vnstat --json`        (persistent daily ledger)
  /api/live  -> parsed `nettop -n -x`  (per-app + per-port live counters)
"""
import json
import re
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VNSTAT = "/usr/local/bin/vnstat"
NETTOP = "/usr/bin/nettop"
NETQUALITY = "/usr/bin/networkQuality"
ROOT = Path(__file__).resolve().parent
LOGO = ROOT / "Home Page JServo Logo-150px.png"
SPEED_HISTORY = ROOT / "speedtests.jsonl"
IP_HISTORY = ROOT / "ip_history.jsonl"
HOST, PORT = "127.0.0.1", 8787

_isp_cache = {"ts": 0, "data": None}
_speed_lock = threading.Lock()

WELL_KNOWN = {
    20: "FTP data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 67: "DHCP", 68: "DHCP", 80: "HTTP", 88: "Kerberos",
    110: "POP3", 123: "NTP", 137: "NetBIOS", 143: "IMAP", 161: "SNMP",
    443: "HTTPS", 445: "SMB", 465: "SMTPS", 500: "IPsec IKE",
    546: "DHCPv6", 547: "DHCPv6", 587: "SMTP submission", 853: "DNS over TLS",
    993: "IMAPS", 995: "POP3S", 1900: "SSDP", 3478: "STUN/TURN",
    4500: "IPsec NAT-T", 5222: "XMPP", 5223: "Apple Push", 5228: "Google Play",
    5353: "mDNS/Bonjour", 8021: "local service", 8787: "NET KIT itself",
    19302: "STUN (Google)",
}

_PORT_RE = re.compile(r"[.:](\d+)$")


def _port_of(endpoint):
    m = _PORT_RE.search(endpoint.strip())
    return int(m.group(1)) if m else None


def _service_port(local, remote):
    """Pick the port that names the service, not the ephemeral side."""
    for p in (remote, local):
        if p and (p in WELL_KNOWN or p < 1024):
            return p
    return remote or local


def _real_names(pids):
    """nettop truncates/mangles process names; resolve them via ps."""
    if not pids:
        return {}
    out = subprocess.run(["ps", "-o", "pid=,comm=", "-p", ",".join(pids)],
                         capture_output=True, timeout=5, text=True).stdout
    names = {}
    for ln in out.splitlines():
        parts = ln.strip().split(None, 1)
        if len(parts) == 2:
            names[parts[0]] = parts[1].rsplit("/", 1)[-1]
    return names


def parse_nettop(raw):
    procs, ports = [], {}
    for line in raw.splitlines()[1:]:
        f = line.split(",")
        if len(f) < 6:
            continue
        name, bi, bo = f[1], f[4], f[5]
        if "<->" in name:
            if not (bi or bo):
                continue  # idle listener rows carry no byte fields
            rx, tx = int(bi or 0), int(bo or 0)
            if rx == 0 and tx == 0:
                continue
            proto_field, _, conn = name.partition(" ")
            proto = "udp" if proto_field.startswith("udp") else "tcp"
            local, _, remote = conn.partition("<->")
            p = _service_port(_port_of(local), _port_of(remote))
            if p is None:
                continue
            key = (p, proto)
            e = ports.setdefault(key, {"port": p, "proto": proto,
                                       "service": WELL_KNOWN.get(p),
                                       "rx": 0, "tx": 0, "conns": 0})
            e["rx"] += rx
            e["tx"] += tx
            e["conns"] += 1
        elif bi.isdigit() and bo.isdigit():
            rx, tx = int(bi), int(bo)
            if rx == 0 and tx == 0:
                continue
            pname, _, pid = name.rpartition(".")
            procs.append((pid if pid.isdigit() else None, pname or name, rx, tx))

    resolved = _real_names(sorted({p[0] for p in procs if p[0]}))
    apps = {}
    for pid, fallback, rx, tx in procs:
        pname = resolved.get(pid, fallback)
        e = apps.setdefault(pname, {"name": pname, "rx": 0, "tx": 0, "procs": 0})
        e["rx"] += rx
        e["tx"] += tx
        e["procs"] += 1

    # nettop truncates names (~15 chars); fold "Google Chrome H" into "Google Chrome"
    merged = {}
    for pname in sorted(apps, key=len):
        target = next((t for t in merged if len(t) >= 8 and pname.startswith(t)), None)
        if target:
            for k in ("rx", "tx", "procs"):
                merged[target][k] += apps[pname][k]
        else:
            merged[pname] = apps[pname]

    key_total = lambda e: e["rx"] + e["tx"]
    return {
        "apps": sorted(merged.values(), key=key_total, reverse=True),
        "ports": sorted(ports.values(), key=key_total, reverse=True),
    }


def get_isp():
    """Public IP + ISP identity, cached 10 min. ifconfig.co first, ipinfo fallback."""
    if _isp_cache["data"] and time.time() - _isp_cache["ts"] < 600:
        return _isp_cache["data"]
    data = None
    for url in ("https://ifconfig.co/json", "https://ipinfo.io/json"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NETKIT/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                j = json.load(r)
            data = {
                "ip": j.get("ip"),
                "isp": j.get("asn_org") or j.get("org"),
                "asn": j.get("asn"),
                "city": j.get("city"),
                "country": j.get("country"),
                "timezone": j.get("time_zone") or j.get("timezone"),
                "source": url.split("/")[2],
            }
            break
        except Exception:
            continue
    if data:
        _isp_cache.update(ts=time.time(), data=data)
    return data or {"error": "ISP lookup unreachable"}


def run_speedtest():
    """Apple networkQuality, sequential mode for true per-direction numbers."""
    out = subprocess.run([NETQUALITY, "-s", "-c"], capture_output=True, timeout=180)
    j = json.loads(out.stdout)
    rec = {
        "ts": int(time.time()),
        "down_mbps": round(j.get("dl_throughput", 0) / 1e6, 1),
        "up_mbps": round(j.get("ul_throughput", 0) / 1e6, 1),
        "rtt_ms": round(j.get("base_rtt", 0)),
        "dl_rpm": round(j.get("dl_responsiveness", 0)),
        "ul_rpm": round(j.get("ul_responsiveness", 0)),
        "endpoint": "Apple CDN (mensura.cdn-apple.com)",
    }
    with open(SPEED_HISTORY, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def _read_jsonl(path, n):
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    return [json.loads(x) for x in lines[-n:]][::-1]


def ip_watch():
    """Log public IP changes; Vodafone rotates DHCP leases, this catches it."""
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
        time.sleep(601)  # one tick past the ISP cache TTL


def speed_history(n=10):
    if not SPEED_HISTORY.exists():
        return []
    lines = SPEED_HISTORY.read_text().strip().splitlines()
    return [json.loads(x) for x in lines[-n:]][::-1]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/speedtest":
            if not _speed_lock.acquire(blocking=False):
                self._send(409, "application/json",
                           json.dumps({"error": "test already running"}).encode())
                return
            try:
                rec = run_speedtest()
                self._send(200, "application/json", json.dumps(rec).encode())
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
                out = subprocess.run(["/usr/sbin/netstat", "-ibn"],
                                     capture_output=True, timeout=10
                                     ).stdout.decode()
                rx = tx = 0
                for ln in out.splitlines():
                    f = ln.split()
                    if len(f) >= 10 and f[0] == "en0" and f[2].startswith("<Link#"):
                        rx, tx = int(f[6]), int(f[9])
                        break
                self._send(200, "application/json",
                           json.dumps({"ts": time.time(), "rx": rx, "tx": tx}).encode())
            elif self.path == "/api/isp":
                self._send(200, "application/json", json.dumps(get_isp()).encode())
            elif self.path == "/api/speedtest/history":
                self._send(200, "application/json",
                           json.dumps(speed_history()).encode())
            elif self.path == "/api/ip/history":
                self._send(200, "application/json",
                           json.dumps(_read_jsonl(IP_HISTORY, 10)).encode())
            elif self.path.startswith("/api/live"):
                out = subprocess.run([NETTOP, "-n", "-x", "-L", "1"],
                                     capture_output=True, timeout=25)
                body = json.dumps(parse_nettop(out.stdout.decode("utf-8", "replace")))
                self._send(200, "application/json", body.encode())
            elif self.path.startswith("/api"):
                out = subprocess.run([VNSTAT, "--json"],
                                     capture_output=True, timeout=15).stdout
                json.loads(out)  # refuse to forward malformed output
                self._send(200, "application/json", out)
            elif self.path == "/logo.png":
                self._send(200, "image/png", LOGO.read_bytes())
            elif self.path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8",
                           (ROOT / "index.html").read_bytes())
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


if __name__ == "__main__":
    threading.Thread(target=ip_watch, daemon=True).start()
    print(f"NET KIT on http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

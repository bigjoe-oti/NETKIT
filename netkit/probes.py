"""Platform abstraction for NET KIT.

Every OS-specific data source lives here behind a uniform interface. macOS is
the fully-implemented and verified path. Linux and Windows are implemented on a
best-effort, stdlib-only basis and degrade gracefully to {"unavailable": ...}
rather than crashing when a tool or permission is missing.

Public surface (all platform-dispatched):
  default_iface()        -> str | None
  iface_counters()       -> (name, rx_bytes, tx_bytes) | None   # cumulative
  live_connections()     -> {"apps": [...], "ports": [...]} (may be empty)
  run_speedtest()        -> dict   (raises RuntimeError if no engine)
  vnstat_json()          -> dict | None   (None if vnstat absent)
"""
import json
import platform
import re
import shutil
import subprocess
import time

SYS = platform.system()  # 'Darwin' | 'Linux' | 'Windows'

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
    for p in (remote, local):
        if p and (p in WELL_KNOWN or p < 1024):
            return p
    return remote or local


def _run(cmd, timeout=15):
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def _which(name):
    return shutil.which(name)


# ───────────────────────── default interface ─────────────────────────

def default_iface():
    try:
        if SYS == "Darwin":
            out = _run(["route", "-n", "get", "default"], 5).stdout.decode()
            m = re.search(r"interface:\s*(\S+)", out)
            return m.group(1) if m else "en0"
        if SYS == "Linux":
            # /proc/net/route: the row whose destination is 00000000 is the default
            with open("/proc/net/route") as f:
                next(f)
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "00000000":
                        return parts[0]
            return None
        if SYS == "Windows":
            ps = ("Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
                  "Sort-Object RouteMetric | Select-Object -First 1 -ExpandProperty ifIndex")
            idx = _run(["powershell", "-NoProfile", "-Command", ps], 10).stdout.decode().strip()
            if idx:
                name = _run(["powershell", "-NoProfile", "-Command",
                             f"(Get-NetAdapter -InterfaceIndex {idx}).Name"], 10).stdout.decode().strip()
                return name or None
    except Exception:
        return None
    return None


# ───────────────────────── interface counters ─────────────────────────

def iface_counters():
    """Return (iface_name, rx_bytes, tx_bytes) cumulative since boot, or None."""
    name = default_iface()
    try:
        if SYS == "Darwin":
            out = _run(["/usr/sbin/netstat", "-ibn"], 10).stdout.decode()
            for ln in out.splitlines():
                f = ln.split()
                if len(f) >= 10 and f[0] == name and f[2].startswith("<Link#"):
                    return (name, int(f[6]), int(f[9]))
            return None
        if SYS == "Linux":
            with open("/proc/net/dev") as fh:
                for ln in fh:
                    if ":" not in ln:
                        continue
                    dev, _, rest = ln.partition(":")
                    dev = dev.strip()
                    if name and dev != name:
                        continue
                    cols = rest.split()
                    # rx bytes = col 0, tx bytes = col 8
                    return (dev, int(cols[0]), int(cols[8]))
            return None
        if SYS == "Windows":
            ps = ("Get-NetAdapterStatistics | Where-Object {$_.ReceivedBytes -gt 0} | "
                  "Sort-Object ReceivedBytes -Descending | Select-Object -First 1 "
                  "Name,ReceivedBytes,SentBytes | ConvertTo-Json -Compress")
            out = _run(["powershell", "-NoProfile", "-Command", ps], 12).stdout.decode().strip()
            if out:
                j = json.loads(out)
                return (j.get("Name", name or "net"),
                        int(j.get("ReceivedBytes", 0)), int(j.get("SentBytes", 0)))
            return None
    except Exception:
        return None
    return None


# ───────────────────────── live connections (apps + ports) ─────────────────────────

def _resolve_pid_names(pids):
    if not pids:
        return {}
    try:
        out = subprocess.run(["ps", "-o", "pid=,comm=", "-p", ",".join(pids)],
                             capture_output=True, timeout=5, text=True).stdout
    except Exception:
        return {}
    names = {}
    for ln in out.splitlines():
        parts = ln.strip().split(None, 1)
        if len(parts) == 2:
            names[parts[0]] = parts[1].rsplit("/", 1)[-1]
    return names


def _parse_nettop(raw):
    procs, ports = [], {}
    for line in raw.splitlines()[1:]:
        f = line.split(",")
        if len(f) < 6:
            continue
        name, bi, bo = f[1], f[4], f[5]
        if "<->" in name:
            if not (bi or bo):
                continue
            rx, tx = int(bi or 0), int(bo or 0)
            if rx == 0 and tx == 0:
                continue
            proto_field, _, conn = name.partition(" ")
            proto = "udp" if proto_field.startswith("udp") else "tcp"
            local, _, remote = conn.partition("<->")
            p = _service_port(_port_of(local), _port_of(remote))
            if p is None:
                continue
            e = ports.setdefault((p, proto), {"port": p, "proto": proto,
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

    resolved = _resolve_pid_names(sorted({p[0] for p in procs if p[0]}))
    apps = {}
    for pid, fallback, rx, tx in procs:
        pname = resolved.get(pid, fallback)
        e = apps.setdefault(pname, {"name": pname, "rx": 0, "tx": 0, "procs": 0})
        e["rx"] += rx
        e["tx"] += tx
        e["procs"] += 1
    merged = {}
    for pname in sorted(apps, key=len):
        target = next((t for t in merged if len(t) >= 8 and pname.startswith(t)), None)
        if target:
            for k in ("rx", "tx", "procs"):
                merged[target][k] += apps[pname][k]
        else:
            merged[pname] = apps[pname]
    tot = lambda e: e["rx"] + e["tx"]
    return {"apps": sorted(merged.values(), key=tot, reverse=True),
            "ports": sorted(ports.values(), key=tot, reverse=True)}


def _linux_connections():
    """ss gives connection + owning process, but not bytes. We report connection
    counts per service and per app — bytes are not available without root/conntrack."""
    if not _which("ss"):
        return {"apps": [], "ports": [],
                "note": "install iproute2 (ss) for the live connection view"}
    out = _run(["ss", "-tunp"], 10).stdout.decode(errors="replace")
    ports, apps = {}, {}
    for ln in out.splitlines()[1:]:
        cols = ln.split()
        if len(cols) < 5:
            continue
        local, peer = cols[-3], cols[-2] if len(cols) >= 6 else cols[-1]
        p = _service_port(_port_of(local), _port_of(peer))
        if p:
            e = ports.setdefault((p, "tcp"), {"port": p, "proto": "tcp",
                                              "service": WELL_KNOWN.get(p),
                                              "rx": 0, "tx": 0, "conns": 0})
            e["conns"] += 1
        m = re.search(r'\(\("([^"]+)"', ln)
        if m:
            a = apps.setdefault(m.group(1), {"name": m.group(1), "rx": 0, "tx": 0, "procs": 0})
            a["procs"] += 1
    return {"apps": sorted(apps.values(), key=lambda e: e["procs"], reverse=True),
            "ports": sorted(ports.values(), key=lambda e: e["conns"], reverse=True),
            "note": "connection counts only; per-app byte totals need root on Linux"}


def _windows_connections():
    ps = ("Get-NetTCPConnection -State Established | "
          "Group-Object -Property RemotePort | "
          "Select-Object Name,Count | ConvertTo-Json -Compress")
    try:
        out = _run(["powershell", "-NoProfile", "-Command", ps], 12).stdout.decode().strip()
        rows = json.loads(out) if out else []
        if isinstance(rows, dict):
            rows = [rows]
        ports = []
        for r in rows:
            p = int(r.get("Name", 0))
            ports.append({"port": p, "proto": "tcp", "service": WELL_KNOWN.get(p),
                          "rx": 0, "tx": 0, "conns": int(r.get("Count", 0))})
        ports.sort(key=lambda e: e["conns"], reverse=True)
        return {"apps": [], "ports": ports,
                "note": "connection counts only on Windows; per-app bytes need a driver"}
    except Exception:
        return {"apps": [], "ports": [], "note": "live view unavailable"}


def live_connections():
    try:
        if SYS == "Darwin":
            out = _run(["/usr/bin/nettop", "-n", "-x", "-L", "1"], 25)
            return _parse_nettop(out.stdout.decode("utf-8", "replace"))
        if SYS == "Linux":
            return _linux_connections()
        if SYS == "Windows":
            return _windows_connections()
    except Exception as e:
        return {"apps": [], "ports": [], "note": f"live view error: {e}"}
    return {"apps": [], "ports": [], "note": "unsupported platform"}


# ───────────────────────── speed test ─────────────────────────

def run_speedtest():
    """Returns a normalized speed record. macOS uses Apple networkQuality;
    other platforms use an installed Ookla/sivel speedtest CLI if present."""
    if SYS == "Darwin" and _which("networkQuality"):
        out = _run(["networkQuality", "-s", "-c"], 180).stdout
        j = json.loads(out)
        return {"ts": int(time.time()),
                "down_mbps": round(j.get("dl_throughput", 0) / 1e6, 1),
                "up_mbps": round(j.get("ul_throughput", 0) / 1e6, 1),
                "rtt_ms": round(j.get("base_rtt", 0)),
                "dl_rpm": round(j.get("dl_responsiveness", 0)),
                "ul_rpm": round(j.get("ul_responsiveness", 0)),
                "endpoint": "Apple CDN (mensura.cdn-apple.com)"}
    # Ookla official CLI: `speedtest --format=json`
    if _which("speedtest"):
        out = _run(["speedtest", "--format=json", "--accept-license", "--accept-gdpr"], 120).stdout
        j = json.loads(out)
        dl = j.get("download", {}).get("bandwidth", 0) * 8 / 1e6
        ul = j.get("upload", {}).get("bandwidth", 0) * 8 / 1e6
        return {"ts": int(time.time()), "down_mbps": round(dl, 1), "up_mbps": round(ul, 1),
                "rtt_ms": round(j.get("ping", {}).get("latency", 0)),
                "dl_rpm": 0, "ul_rpm": 0,
                "endpoint": j.get("server", {}).get("name", "Ookla server")}
    # sivel speedtest-cli: `speedtest-cli --json`
    if _which("speedtest-cli"):
        out = _run(["speedtest-cli", "--json"], 120).stdout
        j = json.loads(out)
        return {"ts": int(time.time()),
                "down_mbps": round(j.get("download", 0) / 1e6, 1),
                "up_mbps": round(j.get("upload", 0) / 1e6, 1),
                "rtt_ms": round(j.get("ping", 0)), "dl_rpm": 0, "ul_rpm": 0,
                "endpoint": j.get("server", {}).get("sponsor", "speedtest.net")}
    raise RuntimeError(
        "no speed-test engine found. macOS ships networkQuality; on Linux/Windows "
        "install the Ookla 'speedtest' CLI or 'speedtest-cli'.")


# ───────────────────────── vnStat ledger (mac/linux when present) ─────────────────────────

def vnstat_json():
    exe = _which("vnstat") or "/usr/local/bin/vnstat"
    if not shutil.which(exe) and not _which("vnstat"):
        return None
    try:
        out = _run([exe if shutil.which(exe) else "vnstat", "--json"], 15).stdout
        data = json.loads(out)
        return data
    except Exception:
        return None

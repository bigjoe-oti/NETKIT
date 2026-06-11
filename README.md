# NET KIT

**Daily Internet Usage Tracker** · NETKIT belongs to [J. Servo LLC](https://jservo.com) Smart Tech Stack

A zero-dependency, cross-platform dashboard for measuring and tracking internet usage. One Python package (stdlib only), one HTML file, no `node_modules`, no build step beyond a single `zipapp`. Builds to a single runnable executable (`netkit.pyz`) or installs as a `netkit` command.

## What it does

- **Persistent daily ledger** — hourly, daily, and monthly usage history that survives reboots. Uses [vnStat](https://github.com/vergoh/vnstat) when present, otherwise a **built-in SQLite poller** so the core feature works on every OS.
- **Speed test with a live RPM-style gauge** — Apple `networkQuality` on macOS, the Ookla `speedtest` CLI or `speedtest-cli` elsewhere; an SVG dial driven by real interface counters polled twice a second.
- **ISP identity panel** — public IP, ISP (with brand colors), ASN, location, plus a public-IP change log that catches DHCP lease rotations.
- **Live panels** — per-application and per-port/protocol consumption.
- **Menu bar readout** (macOS) — today's totals via a [SwiftBar](https://github.com/swiftbar/SwiftBar) plugin.

## Platform support

| Feature | macOS | Linux | Windows |
|---|---|---|---|
| Dashboard + daily ledger (built-in SQLite) | ✅ verified | ✅ implemented | ✅ implemented |
| vnStat ledger (preferred when installed) | ✅ | ✅ | n/a |
| Interface-rate gauge | ✅ `netstat` | ✅ `/proc/net/dev` | ✅ PowerShell |
| Speed test | ✅ `networkQuality` | ⚙️ Ookla CLI | ⚙️ Ookla CLI |
| Live apps / ports | ✅ `nettop` | ⚙️ `ss` (conn counts) | ⚙️ PowerShell (conn counts) |
| ISP panel + IP log | ✅ | ✅ | ✅ |
| Menu bar | ✅ SwiftBar | — | — |

✅ verified on a real host · ⚙️ implemented, depends on the named tool being installed; degrades gracefully if absent. macOS is the reference platform; Linux/Windows paths are implemented stdlib-only and validated in CI (import + boot), but per-OS field testing is ongoing.

## Install & run

**Run from source:**
```sh
git clone https://github.com/bigjoe-oti/NETKIT.git
cd NETKIT
python3 -m netkit            # open http://127.0.0.1:8787
```

**Single-file executable** (no install — runs anywhere with Python 3.9+):
```sh
make build                  # produces dist/netkit.pyz
./dist/netkit.pyz           # or: python3 dist/netkit.pyz
```
Pre-built `netkit.pyz` is also attached to each [GitHub release](https://github.com/bigjoe-oti/NETKIT/releases).

**As a command** (`pipx`):
```sh
make install                # pipx install . → `netkit` on your PATH
netkit
```

**Optional daily ledger engine** (richer history; recommended on macOS/Linux):
```sh
brew install vnstat && brew services start vnstat   # macOS
sudo apt install vnstat && sudo systemctl enable --now vnstat   # Debian/Ubuntu
```
Without vnStat, NET KIT's built-in SQLite ledger takes over automatically.

## Run at startup

- **macOS:** edit the path in `packaging/com.jservo.netkit.plist`, then `make service-mac`.
- **Linux:** edit `packaging/netkit.service`, then `make service-linux` (systemd `--user`).
- **Windows:** register `python -m netkit` (or `netkit.pyz`) with Task Scheduler at logon; use `pythonw` to run without a console window.

## Configuration (env)

| Var | Default | Purpose |
|---|---|---|
| `NETKIT_HOST` | `127.0.0.1` | bind address (loopback only by default) |
| `NETKIT_PORT` | `8787` | dashboard port |
| `NETKIT_DATA` | `~/.netkit` | where the SQLite ledger and telemetry live |

## Documentation

- [Architecture](docs/ARCHITECTURE.md) · [HTTP API](docs/API.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

## Notes

- Usage history accrues from first run; give it a week to get interesting.
- Live app/port panels show counters since each process/connection started; the daily ledger is the persistent truth.
- Telemetry (`speedtests.jsonl`, `ip_history.jsonl`, `netkit.db`) lives in `~/.netkit` and is never committed — it contains your public IP and line history.

---

© 2026 J. Servo LLC · Dashboard binds to `127.0.0.1` only.

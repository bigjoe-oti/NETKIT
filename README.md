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

## Quick start

The fastest path on any OS: download `netkit.pyz` from the [latest release](https://github.com/bigjoe-oti/NETKIT/releases/latest) and run it with Python, then open **http://127.0.0.1:8787** in your browser. Per-OS detail below.

Requirement everywhere: **Python 3.9 or newer** (`python3 --version`). NET KIT has no other dependencies.

---

### 🍎 macOS

**1. Check Python** (macOS ships it; if missing, `brew install python` or get it from [python.org](https://www.python.org/downloads/)):
```sh
python3 --version
```

**2. Install and run** — pick one:

```sh
# A) One-file executable (simplest)
curl -L -o netkit.pyz https://github.com/bigjoe-oti/NETKIT/releases/latest/download/netkit.pyz
python3 netkit.pyz

# B) As a command on your PATH
git clone https://github.com/bigjoe-oti/NETKIT.git && cd NETKIT
make install        # pipx install . → `netkit`
netkit

# C) From source, no install
git clone https://github.com/bigjoe-oti/NETKIT.git && cd NETKIT
python3 -m netkit
```

**3. (Recommended) richer daily history with vnStat:**
```sh
brew install vnstat && brew services start vnstat
```
Without it, NET KIT's built-in ledger tracks daily usage on its own.

**4. (Optional) menu-bar readout** via [SwiftBar](https://github.com/swiftbar/SwiftBar):
```sh
brew install --cask swiftbar
```
Point SwiftBar's plugin folder at `swiftbar-plugins/`, then enable **Launch at Login** in its preferences.

**5. (Optional) run at login** — keeps the dashboard always available:
```sh
# edit WorkingDirectory in packaging/com.jservo.netkit.plist to your clone path, then:
make service-mac
```

---

### 🐧 Linux

**1. Check Python** (install if needed):
```sh
python3 --version
# Debian/Ubuntu:  sudo apt install python3
# Fedora:         sudo dnf install python3
# Arch:           sudo pacman -S python
```

**2. Install and run** — pick one:

```sh
# A) One-file executable (simplest)
curl -L -o netkit.pyz https://github.com/bigjoe-oti/NETKIT/releases/latest/download/netkit.pyz
python3 netkit.pyz

# B) As a command
git clone https://github.com/bigjoe-oti/NETKIT.git && cd NETKIT
make install        # pipx install . → `netkit`   (pipx: sudo apt install pipx)
netkit

# C) From source
git clone https://github.com/bigjoe-oti/NETKIT.git && cd NETKIT
python3 -m netkit
```

**3. (Recommended) daily history with vnStat:**
```sh
sudo apt install vnstat && sudo systemctl enable --now vnstat   # Debian/Ubuntu
```

**4. (For the live apps/ports panel)** ensure `ss` is present — it usually is via `iproute2`:
```sh
sudo apt install iproute2
```

**5. (Optional) speed test** needs the Ookla CLI or `speedtest-cli`:
```sh
sudo apt install speedtest-cli        # or install the official Ookla `speedtest`
```

**6. (Optional) run at login** as a systemd user service:
```sh
# edit WorkingDirectory in packaging/netkit.service to your clone path, then:
make service-linux
```

---

### 🪟 Windows

**1. Install Python** from [python.org](https://www.python.org/downloads/) — during setup, tick **“Add python.exe to PATH.”** Verify in PowerShell:
```powershell
python --version
```

**2. Install and run** — pick one (run in PowerShell):

```powershell
# A) One-file executable (simplest)
curl.exe -L -o netkit.pyz https://github.com/bigjoe-oti/NETKIT/releases/latest/download/netkit.pyz
python netkit.pyz

# B) From source
git clone https://github.com/bigjoe-oti/NETKIT.git
cd NETKIT
python -m netkit

# C) As a command
pip install pipx
pipx install .
netkit
```
Then open **http://127.0.0.1:8787**.

**3. (Optional) speed test** needs the [Ookla `speedtest` CLI](https://www.speedtest.net/apps/cli) (or `pip install speedtest-cli`). Without it, every other panel still works; the speed-test button reports that no engine is installed.

> **Note:** vnStat and SwiftBar do not exist on Windows. NET KIT automatically uses its **built-in SQLite ledger** for daily history, and the live apps/ports panel uses PowerShell (connection counts). Everything else works the same.

**4. (Optional) run at login** with Task Scheduler:
- Open **Task Scheduler → Create Task**.
- Trigger: **At log on**.
- Action: **Start a program** → `pythonw` → arguments `-m netkit` (or point it at `netkit.pyz`). Using `pythonw` runs it silently with no console window.
- Save. NET KIT now starts with Windows.

---

### Build the executable yourself (any OS)

```sh
make build          # produces dist/netkit.pyz
# or directly:
python3 -m zipapp netkit -m "netkit.server:main" -p "/usr/bin/env python3" -o netkit.pyz
```

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

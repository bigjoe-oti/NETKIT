# NET KIT

**Daily Internet Usage Tracker** · NETKIT belongs to [J. Servo LLC](https://jservo.com) Smart Tech Stack

A zero-framework macOS dashboard for measuring and tracking internet usage. One Python file (stdlib only), one HTML file, no node_modules, no build step.

## What it does

- **Persistent daily ledger** — hourly, daily, and monthly usage history that survives reboots, powered by [vnStat](https://github.com/vergoh/vnstat)
- **Speed test with a live RPM-style gauge** — Apple's built-in `networkQuality` engine, with an SVG dial driven by real interface counters polled twice a second (auto-rescaling, phase-aware colors)
- **ISP identity panel** — public IP, ISP (with brand colors), ASN, location, plus a public-IP change log that catches DHCP lease rotations
- **Live panels** — per-application and per-port/protocol consumption via macOS `nettop`, with PID-resolved process names
- **Menu bar readout** — today's down/up totals via a [SwiftBar](https://github.com/swiftbar/SwiftBar) plugin, refreshed every 5 minutes

## Requirements

macOS 12+, [Homebrew](https://brew.sh), Python 3 (ships with Xcode CLT). SwiftBar optional for the menu bar readout.

## Install

```sh
# 1. The data engine
brew install vnstat
brew services start vnstat

# 2. NET KIT - clone OUTSIDE ~/Desktop/~/Documents (launchd agents are TCC-denied there)
git clone https://github.com/bigjoe-oti/NETKIT.git ~/netkit
python3 ~/netkit/server.py
# open http://127.0.0.1:8787
```

To run permanently (start at login, restart on crash), edit the paths in `com.jservo.netdash.plist`, then:

```sh
cp com.jservo.netdash.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jservo.netdash.plist
```

For the menu bar readout: `brew install --cask swiftbar`, point its plugin folder at `swiftbar-plugins/`.

## Notes

- Usage history accrues from the day vnStat starts; give it a week to get interesting.
- The live app/port panels show counters since each process or connection started (macOS `nettop` semantics); the daily ledger above them is the persistent truth.
- Speed tests run against Apple's CDN (`mensura.cdn-apple.com`) and append to a local `speedtests.jsonl` (gitignored, as is the IP change log — that's your personal telemetry).

---

© 2026 J. Servo LLC · Dashboard served on `127.0.0.1` only.

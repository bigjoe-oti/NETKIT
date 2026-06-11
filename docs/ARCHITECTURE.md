# NET KIT Architecture

NET KIT is deliberately boring infrastructure: one stdlib-only Python server, one self-contained HTML file, and three macOS-native data engines it orchestrates. No frameworks, no build step, no database of its own.

```
┌────────────────────────────────────────────────────────┐
│  Browser  http://127.0.0.1:8787                        │
│  index.html (Tailwind CDN + vanilla JS + SVG)          │
└──────────────┬─────────────────────────────────────────┘
               │ fetch, 60 s cycle (500 ms during speed test)
┌──────────────▼─────────────────────────────────────────┐
│  server.py  ThreadingHTTPServer, stdlib only           │
│  + ip_watch daemon thread (10 min)                     │
└──┬────────┬───────────┬────────────┬───────────────────┘
   │        │           │            │
   ▼        ▼           ▼            ▼
 vnstat   nettop   networkQuality  netstat        (subprocess)
 daily    per-app  speed test      live interface
 ledger   per-port (Apple CDN)     counters
   │
   ▼
 vnStat DB (persistent, 5-min ticks, survives reboot)
```

## Components

### server.py
- `ThreadingHTTPServer` bound to `127.0.0.1:8787` — never exposed to the network.
- Every endpoint shells out to a macOS-native tool, parses, returns JSON. No state in the server except two small caches.
- A daemon thread (`ip_watch`) polls the public IP every ~10 minutes and appends changes to `ip_history.jsonl`.
- Speed tests are serialized with a non-blocking lock: a second concurrent request gets `409`.

### Data engines
| Engine | Source of truth for | Persistence |
|---|---|---|
| `vnstat` (Homebrew) | Hourly/daily/monthly ledger | Its own DB, survives reboots |
| `nettop` (macOS) | Per-app and per-port live counters | None — counts since process/connection start |
| `networkQuality` (macOS) | Speed tests | NET KIT appends results to `speedtests.jsonl` |
| `netstat -ibn` (macOS) | Live interface byte counters | None — drives the speed-test gauge needle |
| ifconfig.co / ipinfo.io | Public IP + ISP identity | NET KIT appends IP changes to `ip_history.jsonl` |

### index.html
Single file: styles, markup, and logic together. Key pieces:
- `chart()` — renders the axis/gridline/capsule-bar charts from vnStat JSON.
- `gaugeBuild()/gaugeSet()` — the 240° RPM-style dial. SVG gradients (`<linearGradient>`) because SVG strokes cannot take CSS gradients. Auto-rescales 250 → 500 → 1000 Mbit/s so the needle never pegs.
- During a speed test the UI polls `/api/ifstats` every 500 ms and differentiates byte counters into Mbit/s — the needle shows *real* throughput, not an animation.

## Design decisions worth knowing

1. **Why not run everything from `~/Desktop`?** launchd agents are TCC-denied on Desktop/Documents/Downloads. The repo must live outside those (e.g. `~/netkit`), or the LaunchAgent spawn-loops with `Operation not permitted`.
2. **Why `nettop` names get post-processed:** nettop truncates process names (~15 chars) and sometimes mangles them entirely (a `claude` CLI process once surfaced as `2.1.172`). `server.py` resolves every PID through `ps -o pid=,comm=` and folds helper processes ("Google Chrome Helper") into their parents.
3. **Why two truth systems:** the live panels (nettop) count since each process started and reset on quit/reboot — operational data. The ledger (vnStat) is the persistent daily truth. The UI states this distinction explicitly rather than letting users conflate them.
4. **Why the ISP lookup has a fallback chain:** from at least one Egyptian network, ip-api.com and ipinfo.io silently time out while ifconfig.co works. Order: ifconfig.co → ipinfo.io, cached 10 minutes.
5. **Telemetry stays local:** `speedtests.jsonl` and `ip_history.jsonl` are gitignored — they contain the owner's public IP and line history.

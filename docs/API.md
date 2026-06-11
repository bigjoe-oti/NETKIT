# NET KIT HTTP API

Everything is served from `http://127.0.0.1:8787`. All responses are JSON unless noted. No authentication — the server binds to loopback only.

## GET /

The dashboard (`index.html`). `GET /logo.png` serves the wordmark image.

## GET /api

Raw passthrough of `vnstat --json` — the full ledger for every interface: `fiveminute`, `hour`, `day`, `month`, `year`, and `top` arrays plus lifetime totals. The server validates the JSON before forwarding; malformed vnstat output returns `500`.

The interface that matters on a MacBook is `en0` (Wi-Fi). Sizes are bytes.

## GET /api/live

Parsed `nettop -n -x -L 1` snapshot:

```json
{
  "apps":  [ {"name": "Google Chrome", "rx": 12895432, "tx": 832212, "procs": 3} ],
  "ports": [ {"port": 443, "proto": "tcp", "service": "HTTPS",
              "rx": 18400000, "tx": 18600000, "conns": 25} ]
}
```

- `apps` — per-process totals, PID-resolved real names, helpers folded into parents, sorted by volume.
- `ports` — aggregated by the *service* port (the well-known side of each connection, not the ephemeral side), ~30 named services (HTTPS, DNS, SMTP, FTP, DHCP, mDNS, Apple Push, …). QUIC shows up as `443/udp`.
- Counters run since each process/connection started. This is a live view, not a ledger.

## GET /api/ifstats

Instantaneous `en0` interface byte counters from `netstat -ibn`:

```json
{"ts": 1781132896.84, "rx": 129367688459, "tx": 16635877947}
```

Poll twice, divide the deltas by the time difference, and you have live throughput. This is what drives the speed-test gauge at 500 ms resolution. Counters are since-boot and monotonic (reset on reboot).

## GET /api/isp

Public IP and ISP identity, cached 10 minutes:

```json
{"ip": "196.137.34.10", "isp": "Vodafone-EG", "asn": "AS36935",
 "city": null, "country": "Egypt", "timezone": "Africa/Cairo",
 "source": "ifconfig.co"}
```

Lookup chain: ifconfig.co → ipinfo.io. Returns `{"error": ...}` if both fail.

## GET /api/ip/history

Last 10 public-IP changes (newest first), maintained by the server's watcher thread independent of any open browser:

```json
[{"ts": 1781131882, "ip": "196.137.34.10", "isp": "Vodafone-EG", "asn": "AS36935"}]
```

## POST /api/speedtest

Runs Apple `networkQuality -s -c` (sequential mode — true per-direction numbers). Takes ~60 s. Result is appended to `speedtests.jsonl` and returned:

```json
{"ts": 1781131058, "down_mbps": 168.1, "up_mbps": 43.4, "rtt_ms": 108,
 "dl_rpm": 219, "ul_rpm": 45, "endpoint": "Apple CDN (mensura.cdn-apple.com)"}
```

`*_rpm` is Apple's responsiveness metric (round-trips per minute under load — higher is better). Concurrent requests get `409 {"error": "test already running"}`.

## GET /api/speedtest/history

Last 10 speed test records, newest first.

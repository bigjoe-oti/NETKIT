# NET KIT Troubleshooting

Every entry here is a problem that actually occurred during development, with the real fix.

## LaunchAgent spawn-loops: `can't open file ... Operation not permitted`

**Cause:** the repo lives in `~/Desktop`, `~/Documents`, or `~/Downloads`. macOS privacy protection (TCC) denies launchd-spawned processes access to those folders — even though running `python3 server.py` manually from a terminal works fine (the terminal has its own grant).

**Fix:** move the folder outside TCC scope (e.g. `~/netkit`), update the path in the plist, then:

```sh
launchctl bootout gui/$(id -u)/com.jservo.netdash 2>/dev/null
cp com.jservo.netdash.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jservo.netdash.plist
```

## Dashboard shows zeros / "Database is fresh" banner

vnStat writes to its database every 5 minutes. A newly installed daemon has nothing to show for up to 5 minutes, and the daily/monthly charts only get interesting after days of uptime. Check the daemon is alive:

```sh
brew services info vnstat     # should say Running: true
vnstat -d                     # daily table directly
```

## Port 8787 already in use

```sh
lsof -ti :8787 | xargs kill   # kill whatever holds it (e.g. a manual nohup instance)
launchctl kickstart -k gui/$(id -u)/com.jservo.netdash
```

Two instances can't bind the same port; the LaunchAgent should be the only owner.

## ISP panel says "lookup failed"

Some networks (observed on Vodafone Egypt) silently drop ip-api.com and ipinfo.io while ifconfig.co works — NET KIT already tries ifconfig.co first. If all sources fail you're likely behind a captive portal or a very aggressive firewall. The panel recovers on the next 10-minute cycle.

## Apps panel shows garbled names like `2.1.172`

Shouldn't happen anymore — nettop truncates and sometimes mangles process names, so the server resolves every PID via `ps`. If a process died between the nettop sample and the ps call, the mangled fallback name can briefly appear. It self-corrects on the next refresh.

## Speed test fails or hangs

- `networkQuality` needs macOS 12+.
- The server enforces a 180 s timeout and one-test-at-a-time (`409` on concurrent runs).
- The test saturates the link for ~1 minute — other panels spiking during it is the test itself, not a bug.

## SwiftBar shows nothing in the menu bar

1. `brew install --cask swiftbar` and launch it once.
2. Point its plugin directory at `swiftbar-plugins/` (or `defaults write com.ameba.SwiftBar PluginDirectory -string "<path>"` before first launch).
3. The plugin must be executable: `chmod +x swiftbar-plugins/netdash.5m.sh`.
4. Enable Launch at Login in SwiftBar's preferences to survive reboots.

## Logs

The server (under launchd) writes stdout/stderr to `/tmp/netdash.log`. Python block-buffers prints, so the startup line may not appear immediately — judge health by `launchctl print gui/$(id -u)/com.jservo.netdash | grep state` and an HTTP 200 from the dashboard, not by the log alone.

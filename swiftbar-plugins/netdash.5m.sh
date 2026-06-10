#!/bin/bash
# NET KIT menu bar readout - today's usage from vnStat. Belongs to J. Servo LLC Smart Tech Stack.
/usr/bin/python3 - << 'PY'
import json, subprocess

def f(b):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.0f}{u}" if u == "B" else f"{b:.1f}{u}"
        b /= 1024

try:
    out = subprocess.run(
        ["/usr/local/bin/vnstat", "-i", "en0", "--json", "d", "1"],
        capture_output=True, timeout=10).stdout
    day = json.loads(out)["interfaces"][0]["traffic"]["day"][-1]
    rx, tx = day["rx"], day["tx"]
except Exception:
    print("net: off")
    print("---")
    print("vnStat unreachable | color=red")
    raise SystemExit

print(f"⇣{f(rx)} ⇡{f(tx)}")
print("---")
print(f"Today on en0: {f(rx + tx)} total")
print(f"Down {f(rx)} · Up {f(tx)}")
print("Open NET KIT | href=http://127.0.0.1:8787")
print("J. Servo LLC | href=https://jservo.com")
PY

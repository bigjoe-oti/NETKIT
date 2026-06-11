"""Built-in cross-platform usage ledger (stdlib sqlite3).

This is the universal fallback for platforms where vnStat is unavailable
(notably Windows, or Linux/macOS without it installed). A background thread
samples cumulative interface counters on an interval and stores them; queries
differentiate consecutive samples into positive deltas and bucket them by
hour / day / month, emitting the SAME JSON shape the vnStat path produces so
the dashboard is identical regardless of source.

Counter resets (reboots, interface flap) appear as negative deltas and are
clamped to zero, so a reboot never injects a phantom spike.
"""
import sqlite3
import threading
import time
from datetime import datetime


class BuiltinLedger:
    def __init__(self, db_path, iface_fn, interval=60):
        self.db_path = str(db_path)
        self.iface_fn = iface_fn      # () -> (name, rx_abs, tx_abs) | None
        self.interval = interval
        self._init_db()

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=10)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init_db(self):
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS samples("
                      "ts INTEGER NOT NULL, iface TEXT NOT NULL, "
                      "rx INTEGER NOT NULL, tx INTEGER NOT NULL)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_samples ON samples(iface, ts)")

    def sample_once(self):
        cur = self.iface_fn()
        if not cur:
            return
        name, rx, tx = cur
        now = int(time.time())
        with self._conn() as c:
            c.execute("INSERT INTO samples VALUES (?,?,?,?)", (now, name, rx, tx))
            c.execute("DELETE FROM samples WHERE ts < ?", (now - 400 * 86400,))

    def run(self):
        while True:
            try:
                self.sample_once()
            except Exception:
                pass
            time.sleep(self.interval)

    # ── query → vnstat-compatible JSON ──────────────────────────────

    def _deltas(self, iface):
        """Yield (ts, drx, dtx) positive deltas between consecutive samples."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT ts, rx, tx FROM samples WHERE iface=? ORDER BY ts", (iface,)
            ).fetchall()
        for (t0, rx0, tx0), (t1, rx1, tx1) in zip(rows, rows[1:]):
            drx, dtx = rx1 - rx0, tx1 - tx0
            if drx < 0 or dtx < 0:      # counter reset → skip the straddling interval
                continue
            yield t1, drx, dtx

    def _ifaces(self):
        with self._conn() as c:
            return [r[0] for r in c.execute(
                "SELECT DISTINCT iface FROM samples").fetchall()]

    def to_vnstat_json(self):
        interfaces = []
        for iface in self._ifaces():
            hour, day, month, five = {}, {}, {}, []
            total_rx = total_tx = 0
            for ts, drx, dtx in self._deltas(iface):
                total_rx += drx
                total_tx += dtx
                dt = datetime.fromtimestamp(ts)
                dk = (dt.year, dt.month, dt.day)
                hk = (dt.year, dt.month, dt.day, dt.hour)
                mk = (dt.year, dt.month)
                for bucket, key in ((day, dk), (hour, hk), (month, mk)):
                    b = bucket.setdefault(key, [0, 0])
                    b[0] += drx
                    b[1] += dtx
                five.append({"date": {"year": dt.year, "month": dt.month, "day": dt.day},
                             "time": {"hour": dt.hour, "minute": dt.minute},
                             "rx": drx, "tx": dtx})

            day_list = [{"date": {"year": y, "month": m, "day": d}, "rx": v[0], "tx": v[1]}
                        for (y, m, d), v in sorted(day.items())]
            hour_list = [{"date": {"year": y, "month": m, "day": d},
                          "time": {"hour": h, "minute": 0}, "rx": v[0], "tx": v[1]}
                         for (y, m, d, h), v in sorted(hour.items())]
            month_list = [{"date": {"year": y, "month": m}, "rx": v[0], "tx": v[1]}
                          for (y, m), v in sorted(month.items())]
            top_list = sorted(
                ({"date": d["date"], "rx": d["rx"], "tx": d["tx"]} for d in day_list),
                key=lambda x: x["rx"] + x["tx"], reverse=True)[:10]

            interfaces.append({
                "name": iface, "alias": "",
                "traffic": {
                    "total": {"rx": total_rx, "tx": total_tx},
                    "fiveminute": five[-12:],
                    "hour": hour_list,
                    "day": day_list,
                    "month": month_list,
                    "year": [],
                    "top": top_list,
                },
            })
        return {"vnstatversion": "netkit-builtin", "jsonversion": "2",
                "interfaces": interfaces}

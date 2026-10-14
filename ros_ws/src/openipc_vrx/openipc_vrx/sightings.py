"""A log of what the camera saw: one line when a kind of thing appears and
one when it is gone, not one per picture.

Without the drone's position (not wired in yet) a line holds what is known
from the picture alone: when, what, how many at once, how sure, where in
the picture and for how long. When something appears, its picture with
the boxes is saved next to the log.

Kept free of rclpy so it can be tested without ROS.
"""

import csv
import time
from pathlib import Path

FIELDS = ["cas", "udalost", "co", "pocet", "jistota", "kde_v_obraze", "trvani_s", "snimek"]


def where(x1, x2, width):
    """Left, middle or right third of the picture, with the centre in %."""
    c = (x1 + x2) / 2 / width
    third = "vlevo" if c < 1 / 3 else "uprostred" if c < 2 / 3 else "vpravo"
    return f"{third} {c * 100:.0f} %"


class Sightings:
    """Turns per-picture detections into appear/gone events written to CSV.

    A kind of thing counts as gone after `gone_after` seconds without it, so
    a few pictures the model misses (blur, a turn) do not split one sighting
    into many.
    """

    def __init__(self, log_dir, gone_after=3.0, clock=time.time):
        self.dir = Path(log_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(clock()))
        self.path = self.dir / f"nalezy_{stamp}.csv"
        self.file = open(self.path, "w", newline="", encoding="utf-8")
        self.csv = csv.DictWriter(self.file, FIELDS)
        self.csv.writeheader()
        self.file.flush()
        self.gone_after = gone_after
        self.active = {}        # kind -> dict(start, last, count, best, where)
        self.snaps = 0

    def stamp(self, t):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) + f".{int(t % 1 * 10)}"

    def update(self, found, width, snapshot=None):
        """found: [(kind, score, x1, y1, x2, y2)] of one picture; width in px.

        snapshot: called with a file name to save the boxed picture into,
        only when something appears. Returns the events written.
        """
        now = self.clock()
        events = []
        kinds = {}
        for kind, score, x1, _, x2, _ in found:
            k = kinds.setdefault(kind, {"count": 0, "best": 0.0, "where": ""})
            k["count"] += 1
            if score > k["best"]:
                k["best"], k["where"] = score, where(x1, x2, width)

        for kind, k in kinds.items():
            a = self.active.get(kind)
            if a is None:
                name = ""
                if snapshot is not None:
                    self.snaps += 1
                    name = f"{self.path.stem}_{self.snaps:03d}_{kind}.jpg"
                    snapshot(self.dir / name)
                self.active[kind] = {"start": now, "last": now, **k}
                events.append(self.write(now, "objeveno", kind, k["count"], k["best"], k["where"], "", name))
            else:
                a["last"] = now
                a["count"] = max(a["count"], k["count"])
                if k["best"] > a["best"]:
                    a["best"], a["where"] = k["best"], k["where"]

        for kind in [k for k, a in self.active.items() if now - a["last"] > self.gone_after]:
            a = self.active.pop(kind)
            events.append(self.write(a["last"], "zmizelo", kind, a["count"], a["best"], a["where"],
                                     f"{a['last'] - a['start']:.1f}", ""))
        return events

    def write(self, t, event, kind, count, best, where_, duration, snap):
        row = {"cas": self.stamp(t), "udalost": event, "co": kind, "pocet": count,
               "jistota": f"{best:.2f}", "kde_v_obraze": where_, "trvani_s": duration, "snimek": snap}
        self.csv.writerow(row)
        self.file.flush()
        return row

    def close(self):
        """Everything still in view is written as gone, then the file closes."""
        for kind, a in list(self.active.items()):
            self.write(a["last"], "zmizelo", kind, a["count"], a["best"], a["where"],
                       f"{a['last'] - a['start']:.1f}", "")
        self.active = {}
        self.file.close()

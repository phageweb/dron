#!/usr/bin/env python3
"""Replay one swarm flight from above, with a slider through time.

    python3 scripts/replay_swarm_run.py [run_dir] [-o out.html]

Writes one self-contained HTML page (no network, no libraries) next to the
run's logs as replay.html, and prints its path. Open it in a browser.

What it shows at the moment the slider is on: each agent where the
coordinator placed it, its track so far, a dashed line to the target it was
being sent to (an opening, or - R5a - a place away from the others), and the
speed limit the safety filter gave it, so a stopped agent says why. The map
underneath is the merged map at the end of the flight; the walls are the
world file's.

All of it is from coordinator_log.json and merged_map.json, which
check_swarm_mapping.sh saves: one tick every 0.2 s, positions in the room's
frame, cell-centred at 0.10 m. Pure Python; runs anywhere.
"""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from room_geometry import room_and_enclosure  # noqa: E402

WORLD = "ros_ws/src/openipc_cinewhoop_gazebo/worlds/cluttered_room.sdf"


def flight_s_of(run_dir):
    """How long the run flew: flight_s.txt (OPENIPC_FLIGHT_S), else R3's 130 s."""
    try:
        return float(open(os.path.join(run_dir, "flight_s.txt")).read())
    except (OSError, ValueError):
        return 130.0


def world_of(run_dir):
    """The world the run flew in: world.txt, or the default for older runs."""
    try:
        return open(os.path.join(run_dir, "world.txt")).read().strip() or WORLD
    except OSError:
        return WORLD
PERIOD_S = 0.2  # the coordinator's tick, its period_s parameter


def newest_run():
    runs = sorted(glob.glob("logs/swarm_mapping/*/"), key=os.path.getmtime)
    if not runs:
        sys.exit("No runs under logs/swarm_mapping/.")
    return runs[-1]


def centre(cell, origin, resolution):
    return (round(origin[0] + (cell[0] + 0.5) * resolution, 3),
            round(origin[1] + (cell[1] + 0.5) * resolution, 3))


def frames_from(assignment_log, origin, resolution):
    frames = []
    for entry in assignment_log:
        frame = {}
        for name, cell in entry.get("agent_cells", {}).items():
            agent = {"p": centre(cell, origin, resolution),
                     "lim": entry.get("limits_mps", {}).get(name)}
            if name in entry.get("assigned", {}):
                agent["t"] = centre(entry["assigned"][name]["cell"], origin,
                                    resolution)
                agent["k"] = "opening"
            elif name in entry.get("spread", {}):
                agent["t"] = centre(entry["spread"][name], origin, resolution)
                agent["k"] = "away"
            frame[name] = agent
        frames.append(frame)
    return frames


def frames_from_trace(path):
    """Frames from the coordinator's own trace: every tick from the ground up.

    Newer runs have it (the coordinator's trace_path); it starts with the
    first pose rather than with the first merged map, so take-off and the
    spread out of the launch row are in it. Positions are full precision.
    """
    frames, times = [], []
    grid, deltas = None, []
    for line in open(path):
        tick = json.loads(line)
        if "grid" in tick:
            grid = tick["grid"]
        if "map" in tick:
            deltas.append((len(frames), tick["map"]))
        frame = {}
        for name, position in tick["pos"].items():
            agent = {"p": (position[0], position[1]),
                     "lim": tick["lim"].get(name)}
            if name in tick.get("tgt", {}):
                agent["t"] = tuple(tick["tgt"][name])
                agent["k"] = tick.get("kind", {}).get(name, "opening")
            frame[name] = agent
        frames.append(frame)
        times.append(tick["t"])
    return frames, times, grid, deltas


def truth_window(grid, room, rects, margin_m=0.3):
    """The real room, cell by cell, over the part of the grid round it.

    1 floor, 2 wholly inside a wall or obstacle, 3 a cell the wall's face
    runs along or through - the floor cell touching it, or a cell only
    partly covered - where the map may fairly say either, and 0 outside the
    room, which nobody is scored on.
    """
    res, ox, oy = grid["res"], grid["ox"], grid["oy"]
    x0, x1, y0, y1 = room
    c0 = max(0, int((x0 - margin_m - ox) / res))
    c1 = min(grid["w"], int((x1 + margin_m - ox) / res) + 1)
    r0 = max(0, int((y0 - margin_m - oy) / res))
    r1 = min(grid["h"], int((y1 + margin_m - oy) / res) + 1)
    eps = 1e-6

    def overlaps(cx0, cx1, cy0, cy1, rect):
        return (cx0 < rect[1] - eps and cx1 > rect[0] + eps
                and cy0 < rect[3] - eps and cy1 > rect[2] + eps)

    def covered(cx0, cx1, cy0, cy1):
        """How much of the cell is inside walls or obstacles, 0 to 1."""
        area = 0.0
        for rect in rects:
            w = min(cx1, rect[1]) - max(cx0, rect[0])
            h = min(cy1, rect[3]) - max(cy0, rect[2])
            if w > 0 and h > 0:
                area += w * h
        return min(1.0, area / ((cx1 - cx0) * (cy1 - cy0)))

    def touches(cx0, cx1, cy0, cy1, rect):
        return (cx0 <= rect[1] + eps and cx1 >= rect[0] - eps
                and cy0 <= rect[3] + eps and cy1 >= rect[2] - eps)

    truth = []
    for row in range(r0, r1):
        for col in range(c0, c1):
            cx0, cy0 = ox + col * res, oy + row * res
            cx1, cy1 = cx0 + res, cy0 + res
            part = covered(cx0, cx1, cy0, cy1)
            if part >= 0.99:
                truth.append(2)
            elif part > eps:
                # Part wall, part floor - the baffle is 0.1 m thick and
                # centred on a cell edge, so half of it is in each of two
                # cells. Free and occupied are both a fair answer there.
                truth.append(3)
            elif not (x0 - eps <= cx0 and cx1 <= x1 + eps
                      and y0 - eps <= cy0 and cy1 <= y1 + eps):
                truth.append(0)
            elif any(touches(cx0, cx1, cy0, cy1, r) for r in rects) or (
                    cx0 <= x0 + eps or cx1 >= x1 - eps
                    or cy0 <= y0 + eps or cy1 >= y1 - eps):
                truth.append(3)
            else:
                truth.append(1)
    return {"c0": c0, "r0": r0, "cw": c1 - c0, "ch": r1 - r0}, truth


def airborne_at(path, above_m=0.3):
    """When every agent in the trace was first above `above_m`, trace time.

    The flight's 130 s (R3) run from the moment the last agent is up; the
    trace starts earlier, on the ground, and goes on after the check has
    measured, so neither end of it is the flight.
    """
    for line in open(path):
        tick = json.loads(line)
        pos = tick["pos"]
        if pos and all(p[2] > above_m for p in pos.values()):
            return tick["t"]
    return None


def time_to_coverage(times, deltas, grid, window, truth, inside=None,
                     thresholds=(0.5, 0.8, 0.9), start=None, budget_s=130.0):
    """When the floor was first mapped to each fraction, seconds after `start`.

    Measured from the moment every agent is airborne, as the 130 s are.
    Explore-Bench's time to 90 per cent (reserseRoju 06 section 5, 07
    section 6): coverage at a fixed 130 s says whether a swarm keeps up with
    one drone, not whether it is faster, which is the only reason to fly one.
    The mask is the replay's own: floor cells only (truth 1), never the cells
    a wall's face runs along, so the map drawing a face into them does not
    cap the figure. `inside(col, row)` narrows it, to the enclosure say.
    A threshold never reached within `budget_s` of `start` (the trace's
    first tick if None) maps to None, not to the flight's length.
    """
    start = times[0] if start is None else start
    w, cw = grid["w"], window["cw"]
    floor = set()
    for i, kind in enumerate(truth):
        col, row = window["c0"] + i % cw, window["r0"] + i // cw
        if kind == 1 and (inside is None or inside(col, row)):
            floor.add(row * w + col)
    if not floor:
        return {}
    free = set()
    reached = {}
    at_budget = 0.0
    for frame_index, changes in deltas:
        if times[frame_index] - start > budget_s:
            break
        for index, cls in changes:
            if index in floor:
                if cls == 1:
                    free.add(index)
                else:
                    free.discard(index)
        for threshold in thresholds:
            if threshold not in reached and len(free) >= threshold * len(floor):
                reached[threshold] = max(0.0, times[frame_index] - start)
        at_budget = len(free) / len(floor)
    figures = {t: (reached[t] if t in reached and reached[t] <= budget_s
                   else None) for t in thresholds}
    # The same mask at the end of the budget: the coverage figure the check
    # means, taken at the moment it means rather than when it got round to it.
    figures["at_budget"] = at_budget
    return figures


def occupied_cells(merged):
    """The merged map as run-length rows of occupied and free cells."""
    width = merged["width"]
    cells = {"occ": [], "free": []}
    for row in range(merged["height"]):
        line = merged["data"][row * width:(row + 1) * width]
        col = 0
        while col < width:
            value = line[col]
            kind = None if value < 0 else ("occ" if value >= 65 else "free")
            start = col
            while col < width and (
                    (None if line[col] < 0 else
                     ("occ" if line[col] >= 65 else "free")) == kind):
                col += 1
            if kind:
                cells[kind].append([start, row, col - start])
    return cells


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Swarm Flight Replay</title>
<style>
:root {
  --surface-0: #f4f3ef; --surface-1: #fcfcfb; --border: #dcdbd5;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #8a8984;
  --map-free: #ecebe6; --map-occ: #9a9994; --wall: #0b0b0b; --grid: #e7e6e0;
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a;
  --stop: #e34948;
  --truth-floor: #f3f2ee; --truth-wall: #cbcac3;
  --seen-free: #d7e3ee; --seen-wall: #3d3d3a; --seen-face: #8f8e88; --seen-wrong: #e34948;
  --outline: #b5b4ae;
  --m-ground: #8d8d88; --m-floor: #d6d6d1; --m-floor-seen: #f8f8f5;
  --m-wall-found: #2f9e4f; --m-wall-todo: #f0bf22; --m-wall-miss: #dc3d35;
  --m-outline: #6f6f6a;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --surface-0: #121211; --surface-1: #1a1a19; --border: #33332f;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8f8e86;
    --map-free: #262624; --map-occ: #6b6a65; --wall: #e8e7e1; --grid: #262624;
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
    --stop: #e66767;
    --truth-floor: #1f1f1d; --truth-wall: #3c3c37;
    --seen-free: #2a3a4a; --seen-wall: #d8d7d0; --seen-face: #85847d; --seen-wrong: #e66767;
    --outline: #55554f;
    --m-ground: #2a2a28; --m-floor: #6a6a66; --m-floor-seen: #c9c9c4;
    --m-wall-found: #3fbf63; --m-wall-todo: #f0c435; --m-wall-miss: #ee5a50;
    --m-outline: #9a9a94;
  }
}
:root[data-theme="dark"] {
  --surface-0: #121211; --surface-1: #1a1a19; --border: #33332f;
  --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8f8e86;
  --map-free: #262624; --map-occ: #6b6a65; --wall: #e8e7e1; --grid: #262624;
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
  --stop: #e66767;
  --truth-floor: #1f1f1d; --truth-wall: #3c3c37;
  --seen-free: #2a3a4a; --seen-wall: #d8d7d0; --seen-face: #85847d; --seen-wrong: #e66767;
  --outline: #55554f;
  --m-ground: #2a2a28; --m-floor: #6a6a66; --m-floor-seen: #c9c9c4;
  --m-wall-found: #3fbf63; --m-wall-todo: #f0c435; --m-wall-miss: #ee5a50;
  --m-outline: #9a9a94;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface-0); color: var(--text-primary);
  font: 14px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 16px; }
h1 { font-size: 18px; font-weight: 600; margin: 4px 0 2px; }
.sub { color: var(--text-secondary); margin: 0 0 12px; }
.card { background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px; }
.controls { display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  margin-bottom: 10px; }
button, select { font: inherit; color: var(--text-primary);
  background: var(--surface-0); border: 1px solid var(--border);
  border-radius: 6px; padding: 4px 10px; cursor: pointer; }
input[type=range] { flex: 1 1 260px; min-width: 160px; accent-color: var(--text-secondary); }
.time { font-variant-numeric: tabular-nums; color: var(--text-secondary);
  min-width: 9ch; text-align: right; }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) 230px; gap: 12px; }
@media (max-width: 760px) { .layout { grid-template-columns: 1fr; } }
#map { width: 100%; height: auto; display: block; }
.legend svg { flex: none; }
.agents { display: flex; flex-direction: column; gap: 8px; }
.agent { border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; }
.agent .name { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.swatch { width: 12px; height: 12px; border-radius: 50%; }
.agent .row { color: var(--text-secondary); font-size: 13px;
  font-variant-numeric: tabular-nums; }
.badge { font-size: 12px; padding: 0 6px; border-radius: 4px;
  border: 1px solid var(--border); color: var(--text-secondary); }
.badge.stop { color: var(--stop); border-color: var(--stop); }
.legend { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 14px;
  color: var(--text-secondary); font-size: 12px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.note { color: var(--text-muted); font-size: 12px; margin-top: 10px; }
#tip { position: fixed; pointer-events: none; background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px;
  font-size: 12px; display: none; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
</style>
</head>
<body>
<main>
  <h1 id="title"></h1>
  <p class="sub" id="sub"></p>
  <div class="card">
    <div class="controls">
      <button id="play" aria-label="Play">▶ Play</button>
      <input id="slider" type="range" min="0" value="0" step="1" aria-label="Time">
      <span class="time" id="time"></span>
      <label>speed <select id="speed">
        <option value="1">1×</option><option value="2">2×</option>
        <option value="4" selected>4×</option><option value="8">8×</option>
      </select></label>
      <label><input type="checkbox" id="full"> whole track</label>
    </div>
    <div class="layout">
      <svg id="map" role="img" aria-label="Room seen from above with the agents"></svg>
      <div class="agents" id="agents"></div>
    </div>
    <div class="legend">
      <span><svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke="var(--text-secondary)" stroke-width="2"/></svg>track so far</span>
      <span><svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke="var(--text-secondary)" stroke-width="1.5" stroke-dasharray="4 3"/></svg>where it is being sent</span>
      <span><svg width="12" height="12"><circle cx="6" cy="6" r="4.5" fill="none" stroke="var(--stop)" stroke-width="2"/></svg>held still by the safety filter</span>
      <span class="live-only"><svg width="14" height="12"><rect x="1" y="2" width="12" height="8" fill="var(--m-floor)"/></svg>floor not seen yet</span>
      <span class="live-only"><svg width="14" height="12"><rect x="1" y="2" width="12" height="8" fill="var(--m-floor-seen)" stroke="var(--border)"/></svg>floor seen</span>
      <span class="live-only"><svg width="14" height="12"><rect x="1" y="2" width="12" height="8" fill="var(--m-wall-found)"/></svg>wall found</span>
      <span class="live-only"><svg width="14" height="12"><rect x="1" y="2" width="12" height="8" fill="var(--m-wall-todo)"/></svg>wall not found yet</span>
      <span class="live-only"><svg width="14" height="12"><rect x="1" y="2" width="12" height="8" fill="var(--m-wall-miss)"/></svg>wall not found by the end of the flight</span>
      <span class="final-only"><svg width="14" height="12"><rect x="1" y="2" width="12" height="8" fill="var(--map-free)"/></svg>mapped free</span>
      <span class="final-only"><svg width="14" height="12"><rect x="1" y="2" width="12" height="8" fill="var(--map-occ)"/></svg>mapped occupied</span>
      <span><svg width="14" height="12"><rect x="1" y="2" width="12" height="8" fill="none" stroke="var(--outline)"/></svg>walls (world file)</span>
    </div>
    <p class="note" id="mapnote"></p>
    <p class="note">Positions are where the coordinator placed each agent, 5 times a second. Keys: space plays, ← → step.</p>
  </div>
</main>
<div id="tip"></div>
<script>
const D = __DATA__;
const NS = "http://www.w3.org/2000/svg";
const COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
const names = D.names;
const [rx0, rx1, ry0, ry1] = D.room;
const pad = 0.35, W = rx1 - rx0 + 2 * pad, H = ry1 - ry0 + 2 * pad;
const svg = document.getElementById("map");
svg.setAttribute("viewBox", `${rx0 - pad} ${-(ry1 + pad)} ${W} ${H}`);
// y up: the SVG is drawn with y negated, so north is up like the plot.
const Y = y => -y;
function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  (parent || svg).appendChild(e);
  return e;
}
el("rect", {x: rx0 - pad, y: -(ry1 + pad), width: W, height: H, fill: D.live ? "var(--m-ground)" : "var(--surface-1)"});
const g = el("g", {});
for (let x = Math.ceil(rx0); x <= rx1; x++) el("line", {x1: x, x2: x, y1: Y(ry0 - pad), y2: Y(ry1 + pad), stroke: "var(--grid)", "stroke-width": 0.01}, g);
for (let y = Math.ceil(ry0); y <= ry1; y++) el("line", {x1: rx0 - pad, x2: rx1 + pad, y1: Y(y), y2: Y(y), stroke: "var(--grid)", "stroke-width": 0.01}, g);
const r = D.res, ox = D.origin[0], oy = D.origin[1];
for (const [kind, fill] of [["free", "var(--map-free)"], ["occ", "var(--map-occ)"]]) {
  let d = "";
  for (const [c, row, n] of D.cells[kind]) {
    const x = ox + c * r, y = oy + row * r;
    d += `M${x} ${Y(y + r)}h${n * r}v${r}h${-n * r}z`;
  }
  el("path", {d, fill}, g);
}
for (const [x0, x1, y0, y1] of D.walls) el("rect", {x: x0, y: Y(y1), width: x1 - x0, height: y1 - y0, fill: "none", stroke: D.live ? "var(--m-outline)" : "var(--wall)", "stroke-width": D.live ? 0.008 : 0.025}, g);
const [ex0, ex1, ey0, ey1] = D.enclosure;
el("rect", {x: ex0, y: Y(ey1), width: ex1 - ex0, height: ey1 - ey0, fill: "none", stroke: "var(--text-muted)", "stroke-width": 0.02, "stroke-dasharray": "0.08 0.08"}, g);
const encl = el("text", {x: ex0 + 0.08, y: Y(ey1) + 0.22, "font-size": 0.17, fill: "var(--text-secondary)"}, g);
encl.textContent = "enclosure";
for (let x = Math.ceil(rx0); x <= rx1; x++) { const t = el("text", {x, y: Y(ry0 - pad) - 0.06, "font-size": 0.16, fill: "var(--text-muted)", "text-anchor": "middle"}, g); t.textContent = x + " m"; }

// The map, as it was discovered: a canvas one pixel per cell, redrawn when
// the slider crosses a recorded change, shown under the tracks.
const L = D.live;
const seenStat = {el: null};
let paintMap = () => {};
if (L) {
  document.querySelectorAll(".final-only").forEach(e => e.style.display = "none");
  g.querySelectorAll("path").forEach(p => p.remove());  // drop the final-map layer
  const {c0, r0, cw, ch} = L.win;
  const canvas = document.createElement("canvas");
  canvas.width = cw; canvas.height = ch;
  const ctx = canvas.getContext("2d");
  const img = el("image", {x: L.ox + c0 * L.res, y: Y(L.oy + (r0 + ch) * L.res),
    width: cw * L.res, height: ch * L.res, preserveAspectRatio: "none",
    style: "image-rendering: pixelated"});
  // Under everything else in the room layer: walls, labels and tracks on top.
  g.insertBefore(img, g.firstChild);
  const css = getComputedStyle(document.documentElement);
  const rgb = name => {
    const c = document.createElement("canvas").getContext("2d");
    c.fillStyle = css.getPropertyValue(name).trim(); return c.fillStyle;
  };
  const hex = h => [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)];
  const pal = {};
  for (const k of ["--m-ground", "--m-floor", "--m-floor-seen", "--m-wall-found", "--m-wall-todo", "--m-wall-miss"]) pal[k] = hex(rgb(k));
  // A wall cell with no floor beside it is the inside of a wall or a crate:
  // no beam reaches it, so it is never found or missed, just solid.
  const edge = new Uint8Array(cw * ch);
  for (let row = 0; row < ch; row++) for (let col = 0; col < cw; col++) {
    const i = row * cw + col;
    if (L.truth[i] !== 2) { edge[i] = 1; continue; }
    for (const [dc, dr] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const c2 = col + dc, r2 = row + dr;
      if (c2 >= 0 && c2 < cw && r2 >= 0 && r2 < ch) {
        const t2 = L.truth[r2 * cw + c2];
        if (t2 === 1 || t2 === 3) { edge[i] = 1; break; }
      }
    }
  }
  const cls = new Uint8Array(cw * ch);
  let applied = -1;
  const apply = upto => {
    if (upto < applied) { cls.fill(0); applied = -1; }
    for (let k = applied + 1; k <= upto; k++) { const d = L.deltas[k]; if (d) for (const [i, c] of d) cls[i] = c; }
    applied = upto;
  };
  const note = document.getElementById("mapnote");
  paintMap = upto => {
    apply(upto);
    const image = ctx.createImageData(cw, ch);
    let floor = 0, right = 0, wrong = 0;
    for (let row = 0; row < ch; row++) for (let col = 0; col < cw; col++) {
      const i = row * cw + col, t = L.truth[i], c = cls[i];
      // Floor: grey until seen, then white. Walls - the cells inside a
      // wall or obstacle and those its face runs through - green once the
      // map has them, yellow until then, and red if the flight ended
      // without finding them: what the swarm missed.
      const over = upto >= L.deltas.length - 1 || upto >= L.end;
      let colour;
      if (t === 0) colour = pal["--m-ground"];
      else if (t === 1) colour = c !== 0 ? pal["--m-floor-seen"] : pal["--m-floor"];
      else if (!edge[i]) colour = pal["--m-ground"];
      else if (c === 2) colour = pal["--m-wall-found"];
      else if (t === 3 && c === 1) colour = pal["--m-floor-seen"];
      else colour = over ? pal["--m-wall-miss"] : pal["--m-wall-todo"];
      if (t === 1 || t === 3) { floor++; if (c === 1 || (t === 3 && c === 2)) right++; }
      if ((t === 2 && c === 1) || (t === 1 && c === 2)) wrong++;
      const o = ((ch - 1 - row) * cw + col) * 4;
      image.data[o] = colour[0]; image.data[o+1] = colour[1]; image.data[o+2] = colour[2]; image.data[o+3] = 255;
    }
    ctx.putImageData(image, 0, 0);
    img.setAttribute("href", canvas.toDataURL());
    note.textContent = `Discovered so far: ${(100 * right / floor).toFixed(0)} % of the floor seen correctly, ${wrong} cells wrong. ` +
      "Cells a wall's face runs along or through count as right either way - the map may draw the face into either.";
  };
} else {
  document.querySelectorAll(".live-only").forEach(e => e.style.display = "none");
  document.getElementById("mapnote").textContent = "This run has no recorded map history; the map shown is the merged map at the end of the flight.";
}

const parts = names.map((name, i) => {
  const color = COLORS[i % COLORS.length];
  const ga = el("g", {});
  const trail = el("polyline", {fill: "none", stroke: color, "stroke-width": 0.035, "stroke-linejoin": "round", "stroke-linecap": "round", opacity: 0.9}, ga);
  const aim = el("line", {stroke: color, "stroke-width": 0.022, "stroke-dasharray": "0.09 0.07", opacity: 0.85}, ga);
  const goal = el("circle", {r: 0.07, fill: "var(--surface-1)", stroke: color, "stroke-width": 0.025}, ga);
  const held = el("circle", {r: 0.2, fill: "none", stroke: "var(--stop)", "stroke-width": 0.03}, ga);
  const dot = el("circle", {r: 0.11, fill: color, stroke: "var(--surface-1)", "stroke-width": 0.03}, ga);
  const hit = el("circle", {r: 0.3, fill: "transparent", style: "cursor: default"}, ga);
  const label = el("text", {"font-size": 0.2, "font-weight": 600, fill: "var(--text-primary)"}, ga);
  label.textContent = name;
  return {name, color, trail, aim, goal, held, dot, hit, label};
});

const panel = document.getElementById("agents");
const cards = names.map((name, i) => {
  const div = document.createElement("div");
  div.className = "agent";
  div.innerHTML = `<div class="name"><span class="swatch" style="background:${COLORS[i % COLORS.length]}"></span>${name}<span class="badge"></span></div>
    <div class="row lim"></div><div class="row tgt"></div><div class="row dist"></div>`;
  panel.appendChild(div);
  return div;
});

// Distance flown up to each frame, per agent.
const cum = names.map(n => {
  let s = 0, prev = null; const out = [];
  for (const f of D.frames) { const a = f[n]; if (a && prev) s += Math.hypot(a.p[0] - prev[0], a.p[1] - prev[1]); if (a) prev = a.p; out.push(s); }
  return out;
});

const slider = document.getElementById("slider");
slider.max = D.frames.length - 1;
const full = document.getElementById("full");
let frame = 0;
function describe(a) {
  if (!a) return {badge: "no data", cls: "", lim: "", tgt: ""};
  const lim = a.lim;
  const state = lim === null || lim === undefined ? "no limit" : lim <= 0.0 ? "stopped" : lim < D.vmax - 1e-3 ? "slowed" : "free";
  return {badge: state, cls: state === "stopped" ? "stop" : "",
    lim: `limit ${lim === null || lim === undefined ? "—" : lim.toFixed(2) + " m/s"}`,
    tgt: a.t ? `sent to (${a.t[0].toFixed(1)}, ${a.t[1].toFixed(1)}) · ${a.k === "away" ? "away from the others" : "an opening"}` : "no target"};
}
function draw() {
  const f = D.frames[frame];
  parts.forEach((p, i) => {
    const pts = [];
    const end = full.checked ? D.frames.length - 1 : frame;
    for (let k = 0; k <= end; k++) { const a = D.frames[k][p.name]; if (a) pts.push(`${a.p[0]},${Y(a.p[1])}`); }
    p.trail.setAttribute("points", pts.join(" "));
    const a = f[p.name];
    const show = a ? "visible" : "hidden";
    for (const e of [p.dot, p.hit, p.label]) e.setAttribute("visibility", show);
    if (a) {
      const [x, y] = a.p;
      for (const e of [p.dot, p.hit, p.held]) { e.setAttribute("cx", x); e.setAttribute("cy", Y(y)); }
      p.label.setAttribute("x", x + 0.16); p.label.setAttribute("y", Y(y) - 0.14);
      p.held.setAttribute("visibility", a.lim !== null && a.lim !== undefined && a.lim <= 0 ? "visible" : "hidden");
      if (a.t) {
        p.aim.setAttribute("x1", x); p.aim.setAttribute("y1", Y(y));
        p.aim.setAttribute("x2", a.t[0]); p.aim.setAttribute("y2", Y(a.t[1]));
        p.goal.setAttribute("cx", a.t[0]); p.goal.setAttribute("cy", Y(a.t[1]));
        p.aim.setAttribute("visibility", "visible"); p.goal.setAttribute("visibility", "visible");
      } else { p.aim.setAttribute("visibility", "hidden"); p.goal.setAttribute("visibility", "hidden"); }
    } else { p.held.setAttribute("visibility", "hidden"); p.aim.setAttribute("visibility", "hidden"); p.goal.setAttribute("visibility", "hidden"); }
    const d = describe(a);
    const card = cards[i];
    const badge = card.querySelector(".badge"); badge.textContent = d.badge; badge.className = "badge " + d.cls;
    card.querySelector(".lim").textContent = d.lim;
    card.querySelector(".tgt").textContent = d.tgt;
    card.querySelector(".dist").textContent = `flown ${cum[i][frame].toFixed(1)} m so far`;
  });
  paintMap(frame);
  const t = frame * D.period;
  document.getElementById("time").textContent = `${t.toFixed(1)} s / ${((D.frames.length - 1) * D.period).toFixed(0)} s`;
  slider.value = frame;
}
slider.addEventListener("input", () => { frame = +slider.value; draw(); });
full.addEventListener("change", draw);

let timer = null;
const play = document.getElementById("play");
function toggle() {
  if (timer) { clearInterval(timer); timer = null; play.textContent = "▶ Play"; return; }
  if (frame >= D.frames.length - 1) frame = 0;
  play.textContent = "❚❚ Pause";
  const tick = () => {
    const speed = +document.getElementById("speed").value;
    frame = Math.min(D.frames.length - 1, frame + 1);
    draw();
    if (frame >= D.frames.length - 1) toggle();
  };
  timer = setInterval(tick, 1000 * D.period / +document.getElementById("speed").value);
}
play.addEventListener("click", toggle);
document.getElementById("speed").addEventListener("change", () => { if (timer) { toggle(); toggle(); } });
document.addEventListener("keydown", e => {
  if (e.target.tagName === "SELECT") return;
  if (e.key === " ") { e.preventDefault(); toggle(); }
  if (e.key === "ArrowRight") { frame = Math.min(D.frames.length - 1, frame + 1); draw(); }
  if (e.key === "ArrowLeft") { frame = Math.max(0, frame - 1); draw(); }
});

const tip = document.getElementById("tip");
parts.forEach(p => {
  p.hit.addEventListener("mousemove", ev => {
    const d = describe(D.frames[frame][p.name]);
    tip.innerHTML = `<b>${p.name}</b> · ${d.badge}<br>${d.lim}<br>${d.tgt}`;
    tip.style.display = "block"; tip.style.left = ev.clientX + 12 + "px"; tip.style.top = ev.clientY + 12 + "px";
  });
  p.hit.addEventListener("mouseleave", () => { tip.style.display = "none"; });
});

// replay.html#t=60 opens at that second.
const at = /t=([0-9.]+)/.exec(location.hash);
if (at) frame = Math.max(0, Math.min(D.frames.length - 1, Math.round(+at[1] / D.period)));
document.getElementById("title").textContent = `Swarm flight ${D.run}`;
document.getElementById("sub").textContent = D.summary;
draw();
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description="Replay one swarm flight from above, with a time slider.")
    parser.add_argument("run_dir", nargs="?")
    parser.add_argument("-o", "--out")
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    run_dir = args.run_dir or newest_run()
    for needed in ("merged_map.json", "coordinator_log.json"):
        if not os.path.isfile(os.path.join(run_dir, needed)):
            sys.exit(f"{run_dir} has no {needed}; it predates the check "
                     "saving it, or the flight did not finish.")

    merged = json.load(open(os.path.join(run_dir, "merged_map.json")))
    log = json.load(open(os.path.join(run_dir, "coordinator_log.json")))
    room, enclosure, walls, obstacles = room_and_enclosure(world_of(run_dir))
    trace = os.path.join(run_dir, "trace.jsonl")
    live = None
    reach = None
    if os.path.isfile(trace):
        frames, times, grid, deltas = frames_from_trace(trace)
        if grid and deltas:
            rects = (list(walls.values()) + list(obstacles.values()))
            window, truth = truth_window(grid, room, rects)
            w = grid["w"]
            per_frame = {}
            for frame_index, changes in deltas:
                local = []
                for index, cls in changes:
                    col, row = index % w - window["c0"], index // w - window["r0"]
                    if 0 <= col < window["cw"] and 0 <= row < window["ch"]:
                        local.append([row * window["cw"] + col, cls])
                per_frame[frame_index] = local
            res, ox, oy = grid["res"], grid["ox"], grid["oy"]
            ex0, ex1, ey0, ey1 = enclosure

            def in_enclosure(col, row):
                x, y = ox + (col + 0.5) * res, oy + (row + 0.5) * res
                return ex0 <= x <= ex1 and ey0 <= y <= ey1

            start = airborne_at(trace)
            budget = flight_s_of(run_dir)
            reach = {"room": time_to_coverage(times, deltas, grid, window,
                                              truth, start=start,
                                              budget_s=budget),
                     "enclosure": time_to_coverage(times, deltas, grid, window,
                                                   truth, in_enclosure,
                                                   start=start,
                                                   budget_s=budget)}
            # The frame the flight's budget ends on: from there, floor nobody
            # has found is drawn as missed rather than still to find.
            end = next((k for k, t in enumerate(times)
                        if start is not None and t - start >= budget),
                       len(frames) - 1)
            live = {"win": window, "res": grid["res"], "ox": grid["ox"],
                    "oy": grid["oy"], "truth": truth, "end": end,
                    "deltas": [per_frame.get(k) for k in range(len(frames))]}
        period = ((times[-1] - times[0]) / (len(times) - 1)
                  if len(times) > 1 else PERIOD_S)
        source = "from the ground up"
    else:
        frames = frames_from(log["assignment"], merged["origin"],
                             merged["resolution"])
        period = PERIOD_S
        source = ("from the first merged map - after take-off; "
                  "this run predates the coordinator's trace")
    names = sorted({n for f in frames for n in f})
    limits = [a["lim"] for f in frames for a in f.values()
              if a.get("lim") is not None]

    summary = []
    coverage_path = os.path.join(run_dir, "coverage.txt")
    if os.path.isfile(coverage_path):
        coverage = dict(line.split() for line in open(coverage_path))
        summary.append(f"room {100 * float(coverage['room']):.0f} % mapped, "
                       f"enclosure {100 * float(coverage['enclosure']):.0f} %")
    if reach:
        def when(seconds):
            return "not reached" if seconds is None else f"{seconds:.0f} s"
        for part, figures in reach.items():
            line = ", ".join(f"T{round(100 * t)} {when(v)}"
                             for t, v in figures.items() if t != "at_budget")
            line += (f", {100 * figures['at_budget']:.0f} % at "
                     f"{flight_s_of(run_dir):.0f} s")
            summary.append(f"{part} {line}")
            print(f"{part}: {line}")
        with open(os.path.join(run_dir, "time_to_coverage.json"), "w") as handle:
            json.dump({part: {(t if t == "at_budget" else f"T{round(100 * t)}"): v
                              for t, v in figures.items()}
                       for part, figures in reach.items()}, handle)
    summary.append(f"{len(frames)} coordinator ticks, {source}")

    data = {
        "run": os.path.basename(os.path.normpath(run_dir)),
        "summary": " · ".join(summary),
        "names": names,
        "period": round(period, 4),
        "vmax": max(limits) if limits else 0.5,
        "room": list(room),
        "enclosure": list(enclosure),
        "walls": [list(b) for b in list(walls.values()) + list(obstacles.values())],
        "res": merged["resolution"],
        "origin": merged["origin"],
        "cells": occupied_cells(merged),
        "frames": frames,
        "live": live,
    }
    out = args.out or os.path.join(run_dir, "replay.html")
    with open(out, "w") as handle:
        handle.write(PAGE.replace("__DATA__", json.dumps(data, separators=(",", ":"))))
    print(out)


if __name__ == "__main__":
    main()

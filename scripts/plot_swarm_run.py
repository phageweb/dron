#!/usr/bin/env python3
"""Draw one swarm flight from above: the room, the merged map, and each
agent's track.

    python3 scripts/plot_swarm_run.py [run_dir] [-o out.png]

run_dir defaults to the newest logs/swarm_mapping/<airframe>-<stamp>/. The
picture is written next to the logs as top_down.png unless -o says otherwise.

Everything comes from what check_swarm_mapping.sh already saves: the merged
map at the end of the flight (merged_map.json), and where the coordinator
placed every agent on every tick (coordinator_log.json, 5 Hz, in the room's
frame). The track is therefore the coordinator's view - cell-centred at
0.10 m - which is the view the safety filter and the assignment acted on.
The walls and obstacles are read from the world file, so the map can be
checked against what is really there.

Needs matplotlib; outside the dev shell:
    nix shell --impure --expr 'with import <nixpkgs> {}; \
        python3.withPackages (p: [p.matplotlib])' -c python3 scripts/plot_swarm_run.py
"""

import argparse
import glob
import json
import math
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from room_geometry import room_and_enclosure  # noqa: E402

WORLD = "ros_ws/src/openipc_cinewhoop_gazebo/worlds/cluttered_room.sdf"


def world_of(run_dir):
    """The world the run flew in: world.txt, or the default for older runs."""
    try:
        return open(os.path.join(run_dir, "world.txt")).read().strip() or WORLD
    except OSError:
        return WORLD

# The validated categorical order, slots 1-3 (dataviz reference palette).
# Aqua sits under 3:1 on the light surface, so every track is also labelled
# by name at both ends rather than told apart by colour alone.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
FREE = "#ecebe6"
OCCUPIED = "#8a8984"
WALL = "#0b0b0b"


def newest_run():
    runs = sorted(glob.glob("logs/swarm_mapping/*/"), key=os.path.getmtime)
    if not runs:
        sys.exit("No runs under logs/swarm_mapping/.")
    return runs[-1]


def tracks_from(assignment_log, origin, resolution):
    """Each agent's position per tick, in metres, from the coordinator's log."""
    tracks = {}
    for entry in assignment_log:
        for name, cell in entry.get("agent_cells", {}).items():
            x = origin[0] + (cell[0] + 0.5) * resolution
            y = origin[1] + (cell[1] + 0.5) * resolution
            tracks.setdefault(name, []).append((x, y))
    return tracks


def length(track):
    return sum(math.dist(a, b) for a, b in zip(track, track[1:]))


def main():
    parser = argparse.ArgumentParser(
        description="Draw one swarm flight from above.")
    parser.add_argument("run_dir", nargs="?")
    parser.add_argument("-o", "--out")
    args = parser.parse_args()

    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project)
    run_dir = args.run_dir or newest_run()
    for needed in ("merged_map.json", "coordinator_log.json"):
        if not os.path.isfile(os.path.join(run_dir, needed)):
            sys.exit(f"{run_dir} has no {needed}; it predates the check "
                     "saving it, or the flight did not finish.")

    merged = json.load(open(os.path.join(run_dir, "merged_map.json")))
    log = json.load(open(os.path.join(run_dir, "coordinator_log.json")))
    width, height = merged["width"], merged["height"]
    resolution = merged["resolution"]
    origin = merged["origin"]
    room, enclosure, walls, obstacles = room_and_enclosure(world_of(run_dir))
    tracks = tracks_from(log["assignment"], origin, resolution)

    coverage = {}
    coverage_path = os.path.join(run_dir, "coverage.txt")
    if os.path.isfile(coverage_path):
        for line in open(coverage_path):
            key, value = line.split()
            coverage[key] = float(value)

    fig, ax = plt.subplots(figsize=(9, 7.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    # The merged map: free floor pale, occupied darker, unknown left as the
    # surface. 0 unknown, 1 free, 2 occupied.
    classes = [0 if v < 0 else (2 if v >= 65 else 1) for v in merged["data"]]
    rows = [classes[r * width:(r + 1) * width] for r in range(height)]
    ax.imshow(rows, origin="lower", interpolation="nearest",
              cmap=ListedColormap([SURFACE, FREE, OCCUPIED]), vmin=0, vmax=2,
              extent=(origin[0], origin[0] + width * resolution,
                      origin[1], origin[1] + height * resolution),
              zorder=0)

    # What is really there, from the world file.
    for x0, x1, y0, y1 in list(walls.values()) + list(obstacles.values()):
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False,
                               edgecolor=WALL, linewidth=0.8, zorder=2))
    ex0, ex1, ey0, ey1 = enclosure
    ax.add_patch(Rectangle((ex0, ey0), ex1 - ex0, ey1 - ey0, fill=False,
                           edgecolor=TEXT_2, linewidth=0.8, linestyle=(0, (3, 3)),
                           zorder=2))
    ax.annotate("enclosure", (ex0 + 0.08, ey1 - 0.08), color=TEXT_2,
                fontsize=8, va="top", zorder=5)

    for index, name in enumerate(sorted(tracks)):
        track = tracks[name]
        colour = SERIES[index % len(SERIES)]
        xs, ys = zip(*track)
        ax.plot(xs, ys, color=colour, linewidth=2, solid_capstyle="round",
                solid_joinstyle="round", zorder=3)
        # Where the coordinator first logged it - a little after takeoff,
        # since it logs only once every agent has a map. Open ring. End: filled dot with a surface ring, so a track
        # ending on another is still readable.
        ax.plot(xs[0], ys[0], marker="o", markersize=8, markerfacecolor=SURFACE,
                markeredgecolor=colour, markeredgewidth=2, zorder=4)
        ax.plot(xs[-1], ys[-1], marker="o", markersize=8, markerfacecolor=colour,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
        ax.annotate(f"{name}", (xs[0], ys[0]), xytext=(6, -10),
                    textcoords="offset points", fontsize=8, color=TEXT_2,
                    zorder=5)
        ax.annotate(f"{name}  {length(track):.1f} m", (xs[-1], ys[-1]),
                    xytext=(6, 4), textcoords="offset points", fontsize=8,
                    color=TEXT, fontweight="bold", zorder=5)

    x0, x1, y0, y1 = room
    ax.set_xlim(x0 - 0.4, x1 + 0.4)
    ax.set_ylim(y0 - 0.4, y1 + 0.4)
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]", color=TEXT_2, fontsize=9)
    ax.set_ylabel("y [m]", color=TEXT_2, fontsize=9)
    ax.tick_params(colors=TEXT_2, labelsize=8, length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(True, color="#e3e2dc", linewidth=0.5, zorder=1)

    run_name = os.path.basename(os.path.normpath(run_dir))
    title = f"Swarm flight {run_name}, from above"
    if coverage:
        title += (f" - room {100 * coverage.get('room', 0):.0f} %, "
                  f"enclosure {100 * coverage.get('enclosure', 0):.0f} %")
    ax.set_title(title, loc="left", color=TEXT, fontsize=11, pad=12)

    handles = [Line2D([], [], color=SERIES[i % len(SERIES)], linewidth=2,
                      label=name) for i, name in enumerate(sorted(tracks))]
    handles += [
        Line2D([], [], linestyle="", marker="o", markersize=7,
               markerfacecolor=SURFACE, markeredgecolor=TEXT_2,
               markeredgewidth=1.5, label="first logged (after takeoff)"),
        Line2D([], [], linestyle="", marker="o", markersize=7,
               markerfacecolor=TEXT_2, markeredgecolor=SURFACE, label="end"),
        Rectangle((0, 0), 1, 1, facecolor=FREE, edgecolor="none",
                  label="mapped free"),
        Rectangle((0, 0), 1, 1, facecolor=OCCUPIED, edgecolor="none",
                  label="mapped occupied"),
        Line2D([], [], color=WALL, linewidth=0.8, label="walls, obstacles"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0),
              frameon=False, fontsize=8, labelcolor=TEXT)

    out = args.out or os.path.join(run_dir, "top_down.png")
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    print(out)


if __name__ == "__main__":
    main()

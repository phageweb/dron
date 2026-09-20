"""Where the room is, read out of the world file rather than written down.

`check_room_coverage.sh` derived these rectangles inline, and the swarm flight
needs exactly the same ones or its coverage figure cannot be compared with the
single-drone baseline - which is the whole point of measuring it. So the
derivation lives here once: move a wall in the world and both checks follow.

Nothing here prints. The caller decides what to say, because the two checks
say it differently and the numbers are the same either way.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Tuple

Rect = Tuple[float, float, float, float]  # x_min, x_max, y_min, y_max


def footprint(model) -> Rect:
    """A model's rectangle on the floor, from its collision box."""
    pose = [float(v) for v in model.find("pose").text.split()]
    size = [float(v) for v in
            model.find(".//collision/geometry/box/size").text.split()]
    return (pose[0] - size[0] / 2.0, pose[0] + size[0] / 2.0,
            pose[1] - size[1] / 2.0, pose[1] + size[1] / 2.0)


def boxes_in(world_path: str) -> Dict[str, Rect]:
    """Every box-shaped model in the world except the floor."""
    root = ET.parse(world_path).getroot()
    found = {}
    for model in root.iter("model"):
        name = model.get("name") or ""
        if name == "floor" or model.find(".//collision/geometry/box/size") is None:
            continue
        found[name] = footprint(model)
    return found


def room_and_enclosure(world_path: str):
    """The room's inner faces and the inside of the enclosure within it.

    Returns (room, enclosure, walls, obstacles). Raises ValueError when the
    world is not the shape these checks measure, because a check that quietly
    measured half a room would pass for the wrong reason.
    """
    boxes = boxes_in(world_path)
    walls = {name: box for name, box in boxes.items() if name.startswith("wall_")}
    obstacles = {name: box for name, box in boxes.items()
                 if not name.startswith("wall_")}
    if len(walls) != 4 or not obstacles:
        raise ValueError(
            f"Expected four walls and at least one obstacle in {world_path}; "
            f"found walls {sorted(walls)} and obstacles {sorted(obstacles)}.")

    # The room's inner faces: the wall boxes' edges nearest the origin.
    half_x = min(min(abs(box[0]), abs(box[1]))
                 for name, box in walls.items() if "_x_" in name)
    half_y = min(min(abs(box[2]), abs(box[3]))
                 for name, box in walls.items() if "_y_" in name)
    room = (-half_x, half_x, -half_y, half_y)

    # What the enclosure encloses, derived from its own walls rather than
    # written down again: the bounding box of everything named inner_*, pulled
    # in by their thickness to get the inside rather than the outside.
    inner = {name: box for name, box in boxes.items() if name.startswith("inner_")}
    if len(inner) < 3:
        raise ValueError(
            f"Expected the enclosure's walls as inner_* in {world_path}; "
            f"found {sorted(inner)}.")
    thickness = min(min(box[1] - box[0], box[3] - box[2])
                    for box in inner.values())
    outside = (min(box[0] for box in inner.values()),
               max(box[1] for box in inner.values()),
               min(box[2] for box in inner.values()),
               max(box[3] for box in inner.values()))
    enclosure = (outside[0] + thickness, outside[1] - thickness,
                 outside[2] + thickness, outside[3] - thickness)
    if enclosure[1] <= enclosure[0] or enclosure[3] <= enclosure[2]:
        raise ValueError("The inner_* walls do not enclose anything.")
    return room, enclosure, walls, obstacles

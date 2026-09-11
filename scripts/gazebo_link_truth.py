#!/usr/bin/env python3
"""Where Gazebo really has a link, in metres above a world's floor surface.

The leaning check needs ground truth for the downward sensor's height so the
slant-range correction can be compared against the simulator rather than against
the formula that produced it. Gazebo publishes the model's world pose and its
links' poses relative to the model, so the two have to be composed; the floor's
surface comes out of the world file, because a box centred on z = 0 has its top
at half its thickness and nothing else knows that.

Prints: qx qy qz qw height_above_floor
"""

import re
import subprocess
import sys
import xml.etree.ElementTree as ET


def floor_surface_z(world_path, floor_model="floor"):
    """Top of the floor box, from the world file rather than from memory."""
    root = ET.parse(world_path).getroot()
    for model in root.iter("model"):
        if model.get("name") != floor_model:
            continue
        pose = model.find("pose")
        base = float(pose.text.split()[2]) if pose is not None else 0.0
        size = model.find(".//collision/geometry/box/size")
        if size is None:
            sys.exit(f"The {floor_model} model has no collision box.")
        return base + float(size.text.split()[2]) / 2.0
    sys.exit(f"No model named {floor_model} in {world_path}.")


def poses(world_name):
    """Every pose in one message, by name: (x, y, z) and (qx, qy, qz, qw)."""
    out = subprocess.run(
        ["gz", "topic", "-e", "-t", f"/world/{world_name}/pose/info", "-n", "1"],
        capture_output=True, text=True, timeout=30).stdout
    found = {}
    for block in re.split(r"\npose \{", out):
        name = re.search(r'name: "([^"]+)"', block)
        if name is None:
            continue
        # Protobuf text format omits fields at their default, so a component
        # that is absent is zero - and for a quaternion that means w alone is
        # printed for no rotation at all.
        position = re.search(r"position \{(.*?)\n  \}", block, re.S)
        orientation = re.search(r"orientation \{(.*?)\n  \}", block, re.S)

        def read(match, keys):
            values = dict.fromkeys(keys, 0.0)
            if match is not None:
                values.update({k: float(v) for k, v in
                               re.findall(r"([xyzw]):\s*([-\d.e+]+)", match.group(1))
                               if k in values})
            return values

        found[name.group(1)] = (read(position, "xyz"), read(orientation, "xyzw"))
    return found


def rotate(q, v):
    """q * v * q^-1, written out, so this file needs no quaternion library."""
    x, y, z, w = q["x"], q["y"], q["z"], q["w"]
    vx, vy, vz = v["x"], v["y"], v["z"]
    return (
        (1 - 2 * (y * y + z * z)) * vx + 2 * (x * y - w * z) * vy + 2 * (x * z + w * y) * vz,
        2 * (x * y + w * z) * vx + (1 - 2 * (x * x + z * z)) * vy + 2 * (y * z - w * x) * vz,
        2 * (x * z - w * y) * vx + 2 * (y * z + w * x) * vy + (1 - 2 * (x * x + y * y)) * vz,
    )


def main():
    if len(sys.argv) != 5:
        sys.exit("usage: gazebo_link_truth.py <world_file> <world_name> "
                 "<model_name> <link_name>")
    world_path, world_name, model_name, link_name = sys.argv[1:]

    found = poses(world_name)
    for name in (model_name, link_name):
        if name not in found:
            sys.exit(f"Gazebo published no pose named {name}; it had: "
                     + ", ".join(sorted(found)))
    model_position, model_orientation = found[model_name]
    link_position, _ = found[link_name]

    # Link poses arrive relative to the model, so the model's own rotation is
    # what carries the link's offset up or down when the vehicle leans.
    offset_z = rotate(model_orientation, link_position)[2]
    height = model_position["z"] + offset_z - floor_surface_z(world_path)
    print(f'{model_orientation["x"]} {model_orientation["y"]} '
          f'{model_orientation["z"]} {model_orientation["w"]} {height:.6f}')


if __name__ == "__main__":
    main()

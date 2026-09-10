#!/usr/bin/env python3
"""Assert the URDF and the SDF still describe the same drone.

The airframe is written down twice: once as Xacro for robot_state_publisher and
RViz, once as SDF for Gazebo. Nothing links the two files, so they drift, and the
drift is silent - the simulation keeps flying and RViz keeps drawing, just not
the same vehicle. That has already happened once: `rangefinder_link` was pitched
90 degrees in the SDF and level in the URDF, which put the floor measurement in
front of the drone instead of below it.

This check needs no simulator and no ROS graph. It expands the Xacro, reads both
files, and compares the links they are meant to share: where each one sits
relative to `base_link`, how it is rotated, and what the whole thing weighs.
"""

import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URDF = ROOT / "ros_ws/src/openipc_cinewhoop_description/urdf/openipc_cinewhoop.urdf.xacro"
SDF = ROOT / "ros_ws/src/openipc_cinewhoop_gazebo/models/openipc_cinewhoop/model.sdf"

BASE = "base_link"
TOLERANCE_M = 1e-6
TOLERANCE_RAD = 1e-6
TOLERANCE_KG = 1e-9

# Links that legitimately exist in one file only. Anything else appearing on one
# side is a divergence, which is the whole point of the check.
URDF_ONLY = {
    "camera_optical_frame": "the SDF carries it as the camera's gz_frame_id, not as a link",
    "optical_flow_link": "no optical flow sensor is simulated yet",
}
SDF_ONLY = {
    "rotor_0": "the URDF draws the propellers as visuals on the motor links",
    "rotor_1": "the URDF draws the propellers as visuals on the motor links",
    "rotor_2": "the URDF draws the propellers as visuals on the motor links",
    "rotor_3": "the URDF draws the propellers as visuals on the motor links",
}


def rotation(rpy):
    """Roll-pitch-yaw to a 3x3 matrix, the fixed-axis order both formats use."""
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = (
        math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y))
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def compose(a, b):
    """Chain two (xyz, R) transforms."""
    (ax, aR), (bx, bR) = a, b
    x = tuple(ax[i] + sum(aR[i][k] * bx[k] for k in range(3)) for i in range(3))
    R = tuple(tuple(sum(aR[i][k] * bR[k][j] for k in range(3)) for j in range(3))
              for i in range(3))
    return x, R


def to_rpy(R):
    """Matrix back to roll-pitch-yaw, so the two files can be compared as angles."""
    pitch = math.asin(max(-1.0, min(1.0, -R[2][0])))
    if abs(math.cos(pitch)) < 1e-9:  # gimbal lock; not used by this model
        return (math.atan2(-R[1][2], R[1][1]), pitch, 0.0)
    return (math.atan2(R[2][1], R[2][2]), pitch, math.atan2(R[1][0], R[0][0]))


def urdf_poses():
    """Expand the Xacro and place every link relative to base_link."""
    expanded = subprocess.run(
        ["xacro", str(URDF)], check=True, capture_output=True, text=True).stdout
    root = ET.fromstring(expanded)

    parents = {}
    for joint in root.findall("joint"):
        child = joint.find("child").get("link")
        origin = joint.find("origin")
        xyz = [float(v) for v in (origin.get("xyz") or "0 0 0").split()]
        rpy = [float(v) for v in (origin.get("rpy") or "0 0 0").split()]
        parents[child] = (joint.find("parent").get("link"), (tuple(xyz), rotation(rpy)))

    def place(link):
        if link == BASE:
            return ((0.0, 0.0, 0.0), rotation((0, 0, 0)))
        parent, transform = parents[link]
        return compose(place(parent), transform)

    links = [link.get("name") for link in root.findall("link")]
    poses = {name: place(name) for name in links}
    mass = sum(float(link.find("inertial/mass").get("value"))
               for link in root.findall("link") if link.find("inertial/mass") is not None)
    return poses, mass


def sdf_poses():
    """Read every link's pose, which this model states relative to base_link."""
    root = ET.fromstring(SDF.read_text())
    model = root.find("model")

    raw = {}
    for link in model.findall("link"):
        pose = link.find("pose")
        values = [float(v) for v in (pose.text.split() if pose is not None
                                     else "0 0 0 0 0 0".split())]
        relative_to = pose.get("relative_to") if pose is not None else None
        raw[link.get("name")] = (relative_to, (tuple(values[:3]), rotation(values[3:6])))

    def place(link):
        relative_to, transform = raw[link]
        if relative_to is None or relative_to == link:
            return transform
        return compose(place(relative_to), transform)

    poses = {name: place(name) for name in raw}
    mass = sum(float(link.find("inertial/mass").text) for link in model.findall("link")
               if link.find("inertial/mass") is not None)
    return poses, mass


def main():
    urdf, urdf_mass = urdf_poses()
    sdf, sdf_mass = sdf_poses()
    problems = []

    for name in sorted(set(urdf) - set(sdf)):
        if name not in URDF_ONLY:
            problems.append(f"{name} is in the URDF but not the SDF")
    for name in sorted(set(sdf) - set(urdf)):
        if name not in SDF_ONLY:
            problems.append(f"{name} is in the SDF but not the URDF")

    shared = sorted(set(urdf) & set(sdf))
    for name in shared:
        (ux, uR), (sx, sR) = urdf[name], sdf[name]
        if any(abs(ux[i] - sx[i]) > TOLERANCE_M for i in range(3)):
            problems.append(
                f"{name} sits at {tuple(round(v, 6) for v in ux)} in the URDF and "
                f"{tuple(round(v, 6) for v in sx)} in the SDF")
        urpy, srpy = to_rpy(uR), to_rpy(sR)
        if any(abs(urpy[i] - srpy[i]) > TOLERANCE_RAD for i in range(3)):
            problems.append(
                f"{name} is rotated {tuple(round(v, 6) for v in urpy)} in the URDF and "
                f"{tuple(round(v, 6) for v in srpy)} in the SDF")

    # The URDF lumps everything into base_link because it only has to look right;
    # the SDF spreads mass over the links physics acts on. Only the total is
    # comparable, and it is the number the thrust and tuning were derived from.
    if abs(urdf_mass - sdf_mass) > TOLERANCE_KG:
        problems.append(
            f"total mass is {urdf_mass:.6f} kg in the URDF and {sdf_mass:.6f} kg in the SDF")

    if problems:
        print("The URDF and the SDF describe different drones:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"  {len(shared)} shared links agree on position, rotation and total mass")
    print(f"  total mass {sdf_mass:.3f} kg")
    for name, why in sorted({**URDF_ONLY, **SDF_ONLY}.items()):
        print(f"  {name}: in one file only, {why}")
    print("Model consistency check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

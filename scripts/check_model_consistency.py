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
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The airframes the project describes. Each is a URDF/SDF pair that has to agree
# with itself; only the flown one has to agree with the demo nodes as well,
# because a node carries exactly one set of defaults and the variant is passed
# its numbers as parameters instead. Printing those numbers rather than checking
# them is the point of the `owns_demo_defaults` flag: a variant that silently
# used the wrong corridor width would be worse than one that fails to start.
AIRFRAMES = {
    "cinewhoop": {
        "urdf": "ros_ws/src/openipc_cinewhoop_description/urdf/openipc_cinewhoop.urdf.xacro",
        "sdf": "ros_ws/src/openipc_cinewhoop_gazebo/models/openipc_cinewhoop/model.sdf",
        "parm": "ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params.parm",
        "owns_demo_defaults": True,
    },
    "pavo20": {
        "urdf": "ros_ws/src/openipc_cinewhoop_description/urdf/openipc_pavo20.urdf.xacro",
        "sdf": "ros_ws/src/openipc_cinewhoop_gazebo/models_pavo20/openipc_cinewhoop/model.sdf",
        "parm": "ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params_pavo20.parm",
        "owns_demo_defaults": False,
    },
}

URDF = ROOT / AIRFRAMES["cinewhoop"]["urdf"]
SDF = ROOT / AIRFRAMES["cinewhoop"]["sdf"]

BASE = "base_link"
DEMO = ROOT / "ros_ws/src/openipc_cinewhoop_demo/openipc_cinewhoop_demo"
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


def world_scoped_topics():
    """Sensor topics in the SDF that name a world, which pins the model to it.

    A sensor is free to declare its own <topic>, and the obvious thing to write
    is the name Gazebo would have generated - which contains the world's name.
    The model then only works in a world called that: Gazebo keeps publishing
    under the written name, ArduPilotPlugin looks for the IMU under the real
    world's name, finds nothing, and never sends SITL a JSON state. SITL resends
    servos forever and says only "No JSON sensor message received", which points
    at the network rather than at a name. Found the hard way by writing a second
    world; the fix is to declare no topic at all and let Gazebo scope them.
    """
    return [line.strip() for line in SDF.read_text().splitlines()
            if "<topic>" in line and "/world/" in line]


# Where the demo nodes believe the sensors are, and which distance in the model
# each of those parameters is a copy of. The nodes carry these as parameter
# defaults because that is model knowledge living outside the model: TF has the
# same numbers and none of the nodes listens to TF. Checking them here is what
# makes that safe - a model that moves a sensor has to fail rather than leave a
# node projecting from a place the sensor no longer is.
SENSOR_OFFSETS = {
    # The rangefinder measures a height for a sensor that is not it.
    "lidar_ahead_of_rangefinder_m": ("front_lidar_link", "rangefinder_link", 0),
    "lidar_above_rangefinder_m": ("front_lidar_link", "rangefinder_link", 2),
    # The mapper needs the other end of it too: the returns are measured from
    # the lidar and the pose is base_link's, so a map built without this casts
    # every ray from a place no sensor is.
    "lidar_ahead_of_base_m": ("front_lidar_link", BASE, 0),
    "lidar_left_of_base_m": ("front_lidar_link", BASE, 1),
    "lidar_above_base_m": ("front_lidar_link", BASE, 2),
}
AXES = ("x", "y", "z")


def sdf_rotor_tip_half_width():
    """How far the rotor tips reach from the centre, out of the model itself.

    The demo decides what is in its way by the swath the airframe occupies, so
    the airframe's own half-width is a number a node has to carry - and carrying
    it is the same hazard as carrying a sensor offset. A frame with longer arms
    or a bigger propeller has to fail here rather than fly down a corridor
    narrower than it is.

    Taken over every rotor rather than from one, because the quad is only
    symmetric while nobody has moved a motor.
    """
    root = ET.fromstring(SDF.read_text())
    model = root.find("model")
    reach = []
    for link in model.findall("link"):
        if not (link.get("name") or "").startswith("rotor_"):
            continue
        pose = [float(v) for v in link.find("pose").text.split()]
        radius = link.find(".//visual/geometry/cylinder/radius")
        if radius is None:
            continue
        reach.append(max(abs(pose[0]), abs(pose[1])) + float(radius.text))
    return max(reach) if reach else None


def demo_declared(name):
    """A parameter default the demo nodes carry, wherever they carry it."""
    found = {}
    for path in sorted(DEMO.glob("*.py")):
        match = re.search(
            rf'declare_parameter\(\s*"{name}"\s*,\s*([-\d.eE+]+)\s*\)',
            path.read_text())
        if match is not None:
            found[path.name] = float(match.group(1))
    return found


def demo_sensor_offsets():
    """The offsets the demo nodes carry, read out of their own source."""
    found = {}
    for path in sorted(DEMO.glob("*.py")):
        text = path.read_text()
        for name in SENSOR_OFFSETS:
            match = re.search(
                rf'declare_parameter\(\s*"{name}"\s*,\s*([-\d.eE+]+)\s*\)', text)
            if match is not None:
                found.setdefault((path.name, name), float(match.group(1)))
    return found


def select(airframe):
    """Point the module at one airframe's pair of files."""
    global URDF, SDF
    URDF = ROOT / AIRFRAMES[airframe]["urdf"]
    SDF = ROOT / AIRFRAMES[airframe]["sdf"]



# How far the implied hover throttle may sit from the one the parameter file
# declares. Both airframes currently agree to 0.005, so 0.02 is loose enough
# to survive rounding and tight enough to have caught the fault it exists for:
# the Pavo20 model carried the CineLog's multiplier, which put its real hover
# at 0.75 against a declared 0.53.
TOLERANCE_HOVER = 0.02


def propulsion_problems(airframe):
    """Check the throttle scale against the motor and the parameter file.

    Three numbers have to agree and nothing in the project made them:

    - `<multiplier>` in each ArduPilot control block is the rotor speed that
      full throttle asks for, and `<maxRotVelocity>` is the speed the motor
      model will allow. Below it the airframe can never reach its own rated
      thrust; above it the top of the throttle range is silently clamped.
    - the hover throttle that falls out of the model - the speed needed to
      hold the airframe's own weight, over the multiplier - has to be the
      `MOT_THST_HOVER` the autopilot is told, or the controller starts every
      takeoff from the wrong place.

    This is the check that was missing when models_pavo20 inherited the
    CineLog's multiplier: the geometry agreed, the masses agreed, and the
    machine could not lift itself.
    """
    sdf = (ROOT / AIRFRAMES[airframe]["sdf"]).read_text()
    problems = []

    multipliers = {float(v) for v in re.findall(
        r"<multiplier>([\d.eE+-]+)</multiplier>", sdf)}
    max_speeds = {float(v) for v in re.findall(
        r"<maxRotVelocity>([\d.eE+-]+)</maxRotVelocity>", sdf)}
    constants = {float(v) for v in re.findall(
        r"<motorConstant>([\d.eE+-]+)</motorConstant>", sdf)}
    masses = [float(v) for v in re.findall(r"<mass>([\d.eE+-]+)</mass>", sdf)]

    if len(multipliers) != 1:
        problems.append(
            f"the control blocks ask for {sorted(multipliers)} rad/s at full "
            "throttle; one airframe has one throttle scale")
        return problems
    if len(max_speeds) != 1 or len(constants) != 1:
        problems.append(
            f"the motors disagree with each other: maxRotVelocity "
            f"{sorted(max_speeds)}, motorConstant {sorted(constants)}")
        return problems

    multiplier = multipliers.pop()
    max_speed = max_speeds.pop()
    constant = constants.pop()
    if abs(multiplier - max_speed) > 1e-6:
        problems.append(
            f"full throttle asks for {multiplier:.0f} rad/s while the motors "
            f"allow {max_speed:.0f}; the airframe "
            + ("can never reach its rated thrust"
               if multiplier < max_speed else
               "is clamped at the top of its throttle range"))

    parm = (ROOT / AIRFRAMES[airframe]["parm"]).read_text()
    declared = re.search(r"^MOT_THST_HOVER\s+([\d.]+)", parm, re.M)
    if declared is None:
        problems.append("the parameter file declares no MOT_THST_HOVER")
        return problems
    weight = sum(masses) * 9.81
    hover_speed = math.sqrt(weight / 4.0 / constant)
    implied = hover_speed / multiplier
    if abs(implied - float(declared.group(1))) > TOLERANCE_HOVER:
        problems.append(
            f"the model hovers at {implied:.3f} of full throttle "
            f"({hover_speed:.0f} of {multiplier:.0f} rad/s for {weight:.2f} N) "
            f"while the parameter file says MOT_THST_HOVER "
            f"{float(declared.group(1)):.3f}")
    return problems


def main(airframe="cinewhoop"):
    select(airframe)
    owns_defaults = AIRFRAMES[airframe]["owns_demo_defaults"]
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

    problems.extend(propulsion_problems(airframe))

    # See SENSOR_OFFSETS: each of these is a distance the model owns and a node
    # keeps a copy of, so the copy is checked rather than trusted.
    expected = {}
    for name, (link, reference, axis) in SENSOR_OFFSETS.items():
        expected[name] = sdf[link][0][axis] - sdf[reference][0][axis]
    # The airframe's own half-width, which the demo carries for the same reason
    # and with the same risk as the sensor offsets above.
    tip = sdf_rotor_tip_half_width()
    declared_tip = demo_declared("rotor_tip_half_width_m") if owns_defaults else {}
    if tip is None:
        problems.append(
            "the SDF has no rotor with a propeller radius, so how wide the "
            "vehicle is cannot be read out of the model")
    elif not declared_tip and not owns_defaults:
        pass
    elif not declared_tip:
        problems.append(
            "no demo node declares rotor_tip_half_width_m; the model still says "
            "how wide the vehicle is, so either it was renamed or the node "
            "stopped deciding what is in its way by the airframe's width")
    else:
        for node, value in sorted(declared_tip.items()):
            if abs(value - tip) > TOLERANCE_M:
                problems.append(
                    f"{node} flies a corridor {value:.5f} m either side of the "
                    f"centre and the model's rotor tips reach {tip:.5f} m")

    offsets = demo_sensor_offsets() if owns_defaults else {}
    if not offsets and not owns_defaults:
        pass
    elif not offsets:
        problems.append(
            "no demo node declares where the sensors sit; either the "
            "parameters were renamed or this check is looking in the wrong place")
    declared = {name for _, name in offsets}
    for name in sorted((set(SENSOR_OFFSETS) - declared) if owns_defaults else set()):
        problems.append(
            f"no demo node declares {name}; the model still says what it should "
            "be, so either it was renamed or the node stopped needing it")
    for (node, name), value in sorted(offsets.items()):
        link, reference, axis = SENSOR_OFFSETS[name]
        if abs(value - expected[name]) > TOLERANCE_M:
            problems.append(
                f"{node} places {link} {value:+.4f} m from {reference} along "
                f"{AXES[axis]} and the model places it {expected[name]:+.4f} m")

    pinned = world_scoped_topics()
    if pinned:
        print("The SDF pins the model to one world through its sensor topics:",
              file=sys.stderr)
        for line in pinned:
            print(f"  {line}", file=sys.stderr)
        print("  Remove the <topic> and let Gazebo scope it to the real world.",
              file=sys.stderr)
        return 1

    if problems:
        # Not only the URDF against the SDF any more: the demo nodes carry a
        # piece of the model too, and naming the wrong pair of files is how a
        # reader is sent to look in the wrong place.
        print(f"The {airframe} is described inconsistently across files:",
              file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"{airframe}:")
    print("  no sensor topic names a world, so the model is not pinned to one")
    print(f"  {len(shared)} shared links agree on position, rotation and total mass")
    print(f"  total mass {sdf_mass:.3f} kg")
    print(f"  the rotor tips reach {tip:.5f} m from the centre, which is the "
          "half-width the demo flies a corridor of")
    who = "the demo nodes put" if owns_defaults else "the model puts"
    tail = ", as the model does" if owns_defaults else ""
    for name, (link, reference, axis) in SENSOR_OFFSETS.items():
        print(f"  {who} {link} {expected[name]:+.3f} m from "
              f"{reference} along {AXES[axis]}{tail}")
    for name, why in sorted({**URDF_ONLY, **SDF_ONLY}.items()):
        print(f"  {name}: in one file only, {why}")
    if not owns_defaults:
        # The demo nodes hold the flown airframe's numbers. Anything flying this
        # variant has to override them, so the check hands over the exact list
        # rather than leaving it to be re-derived by hand.
        print(f"  {airframe} is not the airframe the demo nodes default to, so a "
              "run of it must pass:")
        print(f"    rotor_tip_half_width_m:={tip:.5f}")
        for name in SENSOR_OFFSETS:
            print(f"    {name}:={expected[name]:.5f}")
    print(f"Model consistency check passed for {airframe}.")
    return 0


if __name__ == "__main__":
    # No argument checks every airframe the project describes. Checking only the
    # flown one would let a variant drift silently, which is the same failure
    # this script exists to stop.
    wanted = sys.argv[1:] or list(AIRFRAMES)
    unknown = [name for name in wanted if name not in AIRFRAMES]
    if unknown:
        print(f"unknown airframe(s): {', '.join(unknown)}; "
              f"known: {', '.join(AIRFRAMES)}", file=sys.stderr)
        sys.exit(2)
    sys.exit(max(main(name) for name in wanted))

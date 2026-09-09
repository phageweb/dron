# Troubleshooting

This file will be updated continuously during implementation.

## Template

```text
Problem:
Symptom:
Where it appeared:
Diagnostic commands:
Root cause:
Fix:
Verification after fix:
```

## Gazebo Transport Returns Nothing

Symptom:

- `gz topic -l` lists no topics at all while Gazebo is demonstrably running
- `gz topic -e -t <topic>` blocks and never delivers a message
- the ROS bridge works, so the simulation looks healthy from ROS

Root cause:

`gazebo.launch.py` pins the simulator and the bridge to `GZ_PARTITION=openipc_cinewhoop`
so that Transport discovery stays reliable on a host with several interfaces.
Gazebo Transport only discovers peers inside the same partition, so a CLI started
from an ordinary shell sees an empty graph. This is a configuration mismatch, not
a headless or rendering limitation.

Fix:

```bash
GZ_PARTITION=openipc_cinewhoop GZ_IP=127.0.0.1 gz topic -l
GZ_PARTITION=openipc_cinewhoop GZ_IP=127.0.0.1 gz topic -e -t <topic> -n 1
```

Verification after fix:

Without the partition `gz topic -l` returned 0 topics; with it the same command
returned 25, including `/world/indoor_test/model/openipc_cinewhoop/joint_state`
and the front-lidar scan topic.

## Readings Taken From a Crashed Vehicle Are Not Evidence

Symptom:

- `joint_state` reports rotor speeds that look wrong: reversed signs, one joint
  frozen at a constant value, or all four alternating between the same small
  positive and negative number
- the numbers do not change when model parameters change

Root cause:

The vehicle had already tipped over and crashed before the sample was taken.
A free quadrotor that cannot hold attitude flips within one to two seconds of
throttle-up, so anything measured after that describes a wreck. The recurring
`+-61.8 rad/s` alternation is a sampling artefact of this state, not a speed.

Fix:

Measure thrust with the airframe on the virtual thrust stand, where attitude
cannot change and the reading means something:

```bash
nix develop -c scripts/check_thrust_stand.sh
```

Correlate any free-flight rotor reading with attitude and time. A sample taken
more than about a second after throttle-up on a free airframe is worthless
until attitude control is working.

Verification after fix:

The stand check measures a 60 m climb, so the servo path, rotor joints and lift
surfaces all work. That result held both before and after an earlier change to
the rotor damping and torque ceiling, which is how the change was shown to be
unnecessary and, because it lowered the torque ceiling, actively worse.

## Vehicle Flips Immediately After Throttle-Up

Symptom:

- ArduPilot arms, GUIDED and takeoff are accepted
- the airframe rolls or pitches past 40 degrees within about 1.5 s and crashes
- with the same model on the thrust stand, the climb is fine

Diagnostics so far:

The actuation and aerodynamics are not the cause. On the stand the same model
climbs 60 m under real ArduPilot control with symmetric throttle. The channel
map, rotation directions, `modelXYZToAirplaneXForwardZDown` and `gazeboXYZToNED`
are all identical to the Iris reference that flies.

What remains is attitude tuning. `ardupilot_params.parm` sets only `FRAME_CLASS`
and `FRAME_TYPE`, so every gain comes from `copter.parm`, which targets a
vehicle of one to two kilograms. This airframe is 0.240 kg with a roll inertia
of 0.00022 kg m^2. Open item; see the backlog.

## Known Risks Before Implementation

### ROS 2 Packages on NixOS

Symptom:

- a package is missing in `nixpkgs`
- `nix develop` or `colcon build` fails on a missing dependency

Initial diagnostics:

```bash
nix develop
nix flake check
colcon build --symlink-install --base-paths ros_ws/src
```

First fix:

- use `nix-ros-overlay`
- if that is not enough, add a pinned source build or a local override

### Gazebo GUI / RViz2 Graphics

Symptom:

- the application crashes on startup
- OpenGL does not work
- the window is blank or visually broken

Initial diagnostics:

```bash
gz sim --versions
rviz2 --help
echo $DISPLAY
echo $WAYLAND_DISPLAY
```

First fix:

- add the required graphics libraries to the shell
- verify X11/Wayland environment variables
- on non-NixOS consider `nixGL`; on NixOS fix the system graphics configuration

### ArduPilot Gazebo plugin

Symptom:

- the Gazebo model loads, but SITL does not react
- SITL reports that it is waiting for the JSON backend
- motors do not react

Initial diagnostics:

```bash
gz topic -l
sim_vehicle.py -v ArduCopter --model JSON --console --map
echo $GZ_SIM_SYSTEM_PLUGIN_PATH
echo $GZ_SIM_RESOURCE_PATH
```

First fix:

- verify the `ardupilot_gazebo` build
- verify plugin paths
- run the Iris smoke test first

### Wrong Motor Mapping

Symptom:

- the drone flips during arm/takeoff
- hover is not possible
- roll/pitch/yaw reactions are swapped

Initial diagnostics:

- verify ordering of `motor_1` through `motor_4`
- verify rotation directions
- verify propeller torque signs
- compare the SDF plugin configuration with the ArduPilot quad X mixer

First fix:

- fix motor mapping in SDF
- retest takeoff at low altitude

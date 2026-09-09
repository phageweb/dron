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

## Rotors Spin Backwards and the Vehicle Never Climbs

Symptom:

- ArduPilot arms, accepts GUIDED and a takeoff request, and drives full throttle
- reported altitude does not change
- nothing is logged as an error in SITL, Gazebo, the Agent or the ROS graph

Diagnostic commands:

```bash
GZ_PARTITION=openipc_cinewhoop GZ_IP=127.0.0.1 \
  gz topic -e -t /world/indoor_test/model/openipc_cinewhoop/joint_state -n 1
```

Root cause:

The `ArduPilotPlugin` rotor control loop is explicit: each step it applies a
torque bounded by `cmd_max` to a joint of inertia `izz`, so one step changes the
rotor speed by `cmd_max * dt / izz`. A 3 in propeller has around 210x less
inertia than the Iris rotor whose numbers were copied into this model
(8.0e-07 against 1.676e-04), so the same torque ceiling produced a velocity step
far larger than the target speed. The loop never converged, and two of the four
rotors settled turning the wrong way.

A reversed rotor does not merely lose efficiency. `gz-sim-lift-drag-system`
skips a surface entirely when the blade travels opposite its `<forward>` vector,
so those rotors contributed exactly zero force. Half the thrust disappeared
silently, which left the vehicle below hover with no error anywhere.

Fix:

Scale the joint damping and the torque ceiling to the real rotor inertia so the
per-step velocity change stays small next to the commanded speed:

- `<damping>` 0.0002 to 0.00002
- `<cmd_max>` / `<cmd_min>` 3.5 / -3.5 to 0.1 / -0.1

Verification after fix:

`scripts/check_rotor_spin.sh` asserts the measured Quad X directions and passes.
Measured on a constrained thrust stand, all four rotors together give a
thrust-to-weight ratio of 1.0006 at 1600 rad/s, so only two working rotors
cannot leave the ground.

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

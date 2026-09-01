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

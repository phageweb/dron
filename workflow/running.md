# Running the Demo

Every command is run from the repository root. The launch file resolves its
defaults for `external/` and `build/` relative to the working directory, so
running it from elsewhere will not find the upstream builds.

## Everything at once

```bash
scripts/demo.sh
```

Scene, simulator and flight from one command, and it stays up until Ctrl-C so
the result can be looked at rather than raced past. It starts Gazebo with its
window, SITL, both bridges, RViz and the DDS Agent, waits until ArduPilot's ROS 2
services actually answer, then flies the demo in the foreground: arm, take off to
1 m, creep forward at 0.5 m/s and hold short of the wall. `--no-gui` and
`--altitude METRES` are the two arguments. It re-enters `nix develop` on its own.

`--circuit` flies a closed room and turns at the walls instead of stopping at
one obstacle, and `--map` builds the occupancy grid live while it does.

```bash
scripts/demo.sh --explore
```

The coverage flight, with a window on it: the cluttered room, the map being
built, and `frontier_explorer` choosing where to go from it rather than the
vehicle turning towards the roomier side. It implies `--circuit` and `--map`.
`check_room_coverage.sh` flies exactly this and measures the result, but it runs
Gazebo headless because it is a check.

In RViz, set Fixed Frame to `map` and add an Occupancy Map display on
`/openipc_cinewhoop/map` to watch the room fill in - including the inside of the
enclosure, which the reactive rule never sees. `frontier_explorer` says on its
own log which opening it is heading for and how far the route to it is.

Everything it starts, it kills on exit, including the leftover kind: a demo node
that outlives its wrapper keeps publishing `/ap/cmd_vel` and silently stops the
*next* run from taking off.

`scripts/menu.sh` lists this and everything else, and says which entries can run
right now.

## The scene on its own

```bash
nix develop
source install/setup.bash
ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py gui:=true
```

That starts the Gazebo server and GUI, the ROS/Gazebo sensor bridge, the
actuator bridge, `robot_state_publisher`, RViz2, the Micro XRCE-DDS Agent and
ArduPilot SITL with DDS enabled. Verified to produce `/ap`, `/rviz`,
`/robot_state_publisher` and `/ros_gz_bridge` in `ros2 node list`.

Useful arguments:

| Argument | Default | Effect |
| --- | --- | --- |
| `gui` | `false` | Gazebo GUI window |
| `rviz` | `true` | `robot_state_publisher` plus RViz2 |
| `agent` | `true` | Micro XRCE-DDS Agent, which the `/ap/` topics need |
| `sitl` | `true` | ArduPilot SITL; `false` prints the command for another terminal |

## Flying it

The autonomy demo runs in a second terminal. It needs `ardupilot_msgs`, which
lives in the opt-in DDS workspace rather than in the Nix shell:

```bash
nix develop
source install/setup.bash
source external/dds_ws/install/setup.bash
ros2 run openipc_cinewhoop_demo simple_indoor_autonomy \
  --ros-args -p takeoff_altitude_m:=1.0
```

It waits for the front lidar, walks prearm, GUIDED, arm and takeoff through
ArduPilot's ROS 2 services, climbs, then creeps forward at 0.5 m/s and holds
0.8 m short of the wall.

Stop it with Ctrl-C, then make sure it is really gone. `ros2 run` is a wrapper
whose child survives it, and a leftover node keeps publishing `/ap/cmd_vel`,
which silently prevents the *next* run from ever taking off:

```bash
ros2 node list | grep simple_indoor_autonomy
pkill -f openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/simple_indoor_autonomy
```

Watching only, without flying:

```bash
ros2 run openipc_cinewhoop_demo obstacle_monitor
ros2 topic echo /ap/geopose/filtered
```

## Parts on their own

```bash
# Gazebo and the sensor bridge, no ArduPilot
ros2 launch openipc_cinewhoop_gazebo gazebo.launch.py gui:=true

# URDF in RViz only, no simulator
ros2 launch openipc_cinewhoop_description display.launch.py use_sim_time:=false
```

## Watching the tuning flight

`scripts/sweep_rate_gains.sh` normally runs headless, because it is a
measurement. `GUI=1` opens the Gazebo window so the manoeuvre can be watched
instead:

```bash
nix develop
GUI=1 scripts/sweep_rate_gains.sh 0.05
```

The vehicle climbs to 3 m, holds altitude, and then takes a 10 degree roll
command every two seconds. One gain per invocation is the useful way to watch;
0.05 is past the oscillation onset and visibly hunts, while 0.027 tracks the
steps cleanly.

The window costs real time factor, so a run whose numbers matter should leave
`GUI` unset. Results from a watched run are for looking at, not for the table.

## Checking it instead of watching it

```bash
nix develop -c scripts/ci.sh                     # the whole baseline
nix develop -c scripts/check_unified_launch.sh   # this launch, headless
nix develop -c scripts/check_forward_flight.sh   # the full autonomy flight
```

The opt-in checks are listed in [testing strategy](./testing_strategy.md).

## First-time setup

The ROS workspace:

```bash
nix develop
colcon build --symlink-install --base-paths ros_ws/src
```

The upstream pieces, which stay in ignored `external/` because Nixpkgs does not
package them:

```bash
git clone https://github.com/ArduPilot/ardupilot external/ardupilot
git clone https://github.com/ArduPilot/ardupilot_gazebo external/ardupilot_gazebo

nix develop
scripts/build_actuator_bridge.sh   # ArduPilot Doubles -> one Actuators array
scripts/build_dds_workspace.sh     # Micro XRCE-DDS Agent and the message packages
scripts/build_sitl_dds.sh          # ArduCopter SITL with --enable-DDS

# ardupilot_gazebo has no script yet; it needs GStreamer, already in the shell
cmake -S external/ardupilot_gazebo -B build/ardupilot_gazebo \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build/ardupilot_gazebo -j"$(nproc)"
```

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

Two prerequisites were found and fixed while investigating. ArduPilot's output
range defaulted to 1000-2000 while the SDF maps 1100-1900, so a disarmed
vehicle drove its rotors backwards, turned slowly on the floor and failed the
compass check; `MOT_PWM_MIN`/`MOT_PWM_MAX` now match the model. `MOT_THST_EXPO`
is 1.0 because the simulated thrust curve is exactly quadratic.

The actuation and aerodynamics are not the cause. On the stand the same model
climbs 60 m under real ArduPilot control with symmetric throttle. The channel
map, rotation directions, `modelXYZToAirplaneXForwardZDown` and `gazeboXYZToNED`
are all identical to the Iris reference that flies.

The rotor model itself is the obstacle, and parameter nudging does not resolve
it. Three constraints conflict:

- The physical inertia of a 3 in propeller (izz 8.0e-07) makes the plugin's
  explicit velocity loop change rotor speed by 168 % of its target in a single
  step at the configured torque ceiling. The disarmed airframe tumbles at over
  1000 deg/s from that alone.
- Raising the rotor inertia stabilises the loop, but the rotor then stores real
  angular momentum: spin-up reaction reaches 0.36 N m per rotor, and a ten per
  cent asymmetry gives the 0.00038 kg m^2 airframe 5500 deg/s^2 in yaw.
- Lowering the joint damping twentyfold to cut yaw authority does not help,
  because the reaction above comes from inertia rather than damping.

A coherent redesign of the rotor drive is needed rather than further tuning.
The most promising direction is kinematic velocity control (`useForce` 0), which
removes the PID and its reaction torque entirely, paired with explicit yaw
torque so the airframe still has authority about the vertical axis.

What also remains is attitude tuning. `ardupilot_params.parm` sets only `FRAME_CLASS`
and `FRAME_TYPE`, so every gain comes from `copter.parm`, which targets a
vehicle of one to two kilograms. This airframe is 0.240 kg with a roll inertia
of 0.00022 kg m^2. Open item; see the backlog.

## AP_DDS Topics Never Appear in ros2

Symptom:

- the Agent log shows AP_DDS connecting and creating publishers and repliers
- `ros2 topic list` shows only `/parameter_events` and `/rosout`
- the check fails with "AP_DDS services did not appear"

Root cause:

`micro_ros_agent` has no domain option and does not follow `ROS_DOMAIN_ID`, so
it always joins the default domain. Setting `ROS_DOMAIN_ID` for a DDS test only
moves `ros2` away from the Agent and hides every `/ap/` topic.

Fix:

Do not set `ROS_DOMAIN_ID` in a test that talks to the Agent. Isolate concurrent
runs with the Agent's UDP port instead (`DDS_UDP_PORT`, see `dds_smoke.parm`).

Verification after fix:

`scripts/check_iris_dds_control.sh` had been given a ROS domain for isolation
and could no longer see the services. With the domain removed it passes again
and measures 584.19 m to 586.18 m.

## DDS Control Accepts Everything and the Cinewhoop Stays Put

Symptom:

- `/ap/prearm_check`, `/ap/mode_switch`, `/ap/arm_motors` and
  `/ap/experimental/takeoff` all return success
- `/ap/status` confirms `armed: true`
- commanded rotor speed reaches only the arm idle (260 rad/s) and falls back to
  zero, and Gazebo ground truth shows the airframe never leaves z = 0.03 m
- the same airframe takes off over MAVLink, and the Iris takes off over these
  same DDS services

Cause:

A leftover `simple_indoor_autonomy` node from an earlier run was still
publishing `/ap/cmd_vel`. `ros2 run` is a wrapper whose child does not die with
it, so killing the recorded PID left the node alive; it then commanded GUIDED
velocity into the *next* run's vehicle.

That is enough to prevent takeoff entirely. A velocity command replaces the
GUIDED TakeOff submode, and the position-control submodes call
`make_safe_ground_handling()` while `land_complete` is still true, so throttle
output stays at exactly zero. Every service still answers success, which is why
this reads as a vehicle or DDS fault rather than a stray process.

Diagnostics that settle it:

```bash
# Is anything already driving the vehicle?
ros2 node list | grep simple_indoor_autonomy
ros2 topic echo /ap/cmd_vel --once
```

The decisive evidence is in SITL's own dataflash log, which records the guided
target every cycle:

```bash
# GUIP Type=4 with a non-zero vX/vY is a velocity target, not a takeoff.
# CTUN ThO=0.000 with DAlt pinned at the ground altitude confirms the
# position controller was never given a climb.
python3 - external/ardupilot/ArduCopter/logs/<latest>.BIN <<'EOF'
from pymavlink import mavutil
m = mavutil.mavlink_connection(__import__("sys").argv[1])
while (msg := m.recv_match()) is not None:
    if msg.get_type() in ("GUIP", "CTUN", "MSG"):
        print(msg)
EOF
```

Fix:

- `scripts/check_forward_flight.sh` now `pkill`s the node and the ROS/Gazebo
  bridge by their full install paths, and refuses to start while a
  `/simple_indoor_autonomy` node is still in the ROS graph.
- `scripts/check_ros_graph.sh` had the same leak with `trajectory_publisher`.
  It was harmless in itself but ran in baseline CI, leaving one orphan per run.

Do not trust a service reply as proof that a command took effect. The demo node
now re-requests takeoff when the altitude does not actually rise, which is also
what finally made the sequence survive a slow EKF start.

## A Level Lidar Sees Nothing Above a Low Obstacle

Symptom:

- the autonomy demo takes off and then logs `Holding: no valid range in the scan`
- the bridged `LaserScan` is all `inf` in flight, but reads correctly on the ground

Cause:

`front_obstacle` stood exactly 1.0 m tall while the demo cruises at 1.0 m, so
the level front lidar passed over its top, and the world has no walls inside the
8 m maximum range. The node was right to hold: it genuinely could not see.

Fix:

Both obstacles in `indoor_test.sdf` now stand taller than the cruise altitude.
When adding geometry to that world, check it against the flight altitude rather
than only against the vehicle's resting height.

## A Velocity Command Is Not a Brake

Symptom:

- the autonomy demo stops for the wall exactly as designed, yet ends up far
  closer to it than the configured stop distance
- measured: it held 0.80 m from the obstacle and came to rest 0.16 m from it

Cause:

ArduPilot shapes horizontal motion on purpose. `PSC_NE_VEL_P` defaults to 2.0,
the acceleration limit `WPNAV_ACCEL` to 2.5 m/s^2 and the jerk limit to
5 m/s^3, which together coast about 0.6 m when a 0.5 m/s command drops to zero.
Measured from Gazebo ground truth at 59 Hz: speed decayed 0.50 to 0.15 m/s over
1.1 s, an effective 0.3 m/s^2, nowhere near the 2.5 m/s^2 limit.

This is not a defect. Smooth stops are the point of a camera platform, so the
fix is to decide earlier rather than to brake harder. `safe_forward_speed` now
takes a braking distance and stops at clearance plus braking distance, which
took the measured margin from 0.16 m to 0.82 m.

Worth knowing when measuring this: the vehicle also drifts about 0.35 m forward
during the guided takeoff itself, before any velocity command is published, so a
trajectory read after takeoff does not start at the origin.

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

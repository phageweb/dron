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

## A Healthy Sensor Topic That RViz Refuses to Draw

Symptom:

- `ros2 topic echo` on a bridged sensor shows real data at the expected rate
- the matching RViz display stays empty, with no error on the topic itself

Cause:

A Gazebo sensor stamps its messages with its own scoped name unless the model
sets `gz_frame_id`, so the front lidar published
`openipc_cinewhoop/front_lidar_link/front_lidar`. That frame is not in the tree
`robot_state_publisher` serves from the URDF, so every TF-using consumer has
nothing to transform into the fixed frame and quietly shows nothing.

The same mismatch is a simulation-only behaviour: a real driver publishes URDF
link names, so a node tuned against the simulation would meet a different frame
on hardware.

Fix:

Every sensor in `model.sdf` sets `gz_frame_id` to its URDF link, and
`scripts/check_sensor_interface.sh` fails if a bridged frame cannot be
transformed into `base_link`. Check the frame before the display settings:

```bash
ros2 topic echo --once --field header /openipc_cinewhoop/scan/front
ros2 run tf2_tools view_frames
```

## A Rotated Sensor Frame Points the Measurement the Wrong Way

Symptom:

- a downward rangefinder's reading appears in front of the drone in RViz
- the IMU reads -9.81 m/s^2 on z at rest instead of +9.81

Cause:

Two different conventions meet in this model. ArduPilotPlugin reads its IMU in
aircraft convention, x forward, y right, z down, so the sensor carries a 180
degree roll; ROS and AP_DDS use REP 103, x forward, y left, z up. Bridging the
aircraft-convention sensor gave ROS an inverted y and z that only hardware would
have revealed. Separately, both downward sensors measure along +X of their own
frame, so a frame left level with `base_link` describes a beam pointing forward.

Fix:

The model carries a second, unrotated `imu_ros` sensor for the bridge, and
`rangefinder_link` and `optical_flow_link` are pitched 90 degrees in the URDF to
match the SDF. Gravity at rest is the cheap test, and the interface check makes
it:

```bash
ros2 topic echo --once --field linear_acceleration /openipc_cinewhoop/imu
```

## A Parked Front Lidar Measures the Floor, Not the Room

Symptom:

- with the vehicle parked at the origin and no ArduPilot running, the front lidar
  reports 1.41 m straight ahead
- the world's only thing ahead is the front obstacle, whose face is 4.37 m from
  the lidar
- the same 1.41 m was reported before that obstacle was moved from x = 1.8 to
  x = 4.5, when its face was 1.67 m away, so the reading does not track the wall

Cause:

The lidar is grazing the floor. Parked, `front_lidar_link` sits 37 mm above the
floor surface, and the rendered fan is not perfectly flat: its lowest rays fall
by a small angle. For a sensor at height h whose rays depress by an angle phi,
the floor is struck at range `r = (h / phi) / cos(theta)`, which is a plane of
constant depth - exactly the shape measured. From h = 0.037 m and a depth of
1.412 m, phi comes out at 0.026 rad, about 1.5 degrees.

Evidence, in the order that settled it:

- the returns lie on a plane of constant depth, not at a constant range, so it
  is a surface perpendicular to the view axis rather than a ring
- the vehicle really is at the origin and level, and `gz model` confirms the
  loaded scene has the wall at x = 4.5 with the floor at the origin
- the reading is identical at 5 s and at 25 s, so it is not a half-loaded scene
- an obstacle moved to x = 1.0 is measured exactly right, at 0.867 m, which is
  1.0 less the 0.06 half-thickness and the lidar's own 0.073 m offset. Near
  geometry is fine; the floor return simply arrives before anything further
- spawning the vehicle higher moved the plane from 1.412 m to 1.267 m rather
  than removing it, which is `h / phi` changing, not a fixed clip distance

Consequences:

- **In flight nothing is affected.** At the demo's 1 m altitude the floor would
  be struck at about 38 m, far past the sensor's 8 m maximum, so no return comes
  back at all. `check_forward_flight.sh` measures a stop at x = 3.37 m with
  0.99 m of rotor clearance, summing to the 4.44 m where the world puts the wall.
- `scripts/check_front_lidar.sh` runs parked, so the range it sees is the floor.
  It proves the bridge delivers a finite range to the demo node, which is what it
  was written for, and it is not evidence about the room.
- The margin is thinner than it looks. The demo stops below 1.40 m and the parked
  floor return sits at 1.412 m. Raising the stop distance, or hovering much below
  0.3 m, would let the floor read as an obstacle.

Resolved, and by something else entirely. Choosing the LD06 put the sensor on a
mast above the propeller plane, 50 mm up instead of 2 mm, and `h / phi` grew with
it until the floor return fell past the sensor's range. Parked, the front lidar
now reports 4.39 m, which is the wall face at 4.44 m less the sensor's own 46 mm
offset. The diagnosis is left here because it predicts the same thing on
hardware: LDROBOT give the LD06 a pitching angle of 0 to 2 degrees, so a real
unit sitting 35 mm off the ground will see the floor somewhere between 1 and 4 m,
and only altitude takes it out of range.

## In Flight the Floor Becomes a Wall When the Drone Leans

The parked case above has a sibling that has not been dealt with, and it is the
more dangerous one. The LD06 is bolted to the airframe, so its scan plane leans
with the vehicle. Nose down by an angle, and the forward beams point at the
floor; the floor then returns a range like any wall would.

Where that lands, for a scan plane pitched by theta at height h, is the slant
range `h / sin(theta)` - the sensor reports distance along its own beam, which
is what the demo's threshold is compared against:

| Lean | at 1.0 m | at 0.5 m | at 0.3 m |
| ---: | ---: | ---: | ---: |
| 5° | 11.5 m | 5.7 m | 3.4 m |
| 10° | 5.8 m | 2.9 m | 1.7 m |
| 20° | 2.9 m | **1.5 m** | 0.9 m |
| 30° | 2.0 m | 1.0 m | 0.6 m |
| 35° | 1.7 m | 0.9 m | 0.5 m |

The demo stops below 1.40 m, so the bold cell is where the vehicle stops for the
ground. At its 1 m cruise it takes about 45 degrees of lean to get there, which
is far more than 0.5 m/s asks for. **Halve the altitude and 22 degrees is
enough**, and 22 degrees is not an aggressive manoeuvre.

Nothing in the code handles this today, and the simulation reproduces it
faithfully, because the Gazebo sensor is rigidly attached in exactly the same
way. That makes it testable before it is ever flown.

What the options are, worst to best:

- **A gimbal.** Correct, and out of the question at 42 g of lidar on a 306 g
  aircraft.
- **Cap the lean angle.** Cheap, and it only moves the problem: it caps speed
  too, and says nothing about flying low.
- **Tilt the mount up a few degrees.** Buys margin nose-down and spends it
  nose-up, where the ceiling then arrives instead.
- **Transform the scan and filter by height.** Every return becomes a point in a
  gravity-aligned frame using the vehicle's attitude, and anything below a
  height threshold is dropped as ground. This is the real answer, it handles
  roll as well as pitch, and the pieces already exist: the TF tree is correct
  and verified, and `/ap/pose/filtered` carries the orientation that
  `trajectory_publisher` already subscribes to.

Note that ArduPilot compensates proximity data with attitude in its own
avoidance layer, so if the LD06 is also wired to the flight controller, that path
and the ROS path handle this separately and can disagree.

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

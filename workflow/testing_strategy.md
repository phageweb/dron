# Testing Strategy

The project should prefer tests before or alongside implementation whenever the behavior is clear enough to specify.

## Priority

1. Unit tests for deterministic logic.
2. Integration tests for ROS 2 nodes, topics, services, launch files, and Gazebo bridges.
3. E2E tests for complete user-facing simulation flows.
4. CI/CD automation for every check that can run reproducibly under `nix develop`.

## Unit Tests

Use unit tests for:

- LaserScan filtering logic
- obstacle distance calculation
- autonomy state transitions
- parameter parsing
- geometry helpers
- topic name/remapping helpers

Expected tooling:

- Python: `pytest`
- Rust: `cargo test`

## Integration Tests

Use integration tests for:

- ROS 2 node startup
- publisher/subscriber wiring
- service client availability
- launch files
- `ros_gz_bridge` topic mapping
- ArduPilot DDS topic/service presence

Expected tooling:

- ROS 2 launch testing
- `pytest`
- shell smoke checks inside `nix develop`

## E2E Tests

Use E2E tests for:

- Gazebo starts with `indoor_test.sdf`
- custom cinewhoop model appears
- sensor topics are published
- TF tree is connected
- obstacle monitor receives front lidar data
- neither demo node mistakes the floor for an obstacle when the vehicle leans
- autonomy node arms/takes off/stops in the simulated environment
- one launch brings up Gazebo, the bridges, TF and the ArduPilot topics together

E2E tests may be slower and can be marked separately from fast checks.

The heavyweight ones are opt-in rather than part of `scripts/ci.sh`, because
they need the ignored `external/` builds of ArduPilot, `ardupilot_gazebo` and the
Micro XRCE-DDS Agent, which Nixpkgs does not provide:

| Check | What it proves |
| --- | --- |
| `scripts/check_sitl_gazebo.sh` | custom Gazebo state reaches SITL as JSON |
| `scripts/check_thrust_stand.sh` | the rotors and lift model produce a measured climb |
| `scripts/check_guided_takeoff.sh` | a free airframe arms, climbs and holds over MAVLink |
| `scripts/check_sitl_dds.sh` | the `/ap/` topic and service graph appears |
| `scripts/check_sitl_dds_control.sh` | the DDS service request path is accepted |
| `scripts/check_iris_dds_control.sh` | the upstream Iris reference flies over DDS |
| `scripts/check_forward_flight.sh` | the autonomy demo takes off, creeps and stops |
| `scripts/check_room_circuit.sh` | the demo turns at a wall and flies on instead of stopping |
| `scripts/check_room_mapping.sh` | the map built over that circuit is the room the world file describes |
| `scripts/check_unified_launch.sh` | one launch serves Gazebo, ArduPilot and TF |
| `scripts/check_attitude_estimate.sh` | AP_DDS reports the attitude the vehicle really has |
| `scripts/sweep_rate_gains.sh` | measures where the roll rate loop starts to oscillate |

A few more baseline checks cover the shape of the data rather than the graph:

| Check | What it proves |
| --- | --- |
| `scripts/check_model_consistency.py` | the URDF and the SDF describe the same drone |
| `scripts/check_sensor_interface.sh` | message types, frames, the rangefinder cone and the IMU axes match the spec |
| `scripts/check_sensor_dropout.sh` | a dead lidar stops the vehicle and is reported |
| `scripts/check_leaning_scan.sh` | a leaning vehicle does not report the floor as an obstacle |

All of them are cheap enough for every run. The consistency check needs neither a
simulator nor a ROS graph - it expands the Xacro and reads both files - and the
dropout check needs no simulator either: it publishes a scan from the command line and then stops, which is what a
disconnected sensor looks like from inside a node.

`check_attitude_estimate.sh` is the other half of the leaning check. That one
proves the demo rejects the floor *given* an attitude; this one proves the
attitude it is given is real. It parks the vehicle on `ramp_test.sdf`, a slope
tilted in both axes - 20 degrees of pitch and 10 of roll, so a roll/pitch swap
cannot hide behind matching numbers - and compares three things that must agree:
the world file, Gazebo's ground truth, and `/ap/pose/filtered`. Nothing arms and
nothing flies, which is the point: an attitude read from a parked vehicle is two
steady numbers rather than two streams to align during a transient.

The leaning check does need Gazebo, but not SITL and not ArduPilot. It runs over
`leaning_test.sdf`, a world whose only job is to hold the model static at 30
degrees nose-down and 0.60 m up, which is where the front lidar's forward beams
meet the floor. Both demo nodes are run twice over that one scan: once with the
rangefinder topic connected and once with it pointed at nothing, which is what an
unknown height looks like from inside a node. The blind pair must report the
floor at 1.17 m and the compensated pair must report nothing, and the blind half
is asserted first - without it the check would pass just as happily over an empty
scan. That pattern is worth copying: a rejection test needs a control that proves
there was something there to reject.

`scripts/check_topic_remap.sh` runs in baseline CI and additionally exercises the
service remapping when `external/dds_ws` is sourced, using
`scripts/fake_ardupilot_services.py` to stand in for ArduPilot. That harness is
worth reusing: it drives the whole autonomy state machine in seconds with no
Gazebo and no SITL.

The sweep is a measurement rather than a check: it has no pass or fail, it prints
a table and writes traces under `logs/rate_sweep/`, and it takes about a minute
per gain because each point boots the whole stack again to keep runs independent.
`EXTRA_PARAMS` appends parameters to every run, which is how a surrounding
setting gets taken out of the way for a control experiment.

Whatever these start, they must also clean up. A `ros2 run` wrapper's child
outlives the wrapper, and one leftover node publishing `/ap/cmd_vel` silently
prevents the next run from ever taking off, so a new check that launches a node
needs either a process-group kill or a targeted `pkill` on its install path.

## Verification Log

When a test cannot be automated yet, record the manual verification in [log.md](./log.md):

```text
Date:
Scenario:
Command:
Expected result:
Actual result:
Pass/fail:
Follow-up:
```

## NixOS Rule

All test commands should be runnable from:

```bash
nix develop
```

If a test requires external state, graphics, hardware, or a long-running simulator, document that requirement explicitly in the test name or workflow log.

## CI/CD Rule

When a test becomes stable and does not require manual GUI or hardware interaction, add it to [ci_cd.md](./ci_cd.md) and `scripts/ci.sh`.

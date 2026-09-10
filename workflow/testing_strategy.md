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
| `scripts/check_unified_launch.sh` | one launch serves Gazebo, ArduPilot and TF |

`scripts/check_topic_remap.sh` runs in baseline CI and additionally exercises the
service remapping when `external/dds_ws` is sourced, using
`scripts/fake_ardupilot_services.py` to stand in for ArduPilot. That harness is
worth reusing: it drives the whole autonomy state machine in seconds with no
Gazebo and no SITL.

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

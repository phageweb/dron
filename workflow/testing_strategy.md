# Testing Strategy

The project should prefer tests before or alongside implementation whenever the behavior is clear enough to specify.

## Priority

1. Unit tests for deterministic logic.
2. Integration tests for ROS 2 nodes, topics, services, launch files, and Gazebo bridges.
3. E2E tests for complete user-facing simulation flows.

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

E2E tests may be slower and can be marked separately from fast checks.

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

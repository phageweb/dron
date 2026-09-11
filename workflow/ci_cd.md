# CI/CD Pipeline

The project should use CI as soon as there is a reproducible Nix shell, even before the full ROS workspace exists.

## Current Pipeline

GitHub Actions workflow:

```text
.github/workflows/ci.yml
```

Current jobs:

- install Nix
- run `nix flake check --show-trace`
- enter the development shell with `nix develop`
- run `scripts/ci.sh`
- run the development environment smoke checks
- build and test the ROS workspace when ROS packages exist under `ros_ws/src`
- verify the ROS publisher/subscriber graph
- verify the URDF/Xacro TF tree without a GUI
- start Gazebo headlessly and verify bridged sensor topics
- verify the URDF and the SDF still describe the same drone
- verify the bridged sensors carry the specified types, frames and axes
- verify a dead lidar puts the demo nodes into a safe state
- verify a leaning vehicle does not report the floor as an obstacle

## CI Script

Entrypoint:

```bash
scripts/ci.sh
```

The script currently runs:

```bash
scripts/check_dev_env.sh
```

Then, when ROS packages exist:

```bash
colcon build
colcon test
colcon test-result --verbose
python3 -m pytest ros_ws/src/openipc_cinewhoop_demo/test
python3 scripts/check_model_consistency.py
scripts/check_ros_graph.sh
scripts/check_topic_remap.sh
scripts/check_sensor_dropout.sh
scripts/check_sensor_interface.sh
scripts/check_tf_tree.sh
scripts/check_gazebo_headless.sh
scripts/check_front_lidar.sh
scripts/check_leaning_scan.sh
```

The heavier SITL checks stay opt-in, because they need the ignored `external/`
builds. [Testing strategy](./testing_strategy.md) lists them and says what each
one proves.

## Test Levels Expected in CI

Fast checks on every push and pull request:

- Nix flake evaluation
- dev shell smoke check
- Python unit tests
- Rust unit tests, if Rust tools are added
- ROS package build
- ROS launch/unit tests that do not require a GUI

Slower or optional checks:

- sensor topic E2E checks
- ArduPilot SITL integration
- RViz/GUI smoke checks

These can become separate jobs later, for example:

- `unit`
- `ros-build`
- `gazebo-headless`
- `sitl-integration`
- `e2e-simulation`

## Rules

- CI must run through `nix develop` so local and CI environments stay aligned.
- Tests should be added before or alongside implementation when behavior is clear.
- If a CI failure requires a manual workaround, record it in [troubleshooting.md](./troubleshooting.md).
- If a check is skipped because the project is not ready yet, the skip must be explicit in the script output.

## Future Deployment

There is no deployment target yet. Later CI/CD can publish:

- generated documentation
- simulation artifacts
- test logs
- Gazebo screenshots or recordings
- ROS bag files from E2E runs

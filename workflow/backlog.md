# Backlog

## Milestone 1: Generic ROS 2 Shell on NixOS

- [x] Create `flake.nix`
- [x] Add initial CI/CD pipeline
- [x] Verify `nix develop`
- [x] Verify `ros2 --help`
- [x] Verify `colcon --help`
- [x] Verify `gz sim --versions`
- [x] Verify `rviz2 --help`
- [x] Verify `python3 -c "import rclpy"`

## Milestone 2: Generic ROS 2 Demo

- [x] Create `ros_ws/src`
- [x] Create the first Python ROS 2 package
- [x] Add unit tests for the first Python package
- [x] Run Python tests in CI
- [x] Add a publisher
- [x] Add a subscriber
- [x] Verify `ros2 node list`
- [x] Verify `ros2 topic list`
- [x] Verify `ros2 topic echo`

## Milestone 3: TF and RViz2

- [x] Create a simple TF tree
- [x] Run `robot_state_publisher`
- [ ] Run RViz2
- [ ] Save an RViz configuration
- [x] Verify `tf2_tools view_frames`

## Milestone 4: Gazebo Harmonic

- [ ] Run `shapes.sdf`
- [x] Add a headless Gazebo CI smoke test
- [x] List `gz topic -l` (needs `GZ_PARTITION=openipc_cinewhoop`)
- [x] Create a small custom world
- [x] Add a simple sensor topic
- [x] Bridge sensor topics into ROS 2 with `ros_gz_bridge`

## Milestone 5: Cinewhoop Model

- [x] Create ROS package `openipc_cinewhoop_description`
- [x] Create ROS package `openipc_cinewhoop_gazebo`
- [x] Create ROS package `openipc_cinewhoop_demo`
- [x] Create a URDF/Xacro model for RViz2
- [x] Create an SDF model for Gazebo
- [x] Add `base_link`, sensors, and motors
- [ ] Verify scale and the TF tree

## Milestone 6: Sensors

- [x] Add IMU
- [x] Add downward rangefinder
- [x] Add front lidar
- [x] Add camera
- [x] Verify ROS topics
- [ ] Verify RViz visualization

## Milestone 7: ArduPilot SITL

- [x] Verify SITL without Gazebo
- [x] Add repeatable local SITL/Gazebo smoke test (upstream build remains opt-in)
- [x] Verify the Iris smoke test with the Gazebo plugin
- [x] Connect the custom cinewhoop model
- [x] Verify motor mapping (matches the Iris reference; thrust path proven by `scripts/check_thrust_stand.sh`)
- [ ] Verify guided arm/takeoff (thrust verified on the stand; free flight flips, needs attitude tuning for a 0.240 kg airframe)

## Milestone 8: ArduPilot DDS

- [x] Build and run Micro XRCE-DDS Agent (local source workspace; not packaged in current Nixpkgs)
- [x] Build SITL with `--enable-DDS` (local source workspace)
- [x] Verify `/ap/*` topics
- [x] Verify `/ap/*` services
- [x] Verify arm/mode/takeoff through ROS 2 services

## Milestone 9: Demo Nodes

- [x] Implement `obstacle_monitor.py`
- [x] Verify subscriber behavior on the front lidar (`scripts/check_front_lidar.sh`, now in CI)
- [x] Implement `trajectory_publisher.py`
- [x] Implement `simple_indoor_autonomy.py`
- [ ] Verify slow 0.5 m/s forward flight
- [x] Verify stop behavior below 0.8 m from an obstacle

## Milestone 10: Real Drone Build

- [ ] Fill in the exact component table
- [ ] Weigh individual components
- [ ] Verify connectors and supply voltages
- [ ] Plan mechanical sensor placement
- [ ] Prepare a bench checklist without propellers
- [ ] Prepare mapping from simulation topics to real sensors

# Backlog

## Milestone 1: Generic ROS 2 Shell on NixOS

- [ ] Create `flake.nix`
- [ ] Verify `nix develop`
- [ ] Verify `ros2 --help`
- [ ] Verify `colcon --help`
- [ ] Verify `gz sim --versions`
- [ ] Verify `rviz2 --help`
- [ ] Verify `python3 -c "import rclpy"`

## Milestone 2: Generic ROS 2 Demo

- [ ] Create `ros_ws/src`
- [ ] Create the first Python ROS 2 package
- [ ] Add a publisher
- [ ] Add a subscriber
- [ ] Verify `ros2 node list`
- [ ] Verify `ros2 topic list`
- [ ] Verify `ros2 topic echo`

## Milestone 3: TF and RViz2

- [ ] Create a simple TF tree
- [ ] Run `robot_state_publisher`
- [ ] Run RViz2
- [ ] Save an RViz configuration
- [ ] Verify `tf2_tools view_frames`

## Milestone 4: Gazebo Harmonic

- [ ] Run `shapes.sdf`
- [ ] List `gz topic -l`
- [ ] Create a small custom world
- [ ] Add a simple sensor topic
- [ ] Bridge the topic into ROS 2 with `ros_gz_bridge`

## Milestone 5: Cinewhoop Model

- [ ] Create ROS package `openipc_cinewhoop_description`
- [ ] Create ROS package `openipc_cinewhoop_gazebo`
- [ ] Create ROS package `openipc_cinewhoop_demo`
- [ ] Create a URDF/Xacro model for RViz2
- [ ] Create an SDF model for Gazebo
- [ ] Add `base_link`, sensors, and motors
- [ ] Verify scale and the TF tree

## Milestone 6: Sensors

- [ ] Add IMU
- [ ] Add downward rangefinder
- [ ] Add front lidar
- [ ] Add camera
- [ ] Verify ROS topics
- [ ] Verify RViz visualization

## Milestone 7: ArduPilot SITL

- [ ] Verify SITL without Gazebo
- [ ] Verify the Iris smoke test with the Gazebo plugin
- [ ] Connect the custom cinewhoop model
- [ ] Verify motor mapping
- [ ] Verify guided arm/takeoff

## Milestone 8: ArduPilot DDS

- [ ] Run Micro XRCE-DDS Agent
- [ ] Run SITL with `--enable-DDS`
- [ ] Verify `/ap/*` topics
- [ ] Verify `/ap/*` services
- [ ] Verify arm/mode/takeoff through ROS 2 services

## Milestone 9: Demo Nodes

- [ ] Implement `obstacle_monitor.py`
- [ ] Verify subscriber behavior on the front lidar
- [ ] Implement `trajectory_publisher.py`
- [ ] Implement `simple_indoor_autonomy.py`
- [ ] Verify slow 0.5 m/s forward flight
- [ ] Verify stop behavior below 0.8 m from an obstacle

## Milestone 10: Real Drone Build

- [ ] Fill in the exact component table
- [ ] Weigh individual components
- [ ] Verify connectors and supply voltages
- [ ] Plan mechanical sensor placement
- [ ] Prepare a bench checklist without propellers
- [ ] Prepare mapping from simulation topics to real sensors

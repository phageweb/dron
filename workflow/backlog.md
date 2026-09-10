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
- [ ] Run RViz2 (launched by `display.launch.py`; needs a screen to confirm)
- [x] Save an RViz configuration (`cinewhoop.rviz`; visual check still needs a GUI)
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
- [x] Redesign the rotor drive onto `MulticopterMotorModel` fed from the plugin's `COMMAND` type
- [x] Fix the ground-truth attitude offset: the IMU sensor was missing the 180 degree roll into aircraft convention
- [x] Track down the intermittent NaN that crashed SITL (gone with the force PID removed)
- [x] Raise rotor speed and thrust so the controller has attitude margin
- [x] Calibrate `motorConstant` and `momentConstant` against real 3 in propeller
      data; thrust to weight is now 5.9 instead of 3.0 by construction
- [x] Scale the attitude rate gains to this airframe's authority, which is 7.7
      times a ten-inch quad's; stock gains saturated the rate loop
- [ ] Confirm the calibration on a thrust stand with the exact ducted propeller,
      rather than from published motor figures and textbook coefficients
- [ ] Tune the rate gains by a sweep rather than one authority-ratio calculation
- [x] Verify guided arm/takeoff (`scripts/check_guided_takeoff.sh`)

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
- [x] Guard against a stale scan; a dead lidar used to leave the last range in place
- [x] Give the demo node its own arm/mode/takeoff through the ArduPilot services
- [x] Verify slow 0.5 m/s forward flight (`scripts/check_forward_flight.sh`)
- [x] Find why DDS control cannot move the cinewhoop while MAVLink can and the Iris can
      (an orphaned demo node's `/ap/cmd_vel` replaced the GUIDED takeoff submode)
- [x] Stop with real clearance: the demo now decides at the wanted clearance plus
      the measured 0.6 m braking distance, which took the margin to the wall from
      0.16 m to 0.82 m. The braking itself is ArduPilot's deliberate motion
      shaping, so the decision moves earlier rather than the braking getting harder
- [x] Verify stop behavior below 0.8 m from an obstacle

## Milestone 11: Unified Launch

- [x] Bring Gazebo, both bridges, `robot_state_publisher`, RViz2, the Agent and
      SITL up from `sitl_gazebo.launch.py`
- [x] Make `sitl:=false` print how to run SITL in a separate terminal
- [x] Fix `display.launch.py`, where `rviz:=false` did not actually stop RViz2
- [x] Verify Gazebo and ArduPilot topics plus TF from one launch
      (`scripts/check_unified_launch.sh`)
- [ ] Confirm on a screen that RViz shows the model, TF and the lidar correctly

## Milestone 10: Real Drone Build

- [ ] Fill in the exact component table
- [ ] Weigh individual components
- [ ] Verify connectors and supply voltages
- [ ] Plan mechanical sensor placement
- [ ] Prepare a bench checklist without propellers
- [ ] Prepare mapping from simulation topics to real sensors

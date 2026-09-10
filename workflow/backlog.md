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

- [x] Enforce that the URDF and the SDF describe the same drone
      (`scripts/check_model_consistency.py`, in baseline CI). The airframe is
      written down twice and nothing linked the two files; the `rangefinder_link`
      rotation had already drifted between them

- [x] Create ROS package `openipc_cinewhoop_description`
- [x] Create ROS package `openipc_cinewhoop_gazebo`
- [x] Create ROS package `openipc_cinewhoop_demo`
- [x] Create a URDF/Xacro model for RViz2
- [x] Create an SDF model for Gazebo
- [x] Add `base_link`, sensors, and motors
- [ ] Verify scale and the TF tree

## Milestone 6: Sensors

- [x] Explain the static front-lidar reading: parked, the lidar sits 37 mm above
      the floor and the fan's lowest rays graze it, giving a constant-depth plane
      at h/phi. In flight the floor is out of range, so nothing is affected. The
      demo's 1.40 m stop distance and the 1.412 m floor return are closer than
      they look, which constrains raising either
- [x] Give the front lidar more ground clearance: the LD06's mast did it. Parked,
      it now reports the wall at 4.39 m rather than the floor at 1.41 m, so the
      stop distance is no longer bounded by an artefact


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
- [x] Tune the rate gains by a sweep rather than one authority-ratio calculation.
      Eleven flights put the oscillation onset between 0.044 and 0.05, where
      ringing goes from 5 sign changes per run to 141. `ATC_RAT_RLL_P` is 0.027,
      a little over half the onset (`scripts/sweep_rate_gains.sh`)
- [ ] Re-measure the onset on hardware. The simulation has no gyro noise, no
      frame resonance and no ESC lag beyond the motor model, so 0.027 is a
      ceiling to approach rather than a value to fly off the bench
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

- [x] Fill in the exact component table, and do it for three airframes rather than
      one, so the choice is a comparison instead of an assumption
      (`spec/realna_stavba_dronu/03_komponenty.md`)
- [x] Settle the airframe: CineLog30 V3 with the MicoAir H743 V2 stands, after
      comparing lighter alternatives. AP_DDS needs an H7 and no OpenIPC air unit
      runs on 1S. The project has no lightweight fallback as a result
- [x] Verify connectors and supply voltages from the datasheets; physically
      measuring them is step 2 of the bench checklist
- [x] Prepare a bench checklist without propellers
      (`spec/realna_stavba_dronu/04_bench_checklist.md`)
- [ ] Weigh individual components, which needs the parts on a scale
- [ ] Plan mechanical sensor placement, which needs the frame dry-fitted
- [x] Choose the front obstacle sensor: LDRobot LD06, imported. Nothing else in the build is blocked on a
      single decision this hard: LD06 is the only candidate that gives a real
      `LaserScan` but weighs about as much as half the airframe, while a
      VL53L5CX-class sensor keeps the mass but halves the range. The simulated
      front lidar has to be re-specified to it. Czech shops stock 360 degree
      lidars only in the RPLidar class, which starts at 110 g, so it is an import
- [x] Re-specify the simulated `front_lidar` to the LD06: the full 360 degrees at
      1 degree resolution, 10 Hz, 0.02 to 12 m, on a mast above the propellers.
      The demo nodes take a forward sector instead of the whole scan, because
      the real sensor reports what is behind the vehicle too
- [x] Raise the model mass to match the bill of materials: 0.306 kg, with the
      LD06's 42 g on `front_lidar_link` where it actually hangs. Hover throttle
      went to 0.46 and the rate gains had to be measured again, because the mast
      roughly doubles the pitch inertia
- [ ] Re-measure the gains once more if the video unit changes. The 0.306 kg
      assumes a RunCam WiFiLink 2; the EMAX Wyvern Link Alpha would make it
      about 294 g
- [ ] Dry-fit the LD06. It has to see forward past the ducts without meeting a
      propeller on a 128 mm frame, and that can still kill the choice
- [x] Revisit the 0.240 kg the simulation flies on. The published bill of
      materials sums to 238 g, but that omits wiring, screws and TPU, and the
      stock airframe's own dry weight puts the real figure nearer 264 g before
      any front sensor. Thrust to weight would go from 5.9 to about 5.3
- [x] Reconcile the wheelbase: 126 mm was an assumption, GEPRC publish 128 mm.
      Motor coordinates moved from 0.04455 m to 0.04525 m in both model files.
      The rate gains were deliberately not re-derived: the authority ratio moves
      from 7.7 to 7.8, which is inside the accuracy of the method that set them
- [ ] Order a ZH1.5T-4P to JST-SH adapter with the LD06, or plan to reterminate
      its cable. The lidar's connector is 1.5 mm pitch and AIO UART headers are
      usually 1.0 mm
- [ ] Watch the 5 V rail. The LD06 is a brushed motor drawing 300 mA at startup
      on the same BEC as the flow sensor and the receiver. Current is not the
      problem; noise might be
- [ ] Confirm the EMAX Wyvern Link Alpha over the RunCam WiFiLink 2. It is 11 to
      16 g lighter for the same job, which the mass goal prefers, but EMAX publish
      neither power draw nor range where RunCam quote up to 15 W. Those two
      figures are what is missing
- [x] Decide what to do about the 250 g class: there is no class to stay inside.
      Mass is a standing goal and a tie-breaker between equals, not a gate. It
      was silently deciding the front sensor by arithmetic, which is the wrong
      way round
- [ ] Close build phase 8, OpenIPC stream to `sensor_msgs/msg/Image`, with the
      WiFiLink 2 on a desk rather than on an airframe
- [x] Prepare mapping from simulation topics to real sensors; the mapping was
      already specified, so this verified it against the implementation
      (`scripts/check_topic_remap.sh`, in baseline CI)
- [x] Make the ArduPilot service names parameters, which the build spec requires
      and the node had hardcoded
- [x] Fix `trajectory_publisher`'s QoS: a RELIABLE subscription never matched
      AP_DDS's BEST_EFFORT pose publisher
- [x] Close the rest of the sim-to-hardware transition checklist, which turned up
      four defects that only real hardware would have shown
- [x] Give the Gazebo sensors `gz_frame_id`: the lidar, rangefinder and camera
      stamped scoped names that are not in the TF tree, so RViz could not draw
      them and a real driver would publish something else
- [x] Publish `/openipc_cinewhoop/range/down` as `sensor_msgs/msg/Range` through
      `range_adapter`, and make the simulated sensor a 15 degree fan, since a
      time-of-flight rangefinder returns the nearest surface in its cone
- [x] Bridge an unrotated IMU: the ArduPilot-facing sensor is in aircraft
      convention, so ROS was reading -9.81 on z where REP 103 and AP_DDS give
      +9.81
- [x] Make `use_sim_time` a launch argument; hardcoded true would have frozen
      the demo nodes' clocks on hardware and silently disabled the stale-scan guard
- [x] Verify the safe state on sensor dropout (`scripts/check_sensor_dropout.sh`)
- [x] Add `scripts/check_sensor_interface.sh` to baseline CI, which checks the
      shape of the sensor data rather than the names on the graph

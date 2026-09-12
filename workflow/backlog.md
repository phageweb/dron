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

- [x] Compensate the front scan for vehicle attitude in `simple_indoor_autonomy`.
      Returns are projected into a gravity-aligned frame using the pose's roll
      and pitch, and dropped when they work out to be the floor. The height comes
      from the downward rangefinder, and an unknown height discards nothing
- [ ] Decide how lidar data reaches the ground. ELRS telemetry carries hundreds
      of bytes per second and the scan needs 108 kbit/s raw, so it has to ride
      the OpenIPC WiFi link beside the video - about 3.6 per cent of an 8 Mbit/s
      stream. wfb-ng has a data channel; nobody has configured or measured it
- [x] Lean the vehicle in the simulator and assert the floor is not reported
      (`scripts/check_leaning_scan.sh`, in baseline CI). `leaning_test.sdf` holds
      the model static at 30 degrees nose-down and 0.60 m up, where the forward
      beams meet the floor at 1.17 m - inside the demo's 1.40 m stop threshold.
      Both nodes are run again with the rangefinder topic pointed at nothing,
      and that blind pair must stop for the floor; without that control the
      check would pass over an empty scan
- [x] Give `obstacle_monitor` the same compensation, so it no longer reports the
      floor as the nearest obstacle while the autonomy node ignores it
- [x] Make the demo latch why it is holding rather than that it is holding. A
      vehicle that stopped for a stale scan and then stayed stopped for a wall
      logged only the first reason, so the log said the lidar was dead long
      after it had recovered
- [x] Check that AP_DDS reports the attitude the vehicle really has, which the
      floor rejection trusts and nothing tested. `ramp_test.sdf` parks the
      vehicle on a slope tilted in both axes, and
      `scripts/check_attitude_estimate.sh` compares the world file, Gazebo's
      ground truth and `/ap/pose/filtered`: all three agree to 0.01 degrees.
      Parked rather than flying, because a steady attitude is two numbers
      instead of two streams to align during a transient
- [x] Stop the model pinning itself to one world. Its five sensors declared
      topics containing `/world/indoor_test/`, so in any other world
      `ArduPilotPlugin` could not find the IMU, never sent SITL a state frame,
      and SITL resent servos forever saying only "No JSON sensor message
      received". Sensors now declare no topic, `gz_bridge.yaml` is a template
      rendered from the launched world's own name, and
      `check_model_consistency.py` fails if a world name reappears in one
- [x] Guard the floor rejection's own two inputs for freshness. The scan had a
      staleness guard and the attitude and height did not, although neither
      arrives with the scan: the pose comes from the flight controller over DDS
      and the height from a different sensor, so either can stop while the lidar
      stays healthy. Both nodes now switch the rejection off and say why
      (`compensation_height`, `compensation_timeout_s`, default 0.5 s against a
      30 Hz pose and a 20 Hz rangefinder)
- [x] Correct the downward rangefinder for lean. It reports slant range, so at
      30 degrees it read 0.639 m where the sensor was 0.551 m up - 16 per cent,
      growing as 1/cos. `height_from_slant_range` undoes it, and
      `check_leaning_scan.sh` checks the result against where Gazebo says the
      link is rather than against the formula: 0.554 m against 0.551 m, inside
      the sensor's own 0.01 m range resolution
- [x] Exercise the roll term of the projection on a scan Gazebo produced.
      `banked_test.sdf` holds the vehicle at 25 degrees of roll and 20 of pitch,
      0.60 m up, where the floor arrives in the forward sector at 1.21 m off the
      right wing and 6.2 m off the left. `leaning_test.sdf` could not do this:
      the pitch term is even in the bearing, so a scan indexed the other way
      round the circle gives identical numbers there, while the roll term is odd
      and does not. With the roll sign flipped, `leaning_test` still passes and
      `banked_test` fails
- [x] Fly a circuit of the room. `simple_indoor_autonomy` gained a `TURN`
      state: blocked ahead, it yaws towards whichever side has more room and
      goes on. Off by default, because stopping for the wall is the behaviour
      `check_forward_flight.sh` verifies and flying past it is a second thing to
      ask for. `room_test.sdf` is a closed 8 by 6 m room and
      `scripts/check_room_circuit.sh` flies it: 630 degrees of turning, closest
      approach to a wall 0.75 m
- [x] Give the circuit something to produce. It flew a room and kept nothing;
      `occupancy_mapper` turns the scans into a 2D occupancy grid in the flight
      controller's local frame, published as `nav_msgs/msg/OccupancyGrid` on
      `/openipc_cinewhoop/map`. Log-odds rather than a flag, so repeated
      evidence accumulates and a single spurious return is not permanent, and
      unknown is kept distinct from fifty-fifty - which is the only thing that
      says where the vehicle has actually been. It skips a scan outright when
      the pose is stale or the floor rejection is off: the other two nodes can
      fall back on holding, and a wall drawn in the wrong place stays there
- [x] Check the map against the room rather than against itself.
      `scripts/check_room_mapping.sh` flies the same circuit with the mapper
      running and measures the result against the walls read out of the world
      file: all four walls mapped along 100 per cent of their length, wall cells
      0.050 m off the wall at the median and the 90th percentile - exactly the
      half-cell that quantisation costs - and no occupied cell anywhere in the
      middle of an empty room. That one comparison covers the scan's angular
      convention, the yaw the returns are turned by, the ray casting and the
      EKF's own position, which nothing had checked before: every earlier check
      asked about attitude or about a distance the vehicle did not need to know
      where it was to get right
- [x] Root the TF tree in the world. `pose_tf_broadcaster` publishes
      `map` -> `base_link` from `/ap/pose/filtered`, which is what the occupancy
      map was stamped in and nothing reached. `sitl_gazebo.launch.py` starts it
      and `check_unified_launch.sh` fails without it, so the launch that claims
      to serve TF now serves a tree attached to something
- [x] Ignore `/ap/pose/filtered`'s own `header.frame_id`, which says `base_link`
      and is wrong: AP_DDS fills the body from
      `get_relative_position_NED_home` swapped into ENU, so the content is where
      base_link is relative to home. A pose saying where base_link is cannot be
      expressed in base_link or it would be zero for ever, and anything
      believing the label pins every mapped return to the vehicle
- [x] Check the EKF's position and yaw against ground truth, neither of which
      anything had done. `check_attitude_estimate.sh` parks the vehicle on a
      ramp, and a parked vehicle at the origin says nothing about position;
      a ramp cannot be tilted in yaw either, so yaw was the one axis never
      compared against truth. `scripts/check_map_frame.sh` flies the circuit and
      compares `map` -> `base_link` against Gazebo: 0.012 m at the median,
      0.046 m at worst, yaw 0.01 degrees at the median. With the yaw sign
      flipped it fails at 179.5 degrees while the position half still passes
- [ ] Run the simulation on one clock. There are two: Gazebo's `/clock`, and
      every sensor message the bridge carries, count seconds from when the
      simulator started, while AP_DDS stamps `/ap/pose/filtered` with
      ArduPilot's UTC. Measured in the same instant: `/clock` 22.3 s, the front
      scan 22.3 s, the pose 1789156172. Nothing compares stamps across the two
      today - every node takes its ages from its own clock at the moment a
      message arrives - so nothing is broken, but anything that did would be
      wrong by 56 years. `AP_DDS_CLOCK_SUB_ENABLED` is on for SITL and AP_DDS
      subscribes to `/clock`, so this is meant to work and does not; the topic
      name in `AP_DDS_Topic_Table.h` is `"/clock"` for the subscriber and
      `"clock"` for the publisher, which is where to look first
- [ ] Confirm on a screen that RViz draws the occupancy map. The config has the
      display and the transform now exists, but the Fixed Frame is `base_link`
      so the room moves with the vehicle rather than standing still; `map` is
      the frame to watch it in, and changing the default would break
      `display.launch.py` on its own, where no `map` frame exists
- [x] Ask the coverage question somewhere it is a question. An empty convex room
      is the easy case: the LD06 sweeps the whole circle and reaches 12 m, so
      the vehicle maps 96 per cent of an 8 by 6 m room almost as soon as it is
      airborne, whatever path it flies. `cluttered_room.sdf` puts two things in
      the way - a pillar whose shadow sweeps across the room and fills itself in,
      and a dogleg enclosure whose pocket no ray through its door can reach - and
      `scripts/check_room_coverage.sh` flies the circuit and measures the
      enclosure's inside separately from the room. The current rule reads 90 per
      cent of the room and 77 to 80 of the enclosure, having never once gone
      inside it: closest approach 0.60 m in every run
- [x] Make that world actually occlude, which took three shapes and two
      measurements to get right. An alcove 4.5 m wide and 1.45 m deep read 94
      against the room's 96; a plain 2.8 m enclosure behind a 1.6 m door read 97
      against 94, *better* than the room it stands in, on a flight that never
      approached it. A doorway is an aperture rather than a pinhole: each point
      outside admits a different wedge, and their union over a circuit is very
      nearly everything. `inner_baffle` turns the inside into a dogleg and the
      figure falls to 77. The check asserts that too now - an enclosure over
      88 per cent on a flight that stayed outside fails, because the vehicle
      cannot have got better and the geometry can only have stopped hiding
- [x] A rule for where to fly that is better than "turn towards the roomier
      side". `frontier_explorer` reads the map for floor that touches unknown
      space and says which opening to head for; the demo steers at it and is
      otherwise unchanged. 96 per cent of the enclosure on both flights with it,
      against 80 for the reactive rule, which never went in at all. It took two
      further pieces, and each was named by the flight that failed without it:
      the clearance rule had to stop being a cone, and the explorer had to say
      how to get there rather than only where to go
- [x] Decide what is in the way by the swath the vehicle flies rather than by a
      cone. A 60 degree cone at the 1.7 m the demo wants clear is 1.7 m across,
      so no opening narrower than that could ever read clear - on a vehicle
      0.167 m wide. The explorer chose the 1.6 m door eight times in one flight
      and the demo turned away at 1.35 to 1.40 m every time, which was
      arithmetic and not bad luck. `nearest_in_corridor` reports the along-track
      distance of what lies within the rotor tips plus a margin, so a wall still
      stops the vehicle at the same distance and a doorjamb it would pass
      cleanly no longer does. The width is the model's own and
      `check_model_consistency.py` fails if either node's copy drifts from it
- [x] Give the explorer a way there, not only a destination. Publishing the
      frontier itself put the vehicle's nose on a line that crosses the wall
      beside the door, so it entered the enclosure in one flight out of two and
      that one was the line happening to pass through the opening. One
      breadth-first sweep over free cells, with the walls grown by what the
      vehicle needs, ranks openings by the distance actually flown and rules out
      the ones there is no way to; the published point is one stopping distance
      along the route. It also retired the timeout that used to guess an opening
      was "probably behind a wall", because the sweep answers that outright
- [x] Measure what the demo makes of a table, which is the everyday shape of
      what one scan plane misses. `table_room.sdf` and
      `scripts/check_table_height.sh`: the table is never a surface in the map -
      four to seven of the 126 cells it stands on, at either height - and what
      does come back is its outline, because a slice of a table is where the
      plane crosses its legs and its rim. The expected story, unseen at 1.00 m
      and seen at 0.50 m, is not what happens: the plane tips with the airframe,
      so at 0.90 m range 18 degrees of nose-down reaches a table the level plane
      passes 0.28 m over, and braking does that
- [ ] Give the vehicle a way to know a table is a table, which one plane cannot.
      A tilted or nodding lidar, or a depth camera, plus a map with more than
      one layer, plus frontier and clearance reasoning that works in it. That is
      a milestone rather than a task, and until it exists the demo can only say
      something stands about there
- [ ] The floor rejection's margin is a fraction of the height it is flown at,
      and nothing says so. A return is called floor once it works out below
      `ground_margin_m` of 0.25 m, so at the demo's 1.00 m the lidar has 0.80 m
      to give away and a return 3 m out survives a 15.5 degree nose-down. Flown
      at 0.50 m it has 0.30 m, and the same return is discarded at 5.7 degrees -
      less than the vehicle pitches to get moving. Low flight therefore throws
      away real obstacles at range, quietly, exactly where flying low is what
      the job needed. The margin wants to be a fraction of the height, or the
      rejection wants the return's height rather than its drop; either way it is
      a number that was chosen at one altitude and is used at all of them
- [ ] The corridor is the swath of a vehicle going forwards, which is all this
      demo ever does. A sideways or diagonal command would need it pointed along
      the commanded velocity rather than along the nose, and nothing currently
      says so out loud
- [ ] `obstacle_monitor` still reports the nearest return in a cone while the
      demo decides on the corridor. That is defensible - one is a proximity
      warning and the other is a decision - but it means the log can say an
      obstacle is 0.9 m away while the vehicle correctly flies past it, and
      nothing in the monitor's output explains why
- [ ] Place each return with the pose the scan was taken at. The mapper uses the
      latest pose when the message arrives, and the two are tens of milliseconds
      apart; turning at 0.4 rad/s that is a couple of degrees, which at 4 m is
      the 0.15 m by which the worst wall cells overshoot while the median stays
      at the half-cell. Harmless in an empty room and the thing that smears a
      map built while turning faster
- [x] Give the rejection the lidar's height rather than the rangefinder's. The
      two are 26 mm apart along x and 66 mm along z, which level was 66 mm of
      height thrown away and leaning is less, because the offset rotates with
      the airframe. `body_point_height` is the third row written once and used
      twice, for a return in the scan plane and for the offset. The numbers are
      parameter defaults rather than a TF lookup, and
      `check_model_consistency.py` reads them out of the nodes and fails if the
      model moves either sensor - the same guard that keeps the URDF and the SDF
      together. Both worlds now assert the height against `front_lidar_link`
      rather than `rangefinder_link`, which is the property itself
- [x] Start `range_adapter` in the flight checks. Neither
      `check_forward_flight.sh` nor `check_room_circuit.sh` ever did, so
      `/openipc_cinewhoop/range/down` had no publisher, the demo node had no
      height, and every one of those flights ran with the floor rejection off.
      The forward flight check asserted the rejection never switched off during
      the flight and passed, because a rejection that was never on cannot be
      seen switching off; it now asserts it switched on first
- [ ] The attitude check is still simulation agreeing with simulation: SITL's
      EKF is fed a noiseless IMU, so it proves the convention rather than the
      accuracy. A real flight controller on a real ramp is what would test the
      estimate itself


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

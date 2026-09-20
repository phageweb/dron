# Progress Log

## 2026-09-01

- Created the `spec/` folder.
- Split the specification into two tracks:
  - generic ROS 2 on NixOS
  - real OpenIPC cinewhoop build
- Added a simulation plan for a custom 3" cinewhoop Gazebo model.
- Added a verification plan for ROS 2, Gazebo, RViz2, ArduPilot SITL, and DDS.
- Added a tooling review based on community size and maintenance status.
- Created the `workflow/` folder as the working backlog and troubleshooting log.
- Started Milestone 1.
- Added the first `flake.nix` using `nix-ros-overlay` for ROS 2 Jazzy.
- Added `colcon-defaults.yaml`.
- Added `scripts/check_dev_env.sh` as the repeatable development-shell smoke check.
- Added `.github/workflows/ci.yml`.
- Added `scripts/ci.sh` as the CI entrypoint.
- Added [CI/CD Pipeline](./ci_cd.md) documentation.

## 2026-09-08

- Verified `nix flake check --no-build`; the development-shell derivation evaluates successfully.
- Ran the deterministic Python unit tests for `openipc_cinewhoop_demo`: 2 passed.
- Added `.gitignore` entries for colcon and Python-generated artifacts.
- Started the full `nix develop -c scripts/ci.sh` check. Its first run needed to build the large ROS/Gazebo/RViz closure on the configured remote Nix builder, so it was stopped before the smoke checks began. The full CI result remains unverified.
- Completed `nix develop -c scripts/ci.sh`: ROS 2, colcon, RViz2, Gazebo Harmonic, and `rclpy` smoke checks all passed; all three workspace packages built successfully.
- Added the demo package's deterministic `pytest` suite to `scripts/ci.sh`, because `colcon test` currently discovers no tests for this ament-Python package. The two unit tests pass when invoked with `python3 -m pytest`.
- Verified the ROS graph in an isolated local domain: `trajectory_publisher` appears in `ros2 node list` and converts a published `PoseStamped` into a `Path` on `/openipc_cinewhoop/path`. Added this as `scripts/check_ros_graph.sh` and run it from CI.
- Ran the full CI again after adding the ROS graph test: all three packages build, the two `pytest` tests pass, and the graph smoke test passes. The one-shot publisher now waits for its echo subscriber before publishing, preventing a DDS discovery race.
- Ran `gazebo.launch.py` headlessly for 20 seconds: Gazebo loaded `indoor_test`, the cinewhoop model and all configured sensors initialized, and `ros_gz_bridge` created the expected ROS topics. Added `scripts/check_gazebo_headless.sh` to assert those topics; it now runs in CI.
- Completed the full CI with the Gazebo smoke test enabled: all three packages build, both Python unit tests pass, the ROS graph smoke test passes, and the headless Gazebo test finds `/clock`, IMU, front-lidar, down-rangefinder, and camera image topics. The Gazebo test terminates its entire process group cleanly.
- Verified the URDF/Xacro TF tree without a GUI: `robot_state_publisher` starts and `tf2_tools view_frames` reports `base_link` as the parent of the IMU, front lidar, rangefinder, camera, and motor frames; the camera optical frame is a child of `camera_link`. Added `scripts/check_tf_tree.sh` to CI. `display.launch.py` now accepts `rviz:=false` for this headless mode.
- Completed CI with the TF tree test enabled: package build, Python tests, ROS graph test, TF-tree test, and Gazebo bridge test all pass.
- Deferred an automated `gz topic -l` assertion: in this environment the direct Gazebo Transport discovery query can block despite the active simulator and working ROS bridge. The headless test continues to assert the five externally consumed ROS topics; raw Gazebo topic discovery remains a separate backlog item.
- Stabilized the ROS graph smoke test after a DDS discovery race: it now waits until the `Path` echo subscriber is visible before publishing, and assigns each run an isolated ROS domain. Three consecutive direct runs and the subsequent complete CI run passed.
- Attempted to promote the front-lidar message to the headless CI smoke test. The bridge topics appear, but Ogre sensor rendering may initialize after the ten-second message timeout; keep actual sensor-message validation as a longer E2E test rather than making baseline CI flaky.
- ArduPilot SITL is not yet runnable because neither the ArduPilot source tree nor `ardupilot_gazebo` is present or declared in the flake. Continued with the ROS demo: extracted the stop/forward decision into `safe_forward_speed` and added unit coverage for missing scans, sub-threshold obstacles, and the 0.8 m boundary.
- Ran the expanded demo test suite in `nix develop`: 5 passed. The backlog now distinguishes completed implementation and unit-verified stop behavior from the remaining live-sensor and SITL flight checks.
- Cloned the official ArduPilot (`8b9ea700`) and `ardupilot_gazebo` (`082a0fe2`) sources into ignored `external/` for local SITL work. The first SITL readiness check found the missing Python `pexpect` dependency; added it to the Nix shell before continuing dependency discovery.
- `sim_vehicle.py --help` now passes and exposes both JSON and DDS options. `./waf configure --board sitl` also passes. The `ArduCopter` build is currently blocked by GCC 15 treating an upstream `AP_Scripting` generator warning as an error (`var_type_name may be used uninitialized`); use a supported older GCC only for the SITL build before retrying.
- Added GCC 14 to the Nix shell; it becomes the default `gcc/g++` and ArduPilot SITL configuration succeeds with it. The `ardupilot_gazebo` configuration reaches its final dependency check and currently needs GStreamer (`gstreamer-1.0` and `gstreamer-app-1.0`); added the Nix GStreamer runtime and base plugins before retrying.
- With GStreamer present, `ardupilot_gazebo` configures and builds successfully against Gazebo Harmonic. Produced `build/ardupilot_gazebo/libArduPilotPlugin.so` and `libParachutePlugin.so`; the next verification is a short standalone ArduCopter SITL start before connecting it to Gazebo.
- Completed the ArduCopter SITL build after locally initializing the upstream scripting generator's `var_type_name` pointer. A 12-second standalone `--model JSON` smoke run started ArduCopter, opened the JSON control endpoint on `127.0.0.1:9002`, exposed MAVLink TCP port `5760`, and waited for a simulator connection. Marked standalone SITL verification complete.
- The first Iris reference integration attempt loaded the Gazebo model/plugin but did not start SITL: `sim_vehicle.py` invokes an `xterm` wrapper, and its fonts are unavailable in this environment. Avoid that UI-only wrapper by launching the verified `arducopter` binary directly with the Gazebo-Iris parameter file in the next attempt.
- Diagnosed the apparent Iris SITL/Gazebo failure: the direct `arducopter` run was waiting for a MAVLink TCP client on `SERIAL0`, not for Gazebo. Setting `--serial0=udpclient:127.0.0.1:14550` removes that unrelated blocking wait. The reference Iris run then logged `JSON received:` in SITL and `ArduPilot controller has reset` in Gazebo, the latter occurring only after the plugin has detected a valid ArduPilot servo packet.
- Added the same `ArduPilotPlugin` JSON state interface to the custom `openipc_cinewhoop` model, with its existing IMU (`imu_link::imu`) and the standard ENU/FLU-to-NED/FRD transforms. The repeatable `nix develop -c scripts/check_sitl_gazebo.sh` test passed: custom Gazebo state reached SITL as JSON and the plugin detected its controller. The script intentionally requires the ignored local `external/` sources and build outputs, so baseline ROS CI remains independent of heavyweight upstream builds.
- Replaced `sitl_gazebo.launch.py`'s old scaffold message with a real Gazebo + JSON SITL launcher. It defaults to the workspace-local ignored upstream build paths and accepts `ardupilot_dir:=...` and `plugin_dir:=...` overrides. The custom model currently exchanges state only; its visual-only fixed motor links have no thrust model, so motor mapping and guided takeoff remain explicitly incomplete.
- Added four revolute 3-inch rotor links to the custom model, eight paired `LiftDrag` blade surfaces, four `ApplyJointForce` systems, and Quad-X channel controls in the ArduPilot plugin. The SDF validates with `gz sdf -k`, the custom SITL/Gazebo handshake still passes, and the ordinary headless Gazebo smoke test passes after a fresh package install. The 1600 rad/s scale and 0.00045 m² blade area are initial physical estimates, not a validated motor calibration; motor mapping and takeoff checks remain open.
- Completed the full standard CI after the SITL and rotor-model work: all three ROS packages build; five deterministic Python tests, the ROS graph smoke test, TF-tree smoke test, and headless Gazebo/bridge smoke test pass.
- Built the official `micro_ros_agent` Jazzy source plus `micro_ros_msgs` and ArduPilot's `ardupilot_msgs` in ignored `external/dds_ws`; its UDP transport smoke test passes. Added repeatable source-workspace and Agent smoke scripts. This remains opt-in and outside baseline CI because Nixpkgs does not package the Agent.
- Built Micro-XRCE-DDS-Gen with JDK 17 (the upstream Gradle 7.6 project is incompatible with JDK 21), then rebuilt ArduCopter SITL with `--enable-DDS`; Waf reports DDS enabled and produces `build/sitl/bin/arducopter`. Current generator output omits the C++ constants assumed by the selected ArduPilot checkout and no longer accepts its preallocation flag; the checked local ArduPilot source has a SITL-only compatibility adjustment for those API mismatches. `/ap/*` topic/service checks still require a live joined Agent + SITL run and remain open.
- Ran the locally built Micro XRCE-DDS Agent and DDS-enabled ArduCopter SITL together. ROS 2 discovered the expected AP_DDS graph, including `/ap/time`, `/ap/status`, sensor/control topics, and the `/ap/prearm_check`, `/ap/arm_motors`, `/ap/mode_switch`, and `/ap/experimental/takeoff` services. Added the repeatable opt-in `scripts/check_sitl_dds.sh` smoke test; arm, mode, and takeoff service calls remain to be validated.
- Added `geographic_msgs` to the Jazzy development shell because ArduPilot's upstream DDS takeoff test uses `GeoPoseStamped` to confirm altitude. In the standalone internal-SITL test, `/ap/prearm_check` reports the vehicle armable and `/ap/mode_switch` accepts GUIDED (`mode=4`), but `/ap/arm_motors` returns `false`; this remains open. A full Gazebo cinewhoop attempt receives live AP_DDS geopose telemetry, but did not complete the upstream takeoff assertion within its bounded run. Treat DDS graph discovery as verified and actual arm/takeoff as still incomplete.
- Diagnosed the standalone DDS arm response using a local MAVLink client: the initial arm request arrives before EKF has established home (`Arm: AHRS: waiting for home`). After that initialization completes, `/ap/prearm_check`, GUIDED mode switch, arm, and the 2 m takeoff request all return success. Added `scripts/check_sitl_dds_control.sh`, which retries arm while EKF initializes and verifies the complete service-request path. This verifies DDS service handling; actual physical ascent and motor mapping remain Milestone 7 work.
- Ran the DDS control sequence against the custom Gazebo cinewhoop: the model provides live JSON state and AP_DDS geopose telemetry, and the ROS 2 service requests are accepted. During the bounded post-takeoff observation the reported altitude remained about 584.05 m, so no actual ascent is yet proven. Motor-command propagation, rotor directions, and thrust calibration remain the next investigation; do not mark guided flight complete.
- Found and fixed a concrete Gazebo physics configuration defect: all eight custom `LiftDrag` systems used scoped rotor names that do not exist on the top-level cinewhoop model, so Gazebo logged that they generated no forces. The model now uses its local `rotor_*` links and adds `JointStatePublisher`; SDF validation passes and Gazebo loads all lift systems without link errors. A repeated DDS takeoff still measured no altitude increase, so actual ascent remains unverified and needs rotor-speed/thrust calibration. Direct Gazebo Transport joint-state discovery and the JSON SITL secondary MAVLink channel did not yield a usable motor-speed stream in this headless environment.
## 2026-09-09

- Added `scripts/check_front_lidar.sh`, a bounded 45-second E2E check which starts headless Gazebo, the ROS bridge, and `obstacle_monitor`, then requires a valid `LaserScan` result. The bridge topic and monitor subscription appear, and Gazebo initializes Ogre2 and advertises the IMU, but the render-based front lidar produces no message in that window. This is a concrete headless rendering limitation in the current environment rather than proof that the subscriber is correct; keep the live-lidar backlog item open and do not add this nondeterministic check to baseline CI.
- Ran the complete DDS service flight sequence on the unmodified upstream Iris reference model: it became armable, entered GUIDED, armed, accepted a 2 m takeoff, and its AP_DDS geopose altitude changed from 584.19 m to 586.19 m. This isolates the cinewhoop's unchanged altitude to its own motor/aerodynamic setup rather than the Agent, DDS services, SITL, Gazebo, or the test environment. Added `scripts/check_iris_dds_control.sh` as the repeatable opt-in regression check; it requires at least one metre of measured ascent.
- The first script execution completed its flight assertion but the `setsid` process-group cleanup kept the development-shell runner open after all visible simulation processes had gone. The test now follows the established direct-child `SIGINT` cleanup pattern used by the other local SITL checks; rerun is the next verification step.
- Diagnosed the cinewhoop takeoff path with a temporary local-only upstream plugin trace. After GUIDED, arm, and takeoff, ArduPilot continuously sent PWM 1949/1949/1949/1950 and the plugin produced velocity targets +1600/+1600/-1600/-1600 rad/s. The unchanged geopose is therefore not a missing motor command or channel mapping. Added explicit inertials to every fixed sensor/motor link and set the base link to 0.200 kg so the assembled SDF mass is exactly 0.240 kg (`0.200 + 0.014 + 0.020 + 0.006`). The SDF validates, but the repeated takeoff still did not climb (584.50 m to 584.41 m), so the remaining fault is in rotor/aerodynamic calibration. Restored the local upstream plugin source from the temporary diagnostics.
- Isolated the Iris DDS flight regression check in ROS domain 78 after a later manual demonstration detected a stale pre-takeoff altitude. This prevents any concurrent/local DDS session from being mistaken for the newly launched test vehicle.
- A subsequent live Iris demonstration is currently blocked by external local-port ownership: the Agent cannot bind UDP/20199 and SITL cannot bind MAVLink TCP/5762, while process inspection from this workspace does not expose an owning `micro_ros_agent`, `arducopter`, or Gazebo process. Do not kill an unidentified external process; release those ports or restart the hosting session before rerunning `nix develop -c scripts/check_iris_dds_control.sh`.

- Found the root cause behind both "Gazebo Transport does not work headlessly" observations: `gazebo.launch.py` pins the simulator and bridge to `GZ_PARTITION=openipc_cinewhoop`, and Transport only discovers peers inside the same partition. A CLI started from an ordinary shell therefore sees an empty graph. With the partition exported, `gz topic -l` returns 25 topics instead of 0, including the model `joint_state` stream that the motor-mapping work needs. Recorded in [troubleshooting](./troubleshooting.md); this closes the `gz topic -l` backlog item.
- Re-ran `scripts/check_front_lidar.sh` unchanged: it passes. Three consecutive runs each reported the same 1.41 m nearest obstacle, and a direct read of the bridged scan showed 61 finite ranges between 1.413 m and 1.626 m, consistent with the world geometry. The earlier failure was environmental, not an Ogre rendering limitation: an orphaned `scripts/takeoff.py` from the previous session was still holding UDP/14550. The front-lidar check is deterministic here and now runs in baseline CI, closing the Milestone 9 subscriber item.
- Cleared that orphaned process, which also released the UDP/20199 and TCP/5762 ports that had blocked the previous session's Iris rerun.

- Retracted the previous entry's root cause. The claim that two rotors turned backwards and produced zero lift came from a `joint_state` sample taken 25 s after launch, by which time the airframe had already flipped and crashed. That channel is meaningless in this state: it reports the same `+-61.8 rad/s` alternation regardless of the configured rotor speed, and once reported one joint frozen at a constant value.
- Built a virtual thrust stand to measure without that confound: `base_link` on a vertical prismatic joint so attitude cannot change. Under real ArduPilot control the unmodified model climbs 60 m with symmetric throttle, so the servo path, rotor joints and lift surfaces all work.
- The stand also disproved the damping and torque-ceiling change made earlier. The pre-change model reaches the 60 m stop by t=8.5 s; the changed model reaches only 16 m in 13.5 s. The change was unnecessary and reduced thrust, so it is reverted along with the documentation that justified it.
- Replaced `check_rotor_spin.sh` with `check_thrust_stand.sh`. The old script asserted rotor directions from the same unreliable post-crash reading, so it passed regardless of the truth. The stand check asserts a measured climb instead.
- Narrowed the real fault to attitude control. On a free airframe the vehicle rolls or pitches past 40 degrees within about 1.5 s of throttle-up in every configuration tried: unmodified, retuned damping, kinematic velocity commands with `useForce=0`, and a raised rotor speed. Channel map, rotation directions and both frame transforms are identical to the Iris reference that flies.
- `ardupilot_params.parm` sets only `FRAME_CLASS` and `FRAME_TYPE`, so every gain comes from `copter.parm`, which targets a one to two kilogram vehicle. This airframe is 0.240 kg with a roll inertia of 0.00022 kg m^2. Attitude tuning is the next step.
- Matched ArduPilot's output range to the model: `MOT_PWM_MIN` 1100 and `MOT_PWM_MAX` 1900. The defaults are 1000-2000, so below 1100 the plugin computed a negative rotor speed and a disarmed vehicle turned itself on the floor until the compass field check refused to arm it. Set `MOT_THST_EXPO` to 1.0 because the simulated thrust curve is exactly quadratic. The thrust stand check still passes with these, measuring a 60 m climb.
- Left `MOT_THST_HOVER` at its default on purpose. The model reaches a thrust-to-weight ratio of only 1.13, so true hover is near 94 % throttle, which leaves nothing for attitude correction. Writing that number down would entrench a value that should disappear once rotor speed matches a real 3 in cinewhoop.
- Seven tuning iterations did not produce a controlled free flight, and the reason is structural rather than a matter of gains. At the physical rotor inertia the velocity loop changes speed by 168 % of target per step, which alone tumbles the disarmed airframe at over 1000 deg/s. Raising the inertia fixes that but makes the rotor store real angular momentum: 0.36 N m of spin-up reaction per rotor, so a ten per cent asymmetry yaws this 0.00038 kg m^2 airframe at 5500 deg/s^2. Cutting joint damping twentyfold changes nothing, because the reaction is inertial rather than damping.
- Concluded that the rotor drive needs redesigning rather than tuning, most likely kinematic velocity control with explicit yaw torque. Recorded in [troubleshooting](./troubleshooting.md); no unvalidated model changes were kept.
- Ran a web survey of how small rotors are actually simulated for ArduPilot SITL in Gazebo, written up as [research](./research_rotor_simulation.md). The key finding is that `gz-sim` ships `MulticopterMotorModel`, a purpose-built rotor system that commands joint velocity directly and computes thrust and reaction torque analytically, with no velocity PID anywhere. Its `rotorVelocitySlowdownSim` default of 10 exists precisely for the numerical stability problem we hit.
- `ArduPilotPlugin` also supports `type=COMMAND`, which publishes to a topic instead of touching a joint, so the force loop can be bypassed without patching upstream. Bridging it to the motor model needs a small adapter, because the plugin publishes one `Double` per joint while the motor model reads one `Actuators` array.
- ArduPilot's own tuning guide states the default gains target a 9 to 12 inch propeller vehicle and that smaller props need lower rate gains, which confirms the default-gain theory for our 3 in airframe rather than leaving it a guess.
- Tried `AHRS_EKF_TYPE 10`, which the ArduPilot forum recommends for validating a vehicle model against ground truth. Estimator noise does vanish, but ArduPilot then reports the airframe pitched about -90 degrees while it sits level in Gazebo and refuses to arm. Both frame transforms match the Iris reference, so the fault is in that composition. Not shipped in the parameter file; recorded as its own task with the Iris run as the control.
- Two forum threads describe exactly our symptoms on custom ardupilot_gazebo models, one arming but not lifting and one flipping on takeoff, and neither got a working answer. There is also an open gz-sim issue on inverted quadrotor yaw direction, so rotation-sense conventions need measuring rather than trusting.
- Ran the Iris reference with `AHRS_EKF_TYPE 10` as a control experiment. It arms immediately, reports roll and pitch of 0.0 while level, and climbs cleanly from 0.19 m to 2.27 m on symmetric throttle. Ground-truth AHRS therefore works fine through the JSON path, and the -90 degree attitude our model reported is our own defect rather than a general limitation.
- Found the cause: our IMU sensor carries no `<pose>`. `ArduPilotPlugin` states in its own source that it assumes the sensor already uses the aircraft convention (x-forward, y-right, z-down), but a Gazebo body frame is x-forward, y-left, z-up. The Iris reference rotates its IMU sensor 180 degrees about X for exactly this reason; ours never did, so the Y and Z axes of both gyro and accelerometer reached ArduPilot inverted. Added the rotation.
- Confirmed the resting instability is physical, not an estimator artefact: with ground-truth AHRS the unmodified model still reports gyro rates approaching 500 deg/s while disarmed with its rotors commanded to zero. The velocity loop shakes the airframe on its own.
- With the IMU rotation and a stabilised rotor loop together (rotor mass 0.010 kg, izz 7.3e-06, `cmd_max` 0.6, multiplier 2600) the airframe finally sits perfectly still: roll and pitch read 0.00, gyro reads 0.0, and the compass and accelerometer prearm checks pass. That combination is not committed, because Gazebo intermittently emits NaN state that crashes SITL with a floating point exception, so it is not yet a working configuration.
- Committed the IMU rotation on its own. It cannot be independently validated in flight until the rotor loop is fixed, since the unmodified model tumbles at rest, but the evidence is the plugin's stated requirement plus the reference model rather than a measurement of our own.
- Rebuilt the rotor drive onto `MulticopterMotorModel`, following the research, and **the cinewhoop now flies**. Removed the eight `LiftDrag` surfaces, the four `ApplyJointForce` systems and the whole force PID; added one motor model per rotor and switched the plugin's `<control>` blocks to `type=COMMAND`. Thrust is `motorConstant * omega^2` and yaw torque is `momentConstant * thrust`, both analytic, so there is no velocity loop left to go unstable.
- Wrote `tools/ap_actuator_bridge` because the two halves do not speak the same message: `ArduPilotPlugin` publishes one `gz.msgs.Double` per rotor while `MulticopterMotorModel` reads a single `gz.msgs.Actuators` array indexed by `actuator_number`. The bridge subscribes to the four topics and republishes one array at 250 Hz. Built by `scripts/build_actuator_bridge.sh`.
- Three consecutive guided takeoffs all armed, climbed and held the commanded 2 m, settling between 2.02 and 2.09 m with attitude inside 4 degrees and yaw steady. Added `scripts/check_guided_takeoff.sh`, which asserts the climb, the settled altitude and a tilt bound; it measured peak 2.23 m, settled mean 2.04 m and worst tilt 5.7 degrees.
- The intermittent NaN that crashed SITL with a floating point exception is gone. It came from the force PID slamming torque into a rotor whose inertia could not absorb it, so removing that loop removed the NaN as well.
- Corrected an earlier figure: `ArduPilotPlugin` clamps `raw_cmd` to [0, 1] (`ArduPilotPlugin.cc:1678`), so full throttle gives exactly the `<multiplier>` speed. Thrust-to-weight on the old model was therefore 1.0006, not the 1.13 recorded before, which is even less margin than reported.
- The thrust stand check now stops at the commanded altitude instead of running to its 60 m stop, because thrust is modelled rather than emerging from blade aerodynamics. Baseline CI is unaffected and passes end to end.
- Completed what phase 9 of the iteration plan can be checked without a GUI: `cinewhoop.rviz` was missing three of the displays the plan lists, so added the downward rangefinder, the trajectory from `trajectory_publisher` and the front camera. All seven displays load as valid YAML and every topic matches either the bridge config or the demo node that publishes it. The fixed frame stays `base_link` because nothing publishes `map -> base_link` in the standalone display launch; that belongs with phase 12. The visual criteria, that the model and lidar are not rotated, still need someone at a screen.
- Confirmed AP_DDS works with the rebuilt rotor drive: with Gazebo, the actuator bridge, the Agent and DDS-enabled SITL all running, ROS 2 discovers the full `/ap/` graph including `/ap/cmd_vel` as `geometry_msgs/msg/TwistStamped`, which is what the autonomy demo publishes to.
- That took a detour which found a real defect. `micro_ros_agent` has no domain option and ignores `ROS_DOMAIN_ID`, so it always joins the default domain. `scripts/check_iris_dds_control.sh` had been given `ROS_DOMAIN_ID=78` for isolation, which hid the Agent from `ros2` and made the check fail with "AP_DDS services did not appear". The isolation it actually needs already exists as the dedicated Agent UDP port. Removed the domain override and the check passes again, measuring 584.19 m to 586.18 m.
- Fixed two more faults in the same script while it was open: its cleanup blocked on `wait` for an ArduCopter that ignores SIGINT, so the runner hung and left a stray SITL holding UDP/9002; and `printf '%.2f'` rejected the parsed altitudes under a comma locale, reporting "584,00" instead of the real figure. Cleanup now escalates to SIGKILL and the script pins `LC_ALL=C`.
- Started phase 11. Fixed the real bug in `simple_indoor_autonomy.py` first: `_last_scan_time` was recorded and never read, so a lidar that died mid-flight left the last range in place and the vehicle would have kept flying forward. Added `scan_is_usable` to `scan_helpers` with four unit tests, and the node now treats a stale scan exactly like no scan. Nine tests pass.
- Rewrote the node as a readable state machine that takes off on its own through ArduPilot's ROS 2 services, which is what the plan asks for. It walks prearm, GUIDED, arm, a wait on `/ap/status.armed`, takeoff and a climb-to-altitude hold before it publishes any forward velocity. `ardupilot_msgs` is imported lazily so the velocity-only mode and the unit tests still work without the opt-in DDS workspace.
- Added `scripts/check_forward_flight.sh`, which brings up Gazebo, both bridges, the Agent and DDS SITL, runs the demo and measures ground truth. **It currently fails, and the fault is in the vehicle rather than the harness.** Every service returns success, `/ap/status` reports armed, and the airframe does not move: commanded rotor speed reaches only the 260 rad/s arm idle before falling to zero.
- Narrowed it carefully. A manual service sequence identical to the working Iris check fails the same way, so it is not the node. Gating takeoff on real arming, holding `cmd_vel` back until the climb finishes, commanding `cmd_vel` upward directly, and adding `copter.parm` all change nothing. The same airframe flies and holds 2 m over MAVLink, and the Iris flies over these same DDS services. The fault is between AP_DDS and this vehicle configuration; Copter's `auto_armed` latch is the leading suspect. Recorded in [troubleshooting](./troubleshooting.md).

## 2026-09-10

- **Phase 11 passes: the cinewhoop takes off over DDS, creeps forward and stops for the wall.** `scripts/check_forward_flight.sh` now measures a climb to 1.36 m, a hold 0.80 m from the obstacle and a rotor-tip clearance of 0.16 to 0.23 m, twice in a row, with baseline CI still green.
- Retracted the previous session's diagnosis. The fault was never "between AP_DDS and this vehicle configuration" and `auto_armed` was not involved. A leftover `simple_indoor_autonomy` node from an earlier run was still publishing `/ap/cmd_vel`, because `ros2 run` is a wrapper whose child does not die when the recorded PID is killed. Five such orphans were alive at once.
- That single stray publisher is enough to stop the vehicle dead. A GUIDED velocity command replaces the TakeOff submode, and the position-control submodes call `make_safe_ground_handling()` while `land_complete` is still true, so throttle output sits at exactly zero while every service still answers success.
- The evidence came from SITL's own dataflash log rather than more black-box runs: `GUIP Type=4` with `vY=0.4999999` streaming at 10 Hz from before the takeoff request, alongside `CTUN ThO=0.000` and `DAlt` pinned at the ground altitude of 0.05 m. The 0.5 value is the demo's own `forward_speed_mps`, which is what identified the culprit.
- Two intermediate theories were tested and discarded, both on measurement. Gating on the EKF origin via `/ap/gps_global_origin/filtered` fires after 1.1 s because `ahrs.get_origin()` succeeds well before the EKF has a position solution. And takeoff timing relative to "EKF3 origin set" explains nothing: requests at 16.2 s and 17.2 s flew while one at 19.9 s did not.
- The apparent nondeterminism was the orphans accumulating. Every run that reached `CRUISE` left one behind, so each subsequent run failed, which is why the first three runs flew and everything after them did not.
- Fixed the leak rather than only the symptom. `check_forward_flight.sh` now `pkill`s the demo node and the ROS/Gazebo bridge by full install path, and refuses to start while a `/simple_indoor_autonomy` node is still in the ROS graph. The guard tolerates DDS keeping a dead node listed for a few seconds, because back-to-back runs would otherwise trip on the previous run's corpse.
- `scripts/check_ros_graph.sh` had the identical leak with `trajectory_publisher`, and it runs in baseline CI, so every CI run was leaving an orphan behind. Harmless in itself, but the same defect; fixed and verified to leave nothing.
- Found and fixed a second, independent defect on the way. `front_obstacle` stood exactly 1.0 m tall while the demo cruises at 1.0 m, so the level front lidar passed over its top and the scan came back all `inf`; with no walls inside the 8 m range the node correctly held on "no valid range in the scan". Both obstacles in `indoor_test.sdf` now stand taller than the cruise altitude. The ground-level reading that `check_front_lidar.sh` asserts is unchanged at 1.41 m, as expected.
- Kept the takeoff retry that came out of the investigation, because it earns its place: the service reply confirms only that GUIDED accepted the request, and in every passing run the first takeoff still needed one re-request. `takeoff_needs_retry` is unit-tested, and the node also re-arms if it finds itself disarmed before the climb.
- Rewrote the check's final assertions. The old bound of `peak_x > 1.10` assumed no braking distance at all; it now asserts the real requirement from world and model geometry: that the demo held because it saw the obstacle near 0.80 m, that it came to rest rather than crept, and that the forward-most rotor tip cleared the wall face at x = 1.74 by at least 0.10 m. It also prints the trajectory, which is what distinguished a braking overshoot from a slow drift.
- Measured braking distance is about 0.6 m from 0.5 m/s, so the spec's 0.8 m stop threshold leaves only about 0.2 m of real clearance. Recorded as its own backlog item and tied to the open attitude-tuning task rather than papered over by widening the bound.
- Started phase 12. `sitl_gazebo.launch.py` now brings up the whole demo from one command: the Gazebo world, the ROS/Gazebo bridge, the actuator bridge, `robot_state_publisher` with RViz2, the Micro XRCE-DDS Agent and DDS-enabled SITL. `rviz`, `agent` and `sitl` are individually switchable, and `sitl:=false` prints the exact command for a separate terminal, which is the alternative the plan allows.
- Two details the launch had to get right. SITL now loads `dds_smoke.parm` alongside the airframe parameters, without which no `/ap/` topic appears; and the Agent runs through `bash -c 'source ...; exec ...'` because it needs its own workspace on the library path, so the launch works whether or not the caller sourced it. SITL also starts on a six second timer, since it gives up on a JSON peer that is not listening yet.
- Fixed a defect the phase exposed: in `display.launch.py` the `rviz` argument gated `joint_state_publisher` but not RViz2 itself, so `rviz:=false` never stopped it. `scripts/check_tf_tree.sh` had therefore been starting a GUI it never used on every CI run. Verified that the headless launch log now mentions rviz2 zero times and the TF check still passes.
- Added `scripts/check_unified_launch.sh`, which asserts the plan's headless criteria: Gazebo and ArduPilot topics present at the same time, real messages on the front lidar, `/ap/geopose/filtered` and `/tf_static`, `robot_state_publisher` actually serving TF, and `/ap/cmd_vel` available so the demo nodes can still be run separately. It passed twice in a row. The visual criteria still need someone at a screen.
- Wrote the opt-in checks into [testing strategy](./testing_strategy.md) as a table, with the cleanup rule that came out of the orphan hunt: anything a check launches, it has to kill by process group or by install path.
- Calibrated the rotor constants against real hardware instead of against a chosen thrust-to-weight ratio, and the calibration then forced the attitude tuning with it. Written up in [research](./research_rotor_simulation.md).
- The target is 4x GEPRC SPEEDX2 1404 3850 KV on 4S with ducted 3 in props. GEPRC publish no thrust table for that KV, so the figures come from RCINPOWER's same-class 1404 3850 KV (492 g on an open HQ T333, 421 g ducted) and community measurements of ducted 3 in props on 1404 motors at roughly 1400 g total. The ducted number is the relevant one: 350 g per rotor. `maxRotVelocity` 2600 to 3980, `motorConstant` 2.611e-07 to 2.20e-07, `momentConstant` 0.005 to 0.013, and the plugin `<multiplier>` with it, since that is the full-throttle rotor speed. Thrust to weight went from 3.0 to 5.9 and hover from 94 % to 41 % throttle.
- Treated the vendor figures with care rather than taking them at face value: the same page quotes 328 W at 16.8 V, which is 19.5 A, against its own stated 9.6 A maximum. Cross-checked Ct = 0.21 instead, which a 5 in racing prop making 1500 g at 27000 RPM also implies, so it is consistent rather than optimistic. The 0.10 to 0.12 figures recorded earlier are textbook low-pitch values and land far too low for an FPV propeller.
- The first calibrated takeoff overshot a 2 m target to 42 m. Scaling the vertical acceleration gains down made it 54 m, which ruled out the Z axis, and two measurements then found the real fault. On the thrust stand, where attitude is locked, the climb was accurate at 5.42 m for a 5.0 m target. In free flight the dataflash log showed `ThO 0.000` and a commanded descent of -2.5 m/s while the vehicle climbed at 15 m/s, so nothing was commanding it upward.
- Reading the commanded rotor speeds during the climb settled it: one rotor pinned at the `MOT_SPIN_MIN` floor of 597 rad/s while the others ran 1500 to 2200, and which rotor saturated kept rotating. The rate loop was oscillating into the stops, and Copter gives throttle away to keep attitude authority, which is why the log read zero throttle while the motors still averaged about the vehicle's weight in thrust. Reverted the vertical gain change, since it rested on that misdiagnosis.
- The cause is control authority, not thrust. A full roll demand produces 0.311 N m against a roll inertia of 0.00022, which is 80900 deg/s^2, where a 1.5 kg ten-inch quad at a thrust-to-weight ratio of 2 manages about 10500. Dividing the stock rate gains by that 7.7 ratio restored controlled flight on the first attempt.
- Measured after: guided takeoff peaks at 2.07 m and settles at 2.02 m for a 2.00 m target, against 2.24 m and 2.04 m before, and the autonomy demo holds 1.04 m for a 1.0 m target against 1.36 m before. Thrust stand unchanged, forward flight still passes, baseline CI green.
- Braking from 0.5 m/s is still about 0.6 m, unchanged by the extra authority, so that item belongs to the velocity controller's deceleration limits rather than to thrust. Recorded as such rather than left ambiguous.
- Closed the braking-distance item, and it turned out not to be a defect. Measured the stop from Gazebo ground truth at 59 Hz rather than the check's 1.2 s sampling: speed decays from 0.50 to 0.15 m/s over 1.1 s, an effective 0.3 m/s^2, far below the 2.5 m/s^2 acceleration limit. The limit is not what binds; ArduPilot's horizontal motion shaping is, with `PSC_NE_VEL_P` 2.0 and a 5 m/s^3 jerk limit.
- That smoothness is the point on a camera platform, so the decision moves earlier instead of the braking getting harder. `safe_forward_speed` takes a braking distance and stops at wanted clearance plus braking distance; the node defaults it to the measured 0.6 m. Clearance to the wall went from 0.16 m to 0.82 m, and 18 unit tests pass.
- Rewrote the check's hold assertion as the safety property rather than a narrow window around the threshold. Where the vehicle is when it first looks depends on its takeoff excursion, so it now has to decide no later than the threshold and never as late as the bare clearance. The first attempt asserted a +-0.20 m window and the real measurement sat 0.19 m from the centre, which would have flaked.
- Two things cost time and are worth recording. A probe that published `/ap/cmd_vel` itself never moved the vehicle even though the demo node does, so the measurement switched to observing the real node instead of reimplementing its command path. And MAVLink `LOCAL_POSITION_NED` reported no forward velocity during a run where ground truth clearly moved, so Gazebo ground truth is the witness to trust for translation.
- Also measured, while instrumenting: the vehicle drifts about 0.35 m forward during the guided takeoff itself, before any velocity command exists. Recorded in [troubleshooting](./troubleshooting.md) because it makes a post-takeoff trajectory not start at the origin.
- Started Milestone 10. The sim-to-hardware topic mapping was already specified in [the build spec](../spec/realna_stavba_dronu/02_rozhrani_sim_real.md), so the useful work was checking the implementation against it rather than writing the table again. Two real gaps turned up.
- First, the spec requires `arm_service`, `mode_service` and `takeoff_service` to be parameters so that moving off SITL changes the launch and not the algorithm. All four ArduPilot service names were hardcoded in `simple_indoor_autonomy`. They are parameters now.
- Added `scripts/check_topic_remap.sh` to baseline CI. It asserts each node subscribes and publishes on remapped names and that the defaults are gone, so a node cannot quietly listen on both. `ros2 node info` does not list service clients, so the service half is verified behaviourally instead: `scripts/fake_ardupilot_services.py` stands up the four services under remapped names and requires the node to call them. That harness drives the entire autonomy state machine in seconds with no Gazebo and no SITL, which is worth reusing.
- The fake harness immediately earned its place by surfacing the second gap, a QoS warning on the pose topic. AP_DDS publishes `/ap/pose/filtered` BEST_EFFORT, and a RELIABLE subscriber does not match a BEST_EFFORT publisher, so `trajectory_publisher` with default QoS would have received nothing at all from real ArduPilot. Baseline CI passed throughout because `ros2 topic pub` defaults to RELIABLE, so the test publisher matched where hardware never would.
- Fixed both halves: the node subscribes with `qos_profile_sensor_data`, and `check_ros_graph.sh` now publishes BEST_EFFORT so the same mistake fails the test next time. The spec's transition checklist item for sensor-data QoS is ticked with that explanation attached.
- The warning only appeared because a `trajectory_publisher` from an earlier phase of the new check had outlived its `ros2 run` wrapper and was still subscribing. Fixed the check's teardown the same way as the others, by pkill on the install path, and kept the find: an orphan is how the mismatch became visible.

- Worked through the rest of the transition checklist in [the interface spec](../spec/realna_stavba_dronu/02_rozhrani_sim_real.md). Every one of its five open items turned out to hide a defect that only real hardware would have exposed, which is what the checklist is for.
- The Gazebo sensors had no `gz_frame_id`, so the front lidar stamped its scans `openipc_cinewhoop/front_lidar_link/front_lidar`, the rangefinder and camera likewise. Nothing fails loudly: the topic carries data and `ros2 topic echo` looks healthy, but no such frame exists in the TF tree, so RViz silently draws nothing and a real driver would publish a different name. Fixed for all three, and the camera now stamps `camera_optical_frame` with the URDF's 14 mm lens offset carried into the sensor pose. This is why the RViz item could never have passed on a screen.
- The bigger find sat under it. The bridged `/openipc_cinewhoop/imu` was the sensor ArduPilot reads, which the model deliberately rolls 180 degrees into aircraft convention, so at rest it reported z = -9.81 where REP 103 wants +9.81. AP_DDS publishes REP 103 on hardware, so every ROS consumer written against the simulation would have found its y and z inverted on the real drone. The model now carries a second, unrotated `imu_ros` sensor for the bridge and leaves the aircraft-convention one to the plugin. Measured after: +9.80665 on z.
- `/openipc_cinewhoop/range/down` carried a LaserScan while [the ROS interface spec](../spec/04_ros_rozhrani.md) has always said `sensor_msgs/msg/Range`, which is what the MTF-02P's driver publishes. The implementation had drifted from the spec rather than the spec being unfinished. The bridge now ends at `/openipc_cinewhoop/range/down_raw` and a new `range_adapter` owns the logical name.
- While converting it, the simulated sensor became a five-ray 15 degree fan instead of a single ray, because a time-of-flight rangefinder reports the nearest surface inside its cone rather than along a line. The single ray also left `angle_increment` NaN in every message.
- `demo.launch.py` hardcoded `use_sim_time` true. On hardware there is no `/clock`, so those nodes would read the same instant forever, every message age would compute as zero, and the stale-scan guard that stops the vehicle when the lidar dies would quietly never fire. It is a launch argument now, which is the same rule as the topic and service names.
- Both downward sensor frames were rotated to match the SDF. The beams measure along +X of their own frame, and the URDF had `rangefinder_link` and `optical_flow_link` level with `base_link`, which would have put the floor measurement in front of the drone instead of below it.
- Two new baseline checks, both cheap. `scripts/check_sensor_interface.sh` asserts the shape of the data rather than the names on the graph: message types against the spec, every frame_id transformable into `base_link`, the declared rangefinder cone against the fan actually cast, and gravity reading +9.81 on the IMU's z. `scripts/check_sensor_dropout.sh` needs no simulator at all - it publishes a scan from the command line and then stops, which is exactly what a disconnected sensor looks like from inside a node.
- Both were negative-tested rather than trusted. Removing one `gz_frame_id` makes the interface check exit 1 and name the offending frame; making the autonomy node ignore scan freshness makes the dropout check report that it kept commanding 0.5 m/s after the lidar stopped.
- `obstacle_monitor` gained a watchdog while writing that check. It only ever warned about a scan that arrived with no valid ranges, so a lidar that stopped entirely made it go quiet, and a monitor that goes quiet when its sensor dies is worse than no monitor.
- Two things the checks got wrong first and are worth recording. The interface check left its wait loop as soon as the four sensor topics resolved, which could be before the rangefinder's raw scan had arrived, so it failed on slow discovery rather than on a defect; the loop now requires every assertion at once. And the dropout check read the commanded speed with `ros2 topic echo`, which prints its own "does not appear to be published yet" warning on stdout - the warning text passed for a speed and the test accepted it. Only a number counts now.
- One CI run in five saw no injected scan reach the monitor for fifteen seconds, with the nodes behaving correctly on either side of it. That is DDS discovery losing the pairing, so the publisher now waits for a matching subscription and the check republishes once before failing.
- Verified after all of it: baseline CI green, 21 unit tests, and the two opt-in flight checks unchanged - guided takeoff still peaks at 2.07 m and settles at 2.02 m for a 2.00 m target, and the autonomy demo still holds 1.21 m from the wall with 0.79 m of rotor clearance.

- Started Milestone 10's component work, and widened it to three airframes on the spot: Meteor75 Pro with a light OpenIPC unit, Pavo20 Pro with the RunCam WiFiLink 2, and the CineLog30 V3 the simulation is calibrated against. Written up in what is now [the component table](../spec/realna_stavba_dronu/03_komponenty.md). Comparing three answers a question one table cannot: which airframe can actually carry the goal, rather than whether the chosen one happens to.
- Every figure is published by a vendor or a shop, not weighed, and the table says so per row. The motor research earlier in this project found vendor numbers that contradicted themselves, so the column exists rather than the caveat sitting in a sentence nobody reads.
- The useful result is not the table but the cross-check against the simulation. The bill of materials for variant 3 sums to 238 g with the battery, which looks like a perfect match for the 0.240 kg the model flies on - except it omits wiring, solder, screws, TPU and antennas. The stock airframe's own published dry weight of 187 to 192 g against our 164 g of listed parts puts that missing hardware at 23 to 28 g, so the real figure is nearer 264 g. Thrust to weight drops from 5.9 to about 5.3.
- And the front obstacle sensor decides the rest of it. An LD06 is the only candidate that produces a genuine `LaserScan`, but at roughly 42 g it would take the airframe past 300 g, a quarter over what the model assumes. A VL53L5CX-class sensor costs about 2 g and keeps the mass, but halves the range to 4 m. Neither matches what the simulation models today, which is 61 samples across 60 degrees out to 8 m, so the model's front lidar has to be re-specified once the part is chosen. Recorded as a blocking decision rather than left implicit.
- Variant 1 does not work as asked, and the numbers say why rather than an opinion. Both light OpenIPC units need 2S minimum and the Meteor75 Pro is a 1S machine; the lightest of them is 8.8 g without a heatsink on a 31 g airframe. Its 1S flight controller has no ArduPilot target, no spare UART for the MTF-02P and no 5 V rail to run it. It is still worth building, but as the cheapest way to close the OpenIPC to `sensor_msgs/msg/Image` item, which can be done with the camera on a desk.
- Variant 2 is the interesting middle. A Pavo20 Pro lands near 148 g all up and carries the flow sensor, but its F4 flight controller rules out AP_DDS, so it would talk to ROS over a MAVLink adapter instead. [The interface spec](../spec/realna_stavba_dronu/02_rozhrani_sim_real.md) allows that, but it is a different adapter and a different set of checks than the ones that exist for SITL.
- Corrected a mistake from earlier today while reading the MTF-02P datasheet for the table. The rangefinder cone was set to 15 degrees on the assumption that it matched the sensor; MicoAir give the laser a 2 degree emitting angle. The simulated fan and the adapter's declared field of view are both 0.035 rad now, and the interface check confirms they still agree.
- Wrote [the bench checklist](../spec/realna_stavba_dronu/04_bench_checklist.md) as ten ordered steps with explicit stop conditions, ending at the point where propellers go on. Its ROS step is deliberately the same set of assertions the simulation automates: `/openipc_cinewhoop/imu` reading +9.81 on z, every frame_id present in the TF tree, and the node reporting silence within a second of the sensor being unplugged.
- Also noticed while building the table: the model uses a 126 mm wheelbase and GEPRC publish 128 mm, which moves the motor coordinates by 1.6 per cent. Small, but it feeds the inertia and therefore the rate gains, so it is on the backlog rather than fixed silently.

- The three-way comparison then closed itself in one step, on two rules: the flight controller has to be H7, and the airframe has to be able to power an OpenIPC unit. Written up as [a decision](./decisions.md) rather than only in the spec, because it constrains every later hardware choice.
- The H7 rule is not about speed. The 2026-09-01 decision puts the first ROS path on AP_DDS, and AP_DDS needs flash and RAM an F4 or G4 does not have. Both rejected airframes would run ArduPilot; neither would run DDS, so both would have thrown away the adapter work that already passes against SITL.
- Went looking for a lighter OpenIPC unit before dropping the Meteor75, since the whole variant rested on one existing. There is none: Thinker and Mario both need 2S minimum, UltraSight needs 5 V at 3 A, and no 1S whoop has that rail. The one light unit that does run on 1S is BetaFPV's P1 at 6.8 g complete, but it is Artosyn AR803X on the ArtLynk protocol, not OpenIPC, so it is useless for the one thing that variant existed to prove.
- The Pavo20 Pro is worth remembering: about 148 g and comfortably under 250 g, and it comes straight back if the project ever moves from DDS to MAVLink.
- What the decision costs is worth being explicit about: there is now no lightweight fallback. If the CineLog30 V3 comes out too heavy - and the mass estimate already says 264 g rather than the 240 g the model flies on - there is nowhere to retreat to without reopening the DDS decision.
- One more OpenIPC unit came up afterwards, the EMAX Wyvern Link Alpha 200 mW, and it is the one the original question's 200 mW referred to: genuinely OpenIPC, 13.76 g, 2-6S, 25.5x25.5 mm. It does not rescue a 1S airframe, but against the RunCam WiFiLink 2's 25 to 30 g it saves 11 to 16 g on the airframe that stayed, moving the estimate from about 264 g to about 252 g. That is the second largest lever on mass after the front sensor. EMAX publish neither power draw nor range, where RunCam quote up to 15 W, so it is on the backlog as a decision rather than a swap.
- Two corrections came out of pushing on the comparison rather than defending it. The Pavo20 was not actually blocked by its flight controller: its stock F4 sits on the same 25.5x25.5 mm pattern as several ArduPilot-supported H7 AIOs, so the swap is a rebuild rather than an impossibility. And asked which drone the OpenIPC community prefers, the honest answer is none - the OpenIPC wiki names no flight controller at all and wants only a UART carrying MAVLink. The ArduPilot thread on open-source digital video shows no consensus either, and its loudest warning is thermal: over 100 degrees on the bench, for a unit that on a ducted whoop sits under the canopy.
- Closed the exploration there and narrowed the spec back to the one airframe. The variants file became [the component table](../spec/realna_stavba_dronu/03_komponenty.md) for the cinewhoop alone, and the rejected airframes live in [the decision](./decisions.md) with their reasons, which is where a reader would look for them.
- Build phase 8, OpenIPC video into `sensor_msgs/msg/Image`, survives the cull. It needs the WiFiLink 2 and a desk, not an airframe, which is cheaper than the whoop that was going to carry it.

- Wrote `scripts/check_model_consistency.py`, which asserts that the URDF and the SDF still describe the same drone. The airframe is written down twice, once as Xacro for RViz and once as SDF for Gazebo, and nothing linked the two files. The drift is silent when it happens: the simulation keeps flying and RViz keeps drawing, just not the same vehicle. It had already happened once today, with `rangefinder_link` pitched 90 degrees on one side and level on the other.
- It compares where each shared link sits relative to `base_link`, how it is rotated, and what the whole thing weighs. Mass needed care: the URDF lumps 0.240 kg into `base_link` because it only has to look right, while the SDF spreads it over the links physics acts on, so only the totals are comparable. They agree. The links that exist on one side only - `camera_optical_frame`, `optical_flow_link`, and the four rotors - are listed with the reason each one is legitimate, so a new unexplained divergence fails.
- The check needs neither a simulator nor a ROS graph, just xacro, so it went into baseline CI and runs in a second.
- Then used the wheelbase correction to prove it rather than testing it artificially. GEPRC publish 128 mm for the CineLog30 V3; the model carried 126 mm, which was the original assumption. Changing only the URDF made the check fail and name all four motors with both sets of coordinates. Changing the SDF to match made it pass. Motor coordinates are 0.04525 m now.
- Deliberately did not re-derive the rate gains for it. Those came from an authority ratio of 7.7, and the longer arm moves it to 7.8 - 1.6 per cent, far inside the accuracy of a scaling computed once by hand. Redoing them for that would be false precision, and the backlog already carries the item to measure them by a sweep. Both the parameter file and the research note say so where the old number appears, rather than quietly changing history.
- Verified after: baseline CI green with the new check, and all three opt-in flight checks unchanged. Thrust stand climbs 5.01 m for a 5.0 m target, guided takeoff peaks at 2.07 m and settles at 2.02 m for 2.00 m, and the autonomy demo holds 1.23 m from the wall with 0.87 m of rotor clearance.

- Measured the attitude rate gains instead of calculating them, which closes the item deferred earlier today. `scripts/sweep_rate_gains.sh` flies the same roll square wave at a list of gains, one fresh Gazebo and SITL per point, and `scripts/rate_step_response.py` commands the steps through `SET_ATTITUDE_TARGET` and reports overshoot, rise, settle, tracking error and ringing. Results published as [an artifact](https://claude.ai/code/artifact/cff60e7a-e066-4847-ae89-50d2b0e3b189).
- Eleven gains from 0.009 to 0.14. Everything improves monotonically with P up to 0.044, and then the loop falls off a cliff: ringing goes from 5 sign changes per run to 141 at 0.05, overshoot from 8 to 44 per cent. Between 0.044 and 0.05 is the onset. Set `ATC_RAT_RLL_P` and `ATC_RAT_PIT_P` to 0.027, a little over half of that, with I moved with P as it was before.
- 0.040 measured best of every value tried - overshoot 7.7 per cent, ringing 3 - but it sits at 0.85 of the onset, which is no margin at all. Took the margin instead.
- Two things had to be ruled out before the numbers meant anything. Rise time barely moves with gain, near 0.35 s everywhere stable, which looked like the demand being shaped somewhere above the rate loop. Raising `ATC_ACCEL_R_MAX` from 110000 to 400000 changed the results by less than a tenth of a per cent, so it is the attitude loop's own response, not an acceleration limit. And 0.018 was flown three times across separate sweeps: overshoot 9.72, 10.01 and 9.94 per cent, tracking error 1.831, 1.822 and 1.812 degrees, so a spread of a third of a per cent against differences of one to five per cent between gains.
- Verified after the change: thrust stand unchanged at 5.01 m for a 5.0 m target, guided takeoff still settles at 2.02 m for 2.00 m with worst tilt down from 10.0 to 6.5 degrees, and the autonomy demo holds 1.36 m from the wall with 0.88 m of rotor clearance.
- Recorded the limit of the method rather than leaving it implied. This simulation has no gyro noise, no frame resonance and no ESC lag beyond the motor model, and those are what force real gains down. The sweep bounds the gain well from below and optimistically from above, so 0.027 is a ceiling to approach on hardware. On the backlog to re-measure there.

- Moved the wall. `front_obstacle` stood at x = 1.8, so its face was 1.74 m from the spawn while the demo decides at 0.80 m of wanted clearance plus 0.60 m of braking. The vehicle therefore reached cruise and stopped almost immediately - correct behaviour, and nothing anyone could watch. The room is 10 m along x now and the wall is at 4.5, which turns 0.78 m of forward flight into 3.37 m, about six seconds of it. Clearance to the wall came out at 0.99 m.
- `check_forward_flight.sh` had the wall face written into it as 1.74. It reads the obstacle's pose out of the world file now, because a number kept in two places is the same defect the URDF and SDF had this morning.
- Added `scripts/demo.sh`: scene, simulator and flight from one command, holding until Ctrl-C. It waits for `/ap/experimental/takeoff` to actually answer rather than sleeping a fixed time, refuses to start when another SITL is already running, and kills everything it started on the way out - by process group and then by install path, since a `ros2 run` child outlives its wrapper.
- That last part is not hypothetical. The first watched sweep failed with "Vehicle never armed", and the cause was a second SITL still holding the ports from a flight check that had not finished. SITL logged `bind failed on port 5762` into a file nobody reads. Both the sweep and the demo now check for that up front and name what to stop, and the sweep prints ArduPilot's own STATUSTEXT messages when arming really does fail.
- All four demo nodes now exit quietly on Ctrl-C instead of printing an rclpy traceback over the shutdown.
- `scripts/menu.sh` lists everything runnable in one place, marks what cannot run yet and why, and warns before the entries that boot a simulator and then say nothing for minutes. That was written after a run of the forward-flight check looked like a hang when it was simply headless and silent.

- Chased down the front-lidar reading that did not match the world, because an unexplained number in a sensor path is where this project keeps finding real defects. It is the floor: parked, the lidar sits 37 mm above it and the rendered fan's lowest rays graze it, which puts a plane of constant depth at h over phi. From 0.037 m and 1.412 m, phi is about 1.5 degrees. Written up in [troubleshooting](./troubleshooting.md) with the evidence in the order that settled it.
- Five things had to be eliminated, and each ruled out a different story. The returns lie on a plane of constant depth rather than at constant range, so it is a surface, not a ring. The vehicle really is at the origin and level. The scene really has the wall at 4.5 with all four models present, loaded from the file on disk. The reading is the same at 5 s and 25 s, so it is not a half-built render. And an obstacle moved to x = 1.0 measures exactly right at 0.867 m, so near geometry is fine and the floor return simply arrives first.
- The one that settled it was spawning the vehicle higher: the plane moved from 1.412 m to 1.267 m instead of disappearing, which is h over phi changing rather than a fixed clip distance.
- Nothing in flight is affected, and that is worth stating rather than assuming: at the demo's 1 m altitude the floor would be struck near 38 m, past the sensor's 8 m maximum, so no return comes back. The forward flight check's stop at x = 3.37 m with 0.99 m of clearance still sums to the 4.44 m the world puts the wall face at.
- One consequence is worth carrying forward. The demo stops below 1.40 m and the parked floor return sits at 1.412 m, which is twelve millimetres of margin. Raising the stop distance would make the floor read as an obstacle. On the backlog to give the lidar some ground clearance or a degree of up-tilt, so the number is bounded by the room rather than by an artefact.

- Made the simulated front lidar an LD06 now that the part is chosen, rather than the 60 degree, 8 m fan that stood in for a sensor nobody had picked. To its datasheet: the full 360 degrees at 1 degree resolution, 10 Hz nominal, 0.02 to 12 m. It also moved onto a mast, 46 mm forward and 50 mm up, which is where the CAD model says it has to go to clear the propeller discs.
- The 360 degrees is the part with teeth. Taking the minimum over the whole scan would stop the vehicle for a wall behind it, and that is not a simulation artefact - the real sensor reports those returns too, so the demo would have failed the same way on hardware. `nearest_in_sector` windows the scan and both nodes carry a `forward_sector_deg` parameter, default 60.
- Proved it twice. Five unit tests cover the windowing including a scan indexed from straight ahead rather than from behind, and `check_sensor_dropout.sh` gained a behavioural case: a wall 0.3 m behind with clear air ahead must still command 0.5 m/s. Widening the sector to 360 makes that check fail with the reason spelled out, which is the negative test.
- Two things fell out that were not the point of the change. The forward flight still passes, holding 1.37 m from the wall with 0.95 m of rotor clearance after 3.41 m of travel. And the parked floor-grazing artefact is gone: at 50 mm up instead of 2 mm, `h / phi` grew until the floor return fell past the sensor's range, so `check_front_lidar.sh` now reports 4.39 m - the wall at 4.44 m less the sensor's own 46 mm offset.
- Kept the floor diagnosis in [troubleshooting](./troubleshooting.md) anyway, because it predicts the same thing on hardware. LDROBOT give the LD06 a pitching angle of 0 to 2 degrees, so a real unit 35 mm off the ground will see the floor somewhere between 1 and 4 m. Only altitude takes it out of range.
- Corrected something I had written the day before: the LD06's motor is brushless, not brushed. The 300 mA startup on a shared 5 V rail still deserves a capacitor, but the noise argument was overstated.

- Brought the model's mass up to what the bill of materials says: 0.306 kg instead of the 0.240 kg the requirement asked for. The LD06's 42 g went on `front_lidar_link` rather than into `base_link`, because Gazebo composes the body inertia from where the links sit and the whole point is that this mass hangs on a mast.
- That is not a number change. 42 g at 46 mm forward and 50 mm up adds about 1.9e-4 to pitch inertia, as much again as the entire airframe had before, so roll inertia goes from roughly 0.00028 to 0.00045. Hover throttle moved from 0.41 to 0.46, thrust to weight from 5.9 to 4.6, and the tuning stopped being valid: at the old 0.027 the guided takeoff's worst tilt went from 6.5 to 24.0 degrees against the check's 25 degree limit.
- So the sweep was run again, which is what it was built for. At 0.306 kg the onset sits between 0.065 and 0.08: ringing holds at 3 sign changes per run through 0.065, reaches 11 at 0.07, and at 0.08 the loop is gone with 146 sign changes and 62 per cent overshoot. `ATC_RAT_RLL_P` is 0.040, a little under six tenths of the onset, which is the same margin the previous tuning used. 0.065 measured best and sits at 0.93 of the onset, which is no margin.
- Worst tilt came back to 15.6 degrees. Not the 6.5 it had when the airframe was lighter, and it should not be: the drone genuinely carries a lidar on a stick now.
- Verified: baseline CI green with both models agreeing at 0.306 kg, thrust stand unchanged at 5.01 m for a 5.0 m target, guided takeoff settling at 2.02 m for 2.00, forward flight holding 1.39 m from the wall with 0.93 m of rotor clearance.
- One thread left hanging deliberately. The 0.306 kg assumes a RunCam WiFiLink 2; the lighter EMAX Wyvern Link Alpha would make it about 294 g and the gains would want measuring a third time. That decision is still open on the video unit's unpublished power draw, so the mass follows the airframe as specified rather than as hoped.

- Implemented attitude compensation for the front scan, which was the open item with teeth: the lidar is bolted to the airframe, so leaning points its forward beams at the floor and the floor returns a range like a wall. Returns are projected into a gravity-aligned frame using the pose's roll and pitch, and dropped when they work out to be the ground. The height comes from the downward rangefinder, which the autonomy node now subscribes to.
- Wrote the geometry as pure functions and the tests from physics rather than from the formula, because the sign is the whole problem: REP 103 puts y to the left, so a positive rotation about it tips the nose *down*, and a flipped sign would discard the ceiling while keeping the floor. Eight tests state what the vehicle is doing - nose down, nose up, rolled right - rather than what the arithmetic should return.
- One of those tests failed on the first run, and it was the test that was wrong. At 0.5 m up and 20 degrees of lean, a return 1 m out is aimed at a point 16 cm above the floor, and I had asserted that was clearly a wall. It is not clearly anything: a wall's base and the floor are the same measurement there. The test now says so, because the geometry genuinely stops distinguishing them and the answer is to not fly like that.
- Corrected the troubleshooting table with it. It listed `h / tan(theta)`, the horizontal distance, where the sensor reports slant range `h / sin(theta)` - and slant range is what the demo's threshold is compared against. At 1 m it takes about 45 degrees of lean to reach the 1.40 m threshold rather than 35, and at 0.5 m about 22 rather than 20.
- `nearest_in_sector` takes the attitude and height as optional arguments, so leaving them out drops nothing. That is deliberate: an unknown altitude must not start discarding real obstacles, and it keeps the sector tests testing only the sector.
- Verified: 35 unit tests, baseline CI green, forward flight unchanged at 1.36 m from the wall with 0.91 m of rotor clearance. Unchanged is the expected result - at 1 m and a gentle lean there was never anything to reject.
- Which is also the gap, and it is recorded rather than glossed: **nothing has yet flown leaning**. The unit tests pin the geometry, but the simulator test that leans the vehicle and asserts the floor is not reported is still owed. `obstacle_monitor` is also still uncompensated, so it would report the floor while the autonomy node ignores it.

- Leaned the vehicle in the simulator and asserted the floor is not reported, which was the item I had deliberately left hanging: the attitude compensation had eight unit tests behind it and no scan Gazebo had ever produced. `leaning_test.sdf` holds the model static at 30 degrees nose-down, 0.60 m up. Static is the whole trick - `set_pose` does not reset velocity, so a falling model accelerates between teleports and the scan differs every run, while frozen it is identical every time.
- The numbers came out where the geometry said they would. The lidar sits 0.588 m above the floor, the straight-ahead beam reports it at 1.175 m and the edge of the 60 degree sector at 1.352 m, against `h / sin(30)` = 1.18 m. All of that is inside the demo's 1.40 m stop threshold, so the floor really would stop an uncompensated vehicle here. The downward rangefinder reads 0.639 m rather than the true 0.551 m, because tilting its cone by 30 degrees lengthens the slant - that error is in the right direction and well inside the 0.25 m margin, but it is the sort of thing that would have been invisible in a unit test.
- The check runs both demo nodes twice over that one scan: once wired to the rangefinder, once with `range_topic` pointed at a topic nobody publishes, which is exactly what an unknown height looks like from inside a node. The blind pair must report the floor at 1.17 m and the compensated pair must report nothing. The blind half is asserted **first**, on purpose: without a control that proves there was something there to reject, the check would pass just as happily over an empty scan, and that is the failure mode a rejection test has.
- Gave `obstacle_monitor` the same compensation. It had been the other open item, and it is not cosmetic: without it the monitor calls the floor the nearest obstacle at the same moment the autonomy node correctly ignores it, so the two nodes disagree in flight and the log contradicts the vehicle.
- One run in about six failed and I could not reproduce it; chasing it turned up a real defect rather than a flake. `simple_indoor_autonomy` latched *that* it was holding, not *why*, so whichever reason came first was the only one ever logged. A vehicle that stops for a stale scan and then stays stopped because a wall appeared reported a dead lidar indefinitely. `hold_reason` is now a pure function, the node latches the reason and not the distance - so an obstacle drifting 1.17 to 1.16 m does not re-log ten times a second - and five unit tests pin which changes count.
- Two things about the check that are honest limits rather than oversights. The attitude comes from Gazebo's own report of where the model is, not from AP_DDS, because the check runs without SITL; it is read from the simulator rather than copied out of the world file, so the two cannot drift, but nothing there tests the EKF's estimate against the truth. And the compensated nodes are only required to stay clean from their first correct line onwards: before the pose and the rangefinder arrive a node has no attitude and no height, and reporting the floor is then the right thing for it to do.
- Noticed in passing that the model SDF hardcodes `/world/indoor_test/...` in every sensor `<topic>`, so the sensors keep those names under a world called `leaning_test`. That is why the existing bridge config worked unchanged and why the new world needed no second copy of it. It also means two of these worlds cannot run at once, which nothing needs today.
- Verified: 40 unit tests, baseline CI green including the new check, and the opt-in forward flight unchanged at 1.37 m from the wall with 0.88 m of rotor clearance. `gazebo.launch.py` took a `world` argument so the check reuses the same bridge and adapter rather than standing up its own.

- Went after the gap I had just written down: the floor rejection trusts roll and pitch from `/ap/pose/filtered`, and nothing checked that those are the vehicle's real attitude in the convention the projection assumes. A flipped sign there discards the ceiling and keeps the floor, and every existing test still passes.
- Two approaches died first, both worth writing down. Holding the vehicle at an attitude with `set_pose` does not work because the teleport leaves the velocity alone. Making the model static does not work either: `ArduPilotPlugin` cannot produce state for a static model, so SITL sits printing `No JSON sensor message received` forever. That is why `leaning_test.sdf` is static and deliberately runs without SITL.
- The second dead end turned into the real find. A live model on a ramp in a new world deadlocked exactly the same way, and bisecting the world file showed the only thing that mattered was its **name**: identical content passed as `<world name="indoor_test">` and hung as `<world name="ramp_test">`. The model's five sensors each declared a `<topic>` containing `/world/indoor_test/`, so under any other world they kept publishing under the written name while the plugin looked for the IMU under the real one. Nothing in the message points at a name; it reads like a network fault.
- That also corrects what I wrote yesterday, which called the hardcoded topics a curiosity that meant "two of these worlds cannot run at once, which nothing needs today". They were not a curiosity: they silently prevented SITL from running in any world but one.
- Fixed at the source. No sensor declares a topic now - Gazebo's generated names are byte-identical to what was written, with the real world substituted, so `indoor_test` is unchanged - and `config/gz_bridge.yaml` became a template with `@world@` in it, rendered by `gazebo.launch.py` from the `<world name>` read out of the world file rather than guessed from its filename. `check_model_consistency.py` fails if a world name reappears in a sensor topic, which is the guard against writing it back; verified by putting one back and watching it fail.
- With that out of the way the attitude check is almost trivial. `ramp_test.sdf` parks the vehicle on a slope tilted 20 degrees in pitch and 10 in roll - both axes on purpose, so a roll/pitch swap cannot hide behind matching numbers - with friction well inside the 0.41 the slope asks for, so it settles instead of sliding. `scripts/check_attitude_estimate.sh` then compares three numbers that must agree: what the world file asks for, what Gazebo says the vehicle is doing, and what AP_DDS reports.
- All three read roll +10.00, pitch +20.00. The quaternions agree to about 4e-7. Nothing arms and nothing flies, which is the whole point: parked, the attitude is two steady numbers rather than two streams to align during a transient, and the check takes under a minute.
- Proved the check can fail, by making it report roll and pitch the other way round: it rejects with "off by roll +10.00, pitch -10.00 degrees". A single-axis ramp would have let that through.
- What it does not prove, and the backlog says so: SITL's EKF is fed a noiseless IMU, so this is the convention being right, not the estimate being accurate. That still wants a real flight controller on a real ramp.
- Verified: baseline CI green including the new model guard, the leaning check unchanged, the forward flight holding 1.36 m from the wall with 0.89 m of rotor clearance, and the unified launch still serving Gazebo, ArduPilot and TF through the rendered bridge config.

- Gave the floor rejection's own inputs the staleness guard the scan already had. The lidar's freshness was checked and the two things the rejection is run with were not, although neither arrives with the scan: the attitude comes from the flight controller over DDS and the height from a different sensor, so either can stop while the lidar stays perfectly healthy and the node goes on projecting scans with a lean the vehicle no longer holds.
- My first reading of the consequence was wrong, and checking it is what made the case worth making. Dropping returns can only raise the nearest range or remove it, which mostly means over-rejecting: the vehicle holds for nothing and the log blames the lidar. But the drop test is on `range * cos(bearing)`, so a lean removes a wall straight ahead before it removes a farther return at the edge of the sector. Believing 30 degrees nose-down at 0.90 m, the node reads 1.45 m for a wall 1.35 m away - and 1.40 m is where the demo decides to stop. That is the unsafe half, and it is narrow: it needs the true obstacle inside the stop distance and a survivor just outside it.
- `compensation_height` is the whole fix, a pure function that hands back the height to reject with or None and why there is none. None switches the rejection off, which is what an unknown altitude already did, and the reason is split from the age for the same reason `hold_reason` splits them - an age that ticks up every message must not re-log ten times a second. Both nodes use it and both say "Not rejecting floor returns: the attitude is stale" rather than quietly becoming a different node.
- `scan_is_usable` became `reading_is_fresh`. It was already the general function, and calling it `scan_is_usable(pose_age, timeout)` would have been the kind of name that makes a reader trust the wrong thing.
- Proved it as a behaviour, not just as arithmetic. `check_sensor_dropout.sh` publishes that exact geometry, and the lean is the only thing that stops: the scan and the height keep arriving, so nothing the node watched for staleness before has changed. With the attitude live it commands 0.5 m/s, which is correct for a vehicle really leaning that far; a second and a half later it must command zero. Setting the timeout to 1e9 makes it fail with "kept commanding 0.5 after the attitude stopped arriving", which is the negative test.
- The guard has a second failure mode of its own - switching off when nothing is wrong - so `check_forward_flight.sh` now asserts the rejection stays on from "cruising" onwards. AP_DDS publishes the pose every 33 ms and the rangefinder bridges at 20 Hz against a 0.5 s timeout, so anything there would be a real interruption rather than a tight margin.
- Verified: 48 unit tests, baseline CI green, forward flight holding 1.36 m from the wall with 0.91 m of rotor clearance.
- One thing found and deliberately not fixed. The downward rangefinder reports slant range, so leaning 30 degrees it reads 0.639 m where the vehicle is 0.551 m up, and the error grows as 1/cos. Multiplying by cos(roll)cos(pitch) is two lines, but it over-states the height, which under-rejects - the safe direction - and the 0.25 m margin absorbs it today. Correcting it makes the rejection more aggressive, so it belongs with a flight check rather than in this commit. On the backlog.

- Took the slant-range correction off the backlog, which I had left there the same day for wanting a check rather than a commit. The downward rangefinder measures along its own axis, so leaning it reports h / (cos roll cos pitch) and not the height: 0.639 m in the leaning world where the sensor is 0.551 m up. `height_from_slant_range` undoes it, and `compensation_height` applies it, so what the nodes keep from the Range message is now the slant it actually measured rather than a height it never was.
- The check is against the simulator, not against the formula. `scripts/gazebo_link_truth.py` composes the model's world pose with the link's model-relative pose and subtracts the floor's surface - which it reads out of the world file, because a box centred on zero has its top at half its thickness and nothing else knows that. `check_leaning_scan.sh` passes that number in, and the corrected height has to land within a centimetre of it: 0.554 m against 0.551 m, which is the sensor's own 0.01 m range resolution. Making the correction a no-op fails it with both numbers named.
- The check also refuses to pass when the raw reading already matches the truth. Without that it would go on passing at a gentle attitude where the correction does nothing, which is exactly how a check outlives the thing it was written for.
- Retuned the stale-attitude case in `check_sensor_dropout.sh` rather than leaving it to drift: it published 0.90 m as a height, and 0.90 m of slant is now 0.78 m of height, which rejects everything ahead and would have passed for the wrong reason. It publishes 1.039 m of slant, which at 30 degrees is the 0.90 m the geometry was chosen for.
- Baseline CI failed once on the way through, on something I had not touched: `check_sensor_interface.sh` waited for the rangefinder topic and then asked for the type of four, so the 10 Hz lidar could still be undiscovered and the check failed with "expected sensor_msgs/msg/LaserScan, got 'nothing'". It waits for each of the four now. Pre-existing, and a flake that fails loudly is still a flake.
- Verified: 53 unit tests, baseline CI green, forward flight holding 1.39 m from the wall with 0.93 m of rotor clearance.
- Left one thing measured and open. The rejection is handed the rangefinder's height and uses it as the lidar's, and those are 44 mm apart at this lean - 0.551 m against 0.595 m. The direction is over-rejection and the 0.25 m margin covers it, but the fix needs the offset between two links inside the demo nodes, which is model knowledge they do not have. TF already carries it and neither node listens to TF. On the backlog rather than guessed at.

- Banked the vehicle, because everything that had ever produced a real scan was pitched and nothing was rolled. The projection's drop is `-sin(pitch) x + cos(pitch) sin(roll) y`, and those two terms are not equally tested by a pitched world: the pitch term is even in the bearing, so it is the same on both sides of the sector and a scan indexed the other way round the circle would give identical numbers. The roll term is odd. `leaning_test.sdf` therefore cannot see the scan's angular handedness at all, and a unit test cannot either - it writes both conventions itself.
- `banked_test.sdf` holds the model static at 25 degrees of roll and 20 of pitch, two different sizes on purpose so a roll and pitch swapped for each other cannot hide behind matching numbers. The floor then arrives asymmetrically, which is the whole point: 1.21 m off the right wing, 1.76 m straight ahead, 6.2 m off the left where it has run past the edge of the room. Measured 1.205 m at -30 degrees, against 1.217 m predicted from the world file.
- The control is what makes it worth having. Flipping the roll sign in `ground_return_height` leaves `leaning_test` passing and makes `banked_test` fail with "The floor survived compensation as an obstacle at 1.205 m". Two worlds, one defect, and only one of them can see it.
- `check_leaning_scan.sh` takes the world as an argument now, and a minimum roll, so the banked run fails rather than quietly becoming a second pitched one if someone zeroes it. The lean test itself moved from pitch alone to `acos(cos roll cos pitch)`, the angle between the airframe's own up and the world's, which is what leaning means when it is spread over two axes.
- Corrected a comment that had the roll convention backwards. A unit test read "Roll right is negative about the forward axis, which drops the left", and in REP 103's x-forward, y-left, z-up frame a positive roll takes the left wing towards +z: it raises the left and drops the right, which is banking right. The assertion was right and only the label was wrong, which is exactly the confusion that test exists to prevent. Both signs are now stated and tested rather than one.
- The slant correction held up at a second attitude without being retuned, which is the first evidence it is geometry and not a fitted number: 0.646 m of slant became 0.550 m against a true 0.555 m, at a lean built from both axes rather than one.
- Verified: 54 unit tests, baseline CI green with both worlds.
- Said no to one thing. Flying a circuit of the room would test the same geometry with two streams to align during a transient instead of two steady numbers, and the demo cannot turn at all today - it publishes only `twist.linear.x`. That is a demo behaviour to build, not a test to add, and it is on the backlog as such.

- Closed the last thing I had left measured and open: the rejection was handed the rangefinder's height and used it as the lidar's. The two sensors are 26 mm apart along x and 66 mm along z, and level that whole 66 mm was height being thrown away - more than a quarter of the 0.25 m margin that was absorbing it. Leaning it is less, because the offset is bolted to the airframe and rotates with it: at 30 degrees nose-down the part that sits ahead of the rangefinder swings down and takes some of the height back, leaving 44 mm.
- The third row of the rotation is now written once. `body_point_height` takes a body-frame point and says how high it sits, and `ground_return_height` is one call to it with a point in the scan plane. Two copies of those signs would have been two chances to get them wrong, which is the defect this whole thread has been about.
- The offsets are parameter defaults, not a TF lookup. TF carries the same numbers and neither node listens to TF, so this is model knowledge living outside the model - and the answer to that in this project is already established: `check_model_consistency.py` reads the defaults out of the nodes' own source and fails if the model moves either sensor. Verified by moving one: "obstacle_monitor.py places the lidar +0.0500 m from the rangefinder along z and the model places it +0.0660 m".
- That check's failure header said "The URDF and the SDF describe different drones", which is no longer true of everything it can report. It says "The drone is described inconsistently across files" now, because naming the wrong pair of files sends a reader to look in the wrong place.
- Both worlds assert against `front_lidar_link` now rather than `rangefinder_link`, which is the property rather than an intermediate step: what the rejection needs is the height of the sensor whose beams it projects. 0.598 m against 0.595 m pitched, 0.597 m against 0.602 m banked. Two worlds at once, so a number fitted to one of them fails the other.
- Added the three checks that were missing from `scripts/menu.sh` - the pitched world, the banked world and the attitude estimate. A menu that claims to be the one place everything runs from has to be that.
- The dropout check's stale-attitude case failed on the first CI run after this, and it failed at the right step. Its control asserts that with a live attitude the vehicle *does* fly, and 66 mm of extra height moved the wall from inside the rejection to outside it, so the vehicle held. The case published a slant chosen for a 0.90 m height under the old arithmetic; it publishes 0.988 m now, which is 0.856 m for the rangefinder plus 44 mm for the lidar above it. A check whose numbers depend on the pipeline it exercises has to be retuned when the pipeline changes - the alternative is one that quietly passes for the wrong reason, which is what the control is there to prevent.
- Verified: 60 unit tests, baseline CI green over both worlds.

- Gave the demo a `TURN` state, which is the answer to "shouldn't it fly round the room?" - and it is a behaviour, not a test. Blocked ahead, the vehicle yaws towards whichever side has more room and carries on. `nearest_in_sector` took a `centre_rad` so the same windowing and the same floor rejection answer what is off each wing; the rejection has to apply there too, because leaning, the floor is off the wing exactly as much as it is in front.
- Four decisions in it are worth stating, because each is a way it could have gone wrong. Only an obstacle is a reason to turn - a stale or empty scan means the vehicle cannot see, and rotating on that is choosing a direction out of a picture it does not have. The side is chosen once and latched, or a rule that re-decides every scan leaves it rocking in place. Nothing translates during the turn, because the demo decides on a forward sector and while rotating that sector is not where it is going. And resuming is deliberately harder than stopping was: `way_is_clear` wants a further 0.3 m, or the two decisions chatter against each other at the threshold.
- Off by default. Stopping for the wall is the behaviour `check_forward_flight.sh` verifies and the one worth trusting; flying on past it is a second thing to ask for, not a change to the first.
- `room_test.sdf` is a closed room, 8 m by 6 m, because `indoor_test.sdf` is not a room at all - a floor and two panels - and a turning vehicle simply leaves it. `scripts/check_room_circuit.sh` flies it and reads the walls' inner faces out of the world file rather than repeating them: 630 degrees of turning in 110 s, first leg to x = 3.10 m, then 6.23 m on a heading of +168 degrees, closest approach to any wall 0.75 m.
- The first run of that check failed and the defect was in the check. It reported "turned 11 degrees" and called the yaw rate broken, when 11 was radians: the vehicle had turned 630 degrees, nearly two full circuits, and the track showed it plainly. A check that converts nothing and asserts against a number in the other unit fails in the direction that blames the thing it is watching.
- Then the log line "Turning right: 2.81 m off the left wing, 2.81 m off the right" turned out to be a near-tie printed to two decimals - the sides differed by 6 mm. Printed to three now, because a log that reads like a contradiction costs more than the two characters.
- Found a real defect on the way to making it watchable. `sitl_gazebo.launch.py` includes `gazebo.launch.py` and passed it nothing, while declaring neither `gui` nor `world` itself. So `scripts/demo.sh` asked for `gui:=true` on every run and it went nowhere - the Gazebo window never opened, against a default of false, while the script's own message said "Opens Gazebo and RViz" - and `--no-gui` turned off something already off. Both are declared and passed through now, which is also what lets `--circuit` select the room.
- `scripts/demo.sh --circuit` and two menu entries, so the thing can be watched rather than only asserted.
- One more defect fell out of verifying all this, and the first explanation for it was wrong. `check_unified_launch.sh` failed with "/ap/cmd_vel is missing" straight after I had given the unified launch a `gui` argument, so the argument looked guilty - except that check passes `gui:=false` explicitly and always had. The real cause was a `gz sim` from the previous check still running three minutes later, holding the partition. Killing the launch's process group misses it often enough to matter, and all five checks that start `gazebo.launch.py` left it behind the same way. They kill it now, scoped to this project's own world files so an unrelated simulation on the machine is not touched. It is the failure the SITL ports already taught this project: a survivor of one run silently fails the next and looks like a defect somewhere else entirely.
- The `gui` default went back to false anyway, matching the launch it includes. Declaring an argument that was being dropped should make it work, not change what every existing caller gets.
- Verified: 67 unit tests, baseline CI green, forward flight still holding at the wall with turning off, the circuit check passing, and the unified launch serving Gazebo, ArduPilot and TF with no Gazebo left behind afterwards.
- What this is not is coverage. Turning towards the roomier side is enough to fly a room and not enough to cover one: the vehicle repeats a loop rather than visiting anywhere in particular, and nothing maps what it has seen. That is on the backlog as the next question rather than implied to be solved.

- Built the map, which is the half of "what is the circuit for" that has to exist before the other half is a question. The vehicle could fly a room and keep nothing; `occupancy_mapper` now ray-casts each accepted return from where the lidar was and publishes a 2D occupancy grid on `/openipc_cinewhoop/map`. Log-odds rather than a flag, because a flag cannot be argued out of once it is set - one spurious return would leave a wall in the map for ever - and unknown is kept apart from fifty-fifty, since a cell no beam has crossed is the only thing that says where the vehicle has not been.
- It is stricter with itself than the other two nodes are, on purpose. They can fall back on holding when the attitude goes stale or the floor rejection switches off; this one stops mapping entirely, because their failure is a transient stop and its failure is a wall drawn somewhere the vehicle never was, which stays in the map after the input recovers.
- The rotation is now written exactly once. `body_point_height` was the third row of Rz Ry Rx and the mapper needs all three, so `body_point_offset` is the whole matrix and the height is its third row - yaw drops out of that row, which is also why the floor rejection has never needed to know which way the vehicle is facing. Rejected floor returns are dropped whole rather than carved as free space up to the return: the beam did travel there unobstructed, but it was travelling downwards to do it, and that is not what a cell in a horizontal slice means.
- `scripts/check_room_mapping.sh` flies the circuit with the mapper running and asks the map what the room was, against the walls read out of the world file. All four walls mapped along 100 per cent of their length, wall cells 0.050 m off the wall at the median and at the 90th percentile, no occupied cell anywhere in the middle of an empty room, 97 per cent of the floor called free. That one comparison covers the scan's angular convention, the yaw the returns are turned by, the ray casting and the EKF's position - and the position is the part nothing had ever checked, because every earlier check asked about attitude or about a distance the vehicle did not have to know where it was to get right.
- The first run of the check mapped nothing at all, and the reason was the find of the day. Nothing started `range_adapter`, so `/openipc_cinewhoop/range/down` had no publisher, and the mapper correctly refused every scan. That topic is the demo's only source of height - and `check_forward_flight.sh` and `check_room_circuit.sh` had never started it either. Every flight either of them has ever run was flown with the floor rejection off.
- Worse, the forward flight check was written to catch exactly this and could not. It asserted that "Not rejecting floor returns" never appears after "cruising", and a node that never had a height says that once at startup and then has nothing left to switch off. A guard against something being turned off has to establish that it was on, or it passes most loudly in the case it exists to catch. It now requires "Rejecting floor returns again" first. Proved both halves: with `range_adapter` the flight is unchanged and holds 1.38 m from the wall with 0.91 m of rotor clearance, and without it the trajectory is identical to the centimetre and the check now fails with "The floor rejection never switched on".
- The map came out 0.15 m too big at the extremes and I nearly wrote that down as a finding. The median and the 90th percentile are both 0.050 m, which is exactly the half-cell quantisation costs, so the extent was two outlying cells and not a bias - the check reports all three now, because an extreme is what a bounding box gives you and it is the least representative number in the set. The tail is probably the pose being read when the scan message arrives rather than when it was taken: tens of milliseconds, which at 0.4 rad/s of yaw and 4 m of range is about that far. On the backlog rather than asserted.
- The wall-coverage assertion failed on its first run with the y+ wall at 6 per cent while the cell count on that same wall said 105. The defect was in the check: it searched for each wall *along* its length instead of across it, so the three continuous walls passed for the wrong reason and the fourth failed for a wrong one. A check that agrees with itself in three places out of four is still wrong in all four.
- The check writes the map out as a PGM now. Every question it raised cost another six-minute flight to answer, and one of those files answers most of them.
- Said no to two things. The map is stamped in a `map` frame that nothing broadcasts, so RViz has nowhere to put it and `scripts/demo.sh --map` says so rather than claiming a picture it cannot draw. And coverage is still not a question here: the LD06 sweeps the whole circle and reaches 12 m, so an empty convex 8 by 6 m room is mapped almost as soon as the vehicle is airborne, whatever path it flies. Coverage separates a good path from a bad one only where something blocks the view. Both on the backlog.
- Verified: 102 unit tests, baseline CI green including the model guard extended to the lidar's offset from `base_link`, forward flight holding 1.38 m from the wall with the rejection now demonstrably on, the circuit unchanged at 630 degrees of turning and 0.79 m of closest approach, and the mapping check passing.

- Gave the TF tree a root in the world, which is what the map was waiting for. `robot_state_publisher` served `base_link` and everything bolted to it, so the tree knew where the lidar was relative to the airframe and nothing knew where the airframe was - and the occupancy grid is stamped in a `map` frame that no transform reached. `pose_tf_broadcaster` publishes `map` -> `base_link` from `/ap/pose/filtered`, `sitl_gazebo.launch.py` starts it, and `check_unified_launch.sh` fails without it: a launch that claims to serve TF should serve a tree attached to something.
- Reading AP_DDS to write it turned up something worth knowing. `/ap/pose/filtered` carries `header.frame_id` = `base_link`, and that is wrong rather than a convention I disagree with: the body is filled from `get_relative_position_NED_home` swapped into ENU, so the content is where base_link is relative to home. A pose saying where base_link is cannot be expressed in base_link or it would be zero for ever. The mapper had already been ignoring the label and using the content, which is why its walls landed where the world file puts them; the broadcaster now ignores it deliberately and says so in the log line it prints on the first message, instead of leaving the next reader to find it the hard way.
- Collapsed REP 105's `map` -> `odom` -> `base_link` into one transform, and named the cost rather than pretending there is none. There is one estimate and nothing to correct it with, so the two frames would be the same numbers written twice; what is given up is that an EKF reset now teleports `base_link` where a separate `odom` would have absorbed the jump. Nothing downstream depends on that today.
- The broadcaster does not repeat the last transform on a timer. A pose that stops arriving has to become a gap in TF: a consumer meeting a gap refuses to transform, which is what an unknown position deserves, while one meeting a stale transform draws the map somewhere confidently wrong. Same reasoning as every other staleness guard here, in the one place where the failure is permanent rather than transient.
- `scripts/check_map_frame.sh` compares the transform against Gazebo's ground truth over a circuit, and two of the three things it asserts had never been checked. Position: `check_attitude_estimate.sh` parks the vehicle on a ramp, and a parked vehicle at the origin says nothing about where the EKF thinks it is. And yaw: a ramp is tilted in roll and pitch and cannot be tilted in yaw, so the one axis the floor rejection never needed was the one nothing had ever compared against truth. Result: 0.012 m at the median, 0.046 m at worst, yaw 0.01 degrees at the median over 3.6 m of travel and 630 degrees of turning.
- Its first run reported 1.17 m of error and 86 degrees of yaw error, and the defect was in the check. It called `spin_once` between samples, which processes one message at a time, while `/tf` arrives at 30 Hz and most of each iteration was spent waiting on `gz topic` - so the buffer fell further behind every second and the lookup returned where the vehicle had been. The listener is spun on its own thread now. A check that samples one stream by polling and another by subscribing has to be honest about which one it is starving, and the failure it produces blames the thing it is watching.
- Proved the yaw half bites by flipping the sign of the broadcast yaw: 179.5 degrees at worst, while the position half went on passing at 0.013 m. That is the point of asserting it separately - the two halves fail to different defects, and a check that only measured distance would have called that run clean. The position half had already proved it bites, by accident, when the lag run failed on it.
- The RViz config has an Occupancy Map display now and the Fixed Frame is still `base_link`. Switching it to `map` is what makes the room stand still instead of the vehicle, but it would break `display.launch.py` run on its own, where nothing publishes a `map` frame at all. One config that works in both launches, and the screen confirmation stays on the backlog where it already was.
- Checking one assumption about the new transform turned up something else. TF is looked up by time, so I measured what clock AP_DDS stamps the pose with rather than guessing: ArduPilot's UTC. The next question was what clock a consumer would be on, and the answer I wrote down - that Gazebo publishes no clock topic at all - was wrong. See the following entry; the probe that produced it was not talking to Gazebo.
- The one thing it did change here: the broadcaster is launched without `use_sim_time`. It reads no clock, copying the pose's own stamp rather than restamping, so the setting would do nothing either way.
- Verified: baseline CI green, the unified launch now asserting the rooted tree, the map frame check passing, and the TF tree smoke check unchanged.

- Corrected yesterday's finding, which was wrong, and the correction is the substance of this entry. I wrote that "Gazebo publishes no clock topic at all - not `/clock`, not `/world/<name>/clock`; `gz topic -l` lists neither". It publishes all of them. The probe that produced that was missing `GZ_IP`, so it was not talking to Gazebo at all - and it was not silent about it, it just reported nothing where I read "nothing published". What gave it away was running the same probe again and seeing no `dynamic_pose` topic either, which every flight check reads successfully every run. A probe that finds nothing has to be made to find something known first, or its nothing means nothing.
- The real state, measured in one instant with all three subscribed at once: Gazebo's `/clock` 22.3 s, the bridged front scan 22.3 s, `/ap/pose/filtered` 1789156172. Sim time counting from the simulator's start on one side, ArduPilot's UTC on the other, and the split is permanent - sampled every 15 s for a minute and both sides stayed on their own clock. So the conclusion survives and the cause does not: anything comparing stamps across the two halves of this system is wrong by 56 years, and nothing does, because every node takes its ages from its own clock at the moment a message arrives.
- What it does break is the one thing that has to compare them: a consumer looking up `map` -> `base_link` at the stamp of the thing it is drawing. That transform carries AP_DDS's UTC, so RViz on sim time can look it up at "latest" and at no particular time at all. `sitl_gazebo.launch.py` passes `use_sim_time` into `display.launch.py`, and it now passes false. On the wall clock the transform is usable, and `check_map_frame.sh` now measures that rather than assuming it: 20 timed lookups out of 20 at a stamp half a second old, alongside the position and yaw it already checked.
- Nearly shipped a second wrong thing on the way. The first run of that new assertion failed 20 times out of 20 with "extrapolation into the future", which reads exactly like the epoch split, and I changed the broadcaster to restamp every transform with its own clock - overriding the rule that a measurement keeps the stamp it was taken at - with a careful comment explaining why the measurement justified it. It did not. The assertion was running *after* `executor.shutdown()`, so the TF buffer was frozen and the transform aged by precisely the loop's own sleep: 0.05 s per iteration, then 0.55 s once each lookup added its half-second timeout. Two numbers that are exactly the loop's own timing are not a finding about the system.
- With the ordering fixed, the pose's own stamp passes 20 out of 20 as well, so the restamping was reverted and the rule stands. AP_DDS's UTC runs a couple of seconds *ahead* of wall time, and ahead is the harmless direction: a consumer asking for half a second ago asks for a time the transform has already passed. It drifts, because that UTC advances at simulation rate rather than real time, and if the simulation ever ran slow enough to fall behind the wall clock this would start failing - which is an argument for one clock, not for restamping.
- The whole episode is one shape twice: a measurement taken through an instrument that was not working, read as a fact about the thing being measured. Once with `GZ_IP` missing, once with the executor already shut down. Both produced confident, plausible, wrong explanations, and both were caught by asking the instrument to show me something I already knew was there.
- Verified: the map frame check passing with the timed-lookup assertion, 0.013 m at the median and 0.01 degrees of yaw unchanged, and baseline CI green.

- Built the world where coverage is a question rather than an answer, and the substance of this entry is that the first two versions of it silently were not. `cluttered_room.sdf` is `room_test.sdf` with a pillar and an enclosure in it, and `scripts/check_room_coverage.sh` flies the same circuit and measures the enclosure's inside separately from the room.
- Version one was an alcove along the +y wall, 4.5 m wide and 1.45 m deep: 94 per cent against the room's 96. Version two was a 2.8 m square enclosure with a 1.6 m door offset to one corner, on the stated theory that the corners furthest from the door are behind a wall from every point outside. It measured 97 against 94 - the inside of the enclosure came out *better covered than the room it stands in* - and the check passed and printed a satisfied summary while it did.
- What caught it was making the check record the path as well as the map. The vehicle had never gone in: 0 of 3636 poses inside the enclosure, closest approach 0.60 m. A coverage figure alone cannot say whether the map is good because the path was good or because the room was easy, which is the one thing this world exists to tell apart, so the path is now half of what the check prints.
- The geometry I had reasoned from was wrong in a specific way worth writing down. I checked whether a corner was visible from *a* point outside, found it was not, and generalised. A doorway is an aperture, not a pinhole: every point outside admits a different wedge, and the map accumulates over a whole circuit, so what has to be dark is the region no ray through *any* part of the opening reaches. Against that test a 1.6 m opening in a 2.8 m wall hides almost nothing. Occlusion needs a turn behind the opening, not depth behind it.
- Version three: `inner_baffle`, 1.2 m across the enclosure off the same wall the door is flush with, leaving a 1.6 m gap at the far end - a dogleg. Predicted the pocket behind it at about a sixth of the inside by working the umbra of the baffle against the whole doorway rather than against one point of it; measured 77 to 80 per cent where the plain enclosure gave 97. Both apertures are 1.6 m, which is what the demo needs ahead of it to keep flying, so the pocket is unreachable because of where the vehicle chose to go and not because it could not fit.
- Added the assertion the two failures were missing. There is still no ceiling on the enclosure figure while the vehicle is inside - that number is what a better rule for where to fly is meant to raise, and failing when it rises would punish the improvement being tracked - but a flight that stayed outside and still reads over 88 per cent fails, because the vehicle cannot have got better and the geometry can only have stopped hiding. Proved it bites by flying the world with the baffle deleted: 94 per cent, and the check fails with that message.
- The threshold is between the two measured bands rather than just above one: 77 to 80 with the baffle, 94 to 97 without, and about three points of run-to-run spread either side.
- The shape of the mistake is the same one as the `GZ_IP` probe and the shut-down executor, a third time: a measurement taken through an instrument that could not see the thing being measured, read as a fact about the thing. Here the instrument was the check itself, which reported coverage without reporting where the vehicle went, so a number that could only mean "the world is not occluding" read as "the map is good". The fix each time has been to make the instrument show something already known - here, the path.
- Verified: baseline CI green, `check_room_coverage.sh` passing at 77 per cent with the baffle and failing at 94 without it, and `check_room_mapping.sh` still passing unchanged at 96 per cent after the `coverage_fraction` signature moved to regions and exclusions.

## 2026-09-12

- **The demo goes into the enclosure now, and the number it was built to move moved: 96 per cent of the inside against 80 for the reactive rule, on flights that spend a sixth to a third of their poses in there against none at all.** Three pieces, and each of the last two exists because the flight before it failed in a way that named the next problem.
- `frontier_explorer` is the first: it reads the published map, finds the cells of known floor that touch unknown space, groups them into openings and says which one to head for. `simple_indoor_autonomy` steers at what it publishes and is otherwise untouched - it still answers "may I move", the new node answers "where to", and with the explorer stopped the demo is exactly the reactive circuit it always was.
- The first flight with it was a clean failure and worth the whole session. The explorer chose the enclosure's door eight times and the vehicle turned away from it eight times, at 1.35 to 1.40 m every time. Nothing was wrong with the steering: `way_is_clear` took the nearest return in a 60 degree cone and wanted 1.7 m of it, and a 60 degree cone at 1.7 m is 1.7 m across. An opening narrower than that cannot read clear however well the vehicle is lined up on it, and the vehicle is 0.167 m wide. The demo could not have flown through that door under any rule for choosing it.
- `nearest_in_corridor` replaces the cone with the swath the vehicle actually occupies: the rotor tips reach 0.08335 m from the centre, `corridor_margin_m` adds 0.25 m either side, and what is reported is the along-track distance rather than the slant range. A return outside that width is passed cleanly and is not an obstacle; a wall across the front reads exactly as before. The corridor starts at the nose, because a pillar drawing level has an along-track distance of nearly zero while being no obstacle at all, and stopping for it is stopping where stopping cannot help.
- The wall is what the safety property was always about, and it is unchanged: `check_forward_flight.sh` holds at 1.39 m and stops with 0.93 m of rotor-tip clearance, where the threshold is 0.80 m of wanted clearance plus 0.60 m of braking. `obstacle_monitor` keeps the cone on purpose - it tells whoever is watching what is nearby, which is a proximity warning, not a decision about whether to move.
- The airframe's own width is now model knowledge that a node carries, so it is checked rather than trusted: `check_model_consistency.py` reads the rotor poses and propeller radius out of the SDF and fails if either node's `rotor_tip_half_width_m` drifts from it. Verified by setting it to 0.09 and watching the check fail with both numbers.
- That got the vehicle in - once. The second flight never entered, and the reason was the other half of the problem: the explorer said *where* and not *how*. It published the frontier's centroid, the vehicle turned to face it, and through a doorway the line to somewhere inside crosses the wall beside the door. Getting in the first time was the vehicle happening to be somewhere the line went through the opening.
- So the explorer works out a way there. `blocked_cells` grows the walls by what the vehicle needs - roundly, because a square corner claims 1.41 times the clearance diagonally and that closes doors it fits through - `reachability` sweeps outward from the vehicle over known free floor, and the openings are ranked by that distance rather than by the straight line. `carrot` puts the published point one stopping distance along the route, which is a direction that leads to the destination instead of one that merely points at it.
- The route answers outright what the previous version had to guess at. An opening with no way to it is not reached by the sweep and is never chosen, so the timeout that abandoned a target "probably behind a wall" is gone, and so is the cooldown that stopped it being re-picked immediately. Both were inferences from how long the vehicle had been failing to arrive.
- Two flights with the route: in both, and 96 per cent of the enclosure in both. Before it, one in two.
- Then two more that were not, and each named its own cause. One planned a route that ran along the grown wall, which through a 1.6 m door leaves the vehicle half a metre off centre with a jamb 0.3 m to one side - inside the corridor, so the demo read the way as blocked at the very door it was sent to. The route now keeps a cell more than the corridor's half width, and that cost the openings between 0.67 m and 1.0 m wide, which is the right way round: a route the vehicle cannot reliably fly is not a route.
- That in turn exposed a vehicle standing closer to a wall than the clearance having nowhere to step at all, so the sweep found nothing and the explorer would have called a room covered from half a metre off a wall it had not looked behind. Leaving the grown region is allowed now, bounded by its own thickness and spent by reaching clear floor.
- The other flight got through the door and spent its second half turning: 133, 143, 146, 171 and 172 degrees, one after another. Nearest-by-distance does that by construction - fly to an opening, the opening is explored and stops being one, and the nearest of what is left is behind you. A turn is not free and the vehicle knows what it costs: 0.4 rad/s of yaw against 0.5 m/s of cruise makes a radian worth 1.25 m, so turning right round costs four metres of flying. Openings are chosen by that cost now, which is a price rather than a prohibition - a turn worth taking is still taken.
- Two flights with the turn priced in: in on both, 96 and 97 per cent, 15 and 35 per cent of the poses inside.
- **Asked what the demo makes of a table, and the answer was worth writing down as a check.** The LD06 is one plane high - that is the datasheet sensor, not a simplification of it - so everything the vehicle knows is a horizontal slice at the height it is flying. A table's top is at 0.75 m and the demo cruises at 1.00 m, which was the whole expected story: fly over it, see nothing.
- Written that way the check failed, and the measurement was right. Flown at 1.00 m the map held seven cells of a table the level plane passes 0.28 m above. The plane is the airframe's and not the world's: it tips with every degree of pitch, and at the 0.90 m the vehicle came to the table, 18 degrees of nose-down reaches it - which is what braking from 0.5 m/s looks like. The seen-and-unseen framing was mine rather than the physics', and height alone decides nothing.
- The two heights also refuse to be told apart by how much reaches the map: 0.50 m through the legs gave four cells and 1.00 m over the top gave seven, so the bands overlap and overlap the wrong way round. What separates nothing is not a threshold.
- What is true at both heights is what the check asserts now. The table is never a surface - four to seven of the 126 cells it stands on, under a tenth - and what does come back is its outline, every cell within 0.30 m of the footprint's edge, because a slice of a table is where the plane crosses its legs and its rim. So the map can say something stands about there and cannot say it is a table: nothing downstream can fly under it, avoid its top, or know it is one object.
- The check had repeated this project's own mistake twice over before it was any use. It asserted about the map without recording the path, so "the table is not in the map" could equally have meant the vehicle never went near it; and it wrote its picture after the assertions, so a failing run left nothing to look at. Both fixed: the path is recorded, the closest approach is printed, a flight that never came within the 4.6 m where one degree of beam spacing is sure to catch a 0.08 m leg fails outright, and the map is written before anything can exit.
- One arithmetic finding fell out of flying at 0.50 m and is now a backlog item rather than a surprise for later. `ground_margin_m` is a fixed 0.25 m, so at 1.00 m the lidar has 0.80 m to give away and a return 3 m out survives 15.5 degrees of nose-down; at 0.50 m it has 0.30 m and the same return is discarded at 5.7 degrees, which is less than the vehicle pitches to get moving. Low flight quietly throws away real obstacles at range, exactly where flying low was the point.
- `scripts/demo.sh` grew `--explore` and `--table`, and `scripts/menu.sh` lists both. The checks run headless because they are checks; there was no way to watch the flights they measure.
- **Made the floor rejection's margin the error bar it always was, and the map got better at once.** `ground_margin_m` was a flat 0.25 m: anything computing out lower than that was floor. That answers "is this return low", and the question is "is this return on the floor". The two differ wherever a beam strikes something tall near its foot, which is what a leaning vehicle's forward beams do - nose-down 5.7 degrees at 0.55 m, a wall 3 m away is struck 0.25 m up its face, and that return, the only evidence of the wall the vehicle is about to fly into, was thrown away as ground.
- An error bar grows with range, because an attitude wrong by an angle puts a return at range r wrong by r times that angle. So the margin is 0.10 m for what is wrong here - the rangefinder's reading, the floor not being flat - plus two degrees of lean, which is 0.035 m per metre. At 3 m that is 0.21 m and at 8 m 0.38 m, where a floor return genuinely cannot be told from a low one. The two degrees is the number hardware has to settle; SITL's EKF is fed a noiseless IMU and would accept anything.
- The unit test that had to change said the right thing for the wrong reason. It held that at 0.5 m up and 20 degrees down a return 1.0 m out is indistinguishable from the floor, and called that a property of the geometry. It is a property of the error bar, and with a bar of 0.135 m at that range the return at 0.16 m is a wall - which it has to be, because 0.16 m up a wall is the only warning of the two metres of wall above it. The property survives further out: at 2.0 m the same beam is aimed below the floor and there is nothing to tell apart.
- `check_sensor_dropout.sh` had its leaning case built around the flat bar, so its numbers were rebuilt around the new one: 0.850 m of slant instead of 0.988, which puts the lidar at 0.780 m, and the two returns are then split by four millimetres. That narrowness is the case, not a fragile test - the returns are 0.05 m apart in height and the rule has to put the bar between them.
- The table measured the improvement without being asked to. `check_table_height.sh` flown at 0.50 m gave four cells on two legs with the flat bar and fourteen on all four with the error bar, and failed on its own ceiling of a tenth of the footprint - a check written against the old measurement catching the new one. Most of the table had been going into the map as floor, which is the wall defect from the other side. It is still an outline and still not a surface: every one of the fourteen sits within 0.10 m of the footprint's edge.
- Verified: baseline CI green, `check_sensor_dropout.sh` passing on rebuilt numbers, and a coverage flight into the enclosure at 94 per cent.
- The check had to be corrected twice on the way, both times for measuring the path when it meant to measure the mapper. Each wall was held to 60 per cent of its length, and the same working mapper read 47, 48 and 73 per cent of the x- wall on three flights that differed only in how long the vehicle spent inside the enclosure. 2.9 m of that 6 m wall stands behind a 0.50 m slot, and the vehicle flies a 0.67 m corridor, so it can never get in front of that stretch. Wall coverage is now measured over the reachable length, where 80 per cent is a statement about the mapper again, and the reachable fraction is printed beside it.
- The other correction is that the check now asserts the improvement instead of only printing it. With the explorer flying, the vehicle must enter the enclosure and must read above the 88 per cent a flight from outside can get through the doorway - the ceiling that already proves a flight stayed out, used as a floor for one that went in. `EXPLORE=0` still flies the reactive rule and is held to none of it, so the comparison stays honest: 80 per cent, never in, closest approach 0.37 m.
- It also collects the wall complaints to the end rather than exiting on the first. A check that stops at its first complaint shows whichever number it reached first, and the wall figures are the ones the coverage figures explain.

- **Wrote the implementation specification, because there was no document anyone could build this from.** `spec/05_demo_nody.md` describes five nodes and is two nodes and a session behind - no `frontier_explorer`, no `range_adapter`, and parameters named things the code never called them, like `turn_duration_s`. Worse than incomplete: it would send a reimplementation the wrong way. And the algorithms live in the two helper modules, which no document in `spec/` mentions at all.
- `spec/10_implementation_spec.md` is that document. Every rule, every constant and every edge case, written so the behaviour can be rebuilt in another language without reading the Python - which is the point, because that is what it is for. Each number says where it came from, and they are sorted at the end into the four kinds: out of the model, measured, policy, and unfounded. The last kind has one entry, the two degrees of attitude error, and it says so.
- The two older documents now say at the top that they are the original design and that this one wins where they disagree.

## 2026-09-13

- Costed the BetaFPV Pavo20 Pro as a carrier for the LD06 and the EMAX Wyvern, which is the revision [the H7 decision](./decisions.md) said to make if the mass estimate became a problem. It did: with the lidar the CineLog build is 294 g. Written up as [Pavo20 as a carrier for the LD06](../spec/realna_stavba_dronu/10_pavo20.md).
- The first answer was wrong twice over and both corrections are in the document rather than edited out of it. Czech shops were said to carry nothing but an O4 Pro bundle at 487 EUR; hobbydrone.cz has the bare frame at 352 Kc, in stock, which makes the Pavo20 build about 1000 Kc cheaper than the CineLog rather than dearer. And switching airframes was said to cost a recalibration of the whole project; across all four demo nodes exactly one parameter knows about the airframe, `rotor_tip_half_width_m`.
- On 3S the Pavo20 is a worse machine and the reason is not the frame. Halving the disc area only takes 21 per cent off the induced power while the smaller pack takes 46 per cent off the energy, so endurance drops to about 2.4 minutes against 3.5. On 4S with the same 750 mAh LiHV pack the two airframes come out at the same endurance to three figures, at 239 g against 294 g. The whole "Pavo20 flies less" result is "3S 550 mAh is half the energy".
- Three things looked like they could kill it and the document works through all three. The 36 mm MicoAir may not clear a 93.7 mm frame - but the iFlight Beast H7 55A AIO is ArduPilot-supported at 32.5 mm and 8.5 g, so a failure there is a smaller board rather than the end. The thermal worry stops being a discriminator once the frame's design load is named: it is sold with a DJI O3 bracket, and an O3 draws 12 to 16 W against a 200 mW OpenIPC unit's 2 W class. Only the third is genuinely worse here, and it is geometry: solving the CG puts the LD06 at x = +36.4 mm and the battery at -20.9 mm, and their footprints touch exactly, where the CineLog has 17.7 mm of slack.
- Corrected `decisions.md` while checking that: it recorded the stock BetaFPV F4 as sharing the 25.5 x 25.5 pattern of the ArduPilot H7 AIOs. BetaFPV publish 26 x 26, for both the board and the frame, and so does the Czech listing. Close enough to bolt together, not the same number.
- Then built the airframe in simulation rather than leaving it a table. `models_pavo20/` holds a model of the same name as the flown one, so all seven worlds and `gz_bridge.yaml` keep working untouched; `OPENIPC_AIRFRAME=pavo20` picks the directory and the parameter file. `check_model_consistency.py` takes an airframe argument and checks every one it knows by default, printing the node parameters a variant must be passed instead of asserting defaults it cannot own. Negative-tested by moving the variant's lidar 3.6 mm.
- The rate gains transfer unchanged, and that is a result rather than a shortcut. Roll authority is peak moment over roll inertia: the CineLog is 0.3154 N m over 0.000458 and the Pavo20 is 0.1492 over 0.000218, which is 689 against 684 rad/s^2. The shorter arm and weaker motors cut the moment by 53 per cent and the lighter frame with its lower mast cuts the inertia by 52 per cent. One value differs in the whole parameter file, `MOT_THST_HOVER` 0.49 against 0.46 - higher despite 84 g less, because 2.2 in propellers give up more thrust than the airframe gives up mass.
- Flown against the same checks, and the prediction held to a tenth of a degree. Thrust stand 5.04 m for 5.0; guided takeoff peaks at 2.08 m and settles at 2.01 for 2.00 with a worst tilt of 15.5 degrees against the CineLog's 15.6 on the same day; forward flight holds 1.39 m off the wall with 0.93 m of rotor clearance against 1.36 and 0.90. Baseline CI stayed green.
- The coverage result corrects something said earlier in the same document. A machine 45 mm narrower was called a noticeably different proposition for getting through a door; it is not, for today's rule. Both airframes went inside the enclosure, the Pavo20 7 cm deeper and with 17 per cent of its poses in there against 15. That is what the geometry predicted - the corridor is 622 mm against 667 because `corridor_margin_m` 0.25 dominates it - and single runs at that margin are probably inside run-to-run spread anyway. The honest claim is that nothing got worse, not that the mapping improved.
- Then went and looked at how the frame is actually built, from teardown photographs and the frame's own parts list, because points 1 and 3 were resting on assumptions nobody had checked. It is not a flat-plate whoop: the ducts are one moulded ring assembly at the bottom, a carbon X plate above them carries the motors and the FC on 8 mm shock balls, a plastic tower on top carries the camera and HD VTX, and the battery straps over the tower.
- That turned point 1 into a wrongly asked question. The propeller-free circle in the middle has a radius of 18.91 mm, so no candidate board fits inside it - the stock 29 mm board's corners are already 1.6 mm under the discs, and the photograph shows the blades passing over the FC. Footprint is not pass/fail; height is. Against an 8 mm shock ball the MicoAir's 8 mm thickness is about 2 mm more than the stock board, which is a far smaller question than 7 mm a side, and the 32.5 mm Beast H7 sits under it as the fallback.
- Corrected a claim made earlier in the same document: the Wyvern does not need a TPU adapter for the VTX bay. BetaFPV list the O3 bracket as taking the Caddx Vista and the RunCam Link, both 25.5 x 25.5 stack units, and the bracket is built for a module of 32.5 x 30.5 x 14.5 mm and 28 g. The 20 mm in the catalogue is the camera spacing, not the VTX.
- Point 3 got worse, and only the photographs could have shown it. The CG solve puts the LD06 body from +17 to +56 mm, and that is exactly the footprint of the camera tower - which the model carries as a 26 x 22 x 20 mm box on the nose because that is what the CineLog has. The lidar would be inside it. The resolution is a part that has to be designed anyway: the Wyvern replaces a 28 g O3 with a 14 g board, so the stock bracket comes off and a TPU tower carries the Wyvern lower with a platform for the LD06 on top, returning about 18 g.
- What that reorders is the next action. The board mock-up is no longer first; the tower height and where the LD06 lands on it is, because it is the only thing still deciding and the only thing photographs cannot give. The 352 Kc frame comes after it, to measure against.
- What the simulation did not close: a rate-gain sweep on this airframe, anything mechanical, and endurance. The model has no battery, no board outline and no duct height that is not still a placeholder on both machines. The 352 Kc frame and a printed mock-up of the board remain the next thing to do.

## 2026-09-14

- Published the Pavo20 parts list and the CineLog one as web pages, and in doing so found that the simulation and the shopping list had drifted apart. `models_pavo20/` was built from the airframe study in `10_pavo20.md`, which chose LAVA 1104 5500KV, an iFlight Beast H7 and a 750 mAh pack at 0.2216 kg. The costing found the LAVA is not sold in this country at all, so the bill of materials buys Flashhobby A1204 5200KV, a MicoAir H743 and an 850 mAh pack, and the machine is 0.22934 kg. The model now follows the bill of materials rather than the study that preceded it: `maxRotVelocity` 5950 -> 5580, per-link masses off the itemised budget, `MOT_THST_HOVER` 0.49 -> 0.53.
- Every figure the published list quotes now comes out of the model too: 202 g per motor, 808 g of thrust, thrust to weight 3.52, hover at 53 per cent. That is not a coincidence - the list derived 202 g by the same method the model uses, so making them agree was a matter of applying it in both places rather than of choosing numbers.
- The statement in yesterday's entry that "the rate gains transfer unchanged, and that is a result rather than a shortcut" was true of the model as it stood then and is not true of this one. Roll authority is 583 rad/s^2 against the CineLog's 689, a ratio of **0.85** where it was 0.99: the A1204 is 12 per cent weaker than the LAVA and the in-stock parts are heavier, so the moment fell further than the inertia did.
- So the sweep finally got run on this airframe, which is the piece of work yesterday's entry listed as not closed. `sweep_rate_gains.sh` could not do it - the base parameter file and the model directory were both hardcoded, which is exactly the substitution the parameter file was making an argument for. It now takes `OPENIPC_AIRFRAME` the way `check_guided_takeoff.sh` does and writes into `logs/rate_sweep/<airframe>-<stamp>/`. Its default gains were also centred on "the current 0.018" long after both files went to 0.040, so a default sweep could not have found an onset above the flown value.
- Measured: 0.065 is clean (overshoot 4.3 per cent, 4 sign changes), 0.080 is gone (49.6 per cent, 162). The onset is in the same bracket as the CineLog's and 0.040 keeps the same 0.62 margin, so the gains stay - now measured rather than argued. **The prediction the sweep was run to test did not survive**: 15 per cent less authority should have moved the onset up by about as much and did not measurably. One step of the grid is 23 per cent, wider than the 18 per cent being looked for, so this is a grid too coarse rather than evidence against; nothing depends on which it is.
- Guided takeoff on the rebuilt model: peak 2.08 m, settled 2.01 m for 2.00, worst tilt 15.5 degrees - the LAVA model's numbers to a tenth. Checked that it was not a stale run, since `install/` could have shadowed the edits: the installed copies are symlinks into the source tree, and the script points `GZ_SIM_RESOURCE_PATH` and `--defaults` at the source anyway. The match is real, and the reason is that the altitude controller holds the climb rather than the thrust surplus, so this manoeuvre cannot see 15 per cent less authority.
- **The frame was being called by the wrong name, and a reader caught it.** Every document justifying the airframe said "Pavo20 Pro II", because Pro II is the ready-built 4S machine while the stock Pro is 2-3S on F4. But the build buys a bare frame and throws the electronics away, so 4S is a property of this build and not of the frame. Checked both catalogues: the two frames share the FC pattern 26 x 26, the motor pattern 4 x M2 at 9 mm and the 20 mm battery slot, and differ by 0.2 mm of wheelbase - 93.7 against 93.9 - and by their ducts. BetaFPV say that 0.2 mm is enough for a Pro II plate to rub propellers on the older duct, so the two are not to be crossed for spares. Corrected in `10_pavo20.md`, `11_kusovnik_pavo20.md` and `decisions.md`; the model and the CAD were already on 93.7 mm, which is what is bought.
- This is the second time the two catalogues got mixed: the 18 g correction in `10_pavo20.md` came from counting a Pro II top plate and bracket against the Pro frame.
- Two arithmetic errors fell out of building the pages, because a calculator makes claims checkable that prose does not. The Pavo20 page said the CineLog costs 12 330 Kc in six shipments; 12 330 is the consolidated variant and it is five, so the saving is two shipments and not three. And `08_kalkulace_dopravy.md` had variant A's goods copied from variant B, making A read 12 570 Kc against B's 12 330 - a 240 Kc gap where its own prose two paragraphs above says 218. A is 11 170 and 12 548, and the 218 was right.
- The pages carry what the documents had and the earlier versions did not: a basket calculator with a switchable source per line that prices the whole cart including the shipment it adds or saves, the ground equipment that is in no total anywhere, and the LD06's Allegro alternative - 636 Kc dearer on goods but only 329 Kc on the bill once the 419 Kc import shipping goes away. The CineLog page got the missing companion computer written out properly as the four paths from `09_kudy_do_ros.md`.
- Named the OpenIPC ground receiver, which had been "a WiFi card, chip not chosen". wfb-ng names RTL8812AU (tested on the ALFA AWUS036ACH), RTL8812EU (LB-LINK BL-M8812EU2) and Atheros AR9350. The documented shortcut that any monitor-mode card will do for receive-only does not apply to this build: the avoidance loop closes on the ground, so the station transmits too.

## 2026-09-19

- Two literature reviews landed, `reserseRoju` on coordinating a group and
  `reserseDronu` on the machine underneath it, written the same day and left as
  two folders because they are two storeys of one building. The second one
  reviews the first: nine claims they reach independently, six where they part.
  The sharpest is that the swarm review builds its platform chapter on "smaller
  is more agile" from the literature while this repository holds a measured
  counterexample - 583 rad/s^2 against 689 - and that mounting one 42 g sensor
  on the mast moved the machine ten times further than the whole frame change.
- Then set an actual task in `spec/roj/`: three drones map `cluttered_room.sdf`
  in simulation. That world was chosen because the repository already scores it,
  so the swarm has a number to beat rather than a demonstration to give.
- The task is stated as a split - one layer that does not know a swarm exists,
  one coordinator that may assume only what the contract lists - and working
  through the eighteen open questions moved where that seam is.
  `simple_indoor_autonomy` already subscribes to `explore/target`, so a
  coordinator writing `/ap/cmd_vel` directly would bypass wall avoidance, floor
  rejection and the battery landing. It sends a target and a speed limit
  instead, and a per-agent arbiter clips the nominal command. The cost is
  written down with it: a target today only biases which way the machine turns
  at a wall, so the swarm's authority starts at direction and brake.
- Two answers came out of source rather than reasoning. `fdm_port_in` is read
  only from SDF (`ArduPilotPlugin.cc:1272`), so three instances need a generated
  model and not an `<include>` override. And `occupancy_mapper` centres its grid
  on the frame origin, which is each agent's own EKF origin - three origins that
  differ make cell-by-cell merging meaningless, so that is now something M2
  measures against ground truth rather than something the plan assumes.
- The airframe for the swarm work is the Pavo20, recorded in `decisions.md`.
  Separation is geometry before it is anything else: rotor tip 0.06107 m against
  0.08335 m, so a pair needs 0.1221 m against 0.1667 m, and in a room 8 x 6 m
  with three machines that is spent three times over.

**M0, the single-drone baseline on the Pavo20.** Three runs of
`check_room_coverage.sh`, all green:

| | run 1 | run 2 | run 3 | spread |
| --- | ---: | ---: | ---: | ---: |
| room floor called free | 94 % | 93 % | 93 % | 1 point |
| enclosure inside | 96 % | 95 % | 94 % | 2 points |
| wall x- of the reachable part | 93 % | 97 % | 97 % | 4 points |
| wall y+ | 92 % | 92 % | 92 % | 0 |
| wall y- | 98 % | 100 % | 100 % | 2 points |
| poses inside the enclosure | 592/3661 | 607/3665 | 599/3658 | 16-17 % |
| deepest y reached inside | +1.04 m | +1.20 m | +1.17 m | 0.16 m |
| known cells | 4945 | 4926 | 4935 | 19 cells |

- So the noise floor of this measurement is about **2 points on the enclosure
  figure and 4 on a single wall**, and 16 cm on how deep the vehicle got. A
  swarm result inside that band is not a result. That is the number M0 existed
  to produce, and it is worth more than the coverage figures themselves: the
  earlier comment in the check about one wall reading 47, 48 and 73 per cent
  across three runs was the warning that this spread can be much wider.
- Run 1 is the interesting row. It has the best enclosure figure and the
  shallowest penetration, which says the enclosure number is not a
  straightforward function of how far in the vehicle went - so K2 for the swarm
  should be read together with the path, not alone.
- The second run failed before it flew, and the cause is worth the entry it got
  in `troubleshooting.md`: the guard against a second autonomy node asks
  `ros2 node list`, which asks a caching daemon, and 16 s after a green run that
  cache still held the dead node. `ros2 daemon stop` plus 20 s between runs
  fixed it. Three agents will make this worse, and a check for "is my agent
  already flying" cannot be a question to a cache.

## 2026-09-20

**M1: the three terms of `d_safe` nobody had measured.** Two new files,
`scripts/check_dynamic_limits.sh` for the stack and
`scripts/measure_dynamic_limits.py` for the measurement, one sortie in an empty
`room_test`. Pavo20, two good runs:

| commanded | steady speed | coast | coast time |
| ---: | ---: | ---: | ---: |
| 0.25 m/s | 0.255 / 0.256 | 0.144 / 0.143 m | 0.82 s |
| 0.50 m/s | 0.509 / 0.509 | 0.331 / 0.319 m | 1.09 s |
| 1.00 m/s | 0.978 / 0.984 | 0.790 / 0.770 m | 1.99 s |

Latency from command to motion 0.340 to 0.392 s over three identical trials in
each run, ramp tracking 0.095 and 0.097 m/s RMS, drift of the estimate against
truth 0.010 m horizontally over a 60 s hover. So `d_safe` is **1.30 m plus a
margin** at 1 m/s and 0.58 m at 0.5 m/s, and the script prints the sum with its
terms rather than a number on its own.

- Everything is measured against Gazebo ground truth, and every interval is
  read from that one stream. There are three clocks in this simulation - the
  pose's ArduPilot UTC, Gazebo's own, and the measuring process's monotonic -
  so a command's moment is taken as the simulator stamp of the last truth
  sample that had arrived when it went out. The pipeline delay then sits at
  both ends of every interval and cancels.
- **The first run measured a flight of zeros and looked like data.** A GUIDED
  velocity command replaces the takeoff submode, and the pilot node began
  publishing zeros from the moment it was constructed, so it cancelled the
  climb it was about to measure while every service reported success. The
  repository already knew this mechanism from the other direction - a leftover
  node from a previous run - and the guard in `check_forward_flight.sh` is
  exactly about it. Now in `troubleshooting.md` as its own entry, because a
  braking distance of 0.00 m written into `d_safe` would have meant three
  machines flying inside each other.
- The second run's drift figure was wrong too, and wrong the other way: 0.70 m
  horizontally and 0.957 m vertically. The estimate series was referred to its
  own first sample, taken after the climb, and the truth to its own, taken on
  the ground before it - so the whole takeoff was charged to the drift, and
  0.957 m was the takeoff altitude. Both series now refer to one instant, and
  the figure is measured over the stationary hover as well as the whole sortie.
- **The braking distance the project designs against is not the one it has.**
  `simple_indoor_autonomy` and `check_forward_flight.sh` use 0.60 m at 0.5 m/s,
  derived from the `PSC` parameters in `troubleshooting.md`; measured, it is
  0.33 m. The margin is about twice what is needed, which is the safe
  direction, but it is a margin and not a measurement.
- The drift number is the weak one and it is weak in the unsafe direction: 1 cm
  per minute is a property of noiseless SITL sensors, not of an optical flow
  sensor over a real floor. It enters `d_safe` twice, so on hardware it is the
  term that will decide the separation. Recorded as a lower bound.
- `GUID_TIMEOUT` is still at the default 3 s, and the measurement says what
  that costs: 3 m of travel at 1 m/s before braking even starts, in a room
  8 x 6 m. The parameter's range is 0.1 to 5 s and the swarm will command at 10
  to 20 Hz, so 0.5 s tolerates five to ten lost messages and costs 0.5 m.
  Deliberately not changed yet: every existing check would have to be reflown,
  because any pause in publishing longer than half a second becomes a stop.
  It is an M2 item.

- **M2 started, at the end with no flight in it.**
  `scripts/check_multi_instance_dds.sh` runs two SITL instances against one
  Micro XRCE-DDS Agent on SITL's own `quad` model - no Gazebo, no actuator
  bridge, no propellers - because before three models can share a world, two
  autopilots have to share a ROS graph without collision.
- It answers the question `spec/roj/05` left open: **one Agent serves both
  clients**. 18 topics under `/ap/v1/` and 18 under `/ap/v2/`, nothing
  un-namespaced beside them, both actually publishing rather than merely
  existing. Killing v2 leaves v1 publishing, v2 comes back as v2, and no third
  identity appears - which is an acceptance item of M2 in its own right.
- One thing fell out of `--wipe`: it writes `eeprom.bin` into the working
  directory, so each instance needs its own. Two autopilots over one storage
  file are not two autopilots.

- **M2, second half: the generator works and the flight does not.**
  `scripts/generate_agent_models.py` writes one model and one world per agent
  into `build/`, renaming the model, its four `<robotNamespace>` entries and
  its four rotor `<cmd_topic>` entries, and setting `fdm_port_in` to
  9002 + 10*index. That last part is why generation is needed at all: the port
  is read only from SDF. Both autopilots then reach the graph as `/ap/v1` and
  `/ap/v2`, both models spawn at the poses `spec/roj/08` R15 chose, and the
  identity-to-position mapping is right.
- **Then nothing takes off, and the reason is not in this repository.** A
  renamed Gazebo model does not turn its rotors. Four variants of the same file
  narrow it: unchanged flies; renamed to `openipc_cinewhoop_v1` does not;
  renamed to `alpha` does not, so it is not the name chosen; and renaming only
  the instance with `<include><name>` does not either, so it is the entity's
  name rather than where the name came from. In the failing case the autopilot
  ramps to 99 per cent throttle, all four rotor command topics carry healthy
  values, the motor topic has one publisher and four subscribers - and
  `rotor_0`'s orientation is identical across 0.6 s.
- Ruled out by measurement: the world edit, the offset start pose,
  `<robotNamespace>`, the IMU lookup and the state feed, a duplicate model, and
  stray processes. Written up in `troubleshooting.md`.
- Two of my own measurements turned out to measure nothing and are recorded as
  such: `joint_state` publishes no velocities even when the vehicle is flying,
  and driving the motors with a standing command and no ArduPilot plugin lifts
  neither model - so that isolation cannot separate the two plugins. A method
  that fails on the control case is not evidence about the test case.
- `check_two_agents_fly.sh` is committed **failing**, with the reason in its
  header. Nothing in CI runs it; `ci.sh` has an explicit list. The alternative
  was to leave 400 lines of working infrastructure untracked, which hides the
  state rather than recording it.

- **M4 built while M2 is blocked, because none of it needs a simulator.**
  New package `ros_ws/src/openipc_swarm/`: merging the agents' occupancy grids
  with a conflict count, assigning frontier targets so no two agents are sent
  to one opening, the separation filter, and the staleness and mission-epoch
  tracking. 40 tests, plus 9 for the arbiter in the demo package. Both suites
  run in `scripts/ci.sh` with no Gazebo and no autopilot.
- The exploration arithmetic is reused rather than rewritten: frontier
  detection, the reachability sweep and the turn-aware route cost all come
  from `grid_helpers`, which the single-drone explorer already uses and which
  `check_room_coverage.sh` already measures. Using the same cost function is
  what makes a swarm result comparable with the single-drone baseline.
- **A test corrected the design of the safety filter, and the correction
  matters.** `spec/roj/03` said to order the stop when the predicted
  separation drops below `d_safe`. But `d_safe` is a sum that already contains
  the braking distance and the latency, so a stop ordered at that line is
  ordered too late: the machines coast through it while obeying. The stop is
  now ordered at `d_safe + v_max*t_latency + s_braking`, which on the Pavo20
  at 1 m/s is 2.46 m, and `d_safe` goes back to being what K1 says it is - the
  line the run must not cross. Three stepped trajectories, with the machines
  decelerating at the 0.65 m/s^2 that M1 implies rather than instantly, now
  hold it: head-on, catch-up, and three converging on one point.
- A second correction from the same tests: scaling the speed limit by the
  agents' *current* distance looks sensible and does nothing. A pair 5 m apart
  and closing fast gets flagged and then told it may keep full speed, because
  5 m is a comfortable distance - which it is, right up until it is not. The
  limit scales on the predicted closest approach, which is also what raised
  the alarm.
- The arbiter (G9) is the agent's half of the seam. Two of its decisions go
  against the first instinct and are written down where they are made:
  silence from the coordinator means **slow** (0.25 m/s), not stop, because a
  stopped agent cannot even back out of a deadlock and `GUID_TIMEOUT` is the
  thing that stops a machine whose link is really gone - while an explicit
  stop is honoured immediately and never confused with silence. And the
  arbiter is opt-in: with it not running the autonomy publishes straight to
  `/ap/cmd_vel` as today, so every single-drone check flies unchanged.
- What M4 still cannot do is the contract tests from `spec/roj/04` - swapped
  identities and the coordinator going quiet - because those need machines
  running. They wait for M2.

- **The airframe switch was not switching the airframe, and it invalidates
  two milestones.** `model://` is resolved by sdformat through `SDF_PATH`, not
  through `GZ_SIM_RESOURCE_PATH`. The dev shell exports `SDF_PATH` pointing at
  `models/` - the CineLog - and `gazebo.launch.py` overrides it per airframe,
  but the fourteen shell check scripts never did. So every `check_*.sh` run
  with `OPENIPC_AIRFRAME=pavo20` loaded the CineLog and flew it under the
  Pavo20's parameters. Measured directly: with the environment those scripts
  build for pavo20, the file that loads is
  `models/openipc_cinewhoop/model.sdf`.
- All fourteen now export `SDF_PATH` with the airframe's directory in front,
  and the same command then loads `models_pavo20/openipc_cinewhoop/model.sdf`.
- What that costs: the M0 coverage baseline, the M1 dynamic limits and so
  `d_safe`, the pavo20 rate sweep, guided takeoff and forward flight are all
  CineLog numbers wearing a Pavo20 label. They are marked in place in
  `spec/roj/` rather than deleted - as CineLog measurements they are sound,
  and M0's run-to-run spread is still the noise floor it was measured to be.
- It also explains two days of "a renamed Gazebo model does not turn its
  rotors". There was no mechanism because there was no phenomenon: every
  variant that flew was the CineLog being substituted through `SDF_PATH`, and
  every variant that did not was the first time the Pavo20 model had ever been
  loaded. Renaming did not stop the rotors; it stopped the substitution. The
  entry is retracted in place with its evidence kept, because the sequence of
  eliminations is the useful part and the conclusion was the wrong one.
- The honest reading of the week: the thing that looked like a Gazebo bug was
  a substitution nobody had reason to suspect, and the tell was in the log all
  along - "the LAVA model's numbers to a tenth", "the rate gains transfer
  unchanged", a 15 per cent difference in roll authority that the sweep could
  not see. Three separate results that all meant the same thing, read three
  times as a coincidence.
- **And the real defect underneath: the Pavo20 model has never flown.** Loaded
  properly it ramps throttle to 46 per cent and stays on the ground. Next.

- **The Pavo20 model could not lift because its multiplier was the CineLog's.**
  The ArduPilot plugin maps full throttle onto `<multiplier>` rad/s and the
  motor model clamps at `<maxRotVelocity>`. The Pavo20 model carried
  multiplier 3980 - inherited from the CineLog, where 3980 is also its
  maxRotVelocity - while its own maxRotVelocity is 5580. So full stick reached
  3980 rad/s, which with its motor constant is 1.79 times its weight, and
  hover would have needed 75 per cent throttle against the 53 per cent its
  parameter file expects.
- The arithmetic says the multiplier should be 5580, and says it three ways at
  once: 6.36e-8 * 5580^2 is 1.980 N, which is **202 g per rotor and 807 g of
  thrust** against the bill of materials' 202 g and 808 g; thrust to weight
  3.53 against its documented 3.52; and hover at **53 per cent**, which is
  `MOT_THST_HOVER 0.53` in the parameter file to the digit. The parameter file
  had been computed for a model that was never built.
- Changed in all four control blocks, and **the Pavo20 then flew for the first
  time**: peak 2.09 m, settled 2.01 m against a 2.00 m target.
- It failed the check anyway, and the failure is the interesting part: worst
  tilt **33.4 degrees** against the 25 the check allows, where the CineLog
  does the same manoeuvre at 15.5. The gains it is flying were measured on
  what turned out to be the CineLog, so this is the first evidence about how
  the Pavo20 actually behaves - and it says the tuning does not transfer. The
  repository suspected something like this when it computed 583 against
  689 rad/s^2 of roll authority and then could not see the difference in a
  sweep; the sweep was flying the CineLog too.
- `check_model_consistency.py pavo20` still passes, so the URDF and the SDF
  agree about geometry; the multiplier is not something it checks.

- **The Pavo20 swept for the first time, and it needs its own gains.** With
  the throttle scale fixed and `SDF_PATH` no longer substituting the CineLog:

| ATC_RAT_RLL_P | result |
| --- | --- |
| 0.020 | never left the ground: 0.01 m of a 3.00 m target |
| 0.030 | the same |
| 0.040 | overshoot 8.1 %, rise 0.29 s, settle 0.82 s, rms 2.10 deg, 6 sign changes |
| 0.060 | overshoot 7.6 %, rise 0.31 s, settle 0.91 s, rms 1.71 deg, 6 sign changes |
| 0.080 | overshoot 8.4 %, rise 0.38 s, settle 1.08 s, rms 1.50 deg, 17 sign changes |

- At the bottom of the range this machine behaves the opposite way to the
  CineLog: too soft a rate loop and it does not take off at all, rather than
  wallowing its way up. At the top, 0.080 rings (17 sign changes) but is
  nowhere near the CineLog's 0.080, which was gone entirely at 49.6 per cent
  overshoot and 162 sign changes. Different machine, different curve - which
  is what the airframe flag was for and what it had never actually delivered.
- The gains moved to **0.060** in `ardupilot_params_pavo20.parm`, with the
  sweep written into the file above them. At the inherited 0.040 the Pavo20
  climbs but reaches 33.4 degrees of tilt, against the 25 the check allows; at
  0.060 that is 20.4 and `check_guided_takeoff.sh` passes. `check_forward_flight.sh`
  passes too: held 1.38 m off the wall with 0.82 m of rotor clearance.
- Also fixed the gap that let this through: `check_model_consistency.py` now
  compares `<multiplier>` against `<maxRotVelocity>` and the model's implied
  hover against `MOT_THST_HOVER`. Negative-tested against the old multiplier.
- **A mistake worth recording.** The first attempt at this sweep was run while
  the negative test was reverting the model file underneath it, so its first
  two gains failed for a reason that had nothing to do with tuning. Killed it,
  checked for stray processes and a clean tree, and swept again. Nothing from
  the first attempt is used.

- **M1 re-measured on the airframe it claims to measure.** With `SDF_PATH`
  fixed and the throttle scale corrected, the real Pavo20:

| | real Pavo20 | what was recorded (CineLog) |
| --- | ---: | ---: |
| coast from 0.25 m/s | 0.174 m | 0.144 m |
| coast from 0.50 m/s | 0.426 m | 0.331 m |
| coast from 1.00 m/s | **1.001 m** | 0.770 m |
| latency, three trials | 0.324-0.408 s | 0.340-0.392 s |
| drift over a 60 s hover | 0.012 m | 0.010 m |
| **d_safe at 1 m/s** | **1.56 m** | 1.30 m |

- The braking distance is 30 per cent worse and that is what moves `d_safe`.
  Latency and drift barely change, which makes sense: one is the command path
  and the other is the estimator, and neither is about this airframe.
- `spec/roj/02` and `/03` now carry these instead of the invalidation notices,
  and `test_safety.py` follows: `D_SAFE_M` 1.56, stopping room 1.409 m,
  deceleration 0.50 m/s^2. All 40 coordinator tests still pass, including the
  three stepped trajectories that assert K1 - the filter holds the larger
  separation with the slower braking, which is the point of having measured
  both rather than assumed either.
- M0 re-measured too, two runs so far: room 93 per cent, enclosure 94, 16 per
  cent of poses inside. **Coverage barely moved** - the CineLog read 93-94 and
  94-96 on the same trip. That is worth knowing: this metric is dominated by
  the flight policy and the room, not by which machine flies it, so the swarm
  comparison it exists for stays valid across the correction.

- **Two agents fly in one world, and the blocker was never what it looked
  like.** `check_two_agents_fly.sh` passes: both autopilots on the graph as
  /ap/v1 and /ap/v2, both models spawned where the generator put them, v1
  told to climb and v1 alone climbing - which is the test a crossed
  `fdm_port_in` would fail - then v2, then both holding 1.92 m apart against
  a `d_safe` of 1.56.
- Nothing about naming had to change. Two days of "a renamed Gazebo model
  does not turn its rotors" were the Pavo20's inherited throttle multiplier,
  seen only in the renamed variants because those were the only ones that
  actually loaded the Pavo20. The entry stays in `troubleshooting.md` with a
  line saying what cleared it, because the eliminations in it are sound and
  the conclusion was not.
- One more thing the bulk SDF_PATH fix got wrong and this run caught: in this
  script it pointed at the airframe directory, when the world includes
  `model://openipc_cinewhoop_v1` and only the generated directory has those.
  A mechanical fix applied to fourteen files needed one of them to be
  different, which is the usual way mechanical fixes fail.
- **R14 does not need revising.** One simulator per agent was the fallback if
  three models could not share a world; they can.

- **Three agents fly in one world, and the simulator does not notice.** Real
  time factor 1.0004 with one agent, 1.0000 with two, 0.9991 with three - so
  the answer to "what gets switched off when it will not fit" is nothing. That
  was M3's open question and it turned out not to be a constraint on this
  machine; on a slower one it is the first thing to measure again.
- `check_two_agents_fly.sh` is now `check_agents_fly.sh` and takes a count,
  because a script called "two agents" that flies three is a lie. One is
  allowed too, and is the control case the other figures are read against.
- Each machine climbs on its own command and the others stay down: v1 to
  0.88 m with v2 and v3 at 0.00, then v2, then v3. Closest approach between
  any pair while all three hold: **1.94 m** against a `d_safe` of 1.56.
- Two bugs of my own in the generalisation, both caught before their numbers
  were written anywhere. The single-agent run tripped on `truth[2]`, and the
  three-agent run measured only the v1-v2 pair - so the first 1.96 m figure
  was the closest approach of two thirds of the swarm. Re-measured over every
  pair: 1.94 m. Publishing the first number would have been the same mistake
  the airframe substitution was, on a smaller scale.

- **M0 re-measured on the Pavo20, and the third run changed what the baseline
  means.** Runs 1 and 2 read room 93 per cent, enclosure 94, with 16 per cent
  of poses inside. Run 3 read 89, 92 and **62 per cent inside**: it went into
  the enclosure and stayed, and the room outside paid for it - the x- wall
  dropped from 93 and 97 to 83.
- So this policy on this airframe is bimodal: it either commits to the
  enclosure or circles outside it, and which one a run gets is the largest
  term in the spread. The noise floor is not the 2 points the CineLog showed
  but **4 points on the room and 14 on a single wall**. Any swarm result
  smaller than that is indistinguishable from which mode the run fell into.
- That is a more useful baseline than three tidy runs would have been, and it
  is the second time this project has been saved by measuring three times
  instead of once.
- The CineLog on the same course read 94/93/93 and 96/95/94 with 16/17/16 per
  cent inside - much tighter. The difference between the airframes is
  therefore not only where they fly but how repeatably.

- **`GUID_TIMEOUT` is 0.5 s on both airframes now, down from the 3 s default.**
  M1 said what the default cost: a machine that stops hearing commands at
  1 m/s covers 3 m before it begins the metre it needs to stop, in a room
  8 x 6 m. The swarm commands at 10 to 20 Hz, so half a second tolerates five
  to ten lost messages.
- The worry was that it would end flights early, and it does not, because the
  autonomy publishes at 10 Hz through cruise and turns and publishes nothing
  at all while climbing - which is deliberate, and which the timeout does not
  touch: it covers velocity, attitude and rate control, and a guided takeoff
  is none of those.
- Reflown end to end on both machines, six checks, all green and nothing
  moved. Pavo20: takeoff 2.08 m at 19.7 degrees, forward flight 1.38 m off the
  wall, coverage 92 and 94 per cent. CineLog: takeoff 2.08 m at 15.5 degrees,
  forward flight 1.36 m with 0.89 m of clearance, coverage 94 and 95 per cent.
  Both coverage runs took the outside mode, 16 per cent of poses inside.

- **The three EKFs share one origin, and that was the last thing M2 had to
  find out.** The agents stand 2 m apart, so it took no manoeuvre to answer:
  v1 reports (-1.98, +0.49), v2 (+0.00, +0.49), v3 (+2.00, +0.49), against
  ground truth of (+0.50, -2.00), (+0.50, 0.00) and (+0.50, +2.00). Each
  reports its **spawn offset** rather than zero, so the origin is the world's
  and not each machine's own.
- That clears R16, which was the risk the merged map rested on: three grids
  centred on the frame origin are centred on the same physical point, so
  merging them cell by cell is sound. `spec/roj/04`, `/06`, `/07` and `/08`
  updated accordingly - the open-questions table in 08 is now empty.
- It also shows the axis mapping: reported x is world y and reported y is
  world x, which is `gazeboXYZToNED 0 0 0 180 0 90` in the model. Measured on
  MAVLink; whether `/ap/v<i>/pose/filtered` agrees is a separate check, and
  the coordinator is the thing that will need it.

- **Each agent's sensors now reach ROS under its own namespace**, which was
  P3 and the last piece of plumbing M2 needed. `generate_agent_models.py`
  derives one bridge config per agent from the single-drone template rather
  than the template growing placeholders: it substitutes the world, the model
  name and the ROS prefix, so `/openipc_cinewhoop/scan/front` becomes
  `/v1/scan/front` and the fourteen single-drone scripts that render the same
  template with `sed s/@world@/.../` carry on knowing nothing about agents.
- `/clock` goes to the first agent only. Three bridges forwarding one topic
  are three publishers on it, which is a race rather than redundancy.
- Flown with three: real time factor 1.0000 even with three bridges running,
  every agent's scan and rangefinder present under its own namespace, EKF
  origins still shared, closest approach 1.94 m.
- What is left of M2 is TF prefixes, which nothing consumes yet, and the
  per-agent acceptance runs. The next real piece is the coordinator node -
  wiring the arithmetic in `openipc_swarm` to agents that are now, finally,
  three separately addressable machines with sensors.

- **The coordinator exists as a node.** `ros2 run openipc_swarm coordinator`
  subscribes to each agent's pose and map and publishes targets, speed
  constraints, the merged map and the two logs. Smoke-tested: the graph comes
  up with `/swarm/map`, `/swarm/assignment`, `/swarm/safety` and a
  target-and-constraint pair per agent.
- It is deliberately thin. Everything it decides is decided by `merge`,
  `assignment`, `safety` and `tracking`, which have no ROS in them and 45
  tests between them; what is left in the node is wiring, and wiring is
  exactly what those tests cannot cover, so there is as little of it as the
  job allows.
- One piece of arithmetic did end up here and is tested: velocity by
  differencing consecutive poses, because the filter needs a velocity and
  AP_DDS gives a filtered pose. A one-sample-stale velocity makes the filter
  slightly conservative, which is the direction to be wrong in.
- It never publishes `/ap/v<i>/cmd_vel`. R19 again: the arbiter on each agent
  clips its own autonomy, so the worst a wrong decision here can do is slow a
  machine down.

- **The whole swarm stack runs and the loop closes.**
  `scripts/check_swarm_mapping.sh 3` brings up three agents in
  `cluttered_room` - each with its own bridge, mapper, autonomy and arbiter -
  plus the coordinator, and asserts that maps come out of the agents and
  constraints come back. Both directions verified by traffic and not only by
  a topic existing, which is the failure this project keeps meeting.
- Three copies of the demo stack is a configuration rather than a fork: every
  topic in those nodes is a parameter, and the airframe's geometry is passed
  from `check_model_consistency.py` exactly as `check_forward_flight.sh` does
  it, so a variant cannot quietly fly the other airframe's corridor width.
- Real time factor with everything running - three SITLs, three mappers,
  three autonomies, three arbiters, three bridges and the coordinator - is
  **0.979**. Still real time to within two per cent, so the M3 answer holds
  with the full stack rather than only with bare autopilots.
- What is left for M5 is the flight itself: take off, map for 130 s, and
  measure `/swarm/map` against the baseline of 89 to 93 per cent.

- **The first swarm mapping flight, and the swarm does worse than one drone.**
  Three agents in `cluttered_room`, each with its own mapper, autonomy and
  arbiter, coordinated: the merged map calls **83 per cent** of the room free
  and **86 per cent** of the enclosure, against a single-drone baseline of 89
  to 93 and 92 to 94. Recorded as it stands - `spec/roj/01` named this
  outcome as a real possibility before the first line of coordinator code.
- The merge itself is sound and that is worth separating from the result:
  7105 cells known in the merged map against 4194, 3651 and 3191 in the
  agents' own, so the union is genuinely more than any single agent saw.
- Two bugs found by flying, both mine, both the same shape as ones this
  project has met before. The coordinator published `/swarm/map` volatile
  while the check subscribed transient local, so the two never matched -
  R11 already said maps are transient local and the node did not follow it.
  And the check commanded the takeoff over MAVLink while each agent's
  autonomy was already cruising, so the velocity command replaced the takeoff
  submode: the machines never left the ground, the rangefinder sat 0.021 m up
  reading inf against a 0.05 m minimum, and the mapper refused to map scans
  it could not place above a floor it could not see. Letting each agent take
  itself off - the path the single-drone checks fly - fixes it, and in flight
  the rangefinder reads 290 finite samples of 290 at about 1.12 m.
- The check now asserts traffic on every sensor topic rather than its
  existence, because the difference between those two is where this hour went.

## Log Entry Template

```text
Date:
Step:
Command:
Result:
Problem:
Diagnostics:
Fix:
Follow-up task:
```

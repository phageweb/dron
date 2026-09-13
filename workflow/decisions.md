# Decisions

## 2026-09-01: Documentation Split

Decision:

- `spec/` will hold the design, architecture, interfaces, and target checklists.
- `workflow/` will hold the backlog, progress log, and concrete troubleshooting notes.

Reason:

- The specification should stay relatively stable.
- The workflow will change often based on what actually passes during verification on NixOS.

## 2026-09-01: Initial ROS/Gazebo Stack

Decision:

- the first implementation path is ROS 2 Jazzy + Gazebo Harmonic
- ROS 2 Lyrical + Gazebo Jetty remains an upgrade alternative

Reason:

- Jazzy/Harmonic is an officially recommended combination and has an LTS horizon until May 2029.
- Lyrical/Jetty is the newer LTS track, but may require more NixOS packaging work.

## 2026-09-01: Autopilot

Decision:

- the primary autopilot is ArduPilot
- PX4 remains a major alternative, but it will not be mixed into the first implementation

Reason:

- the planned real flight controller target is ArduPilot.
- ArduPilot has official SITL, a Gazebo plugin, and DDS integration.

## 2026-09-01: Autopilot ROS Integration

Decision:

- the first attempt is AP_DDS through Micro XRCE-DDS Agent
- MAVROS is the fallback

Reason:

- AP_DDS is the native ROS 2/DDS path in the ArduPilot ecosystem.
- MAVROS is the larger and older MAVLink/ROS bridge, useful for diagnostics and fallback.

## 2026-09-01: CI/CD

Decision:

- add GitHub Actions immediately
- run CI through `nix develop`
- start with flake checks and dev-shell smoke checks
- extend CI with `colcon build`, `colcon test`, Gazebo headless tests, and SITL tests as those parts become stable

Reason:

- local and CI environments should share the same Nix-defined dependency graph.
- skipped checks are acceptable early, but they must be explicit.

## 2026-09-10: H7 Flight Controller as a Build Requirement

Decision:

- the real build's flight controller must be H7 class
- the airframe stays GEPRC CineLog30 V3 with the MicoAir H743 V2 45A AIO
- lighter airframes were compared and dropped rather than assumed away

Reason:

- the 2026-09-01 decision puts the first ROS path on AP_DDS through Micro
  XRCE-DDS Agent, and AP_DDS needs flash and RAM that F4 and G4 boards do not
  have. ArduPilot would run on them, but only over a MAVLink adapter, which is a
  different adapter and a different set of checks than the ones already built
  and passing against SITL.
- separately, no OpenIPC air unit runs on 1S. Thinker and Mario need 2S minimum
  and UltraSight needs 5 V at 3 A, so a 1S airframe cannot carry the video the
  project is built around. The one light unit that does run on 1S, BetaFPV's P1,
  is Artosyn AR803X rather than OpenIPC.

Cost:

- the project has no lightweight fallback platform. A CineLog30 V3 that comes
  out too heavy has nowhere to retreat to without reopening the DDS decision.
- a BetaFPV Pavo20 Pro would have been about 148 g against 252 to 264 g, and
  would have stayed inside the 250 g class. Its stock F4 sits on a 26x26 mm
  pattern against the 25.5x25.5 mm of several ArduPilot-supported H7 AIOs, close
  enough to bolt together, so the swap is not impossible, but it means a full
  rebuild and a board that may not clear the frame bay. Recorded in case the mass
  estimate turns out to be a problem.
- the estimate did turn out to be a problem: with the LD06 the build is 294 g.
  The revision this line anticipated is
  [Pavo20 as a carrier for the LD06](../spec/realna_stavba_dronu/10_pavo20.md).
  It comes out the same way for a sharper reason - on 3S the smaller disc gives
  back almost none of the 89 g saved, so endurance drops to about 2.4 minutes
  against 3.5, and only a 4S Pavo20 Pro II matches the CineLog's range, at 239 g
  and the cost of recalibrating the simulation. The pattern figure above is the
  correction that came out of it.

## 2026-09-10: Mass Is a Goal, Not a Limit

Decision:

- there is no weight class to stay inside. The 250 g line is not a requirement
  for this build and does not gate any component choice
- mass stays a standing goal: where two options do the same job, the lighter one
  wins, and build practice keeps the grams that cost nothing to keep
- a component that buys real capability is allowed to cost mass, and the cost is
  recorded rather than argued away

Reason:

- the estimate already lands near 264 g before any front obstacle sensor, so
  treating 250 g as a gate would have decided the sensor by arithmetic rather
  than by what the drone is for.
- this is a camera platform with a research roadmap, not a machine built to fit
  a regulatory class. Thrust to weight around 4.6 is still healthy for it.

What it unblocks:

- the front obstacle sensor can be chosen on capability. The LD06's objection
  was never really its 42 g; what remains is where it mounts on a 128 mm ducted
  frame and what it costs in flight time.
- between two OpenIPC video units that do the same job, the 13.76 g EMAX Wyvern
  Link Alpha is preferred over the 25 to 30 g RunCam WiFiLink 2, subject to
  confirming the power draw and range EMAX do not publish.
- the small savings - shortened motor leads, aluminium screws, a canopy that
  suits the actual video unit rather than a DJI O4, a battery lead cut to length
  - are worth ten to twenty grams together. They are build practice now, not a
  rescue plan for a budget that no longer exists.

## 2026-09-10: Front Obstacle Sensor is the LDRobot LD06, Imported

Decision:

- the front obstacle sensor is an LDRobot LD06, bought as an import rather than
  from a Czech shop
- the simulated `front_lidar` is re-specified to it: today's 61 samples across
  60 degrees out to 8 m is a stand-in, not a model of anything real

Reason:

- it is the only sensor in the drone's weight class that produces a genuine 2D
  scan, which is what `spec/08_rozsireni.md` needs for SLAM Toolbox, and
  ArduPilot supports it natively as a proximity sensor - a layer that works
  without ROS at all.
- the simulation barely changes: today's forward fan is close to a window cut
  out of an LD06's 360 degrees, where a VL53L5CX would mean re-specifying to 4 m
  and a coarse 8 column grid.
- mass is no longer a gate, and thrust to weight near 4.6 stays healthy.

Availability forced the import, and that is the real cost:

- Czech shops stock 360 degree lidars only in the RPLidar class, and the
  lightest of those is 110 g in a 55 mm rotating cylinder - 40 per cent of this
  drone's mass, on a 128 mm frame. Not a variant, a different aircraft.
- the light sensors they do stock, TF-Luna at 799 Kc and TFmini-S at 1245 Kc,
  are single-point. They would work for today's demo and would end SLAM.
- TME lists the LD06 as withdrawn, so the source is AliExpress or Amazon.

Open against it: where it mounts. It is a rotating unit that has to see forward
past the ducts without meeting a propeller, on a frame with 128 mm between motor
centres. That is a dry-fit question and it can still kill the choice.

## 2026-09-13: The AP_DDS Fork Is Not a Path to SLAM

Decision:

- writing a LaserScan publisher into AP_DDS is ruled out as the way to get the
  LD06 scan into ROS 2. It stays on the table only as a fallback for the
  reactive demo, if every other path fails and SLAM is given up
- the next thing to try instead is forwarding the LD06's UART off the vehicle
  through the OpenIPC video unit, which is already in the parts list
- no companion computer is ordered until that attempt fails

Reason:

- checked against `external/ardupilot` at `8b9ea70` (2026-09-09), not against
  the documentation. The AP_DDS topic table has 19 entries and none of them is a
  scan, a proximity or a range; the generated IDL types are BatteryState, Imu,
  Joy, NavSatFix and NavSatStatus, with no LaserScan among them.
- the fork would have to publish what `AP_Proximity` actually holds, and that is
  `PROXIMITY_MAX_DIRECTION == 8`: eight distances 45 degrees apart, pinned by a
  `static_assert(PROXIMITY_NUM_SECTORS == 8)`. Eight numbers out of a 4.5 kHz
  sensor is enough for today's "is anything closer than 1.40 m" rule and is not
  SLAM. Going under the proximity layer to the backend means keeping a second
  driver inside the autopilot, which is not a publisher any more.
- the LD06 itself is not the problem: `AP_Proximity_LD06.cpp` is already there
  and the autopilot reads the sensor natively. Only the export is missing.
- "ROS on the ground" was never a third option on its own - with the autopilot
  offering only those eight sectors, nothing onboard can send the raw scan down.
  It needs a forwarder, and the video unit is one that costs no grams.

The mass budget is what makes this urgent rather than academic:

- the build is 227.2 g with the battery and no lidar; the LD06's ~42 g plus
  mounts and cabling spend the rest of the 294 g the CAD targets. There is no
  room in that figure for a companion computer.
- a Pi Zero 2 W is 10 g but has 512 MB of RAM, and the guides that actually run
  ROS 2 Jazzy with a lidar driver reach for a Pi 4 or 5. A board that genuinely
  carries it is 20-30 g with cooling - more than the 11 g between the Wyvern and
  the RunCam, which the parts list treats as a real difference.
- so a companion computer is not a line item. It is a re-run of thrust-to-weight,
  endurance on 750 mAh, and the gains that are already tied to 0.306 kg.

Open against this: whether the chosen video unit has a UART broken out and
reachable in the assembled frame, whether it holds 230400 baud beside the video
encoder without overheating, and whether its OpenIPC build ships `mavfwd` or
`msposd` at all. Any of those can send this back to the companion computer.

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
  would have stayed inside the 250 g class. Its stock F4 sits on the same
  25.5x25.5 mm pattern as several ArduPilot-supported H7 AIOs, so the swap is
  not impossible, but it means a full rebuild and a board that may not clear the
  frame bay. Recorded in case the mass estimate turns out to be a problem.

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

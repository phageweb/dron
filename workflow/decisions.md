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

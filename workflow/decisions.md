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

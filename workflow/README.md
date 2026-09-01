# Workflow and Backlog

## Project Priorities

Preferred tools and languages:

- NixOS as the target development system
- `flake.nix` and `nix develop` for reproducible environments
- Python for ROS 2 demo nodes, integration scripts, fast prototyping, and tests
- Rust for new standalone tools, adapters, and helper services when type safety and a robust binary are useful
- C++ only where it naturally follows from ROS/Gazebo plugins or upstream libraries

Testing rule:

- write tests before or alongside implementation where practical
- use unit tests for pure logic
- use integration tests for ROS 2 topics, services, launch files, and bridges
- use E2E tests for complete scenarios such as Gazebo startup, sensor topics, RViz/TF smoke checks, and autonomous demos
- every bug fix should ideally include a reproducing test or at least a recorded verification command in this folder

This folder is the working layer next to `spec/`.

- `spec/` describes the target design, architecture, interfaces, and planning decisions.
- `workflow/` tracks concrete execution steps, backlog items, verification results, and troubleshooting notes.

## Files

- [Backlog](./backlog.md)
- [Progress Log](./log.md)
- [Decisions](./decisions.md)
- [Troubleshooting](./troubleshooting.md)
- [Testing Strategy](./testing_strategy.md)

## How to Use

During implementation, this folder should record:

- the next concrete step
- the command that was run
- what passed
- what failed
- how the failure was diagnosed
- which fix was used
- what remains open

Rule:

- update `spec/` when the design, architecture, or plan changes
- update `workflow/` continuously during implementation and verification

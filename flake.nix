{
  description = "OpenIPC cinewhoop ROS 2 / Gazebo / ArduPilot development shell";

  inputs = {
    nix-ros-overlay.url = "github:lopsided98/nix-ros-overlay/master";
    nixpkgs.follows = "nix-ros-overlay/nixpkgs";
    flake-utils.follows = "nix-ros-overlay/flake-utils";
  };

  outputs = { self, nixpkgs, nix-ros-overlay, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ nix-ros-overlay.overlays.default ];
        };

        ros = pkgs.rosPackages.jazzy;
        rosEnv = with ros; buildEnv {
          underlay = true;
          paths = [
            ros-core
            ros-base
            rclpy
            std-msgs
            std-srvs
            sensor-msgs
            geometry-msgs
            geographic-msgs
            nav-msgs
            tf2
            tf2-ros
            tf2-tools
            robot-state-publisher
            joint-state-publisher
            xacro
            rviz2
            ros-gz
            ros-gz-bridge
            ros-gz-sim
            ros-gz-image
            demo-nodes-cpp
            demo-nodes-py
            launch-testing
            launch-testing-ros
          ];
        };
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            rosEnv
            ros.ament-cmake
            ros.ament-cmake-core
            ros.ament-cmake-python
            ros.ament-index-python
            ros.ament-package
            ros.launch
            ros.launch-ros
            ros.ros2launch

            pkgs.bashInteractive
            pkgs.cmake
            pkgs.colcon
            pkgs.gcc14
            pkgs.git
            pkgs.gnumake
            pkgs.gst_all_1.gst-plugins-base
            pkgs.gst_all_1.gstreamer
            pkgs.jdk17
            pkgs.ninja
            pkgs.pkg-config
            pkgs.python3
            pkgs.python3Packages.pymavlink
            pkgs.python3Packages.pexpect
            pkgs.python3Packages.pytest
            pkgs.ripgrep
          ];

          shellHook = ''
            export ROS_DISTRO=jazzy
            export GZ_VERSION=harmonic
            export RMW_IMPLEMENTATION=''${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}
            export PROJECT_ROOT="$PWD"
            export ROS_WS="$PROJECT_ROOT/ros_ws"
            export GZ_SIM_RESOURCE_PATH="$PROJECT_ROOT/worlds:$PROJECT_ROOT/models:$PROJECT_ROOT/ros_ws/src/openipc_cinewhoop_gazebo/worlds:$PROJECT_ROOT/ros_ws/src/openipc_cinewhoop_gazebo/models:''${GZ_SIM_RESOURCE_PATH:-}"
            export SDF_PATH="$PROJECT_ROOT/models:$PROJECT_ROOT/ros_ws/src/openipc_cinewhoop_gazebo/models:''${SDF_PATH:-}"
            export GZ_SIM_SYSTEM_PLUGIN_PATH="$PROJECT_ROOT/build/ardupilot_gazebo:''${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
            export COLCON_DEFAULTS_FILE="$PROJECT_ROOT/colcon-defaults.yaml"

            if [ -f "$PROJECT_ROOT/install/setup.bash" ]; then
              source "$PROJECT_ROOT/install/setup.bash"
            elif [ -f "$ROS_WS/install/setup.bash" ]; then
              source "$ROS_WS/install/setup.bash"
            fi

            echo "OpenIPC cinewhoop dev shell"
            echo "ROS_DISTRO=$ROS_DISTRO"
            echo "GZ_VERSION=$GZ_VERSION"
            echo "Run: scripts/check_dev_env.sh"
          '';
        };
      });
}

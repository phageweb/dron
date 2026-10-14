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
            vision-msgs
          ];
        };

        # Live web view of the D500 lidar and player of the phone recordings: nix run .#lidar [-- --port /dev/ttyUSB0]
        lidarWeb = pkgs.writeShellApplication {
          name = "lidar-web";
          runtimeInputs = [ pkgs.python3 pkgs.android-tools ];
          text = ''exec python3 ${./lidar}/lidar_web.py "$@"'';
        };

        # The Walksnail VRX Pro picture with OSD on the PC: nix run .#vrx [-- --record]
        # Plain nixpkgs: with the ROS overlay ffmpeg and SDL miss the binary
        # cache and build from source.
        plainPkgs = nixpkgs.legacyPackages.${system};
        vrxView = plainPkgs.writeShellApplication {
          name = "vrx";
          runtimeInputs = [ (plainPkgs.python3.withPackages (p: [ p.pygame-ce p.numpy ])) plainPkgs.ffmpeg ];
          # lidar/osd for reading the scan out of the OSD rows (osdvideo.py)
          text = ''
            export PYTHONPATH=${./lidar/osd}
            exec python3 ${./vrx}/vrx.py "$@"
          '';
        };

        # The lidar scan out of a VRX recording, for the lidar page:
        # nix run .#osdvideo -- ~/Videos/vrx/vrx_....mkv --session lidar/sessions
        osdVideo = plainPkgs.writeShellApplication {
          name = "osdvideo";
          runtimeInputs = [ (plainPkgs.python3.withPackages (p: [ p.numpy ])) plainPkgs.ffmpeg ];
          text = ''exec python3 ${./lidar/osd}/osdvideo.py "$@"'';
        };

        # A Lua script onto the flight controller over USB (MAVFTP), scripting restarted:
        # nix run .#fc-upload [-- other.lua]
        fcUpload = plainPkgs.writeShellApplication {
          name = "fc-upload";
          runtimeInputs = [ (plainPkgs.python3.withPackages (p: [ p.pymavlink p.pyserial ])) ];
          text = ''exec python3 ${./lidar/osd}/upload.py "$@"'';
        };

        # The phone recorder in android/lidarcam: nix develop .#android
        androidPkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
            android_sdk.accept_license = true;
          };
        };
        androidSdk = (androidPkgs.androidenv.composeAndroidPackages {
          platformVersions = [ "35" ];
          buildToolsVersions = [ "35.0.0" ];
          includeEmulator = false;
          includeNDK = false;
        }).androidsdk;
        androidHome = "${androidSdk}/libexec/android-sdk";
      in
      {
        packages.lidar = lidarWeb;
        packages.vrx = vrxView;
        packages.osdvideo = osdVideo;
        packages.fc-upload = fcUpload;

        devShells.android = pkgs.mkShell {
          packages = [ androidSdk pkgs.gradle pkgs.jdk17 pkgs.android-tools ];
          ANDROID_HOME = androidHome;
          ANDROID_SDK_ROOT = androidHome;
          JAVA_HOME = pkgs.jdk17.home;
          # The aapt2 that Gradle downloads from Maven does not run on NixOS.
          GRADLE_OPTS = "-Dorg.gradle.project.android.aapt2FromMavenOverride=${androidHome}/build-tools/35.0.0/aapt2";
        };
        apps.lidar = flake-utils.lib.mkApp { drv = lidarWeb; };
        apps.vrx = flake-utils.lib.mkApp { drv = vrxView; };
        apps.osdvideo = flake-utils.lib.mkApp { drv = osdVideo; };
        apps.fc-upload = flake-utils.lib.mkApp { drv = fcUpload; };

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
            # CAD for the physical build lives in cad_claude/ and cad_codex/;
            # openscad renders those to PNG without a display.
            pkgs.openscad
            pkgs.pkg-config
            pkgs.python3
            pkgs.python3Packages.pymavlink
            pkgs.python3Packages.pexpect
            pkgs.python3Packages.pytest
            pkgs.ripgrep
            # openipc_vrx reads the VRX's UVC through ffmpeg and finds people
            # with YOLO in ONNX; plain nixpkgs so they come from the binary cache.
            plainPkgs.ffmpeg
            pkgs.python3Packages.onnxruntime
            pkgs.python3Packages.numpy
            pkgs.python3Packages.pillow
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

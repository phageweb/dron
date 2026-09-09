import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, LogInfo, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare("openipc_cinewhoop_gazebo")
    gazebo_launch = PathJoinSubstitution([
        pkg_share,
        "launch",
        "gazebo.launch.py",
    ])
    params_file = PathJoinSubstitution([pkg_share, "config", "ardupilot_params.parm"])
    ardupilot_dir = LaunchConfiguration("ardupilot_dir")
    plugin_dir = LaunchConfiguration("plugin_dir")
    bridge_bin = LaunchConfiguration("bridge_bin")

    return LaunchDescription([
        DeclareLaunchArgument(
            "ardupilot_dir",
            default_value=os.path.join(os.getcwd(), "external", "ardupilot"),
            description="Local official ArduPilot checkout containing build/sitl/bin/arducopter.",
        ),
        DeclareLaunchArgument(
            "bridge_bin",
            default_value=os.path.join(
                os.getcwd(), "build", "ap_actuator_bridge", "ap_actuator_bridge"),
            description=(
                "Actuator bridge from scripts/build_actuator_bridge.sh. ArduPilot "
                "publishes one Double per rotor and the motor models read one "
                "Actuators array; without this the rotors never turn."
            ),
        ),
        DeclareLaunchArgument(
            "plugin_dir",
            default_value=os.path.join(os.getcwd(), "build", "ardupilot_gazebo"),
            description="Directory containing libArduPilotPlugin.so built from ardupilot_gazebo.",
        ),
        SetEnvironmentVariable(
            "GZ_SIM_SYSTEM_PLUGIN_PATH",
            [plugin_dir, ":", EnvironmentVariable("GZ_SIM_SYSTEM_PLUGIN_PATH", default_value="")],
        ),
        LogInfo(msg=(
            "Starting the custom cinewhoop Gazebo model, the actuator bridge and "
            "ArduPilot JSON SITL. Once armed the airframe holds a guided hover; "
            "attitude gains are still ArduPilot defaults."
        )),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(gazebo_launch)),
        ExecuteProcess(cmd=[bridge_bin], output="screen"),
        ExecuteProcess(
            cmd=[
                PathJoinSubstitution([ardupilot_dir, "build", "sitl", "bin", "arducopter"]),
                "--wipe",
                "--model", "JSON",
                "--speedup", "1",
                "--slave", "0",
                "-I0",
                "--sim-address=127.0.0.1",
                "--sim-port-out=9002",
                "--serial0=udpclient:127.0.0.1:14550",
                "--defaults", params_file,
            ],
            output="screen",
        ),
    ])

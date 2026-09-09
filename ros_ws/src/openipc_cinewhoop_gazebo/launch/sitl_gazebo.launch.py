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

    return LaunchDescription([
        DeclareLaunchArgument(
            "ardupilot_dir",
            default_value=os.path.join(os.getcwd(), "external", "ardupilot"),
            description="Local official ArduPilot checkout containing build/sitl/bin/arducopter.",
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
            "Starting the custom cinewhoop Gazebo model and ArduPilot JSON SITL. "
            "The preliminary rotor model still needs thrust and flight calibration."
        )),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(gazebo_launch)),
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

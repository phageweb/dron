import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, SetEnvironmentVariable, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_share = get_package_share_directory("openipc_cinewhoop_gazebo")
    worlds_path = os.path.join(pkg_share, "worlds")
    models_path = os.path.join(pkg_share, "models")
    bridge_config = os.path.join(pkg_share, "config", "gz_bridge.yaml")

    use_bridge = LaunchConfiguration("use_bridge")
    world = LaunchConfiguration("world")
    gui = LaunchConfiguration("gui")
    gz_partition = LaunchConfiguration("gz_partition")
    gz_ip = LaunchConfiguration("gz_ip")

    return LaunchDescription([
        DeclareLaunchArgument("use_bridge", default_value="true"),
        # The world is an argument so a check can bring the same bridge and
        # adapter up over a different scene; leaning_test.sdf is one.
        DeclareLaunchArgument("world", default_value="indoor_test.sdf"),
        DeclareLaunchArgument("gui", default_value="false"),
        # Gazebo Transport discovers the standalone GUI over UDP multicast.
        # Pin both processes to one local partition and interface so discovery
        # remains reliable on hosts with several network interfaces.
        DeclareLaunchArgument("gz_partition", default_value="openipc_cinewhoop"),
        DeclareLaunchArgument("gz_ip", default_value="127.0.0.1"),
        SetEnvironmentVariable("GZ_PARTITION", gz_partition),
        SetEnvironmentVariable("GZ_IP", gz_ip),
        SetEnvironmentVariable(
            "GZ_SIM_RESOURCE_PATH",
            [models_path, ":", worlds_path, ":", EnvironmentVariable("GZ_SIM_RESOURCE_PATH", default_value="")],
        ),
        SetEnvironmentVariable(
            "SDF_PATH",
            [models_path, ":", EnvironmentVariable("SDF_PATH", default_value="")],
        ),
        ExecuteProcess(
            cmd=["gz", "sim", "-s", "-v4", "-r",
                 PathJoinSubstitution([worlds_path, world])],
            output="screen",
        ),
        TimerAction(
            # The server must finish registering /gazebo/worlds before a
            # standalone GUI client queries it.  Starting both at once leaves
            # the GUI stuck at the world-selection screen on slower systems.
            period=8.0,
            actions=[
                ExecuteProcess(
                    cmd=["gz", "sim", "-g"],
                    output="screen",
                    condition=IfCondition(gui),
                ),
            ],
        ),
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            arguments=["--ros-args", "-p", f"config_file:={bridge_config}"],
            parameters=[{"use_sim_time": True}],
            output="screen",
            condition=IfCondition(use_bridge),
        ),
        # Part of the bridge rather than of the demo: without it the logical
        # rangefinder topic would carry a LaserScan in simulation and a Range on
        # hardware, which the demo nodes are not allowed to notice.
        Node(
            package="openipc_cinewhoop_demo",
            executable="range_adapter",
            parameters=[{"use_sim_time": True}],
            output="screen",
            condition=IfCondition(use_bridge),
        ),
    ])

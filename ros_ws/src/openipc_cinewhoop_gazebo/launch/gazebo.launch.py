import os
import re
import tempfile

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def render_bridge_config(context, worlds_path, template):
    """Write the bridge config for the world actually being launched.

    The sensors do not name their own topics, so Gazebo scopes them under the
    real world's name. The bridge has to be told that name, and taking it from
    the world file rather than from the file name means a world whose name and
    file disagree cannot quietly bridge nothing.
    """
    world_file = os.path.join(
        worlds_path, context.perform_substitution(LaunchConfiguration("world")))
    with open(world_file) as handle:
        found = re.search(r'<world\s+name="([^"]+)"', handle.read())
    if found is None:
        raise RuntimeError(f"No <world name=...> in {world_file}")
    with open(template) as handle:
        rendered = handle.read().replace("@world@", found.group(1))
    # Deterministic per user and world, so repeated launches reuse one file
    # instead of littering a temporary directory per run.
    path = os.path.join(
        tempfile.gettempdir(),
        f"openipc_gz_bridge_{os.getuid()}_{found.group(1)}.yaml")
    with open(path, "w") as handle:
        handle.write(rendered)
    return [Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=["--ros-args", "-p", f"config_file:={path}"],
        parameters=[{"use_sim_time": True}],
        output="screen",
    )]


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
        OpaqueFunction(
            function=render_bridge_config,
            args=[worlds_path, bridge_config],
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

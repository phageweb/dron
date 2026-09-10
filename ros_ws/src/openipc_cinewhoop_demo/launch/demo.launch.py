from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Not hardcoded: on hardware there is no /clock, and a node left with
    # use_sim_time true reads the same instant forever. Every age the demo
    # nodes compute would then be zero, which silently disables the stale-scan
    # guard that stops the vehicle when the lidar dies.
    use_sim_time = LaunchConfiguration("use_sim_time")

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        Node(
            package="openipc_cinewhoop_demo",
            executable="obstacle_monitor",
            parameters=[{"use_sim_time": use_sim_time}],
            output="screen",
        ),
        Node(
            package="openipc_cinewhoop_demo",
            executable="trajectory_publisher",
            parameters=[{"use_sim_time": use_sim_time}],
            output="screen",
        ),
    ])

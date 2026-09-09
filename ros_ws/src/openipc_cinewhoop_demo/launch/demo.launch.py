from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="openipc_cinewhoop_demo",
            executable="obstacle_monitor",
            parameters=[{"use_sim_time": True}],
            output="screen",
        ),
        Node(
            package="openipc_cinewhoop_demo",
            executable="trajectory_publisher",
            parameters=[{"use_sim_time": True}],
            output="screen",
        ),
    ])

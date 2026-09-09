from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")
    rviz = LaunchConfiguration("rviz")
    urdf_path = PathJoinSubstitution([
        FindPackageShare("openipc_cinewhoop_description"),
        "urdf",
        "openipc_cinewhoop.urdf.xacro",
    ])
    rviz_config = PathJoinSubstitution([
        FindPackageShare("openipc_cinewhoop_description"),
        "rviz",
        "cinewhoop.rviz",
    ])

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("rviz", default_value="true"),
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[{
                "robot_description": Command(["xacro ", urdf_path]),
                "use_sim_time": use_sim_time,
            }],
            output="screen",
        ),
        Node(
            package="joint_state_publisher",
            executable="joint_state_publisher",
            parameters=[{"use_sim_time": use_sim_time}],
            output="screen",
            condition=IfCondition(rviz),
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            arguments=["-d", rviz_config],
            parameters=[{"use_sim_time": use_sim_time}],
            output="screen",
        ),
    ])

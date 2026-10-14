"""The VRX bridge with its parameters on the command line.

    ros2 launch openipc_vrx vrx_bridge.launch.py latency_ms:=80 \
        scan_source:=msp:tcp:127.0.0.1:5772 detect:=true classes:=person
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ARGS = {
    "device": ("", "UVC device of the VRX; found by name when empty"),
    "latency_ms": ("0.0", "camera-to-arrival latency from `vrx.py --latency`, taken off the stamps"),
    "scan_source": ("", "msp:tcp:HOST:PORT or msp:/dev/ttyX for the OSD scan; empty is off"),
    "camera_info_file": ("", "camera_calibration YAML of the camera seen through the VRX"),
}
DETECT_ARGS = {
    "detect": ("false", "also run the YOLO detector on the picture"),
    "classes": ("", "COCO classes to report, e.g. person,backpack; empty is all 80"),
    "view": ("false", "serve the picture (with boxes when detect is on) on http://localhost:8090"),
}


def generate_launch_description():
    declared = [DeclareLaunchArgument(k, default_value=v, description=d)
                for k, (v, d) in {**ARGS, **DETECT_ARGS}.items()]
    params = {k: LaunchConfiguration(k) for k in ARGS}
    return LaunchDescription(declared + [
        Node(package="openipc_vrx", executable="vrx_bridge", name="vrx_bridge", output="screen",
             parameters=[params]),
        Node(package="openipc_vrx", executable="detector", name="vrx_detector", output="screen",
             parameters=[{"classes": LaunchConfiguration("classes")}],
             condition=IfCondition(LaunchConfiguration("detect"))),
        Node(package="openipc_vrx", executable="web_view", name="vrx_web_view", output="screen",
             condition=IfCondition(LaunchConfiguration("view"))),
    ])

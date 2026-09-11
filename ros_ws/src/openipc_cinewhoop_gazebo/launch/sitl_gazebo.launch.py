"""One launch for the whole demo: Gazebo, bridges, RViz, the Agent and SITL.

This is phase 12 of the iteration plan. Every heavyweight upstream piece stays
optional, because the ArduPilot, ardupilot_gazebo and Micro XRCE-DDS Agent
builds live in the ignored `external/` tree rather than in the Nix shell:

    ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py
    ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py gui:=true
    ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py sitl:=false

The demo nodes are deliberately not started here; run them separately so their
output stays readable, as the iteration plan asks.
"""

import os

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    LogInfo,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import (
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare("openipc_cinewhoop_gazebo")
    gazebo_launch = PathJoinSubstitution([pkg_share, "launch", "gazebo.launch.py"])
    display_launch = PathJoinSubstitution([
        FindPackageShare("openipc_cinewhoop_description"),
        "launch",
        "display.launch.py",
    ])
    params_file = PathJoinSubstitution([pkg_share, "config", "ardupilot_params.parm"])
    dds_params_file = PathJoinSubstitution([pkg_share, "config", "dds_smoke.parm"])

    ardupilot_dir = LaunchConfiguration("ardupilot_dir")
    plugin_dir = LaunchConfiguration("plugin_dir")
    bridge_bin = LaunchConfiguration("bridge_bin")
    agent_bin = LaunchConfiguration("agent_bin")
    agent_setup = LaunchConfiguration("agent_setup")
    agent_port = LaunchConfiguration("agent_port")
    rviz = LaunchConfiguration("rviz")
    agent = LaunchConfiguration("agent")
    sitl = LaunchConfiguration("sitl")

    workspace_root = os.getcwd()

    return LaunchDescription([
        DeclareLaunchArgument(
            "ardupilot_dir",
            default_value=os.path.join(workspace_root, "external", "ardupilot"),
            description="Local official ArduPilot checkout containing build/sitl/bin/arducopter.",
        ),
        DeclareLaunchArgument(
            "bridge_bin",
            default_value=os.path.join(
                workspace_root, "build", "ap_actuator_bridge", "ap_actuator_bridge"),
            description=(
                "Actuator bridge from scripts/build_actuator_bridge.sh. ArduPilot "
                "publishes one Double per rotor and the motor models read one "
                "Actuators array; without this the rotors never turn."
            ),
        ),
        DeclareLaunchArgument(
            "plugin_dir",
            default_value=os.path.join(workspace_root, "build", "ardupilot_gazebo"),
            description="Directory containing libArduPilotPlugin.so built from ardupilot_gazebo.",
        ),
        DeclareLaunchArgument(
            "agent_setup",
            default_value=os.path.join(
                workspace_root, "external", "dds_ws", "install", "setup.bash"),
            description=(
                "Setup script of the local Micro XRCE-DDS Agent workspace from "
                "scripts/build_dds_workspace.sh. It is sourced for the Agent so "
                "the launch works whether or not the caller sourced it."
            ),
        ),
        DeclareLaunchArgument(
            "agent_bin",
            default_value=os.path.join(
                workspace_root, "external", "dds_ws", "install", "lib",
                "micro_ros_agent", "micro_ros_agent"),
            description="Micro XRCE-DDS Agent executable; Nixpkgs does not package it.",
        ),
        DeclareLaunchArgument(
            "agent_port",
            default_value="20199",
            # Must match DDS_UDP_PORT in config/dds_smoke.parm.
            description="UDP port the Agent listens on, matching dds_smoke.parm.",
        ),
        DeclareLaunchArgument(
            "rviz", default_value="true",
            description="Start robot_state_publisher with RViz2; false leaves TF only.",
        ),
        # These two belong to gazebo.launch.py, which this one includes. They
        # were not declared here and not passed on, so `gui:=true` and
        # `world:=...` on this launch went nowhere: scripts/demo.sh asked for a
        # Gazebo window on every run and never got one, and --no-gui turned off
        # something that was already off.
        DeclareLaunchArgument(
            "gui", default_value="false",
            description=(
                "Open the Gazebo window. False to match gazebo.launch.py, so "
                "that declaring this argument makes it work rather than "
                "changing what every existing caller gets. scripts/demo.sh "
                "asks for true."
            ),
        ),
        DeclareLaunchArgument(
            "world", default_value="indoor_test.sdf",
            description=(
                "World to load. room_test.sdf is the closed room the demo flies "
                "a circuit of with enable_turning."
            ),
        ),
        DeclareLaunchArgument(
            "agent", default_value="true",
            description="Start the Micro XRCE-DDS Agent so the /ap/ topics appear.",
        ),
        DeclareLaunchArgument(
            "sitl", default_value="true",
            description="Start ArduPilot SITL here; false prints how to run it separately.",
        ),
        SetEnvironmentVariable(
            "GZ_SIM_SYSTEM_PLUGIN_PATH",
            [plugin_dir, ":", EnvironmentVariable("GZ_SIM_SYSTEM_PLUGIN_PATH", default_value="")],
        ),
        LogInfo(msg=(
            "Starting the custom cinewhoop Gazebo model, the actuator bridge, the "
            "ROS/Gazebo bridge, RViz and ArduPilot JSON SITL with DDS. Once armed "
            "the airframe holds a guided hover; attitude gains are still "
            "ArduPilot defaults."
        )),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch),
            launch_arguments={
                "gui": LaunchConfiguration("gui"),
                "world": LaunchConfiguration("world"),
            }.items(),
        ),

        # robot_state_publisher and RViz2 read the URDF, which is the description
        # package's business rather than a second copy of it here.
        #
        # use_sim_time is false, and it used to be true. This simulation runs two
        # clocks: Gazebo's /clock, and every sensor message the bridge carries,
        # count seconds from when the simulator started, while AP_DDS stamps
        # /ap/pose/filtered with ArduPilot's UTC - measured at 22.3 s against
        # 1789156172 in the same instant. map -> base_link carries the second of
        # those, so a consumer on sim time sees it 56 years in the future and can
        # never look it up at a time; on the wall clock it works, measured at 20
        # timed lookups out of 20 by check_map_frame.sh. The map's own publisher
        # stamps from its clock and the scan and model need only static
        # transforms, which carry no time.
        #
        # This is a workaround for the split, not a fix: AP_DDS subscribes to
        # /clock and never receives it, which is on the backlog. That RViz then
        # actually draws the map is the part nothing headless can confirm, and
        # it is on the backlog too.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(display_launch),
            launch_arguments={"use_sim_time": "false", "rviz": rviz}.items(),
        ),

        # The only thing that roots the TF tree in the world. Without it
        # robot_state_publisher serves base_link and everything bolted to it,
        # and nothing says where base_link is - so the occupancy map, which is
        # stamped in a `map` frame, has no transform reaching it and RViz has
        # nowhere to put it. It lives here rather than in demo.launch.py because
        # it needs /ap/pose/filtered, which only exists when SITL does.
        # No use_sim_time, and not by oversight. This node reads no clock - it
        # restamps nothing, copying the pose's own stamp - so the setting would
        # do nothing, and nothing is the best case: Gazebo publishes no clock
        # topic at all here, the bridge's /clock entry forwards messages that
        # never come, and a node told to use sim time therefore sits at t = 0
        # for ever. See the backlog; it is a defect of this launch and not of
        # this node.
        Node(
            package="openipc_cinewhoop_demo",
            executable="pose_tf_broadcaster",
            output="screen",
            condition=IfCondition(sitl),
        ),

        ExecuteProcess(cmd=[bridge_bin], output="screen"),

        # The Agent needs its own workspace on the library path, so source it.
        ExecuteProcess(
            cmd=["bash", "-c",
                 ["set -e; source ", agent_setup, "; exec ", agent_bin,
                  " udp4 -p ", agent_port]],
            output="screen",
            condition=IfCondition(agent),
        ),

        TimerAction(
            # SITL opens the JSON control socket immediately and gives up on a
            # simulator that is not there yet, so let Gazebo load the model and
            # the plugin first.
            period=6.0,
            actions=[
                ExecuteProcess(
                    cmd=[
                        PathJoinSubstitution(
                            [ardupilot_dir, "build", "sitl", "bin", "arducopter"]),
                        "--wipe",
                        "--model", "JSON",
                        "--speedup", "1",
                        "--slave", "0",
                        "-I0",
                        "--sim-address=127.0.0.1",
                        "--sim-port-out=9002",
                        "--serial0=udpclient:127.0.0.1:14550",
                        "--defaults", [params_file, ",", dds_params_file],
                    ],
                    output="screen",
                    condition=IfCondition(sitl),
                ),
            ],
        ),

        LogInfo(
            condition=UnlessCondition(sitl),
            msg=[
                "SITL was not started. Run it in another terminal from "
                "external/ardupilot/ArduCopter:\n  ",
                PathJoinSubstitution(
                    [ardupilot_dir, "build", "sitl", "bin", "arducopter"]),
                " --wipe --model JSON --speedup 1 --slave 0 -I0"
                " --sim-address=127.0.0.1 --sim-port-out=9002"
                " --serial0=udpclient:127.0.0.1:14550 --defaults ",
                params_file, ",", dds_params_file,
            ],
        ),
    ])

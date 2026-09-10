# ROS 2 rozhraní, topics a TF

## Navržený namespace

Pro vlastní dron:

```text
/openipc_cinewhoop/*
```

Pro ArduPilot DDS:

```text
/ap/*
```

Důvod:

- `/openipc_cinewhoop` reprezentuje companion/simulační senzory.
- `/ap` ponechává nativní názvy ArduPilot DDS rozhraní.

## TF strom

Minimální strom:

```text
map
└── odom
    └── base_link
        ├── camera_link
        │   └── camera_optical_frame
        ├── imu_link
        ├── optical_flow_link
        ├── rangefinder_link
        ├── front_lidar_link
        ├── motor_1
        ├── motor_2
        ├── motor_3
        └── motor_4
```

Poznámky:

- `map -> odom` může být v první verzi identita.
- `odom -> base_link` přijde z Gazebo ground truth nebo ArduPilot filtered pose podle fáze.
- statické transformace publikuje `robot_state_publisher`.
- ArduPilot DDS může publikovat vlastní `/ap/tf_static`; pro RViz je potřeba jasně rozhodnout, který TF strom je autoritativní.

## Gazebo -> ROS topics

Pracovní názvy:

| ROS topic | Typ | Zdroj | Frame |
| --- | --- | --- | --- |
| `/clock` | `rosgraph_msgs/msg/Clock` | Gazebo | n/a |
| `/openipc_cinewhoop/imu` | `sensor_msgs/msg/Imu` | Gazebo IMU | `imu_link` |
| `/openipc_cinewhoop/range/down` | `sensor_msgs/msg/Range` | `range_adapter` | `rangefinder_link` |
| `/openipc_cinewhoop/range/down_raw` | `sensor_msgs/msg/LaserScan` | dolní lidar, jen simulace | `rangefinder_link` |
| `/openipc_cinewhoop/scan/front` | `sensor_msgs/msg/LaserScan` | přední lidar | `front_lidar_link` |
| `/openipc_cinewhoop/camera/image_raw` | `sensor_msgs/msg/Image` | Gazebo camera | `camera_optical_frame` |
| `/openipc_cinewhoop/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Gazebo camera | `camera_optical_frame` |
| `/openipc_cinewhoop/odom` | `nav_msgs/msg/Odometry` | Gazebo/bridge/helper | `odom` -> `base_link` |
| `/openipc_cinewhoop/path` | `nav_msgs/msg/Path` | demo node | `odom` nebo `map` |

`/openipc_cinewhoop/range/down_raw` je jediný topic, který na reálném dronu
neexistuje. Gazebo umí rangefinder jen jako malý lidar, takže bridge končí tady
a `range_adapter` z něj dělá `Range` pod logickým názvem. Demo nody smějí znát
jen ten logický.

Frames v tabulce nejsou popis, ale požadavek: senzory v SDF mají `gz_frame_id`,
protože jinak Gazebo razítkuje zprávy scoped jménem senzoru, které v TF stromu
není. Ověřuje `scripts/check_sensor_interface.sh`.

## ArduPilot DDS topics

Očekávané užitečné topics podle AP_DDS:

| Topic | Typ | Účel |
| --- | --- | --- |
| `/ap/imu/experimental/data` | `sensor_msgs/msg/Imu` | IMU z ArduPilot pohledu |
| `/ap/pose/filtered` | `geometry_msgs/msg/PoseStamped` | filtrovaná pozice |
| `/ap/twist/filtered` | `geometry_msgs/msg/TwistStamped` | filtrovaná rychlost |
| `/ap/battery` | `sensor_msgs/msg/BatteryState` | baterie |
| `/ap/status` | `ardupilot_msgs/msg/Status` | stav autopilotu |
| `/ap/rc` | `ardupilot_msgs/msg/Rc` | RC vstupy |
| `/ap/tf_static` | `tf2_msgs/msg/TFMessage` | statické transformace z AP |
| `/ap/cmd_vel` | `geometry_msgs/msg/TwistStamped` | command velocity vstup |

Skutečná sada topics závisí na build konfiguraci ArduPilotu a `ardupilot_msgs`.

## ArduPilot DDS services

Očekávané služby:

| Service | Typ | Účel |
| --- | --- | --- |
| `/ap/prearm_check` | `std_srvs/srv/Trigger` | ověření před armem |
| `/ap/arm_motors` | `ardupilot_msgs/srv/ArmMotors` | arm/disarm |
| `/ap/mode_switch` | `ardupilot_msgs/srv/ModeSwitch` | změna režimu |
| `/ap/experimental/takeoff` | `ardupilot_msgs/srv/Takeoff` | takeoff |

## QoS poznámky

LaserScan a IMU:

- `SensorDataQoS`
- best effort je obvykle v pořádku pro vysokofrekvenční data

TF static:

- transient local durability
- reliable

Clock:

- používat `use_sim_time:=true` pro všechny ROS nody

## Užitečné CLI příkazy

```bash
ros2 node list
ros2 topic list -v
ros2 service list -t
ros2 topic echo /openipc_cinewhoop/scan/front --once
ros2 topic hz /openipc_cinewhoop/imu
ros2 topic echo /ap/status --once
ros2 service call /ap/prearm_check std_srvs/srv/Trigger
ros2 run tf2_tools view_frames
```

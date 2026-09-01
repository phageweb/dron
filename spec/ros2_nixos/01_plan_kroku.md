# ROS 2 na NixOSu - plán kroků

## Krok 1: Reprodukovatelný shell

Cíl:

- vytvořit `flake.nix`
- dostat do shellu ROS 2 Jazzy, Gazebo Harmonic, RViz2, colcon a Python tooling

Ověření:

```bash
nix develop
ros2 --help
colcon --help
gz sim --versions
rviz2 --help
python3 -c "import rclpy; print('rclpy ok')"
```

Poznámka:

- Na NixOSu nepočítat s `apt` ani `rosdep` jako hlavním zdrojem závislostí.
- Všechny důležité závislosti musí být v `flake.nix`.

## Krok 2: Prázdný ROS 2 workspace

Cíl:

- založit `ros_ws/src`
- ověřit `colcon build`

Ověření:

```bash
mkdir -p ros_ws/src
colcon build --symlink-install --base-paths ros_ws/src
```

## Krok 3: První Python node

Cíl:

- vytvořit malý balíček s `rclpy`
- spustit publisher a subscriber
- pochopit ROS graph

První demo:

```text
/demo_talker publikuje std_msgs/msg/String
/demo_listener subscribuje std_msgs/msg/String
```

Ověření:

```bash
ros2 node list
ros2 topic list
ros2 topic echo /demo/chatter
ros2 topic hz /demo/chatter
```

## Krok 4: Messages a parametry

Cíl:

- číst typ topicu
- zobrazit definici zprávy
- předat parametry nodu

Ověření:

```bash
ros2 topic info /demo/chatter
ros2 interface show std_msgs/msg/String
ros2 param list
```

## Krok 5: TF strom

Cíl:

- vytvořit jednoduchý statický TF strom
- zobrazit ho v RViz2

Příklad:

```text
map
└── base_link
    └── sensor_link
```

Ověření:

```bash
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 map base_link
ros2 run tf2_tools view_frames
rviz2
```

## Krok 6: RViz2

Cíl:

- nastavit fixed frame
- zobrazit TF
- zobrazit jednoduchý marker nebo robot model

Ověření:

```bash
rviz2
```

V RViz2 sledovat:

- `Fixed Frame`
- `TF`
- případně `Marker`, `LaserScan`, `Odometry`

## Krok 7: Gazebo Harmonic

Cíl:

- spustit základní Gazebo svět
- vypsat Gazebo topics

Ověření:

```bash
gz sim -v4 -r shapes.sdf
gz topic -l
```

## Krok 8: Bridge Gazebo -> ROS 2

Cíl:

- použít `ros_gz_bridge`
- převést alespoň `/clock` nebo jednoduchý sensor topic do ROS 2

Ověření:

```bash
ros2 topic list
ros2 topic echo /clock --once
```

## Krok 9: LaserScan demo bez dronu

Cíl:

- vytvořit jednoduchý Gazebo model se senzorem typu lidar
- bridgeovat `LaserScan`
- číst ho Python subscriberem

Ověření:

```bash
ros2 topic echo /demo/scan --once
ros2 run <demo_pkg> obstacle_monitor --ros-args -p scan_topic:=/demo/scan
```

Tohle je přímý předstupeň budoucího `obstacle_monitor.py` pro cinewhoop.

## Krok 10: ArduPilot SITL obecně

Cíl:

- pochopit, že ArduPilot je autopilot proces vedle Gazeba a ROS 2
- nejdřív ověřit SITL bez vlastního modelu

Ověření:

```bash
sim_vehicle.py -v ArduCopter --console --map
```

Další ověření s Gazebo pluginem přijde až v simulační větvi.

## Krok 11: ArduPilot DDS obecně

Cíl:

- spustit Micro XRCE-DDS Agent
- vidět ArduPilot ROS 2 topics a services

Ověření:

```bash
ros2 run micro_ros_agent micro_ros_agent udp4 -p 2019
sim_vehicle.py -v ArduCopter --console --map --enable-DDS
ros2 node list
ros2 topic list | grep /ap/
ros2 service list | grep /ap/
```

## Krok 12: Přechod na cinewhoop simulaci

Po splnění předchozích kroků pokračovat:

```text
ROS 2 basics -> Gazebo basics -> ros_gz bridge -> RViz2 -> ArduPilot SITL -> AP_DDS -> vlastní cinewhoop model
```

Konkrétní cinewhoop plán je v [iteračním implementačním plánu simulace](../03_iteracni_plan.md).

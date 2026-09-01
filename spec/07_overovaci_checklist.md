# Ověřovací checklist

Tento checklist slouží jako závěrečná definice hotového dema.

## Prostředí

- [ ] `nix develop` otevře shell bez ručních systémových instalací
- [ ] `ros2 --help` funguje
- [ ] `colcon --help` funguje
- [ ] `gz sim --versions` ukáže Gazebo Harmonic
- [ ] `rviz2 --help` funguje
- [ ] Python umí importovat `rclpy`

## Build

- [ ] `colcon build --symlink-install --base-paths ros_ws/src` projde
- [ ] `source ros_ws/install/setup.bash` projde
- [ ] `ros2 pkg list | grep openipc_cinewhoop` ukáže všechny tři balíčky

## Model v RViz2

- [ ] `ros2 launch openipc_cinewhoop_description display.launch.py` spustí RViz2
- [ ] model má `base_link`
- [ ] model má `camera_link`
- [ ] model má `imu_link`
- [ ] model má `optical_flow_link`
- [ ] model má `rangefinder_link`
- [ ] model má `front_lidar_link`
- [ ] model má `motor_1` až `motor_4`
- [ ] TF strom je bez odpojených frame

## Gazebo

- [ ] `gz sim -v4 -r worlds/indoor_test.sdf` načte svět
- [ ] ve světě je vidět vlastní `openipc_cinewhoop`
- [ ] model není Iris
- [ ] velikost modelu odpovídá 3" cinewhoopu
- [ ] místnost/bludiště má překážky pro přední lidar
- [ ] model má stabilní inertial parametry

## Senzory

- [ ] `/openipc_cinewhoop/imu` publikuje `sensor_msgs/msg/Imu`
- [ ] `/openipc_cinewhoop/range/down` publikuje `sensor_msgs/msg/Range`
- [ ] `/openipc_cinewhoop/scan/front` publikuje `sensor_msgs/msg/LaserScan`
- [ ] `/openipc_cinewhoop/camera/image_raw` publikuje `sensor_msgs/msg/Image`
- [ ] lidar v RViz2 ukazuje zdi/překážky před dronem
- [ ] dolní rangefinder reaguje na výšku nad podlahou

## ArduPilot SITL a Gazebo

- [ ] Iris smoke test funguje jako dočasná diagnostika
- [ ] vlastní cinewhoop se připojí k ArduPilot SITL přes JSON backend
- [ ] `mode guided` projde
- [ ] `arm throttle` projde
- [ ] `takeoff 1` zvedne vlastní model
- [ ] dron se při takeoffu nepřevrací
- [ ] hover je dostatečně stabilní pro demo

## ArduPilot DDS a ROS 2

- [ ] Micro XRCE-DDS Agent běží na UDP portu 2019
- [ ] SITL běží s `--enable-DDS`
- [ ] `ros2 node list` obsahuje ArduPilot DDS node
- [ ] `ros2 topic list | grep /ap/` vrací telemetry topics
- [ ] `ros2 service list | grep /ap/` vrací ArduPilot služby
- [ ] `/ap/arm_motors` je dostupné
- [ ] `/ap/mode_switch` je dostupné
- [ ] `/ap/experimental/takeoff` je dostupné

## RViz2 demo

- [ ] RobotModel je vidět
- [ ] TF display je čitelný
- [ ] LaserScan display ukazuje přední lidar
- [ ] Odometry/Pose display odpovídá pohybu
- [ ] Path display kreslí trajektorii
- [ ] volitelně kamera ukazuje obraz

## `obstacle_monitor.py`

- [ ] node se spustí přes `ros2 run`
- [ ] subscribuje na `/openipc_cinewhoop/scan/front`
- [ ] ignoruje `nan` a `inf`
- [ ] vypisuje nejbližší překážku v metrech
- [ ] při vzdálenosti pod 0.8 m vypíše varování

## `simple_indoor_autonomy.py`

- [ ] čeká na lidar data
- [ ] čeká na ArduPilot služby
- [ ] přepne režim vhodný pro guided řízení
- [ ] provede prearm check
- [ ] armuje
- [ ] vzlétne na přibližně 1 m
- [ ] letí dopředu přibližně 0.5 m/s
- [ ] zastaví před překážkou pod 0.8 m
- [ ] po zastavení drží bezpečný stav nebo se pomalu otočí

## Finální příkazy v README

README musí na konci obsahovat:

```bash
nix develop
colcon build --symlink-install --base-paths ros_ws/src
source ros_ws/install/setup.bash
ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py
ros2 run openipc_cinewhoop_demo obstacle_monitor
ros2 run openipc_cinewhoop_demo simple_indoor_autonomy
```

A také užitečné diagnostické příkazy:

```bash
ros2 topic list -v
ros2 service list -t
ros2 topic echo /openipc_cinewhoop/scan/front --once
ros2 topic echo /ap/status --once
ros2 topic hz /openipc_cinewhoop/imu
ros2 run tf2_tools view_frames
gz topic -l
```

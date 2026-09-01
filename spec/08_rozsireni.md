# Pozdější rozšíření

Struktura projektu má počítat s tím, že ROS 2 nody napsané pro simulaci půjdou později s minimálními změnami použít na skutečném OpenIPC cinewhoopu.

## SLAM

Připravené vstupy:

- `/openipc_cinewhoop/scan/front`
- `/openipc_cinewhoop/odom`
- TF `odom -> base_link`

Možné rozšíření:

- SLAM Toolbox pro 2D lidar experimenty
- RTAB-Map jako silná alternativa pro RGB-D / stereo / 3D mapping
- Cartographer pouze jako historická/experimentální volba, ne jako default, protože upstream uvádí, že už neprobíhá aktivní vývoj
- později depth camera nebo VIO jako zdroj mapování

## Nav2

Předpoklady:

- stabilní `map`, `odom`, `base_link`
- lokální costmap z předního lidaru/depth senzoru
- command velocity rozhraní oddělené od konkrétního autopilotu

Plán:

- vytvořit adapter node mezi Nav2 `cmd_vel` a ArduPilot `/ap/cmd_vel`
- zachovat bezpečnostní limity rychlosti pro indoor cinewhoop

## OpenCV a ROS image topics

První kamera:

- Gazebo RGB camera topic
- bridge do `sensor_msgs/msg/Image`

Později:

- OpenCV node pro detekci značek/překážek
- image transport
- synchronizace `Image`, `CameraInfo`, IMU

## OpenIPC video stream

Simulace:

- Gazebo camera jako náhrada RunCam WiFiLink 2

Reálný dron:

- ingest IP streamu do ROS 2 image topicu
- oddělit transport videa od autonomie
- zachovat stejné názvy výstupních image topics, pokud to půjde

## VIO / ORB-SLAM3

Předpoklady:

- kamera s kalibrací
- IMU topic s časovou synchronizací
- stabilní TF

Volby:

- RTAB-Map pro praktičtější ROS 2 integraci a širší aktivní údržbu
- ORB-SLAM3 pro výzkumné visual-inertial experimenty, ale ne jako první produkční volba bez ověřeného ROS 2 wrapperu

Rozhraní:

- vstupy držet co nejblíž standardním ROS typům:
  - `sensor_msgs/msg/Image`
  - `sensor_msgs/msg/CameraInfo`
  - `sensor_msgs/msg/Imu`
  - `nav_msgs/msg/Odometry`

## Přechod na reálný MicoAir H743

Zásada:

- ROS demo nody nesmí záviset na Gazebo interních topic názvech.
- Hardware-specific rozdíly řešit přes launch remapping a parametry.

Simulace:

```text
/openipc_cinewhoop/scan/front
/openipc_cinewhoop/range/down
/openipc_cinewhoop/imu
/ap/*
```

Reálný dron:

```text
/openipc_cinewhoop/scan/front     -> skutečný lidar/depth node
/openipc_cinewhoop/range/down     -> MicoAir MTF-02P nebo autopilot rangefinder bridge
/openipc_cinewhoop/imu            -> ArduPilot/MAVLink/DDS IMU
/ap/*                             -> ArduPilot DDS, MAVROS-like bridge, nebo vlastní adapter
```

## Doporučený adapter pattern

V demo nodech používat parametry:

- `scan_topic`
- `range_topic`
- `imu_topic`
- `pose_topic`
- `cmd_vel_topic`
- názvy ArduPilot služeb

Tím se později změní launch soubor, ne Python kód.

## Další plánované balíčky

Možné budoucí balíčky:

```text
openipc_cinewhoop_bringup
openipc_cinewhoop_perception
openipc_cinewhoop_navigation
openipc_cinewhoop_slam
openipc_cinewhoop_hardware
```

První verze zůstane menší:

```text
openipc_cinewhoop_description
openipc_cinewhoop_gazebo
openipc_cinewhoop_demo
```

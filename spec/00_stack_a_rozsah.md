# Stack a rozsah

## Cíl první verze

První verze projektu má dodat spustitelné demo, ve kterém:

- Gazebo zobrazí vlastní model 3" OpenIPC cinewhoopu, ne Iris.
- ArduPilot SITL řídí letovou dynamiku přes Gazebo plugin.
- ROS 2 vidí senzorická data, TF strom, odometrii a ArduPilot DDS rozhraní.
- RViz2 zobrazuje model dronu, TF, lidar, odometrii a trajektorii.
- Python node `obstacle_monitor.py` čte přední lidar a vypisuje nejbližší překážku.
- Python node `simple_indoor_autonomy.py` armuje, vzlétne na přibližně 1 m, letí pomalu dopředu a reaguje na překážku před dronem.

## Navržená kompatibilní kombinace

Záměrně volíme stabilní kombinaci místo nejnovějších možných verzí:

- ROS 2: Jazzy
- Gazebo: Harmonic
- Gazebo knihovny: `gz-sim8`, `gz-transport`, `gz-msgs`
- ROS/Gazebo bridge: `ros_gz`
- Autopilot: ArduPilot SITL, vehicle `ArduCopter`
- Gazebo autopilot bridge: `ardupilot_gazebo` plugin
- SITL physics protocol: ArduPilot JSON backend
- ROS 2 autopilot integration: ArduPilot AP_DDS přes Micro XRCE-DDS Agent
- Jazyk demo nodů: Python 3 přes `rclpy`

Alternativa pro druhou větev nebo pozdější upgrade:

- ROS 2 Lyrical + Gazebo Jetty, pokud bude v NixOS/flake vrstvě dostupná stejně spolehlivě jako Jazzy/Harmonic.
- PX4 místo ArduPilotu, pokud by se projekt rozhodl pro PX4 ekosystém; pro tento konkrétní dron ale zůstává primární ArduPilot, protože flight controller je cílově plánovaný pro ArduPilot.
- MAVROS místo AP_DDS jako fallback ROS 2 integrace, pokud DDS cesta nebude na reálném hardwaru nebo NixOSu dostatečně stabilní.

Odůvodnění:

- ArduPilot dokumentace pro moderní Gazebo uvádí podporu Gazebo Garden a Harmonic.
- Gazebo Harmonic má oficiální ROS 2 integrační cestu přes `ros_gz`.
- ArduPilot DDS publikuje ROS 2 topics a služby jako `/ap/arm_motors`, `/ap/mode_switch`, `/ap/experimental/takeoff`.
- JSON SITL backend je jednoduchý a je standardní cestou používanou `ardupilot_gazebo` pluginem.
- ROS 2 Jazzy + Gazebo Harmonic je oficiálně doporučená kompatibilní kombinace. ROS 2 Lyrical + Gazebo Jetty je druhá velká LTS možnost, ale znamená novější stack a vyšší riziko balení na NixOSu.

## Role jednotlivých částí

Gazebo:

- fyzika, svět, kolize, vizualizace dronu
- generování simulačních sensor topics: IMU, kamera, lidar, rangefinder, optical flow podle dostupných pluginů
- ArduPilot Gazebo plugin přijímá PWM/servo výstupy ze SITL a vrací stav simulace do ArduPilotu

ArduPilot SITL:

- letový controller pro quad X
- režimy, arm/disarm, takeoff, řízení rychlosti
- DDS telemetry a služby pro ROS 2

ROS 2:

- companion computer vrstva
- demonstrace nodů, topics, subscriberů, publisherů, messages a TF
- RViz2 vizualizace
- Python autonomie

## Co první verze nebude řešit

- přesně změřenou aerodynamiku ductů
- přesný thrust curve pro SPEEDX2 1404 3850 KV s konkrétní vrtulí
- reálný OpenIPC video stream z RunCam WiFiLink 2
- plnohodnotný SLAM/Nav2/VIO stack
- přímé připojení MicoAir H743 hardware
- perfektní indoor autonomii

Tyto oblasti se připraví strukturou projektu, ale nebudou podmínkou první funkční verze.

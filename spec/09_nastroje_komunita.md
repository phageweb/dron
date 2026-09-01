# Nástroje, GitHub odkazy a údržba

Kontrola k datu 2026-09-01. Cílem je používat hlavně nástroje s velkou komunitou, aktivní údržbou a jasnou návazností na ROS/droní ekosystém. Menší specializované nástroje jsou povolené jen tehdy, když jsou oficiální součástí většího ekosystému nebo mají jasný fallback.

## Primární volba pro první simulaci

| Oblast | Primární nástroj | GitHub | Stav |
| --- | --- | --- | --- |
| Robotický middleware | ROS 2 Jazzy | https://github.com/ros2/ros2 | velký upstream, LTS do května 2029 |
| Simulátor | Gazebo Harmonic | https://github.com/gazebosim/gz-sim | velký aktivní projekt, Harmonic LTS do května 2029 |
| ROS/Gazebo bridge | `ros_gz` | https://github.com/gazebosim/ros_gz | oficiální bridge, doporučený pro ROS 2 + Gazebo |
| Build ROS workspace | `colcon` | https://github.com/colcon/colcon-core | standardní ROS 2 build nástroj, aktivní organizace |
| Vizualizace | RViz2 | https://github.com/ros2/rviz | součást ROS 2 ekosystému, aktivní |
| Python ROS nody | `rclpy` | https://github.com/ros2/rclpy | oficiální Python klientská knihovna ROS 2 |
| Nix balíčky | `nixpkgs` | https://github.com/NixOS/nixpkgs | velmi velká komunita, hlavní zdroj Nix balíčků |
| ROS na Nixu | `nix-ros-overlay` | https://github.com/lopsided98/nix-ros-overlay | menší, ale relevantní a aktivní ROS/Nix specializace |
| Autopilot | ArduPilot | https://github.com/ArduPilot/ardupilot | velký a aktivní autopilot ekosystém |
| ArduPilot Gazebo plugin | `ardupilot_gazebo` | https://github.com/ArduPilot/ardupilot_gazebo | menší repo, ale oficiální ArduPilot plugin pro moderní Gazebo |
| ArduPilot ROS 2 use cases | `ardupilot_ros` | https://github.com/ArduPilot/ardupilot_ros | menší repo, oficiální ArduPilot ROS integrace |
| DDS agent | Micro XRCE-DDS Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent | aktivní eProsima projekt, používaný micro-ROS/ArduPilot DDS cestou |
| Ground control | QGroundControl | https://github.com/mavlink/qgroundcontrol | velká komunita, podporuje ArduPilot i PX4 přes MAVLink |

## Dvě velké možnosti, kde má smysl volit

### ROS 2 Jazzy + Gazebo Harmonic vs. ROS 2 Lyrical + Gazebo Jetty

Varianta A:

- ROS 2 Jazzy + Gazebo Harmonic
- doporučená pro první implementaci
- oficiálně doporučená kombinace pro Jazzy
- Harmonic i Jazzy mají LTS horizont do května 2029
- pravděpodobně nejméně bolestivá varianta pro ROS/Gazebo balíčky

Varianta B:

- ROS 2 Lyrical + Gazebo Jetty
- novější LTS větev
- delší budoucí support
- použít, pokud bude v NixOS flaku dostupná bez nadměrného ručního patchování

Rozhodnutí:

- začít s Jazzy/Harmonic
- Lyrical/Jetty vést jako upgrade kandidáta, ne jako první krok

### ArduPilot vs. PX4

ArduPilot:

- GitHub: https://github.com/ArduPilot/ardupilot
- vhodnější pro tento projekt, protože cílový flight controller je plánovaný s ArduPilot firmwarem
- silná komunita v hobby, výzkumném i praktickém UAV světě
- oficiální Gazebo plugin a AP_DDS cesta

PX4:

- GitHub: https://github.com/PX4/PX4-Autopilot
- druhý velký open-source autopilot ekosystém
- velmi silná ROS 2/DDS a simulace komunita
- vhodný jako alternativa, pokud by se změnil firmware/hardware plán

Rozhodnutí:

- primární je ArduPilot
- PX4 nezahazovat jako alternativní větev, ale nemíchat ho do první implementace

### AP_DDS vs. MAVROS

AP_DDS:

- GitHub ArduPilot: https://github.com/ArduPilot/ardupilot
- nativnější ROS 2/DDS cesta pro ArduPilot
- vhodné pro nové ROS 2 demo a služby typu arm/mode/takeoff

MAVROS:

- GitHub: https://github.com/mavlink/mavros
- větší a starší ROS/MAVLink bridge
- podporuje ArduPilot i PX4
- vhodný fallback, pokud AP_DDS narazí na problémy v NixOSu nebo na reálném hardwaru

Rozhodnutí:

- začít s AP_DDS
- MAVROS držet jako podporovaný fallback pro reálný dron a diagnostiku

### SLAM Toolbox vs. RTAB-Map

SLAM Toolbox:

- GitHub: https://github.com/SteveMacenski/slam_toolbox
- vhodný pro první 2D lidar SLAM
- ROS Index ho uvádí jako maintained/released a doporučený
- dobrá návaznost na Nav2

RTAB-Map:

- GitHub ROS wrapper: https://github.com/introlab/rtabmap_ros
- GitHub core: https://github.com/introlab/rtabmap
- silná volba pro RGB-D, stereo, 3D mapping a vizuální experimenty
- vhodnější pro pozdější kamerovou/depth větev

Rozhodnutí:

- pro první 2D lidar indoor mapování použít SLAM Toolbox
- pro kamerové/depth experimenty nabídnout RTAB-Map

### Cartographer

- GitHub: https://github.com/cartographer-project/cartographer
- velký historický projekt, ale upstream uvádí, že už není aktivně udržovaný
- nepoužívat jako default pro nový projekt
- zmínit jen jako historickou/experimentální možnost, pokud bude existovat konkrétní důvod

## Pozdější rozšíření s velkou komunitou

| Oblast | Doporučený nástroj | GitHub | Poznámka |
| --- | --- | --- | --- |
| Navigace | Nav2 | https://github.com/ros-navigation/navigation2 | hlavní ROS 2 navigation stack, aktivní a vydávaný pro Jazzy |
| 2D SLAM | SLAM Toolbox | https://github.com/SteveMacenski/slam_toolbox | první volba pro LaserScan SLAM |
| RGB-D/3D SLAM | RTAB-Map ROS | https://github.com/introlab/rtabmap_ros | vhodné pro kameru/depth/VIO experimenty |
| Computer vision | OpenCV | https://github.com/opencv/opencv | velmi velká komunita, základní stavební blok pro vision |
| OpenIPC firmware | OpenIPC firmware | https://github.com/OpenIPC/firmware | aktivní komunita pro open IP camera firmware |
| OpenIPC tooling | OpenIPC org | https://github.com/OpenIPC | použít konkrétní nástroj až podle podporovaného čipu/kamery |
| MAVLink bridge | MAVROS | https://github.com/mavlink/mavros | fallback/alternativa k AP_DDS |
| Ground station | QGroundControl | https://github.com/mavlink/qgroundcontrol | praktický nástroj pro setup a monitoring |

## Explicitně nepoužívat jako základ

| Nástroj | Důvod |
| --- | --- |
| Gazebo Classic | EOL od ledna 2025, nový projekt má používat moderní Gazebo |
| `khancyr/ardupilot_gazebo` | archivovaný legacy plugin pro staré Gazebo |
| Cartographer jako default | upstream nevede aktivní vývoj |
| náhodné malé ORB-SLAM3 ROS 2 wrappery | často jednotlivé experimenty bez široké údržby |

## Kritéria pro přidání nového nástroje

Nový nástroj přidat jen pokud splní alespoň většinu:

- aktivní upstream nebo jasná LTS větev
- GitHub repo není archivované
- existují releases, ROS Index záznam nebo oficiální dokumentace
- komunita je větší než jeden osobní experiment
- má vazbu na ROS 2, ArduPilot/PX4, Gazebo nebo OpenIPC
- jde nahradit přes adapter/remapping, pokud později selže

Výjimka:

- malé specializované drivery pro konkrétní senzor jsou přijatelné, ale musí být izolované v `openipc_cinewhoop_hardware` nebo adapter nodu.

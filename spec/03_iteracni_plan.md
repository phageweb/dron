# Iterační implementační plán

Každý krok musí skončit konkrétním ověřením. Pokud ověření selže, další krok se nezačíná, dokud není problém diagnostikovaný.

## Fáze 0: Repozitář a dokumentace

Cíl:

- vytvořit `spec/`
- založit budoucí strukturu projektu
- zapsat rozhodnutí o stacku, modelech a ověřování

Ověření:

```bash
find spec -maxdepth 1 -type f | sort
```

## Fáze 1: Nix shell

Cíl:

- vytvořit `flake.nix`
- připravit shell pro ROS 2 Jazzy, Gazebo Harmonic, colcon, Python tooling a ArduPilot závislosti
- nepoužívat Docker

Minimální nástroje v shellu:

- `ros2`
- `colcon`
- `rviz2`
- `gz`
- `python3`
- `sim_vehicle.py`
- `MicroXRCEAgent` nebo `micro_ros_agent`
- `cmake`, `ninja`/`make`, `pkg-config`

Ověření:

```bash
nix develop
ros2 --help
gz sim --versions
rviz2 --help
python3 --version
```

Riziko:

- Některé ROS 2/ArduPilot balíčky nemusí být přímo v nixpkgs.
- Může být potřeba použít overlay nebo pinned zdrojové buildy v `flake.nix`.

## Fáze 2: ROS 2 workspace

Cíl:

- vytvořit `ros_ws/src`
- založit tři ROS 2 balíčky:
  - `openipc_cinewhoop_description`
  - `openipc_cinewhoop_gazebo`
  - `openipc_cinewhoop_demo`

Ověření:

```bash
colcon build --symlink-install --base-paths ros_ws/src
source ros_ws/install/setup.bash
ros2 pkg list | grep openipc_cinewhoop
```

## Fáze 3: Základní model pro RViz2

Cíl:

- vytvořit URDF/Xacro s povinnými linky:
  - `base_link`
  - `camera_link`
  - `imu_link`
  - `optical_flow_link`
  - `rangefinder_link`
  - `front_lidar_link`
  - `motor_1` až `motor_4`
- přidat jednoduchou vizualizaci rámu, ductů, motorů a kamery
- spustit `robot_state_publisher`

Ověření:

```bash
ros2 launch openipc_cinewhoop_description display.launch.py
ros2 topic echo /robot_description --once
ros2 run tf2_tools view_frames
```

RViz ověření:

- model je vidět
- linky mají očekávané pozice
- kamera je vpředu
- optical flow a rangefinder míří dolů
- front lidar míří dopředu

## Fáze 4: Základní Gazebo svět a vlastní SDF model

Cíl:

- vytvořit `indoor_test.sdf`
- vytvořit vlastní `openipc_cinewhoop/model.sdf`
- dron se objeví v Gazebu
- svět obsahuje místnost nebo malé bludiště

Ověření:

```bash
gz sim -v4 -r worlds/indoor_test.sdf
gz model --list
gz topic -l
```

Kritéria:

- v Gazebu není výsledným modelem Iris
- dron má správnou přibližnou velikost
- kolize odpovídají ducted cinewhoopu
- model nespadne kvůli invalidním inertial hodnotám

## Fáze 5: Gazebo senzory a bridge do ROS 2

Cíl:

- přidat IMU
- přidat dolní rangefinder
- přidat přední lidar
- přidat kameru
- připravit `ros_gz_bridge` config

Ověření:

```bash
ros2 topic list
ros2 topic echo /openipc_cinewhoop/imu --once
ros2 topic echo /openipc_cinewhoop/range/down --once
ros2 topic echo /openipc_cinewhoop/scan/front --once
ros2 topic hz /openipc_cinewhoop/scan/front
```

RViz ověření:

- LaserScan display ukazuje překážky před dronem
- TF frames sedí se senzory
- odometrie/trajektorie jsou ve správném frame

## Fáze 6: ArduPilot SITL smoke test s Iris

Cíl:

- ověřit, že ArduPilot SITL, Gazebo plugin a JSON backend fungují v Nix shellu
- Iris použít pouze jako dočasnou diagnostiku

Ověření:

```bash
gz sim -v4 -r iris_runway.sdf
sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console --map
```

V MAVProxy:

```text
mode guided
arm throttle
takeoff 2
```

Kritéria:

- SITL se spojí s Gazebo pluginem
- motory reagují
- model vzlétne

## Fáze 7: ArduPilot SITL s vlastním cinewhoop modelem

Cíl:

- do vlastního SDF přidat ArduPilot Gazebo plugin
- nastavit motor joints/plugins podle quad X
- nastavit frame parametry pro ArduCopter
- spustit SITL s vlastním frame/model configem

Ověření:

```bash
gz sim -v4 -r worlds/indoor_test.sdf
sim_vehicle.py -v ArduCopter --model JSON --console --map
```

V MAVProxy:

```text
mode guided
arm throttle
takeoff 1
```

Kritéria:

- dron se neotáčí nekontrolovaně
- hover je přibližně stabilní
- při takeoffu stoupá místo převrácení
- motor mapping odpovídá ArduPilot mixeru

## Fáze 8: ArduPilot DDS / ROS 2 komunikace

Cíl:

- spustit Micro XRCE-DDS Agent
- spustit SITL s DDS
- ověřit ROS 2 topics a services z ArduPilotu

Ověření:

```bash
ros2 run micro_ros_agent micro_ros_agent udp4 -p 2019
sim_vehicle.py -v ArduCopter --model JSON --console --map --enable-DDS
ros2 node list
ros2 topic list | grep /ap/
ros2 service list | grep /ap/
ros2 topic echo /ap/imu/experimental/data --once
```

Očekávané služby:

- `/ap/arm_motors`
- `/ap/mode_switch`
- `/ap/prearm_check`
- `/ap/experimental/takeoff`

## Fáze 9: RViz2 konfigurace

Cíl:

- vytvořit `cinewhoop.rviz`
- zobrazit:
  - RobotModel
  - TF
  - LaserScan předního lidaru
  - dolní range/range marker
  - odometrii
  - trajektorii
  - volitelně kameru

Ověření:

```bash
ros2 launch openipc_cinewhoop_description display.launch.py
```

Kritéria:

- pevný frame je konzistentní, například `map` nebo `odom`
- model a lidar nejsou otočené o 90/180 stupňů
- trajektorie odpovídá pohybu v Gazebu

## Fáze 10: `obstacle_monitor.py`

Cíl:

- jednoduchý subscriber na přední lidar
- výpis nejbližší platné vzdálenosti
- ukázka práce s `sensor_msgs/msg/LaserScan`

Ověření:

```bash
ros2 run openipc_cinewhoop_demo obstacle_monitor
ros2 topic echo /openipc_cinewhoop/scan/front --once
```

Kritéria:

- node ignoruje `inf` a `nan`
- vypisuje minimum v metrech
- při přiblížení ke stěně hodnota klesá

## Fáze 11: `simple_indoor_autonomy.py`

Cíl:

- použít ROS 2 služby ArduPilotu pro arm/mode/takeoff
- posílat nízkou dopřednou rychlost přibližně 0.5 m/s
- sledovat přední lidar
- při překážce pod 0.8 m zastavit
- volitelně otočit yaw a pokračovat

Ověření:

```bash
ros2 run openipc_cinewhoop_demo simple_indoor_autonomy
```

Kritéria:

- node nejdřív čeká na služby a sensor topics
- bez lidaru neodstartuje nebo přejde do bezpečného stavu
- po detekci překážky pošle nulovou rychlost
- demo je pomalé a čitelné

## Fáze 12: Jednotný launch

Cíl:

- připravit jeden launch pro celé demo
- ideálně spouštět:
  - Gazebo world
  - ROS/Gazebo bridge
  - robot_state_publisher
  - RViz2
  - Micro XRCE-DDS Agent
  - volitelně SITL nebo instrukci pro samostatný terminál

Ověření:

```bash
ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py
```

Kritéria:

- uživatel vidí cinewhoop v Gazebu
- RViz ukazuje TF a lidar
- `ros2 topic list` obsahuje Gazebo i ArduPilot topics
- demo nody lze pustit samostatně

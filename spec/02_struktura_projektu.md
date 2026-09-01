# Struktura projektu

Navržená cílová struktura:

```text
flake.nix
README.md

ros_ws/
  src/
    openipc_cinewhoop_description/
      package.xml
      CMakeLists.txt
      launch/
        display.launch.py
      rviz/
        cinewhoop.rviz
      urdf/
        openipc_cinewhoop.urdf.xacro
      meshes/
      config/
        physical_params.yaml

    openipc_cinewhoop_gazebo/
      package.xml
      CMakeLists.txt
      launch/
        gazebo.launch.py
        sitl_gazebo.launch.py
      config/
        gz_bridge.yaml
        ardupilot_params.parm
      worlds/
        indoor_test.sdf
      models/
        openipc_cinewhoop/
          model.config
          model.sdf

    openipc_cinewhoop_demo/
      package.xml
      setup.py
      setup.cfg
      resource/
        openipc_cinewhoop_demo
      openipc_cinewhoop_demo/
        __init__.py
        obstacle_monitor.py
        simple_indoor_autonomy.py
        trajectory_publisher.py
        tf_helpers.py
      launch/
        demo.launch.py

models/
  openipc_cinewhoop/
    model.config
    model.sdf

worlds/
  indoor_test.sdf

scripts/
  dev_env_check.sh
  run_gazebo.sh
  run_sitl.sh
  run_dds_agent.sh
  run_demo.sh
```

## Balíček `openipc_cinewhoop_description`

Účel:

- ROS 2 popis robota
- URDF/Xacro pro RViz2
- TF strom a vizualizace
- sdílené fyzikální parametry

Obsah:

- `urdf/openipc_cinewhoop.urdf.xacro`
- `config/physical_params.yaml`
- `rviz/cinewhoop.rviz`
- launch pro `robot_state_publisher` a RViz2

Poznámka:

- Gazebo primárně poběží ze SDF modelu.
- URDF/Xacro slouží pro ROS/RViz a musí zůstat parametricky konzistentní se SDF.

## Balíček `openipc_cinewhoop_gazebo`

Účel:

- Gazebo svět
- vlastní SDF model dronu
- konfigurace bridge mezi Gazebo a ROS 2
- konfigurace ArduPilot Gazebo pluginu

Obsah:

- `models/openipc_cinewhoop/model.sdf`
- `worlds/indoor_test.sdf`
- `config/gz_bridge.yaml`
- `config/ardupilot_params.parm`
- launch pro Gazebo, bridge a SITL

## Balíček `openipc_cinewhoop_demo`

Účel:

- praktické ROS 2 ukázky
- Python nody pro subscriber/publisher/services
- jednoduchá indoor autonomie

Nody:

- `obstacle_monitor.py`
- `simple_indoor_autonomy.py`
- `trajectory_publisher.py`

## Root `models/` a `worlds/`

Root kopie nebo symlinky budou užitečné pro čisté Gazebo spuštění přes `gz sim` mimo ROS launch.

Finální rozhodnutí při implementaci:

- Buď držet model/world jen v ROS balíčku a root složky používat jako odkazy.
- Nebo držet canonical SDF v root `models/` a `worlds/`, zatímco balíček obsahuje install pravidla.

Preferovaná varianta:

- canonical soubory v ROS balíčku `openipc_cinewhoop_gazebo`
- root `models/` a `worlds/` jako pohodlné entrypointy nebo kopie generované při buildu

## Launch entrypointy

Požadované cílové příkazy:

```bash
nix develop
colcon build --symlink-install --base-paths ros_ws/src
source ros_ws/install/setup.bash
ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py
```

Volitelné separátní terminály pro diagnostiku:

```bash
gz sim -v4 -r worlds/indoor_test.sdf
sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console --map
ros2 run micro_ros_agent micro_ros_agent udp4 -p 2019
ros2 launch openipc_cinewhoop_description display.launch.py
ros2 run openipc_cinewhoop_demo obstacle_monitor
ros2 run openipc_cinewhoop_demo simple_indoor_autonomy
```

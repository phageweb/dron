# NixOS flake plán

## Cíle

- reprodukovatelný vývojový shell přes `nix develop`
- žádný Docker v první implementaci
- pinované zdroje pro ROS 2/Gazebo/ArduPilot tooling
- shell použitelný pro build ROS workspace i ruční diagnostiku

## První návrh `flake.nix`

Preferovaný směr:

- `nixpkgs` pin kompatibilní s ROS 2 Jazzy balíčky
- ROS 2 Jazzy balíčky z nixpkgs nebo `nix-ros-overlay`, pokud bude potřeba
- Gazebo Harmonic / `gz-sim8`
- `colcon`, `rosdep`, `rviz2`, `xacro`, `tf2_tools`, `ros_gz`
- Python balíčky pro ROS nody
- ArduPilot SITL buď:
  - jako zdrojový build v repu/submodulu, nebo
  - přes `nix develop` s potřebnými závislostmi a checkoutem ArduPilotu mimo flake derivaci

## Nix varianta A: `nixpkgs` + `nix-ros-overlay`

Použít jako první pokus, protože `nix-ros-overlay` je specializovaná ROS vrstva pro Nix, obsahuje příklady pro ROS 2 Jazzy a má automatizované generování ROS balíčků.

Riziko:

- je to menší komunita než samotný `nixpkgs`, ROS 2 nebo Gazebo
- cache nemusí vždy obsahovat všechny balíčky
- některé balíčky bude potřeba opravit nebo přepsat overlayem

## Nix varianta B: pinované zdrojové buildy ve flaku

Použít, pokud `nix-ros-overlay` nebude spolehlivě pokrývat potřebné balíčky.

Princip:

- `nixpkgs` řeší systémové knihovny
- ROS 2 workspace se builduje přes `colcon`
- ArduPilot, `ardupilot_gazebo` a případné ROS balíčky se pinují přes `flake.lock`

Riziko:

- více práce v `flake.nix`
- delší build
- méně pohodlné než hotové ROS balíčky

Rozhodnutí pro první implementaci:

- začít variantou A
- variantu B držet jako fallback, ne jako samostatný paralelní projekt

## Očekávané shell proměnné

Shell by měl nastavit:

```bash
export ROS_DISTRO=jazzy
export GZ_VERSION=harmonic
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export GZ_SIM_RESOURCE_PATH=$PWD/ros_ws/src/openipc_cinewhoop_gazebo/worlds:$PWD/ros_ws/src/openipc_cinewhoop_gazebo/models:$PWD/models:$PWD/worlds:${GZ_SIM_RESOURCE_PATH:-}
export GZ_SIM_SYSTEM_PLUGIN_PATH=$PWD/build/ardupilot_gazebo:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}
```

Konkrétní cesta pro `GZ_SIM_SYSTEM_PLUGIN_PATH` se upraví podle toho, kde bude `ardupilot_gazebo` buildnutý.

## Diagnostické příkazy

Po vstupu do shellu:

```bash
ros2 --help
colcon --help
rviz2 --help
gz sim --versions
python3 -c "import rclpy; print('rclpy ok')"
```

Gazebo smoke test:

```bash
gz sim -v4 -r shapes.sdf
```

ROS smoke test:

```bash
ros2 run demo_nodes_cpp talker
ros2 run demo_nodes_py listener
```

Pokud demo balíčky nebudou součástí shellu, smoke test se nahradí vlastním minimálním publisher/subscriber balíčkem.

## ArduPilot a `ardupilot_gazebo`

První ověřená cesta:

1. V shellu mít build dependencies pro ArduPilot a Gazebo plugin.
2. Získat/pinovat `ardupilot` a `ardupilot_gazebo`.
3. Buildnout `ardupilot_gazebo` pro Harmonic.
4. Spustit Iris smoke test.
5. Teprve potom přepnout na vlastní `openipc_cinewhoop` model.

Předpokládané build ověření pluginu:

```bash
export GZ_VERSION=harmonic
cmake -S ardupilot_gazebo -B build/ardupilot_gazebo -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build/ardupilot_gazebo -j
```

## Rizika na NixOS

- GUI aplikace `gz sim` a `rviz2` mohou vyžadovat správné OpenGL/Wayland/X11 knihovny v shellu.
- ArduPilot build skripty mohou očekávat běžné FHS cesty.
- Některé Micro XRCE-DDS/Micro ROS balíčky mohou být jednodušší buildnout ze zdroje.
- `rosdep` není na NixOS hlavní zdroj pravdy; závislosti musí řešit flake.
- Menší Nix/ROS nástroje musí být brané pragmaticky: pokud jsou specializované a aktivní, mohou být použité, ale nesmí být jedinou cestou bez fallbacku.

## Kritérium hotového shellu

Hotový shell musí umožnit:

```bash
nix develop
colcon build --symlink-install --base-paths ros_ws/src
gz sim -v4 -r worlds/indoor_test.sdf
ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py
rviz2
```

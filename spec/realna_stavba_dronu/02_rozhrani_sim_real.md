# Rozhraní simulace vs. reálný dron

## Základní pravidlo

Python ROS 2 nody nemají poznat, jestli běží proti Gazebo simulaci nebo proti reálnému dronu. Rozdíly se mají řešit přes launch parametry, remapping a malé adapter nody.

## Stabilní topic názvy

Držet tyto logické názvy:

| Logický topic | Simulace | Reálný dron |
| --- | --- | --- |
| `/openipc_cinewhoop/imu` | Gazebo IMU nebo AP_DDS IMU | ArduPilot DDS/MAVLink IMU |
| `/openipc_cinewhoop/range/down` | Gazebo range sensor přes `range_adapter` | MicoAir MTF-02P rangefinder |
| `/openipc_cinewhoop/flow/down` | Gazebo/odvozený flow node | MicoAir MTF-02P optical flow |
| `/openipc_cinewhoop/scan/front` | Gazebo lidar | přední lidar/depth/range adapter |
| `/openipc_cinewhoop/camera/image_raw` | Gazebo camera | OpenIPC stream převedený do ROS Image |
| `/openipc_cinewhoop/odom` | Gazebo ground truth/AP pose | EKF/ArduPilot/VIO odometrie |
| `/openipc_cinewhoop/path` | trajectory node | trajectory node |
| `/ap/*` | ArduPilot SITL DDS | ArduPilot hardware DDS nebo MAVLink adapter |

## Parametry demo nodů

Každý node musí mít parametry pro názvy topics/služeb:

```text
scan_topic
range_topic
flow_topic
imu_topic
pose_topic
odom_topic
cmd_vel_topic
arm_service
mode_service
takeoff_service
```

Tím se při přechodu na reálný dron nemění algoritmus, jen launch.

## Adapter nody

Simulace:

```text
Gazebo topic -> ros_gz_bridge -> /openipc_cinewhoop/*
ArduPilot SITL -> AP_DDS -> /ap/*
```

Reálný dron:

```text
hardware sensor -> driver/adapter -> /openipc_cinewhoop/*
ArduPilot hardware -> DDS/MAVLink adapter -> /ap/*
OpenIPC stream -> video adapter -> /openipc_cinewhoop/camera/image_raw
```

## Režimy řízení

První simulační autonomie:

- arm
- takeoff 1 m
- dopředná rychlost 0.5 m/s
- stop pod 0.8 m před překážkou

První reálná autonomie:

- nejdřív jen monitoring bez řízení
- potom pouze nízkorychlostní příkazy v bezpečném režimu
- vždy s ručním převzetím řízení přes RC
- obstacle stop testovat nejdřív bez letu nebo na uvázaném/bezpečně omezeném setupu

## Co se nesmí pevně zadrátovat

Nedávat natvrdo do Python kódu:

- konkrétní Gazebo topic názvy
- konkrétní sériový port
- konkrétní IP adresu OpenIPC kamery
- konkrétní ArduPilot transport
- předpoklad, že zdroj odometrie je vždy Gazebo

Tyto věci patří do launch souborů a YAML konfigurace.

## Ověřeno automaticky

`scripts/check_topic_remap.sh` (běží v baseline CI) ověřuje, že přechod na
hardware je skutečně jen otázka launche:

- všechny tři demo nody subscribují a publikují na přemapovaných názvech a
  default názvy zmizí, takže node neposlouchá omylem na obou
- `simple_indoor_autonomy` skutečně **zavolá** všechny čtyři ArduPilot služby
  pod přemapovanými názvy. `ros2 node info` service clienty nevypisuje, takže se
  to neověřuje introspekcí, ale postavením falešných služeb
  (`scripts/fake_ardupilot_services.py`)
- tím se zároveň projde celý stavový automat bez simulátoru: s 5 m volného
  prostoru node rozjede 0.5 m/s, s překážkou v 1.0 m nepošle dopředu nic

Část se službami potřebuje `ardupilot_msgs` z opt-in DDS workspace; bez něj se
přeskočí, aby baseline CI nezáviselo na `external/`.

`scripts/check_sensor_interface.sh` (baseline CI) ověřuje tvar dat, ne jen jména:
typy zpráv proti [ROS rozhraní](../04_ros_rozhrani.md), že se každý frame_id dá
transformovat do `base_link`, že deklarovaný kužel rangefinderu odpovídá
simulovanému vějíři a že IMU v klidu čte +9.81 na z.

`scripts/check_sensor_dropout.sh` (baseline CI) ověřuje chování při mrtvém
senzoru, viz poslední bod checklistu níž.

## Přechodový checklist

- [x] simulační topic má stejný typ zprávy jako reálný topic

  `/openipc_cinewhoop/range/down` posílal `sensor_msgs/msg/LaserScan`, protože
  Gazebo umí rangefinder jen jako malý lidar. Reálný MTF-02P publikuje
  `sensor_msgs/msg/Range` a [ROS rozhraní](../04_ros_rozhrani.md) to tak
  specifikuje. Bridge teď končí na `/openipc_cinewhoop/range/down_raw` a
  `range_adapter` vlastní logický název. Simulovaný senzor je zároveň úzký vějíř
  místo jednoho paprsku, protože time-of-flight čidlo vrací nejbližší plochu v
  kuželu; MicoAir udávají u MTF-02P vyzařovací úhel 2 stupně. Jeden paprsek
  navíc nechával `angle_increment` NaN.

- [x] frame_id odpovídá stejnému TF stromu

  Bez `gz_frame_id` razítkuje Gazebo senzor zprávy vlastním scoped jménem, takže
  přední lidar posílal `openipc_cinewhoop/front_lidar_link/front_lidar`. Takový
  frame v TF stromu neexistuje, RViz scan zahodí bez chyby v topicu a reálný
  driver by publikoval něco jiného. Lidar, rangefinder i kamera teď posílají
  `front_lidar_link`, `rangefinder_link` a `camera_optical_frame`.

- [x] jednotky jsou stejné

  Jednotky jsou dané typem zprávy, takže tuhle položku držel předchozí bod: metry
  u `Range` a `LaserScan`, rad/s a m/s^2 u `Imu`. `scripts/check_sensor_interface.sh`
  kontroluje typy proti [ROS rozhraní](../04_ros_rozhrani.md).

- [x] znaménka os jsou ověřená

  IMU v modelu je otočené o 180 stupňů do letecké konvence, kterou čte
  ArduPilotPlugin, takže bridgnutý `/openipc_cinewhoop/imu` měl z v klidu -9.81
  místo +9.81. AP_DDS na reálném dronu publikuje REP 103, takže by se znaménko
  otočilo až na hardwaru. Model má proto druhý, neotočený senzor `imu_ros` pro
  ROS a check měří gravitaci.

  Dolní senzory měří podél +X vlastního framu, takže `rangefinder_link` i
  `optical_flow_link` jsou v URDF sklopené o 90 stupňů stejně jako v SDF.

- [x] timestampy používají konzistentní čas

  `demo.launch.py` měl `use_sim_time` natvrdo na `true`. Na hardwaru žádné
  `/clock` není a node by četl pořád stejný okamžik, takže by každé stáří zprávy
  vyšlo nula a ochrana proti mrtvému lidaru by tiše přestala platit. Je to
  launch argument.

- [x] QoS je vhodné pro sensor data

  AP_DDS publikuje `/ap/pose/filtered` jako BEST_EFFORT. RELIABLE subscriber se
  s BEST_EFFORT publisherem **nespáruje**, takže `trajectory_publisher` s
  defaultním QoS od reálného ArduPilotu nikdy nic nedostal. CI to neodhalilo,
  protože `ros2 topic pub` posílá RELIABLE a testovací publisher se tedy
  spároval. Opraveno na `qos_profile_sensor_data` a `check_ros_graph.sh`
  publikuje BEST_EFFORT, aby to příště spadlo.

- [x] při výpadku senzoru node přejde do bezpečného stavu

  Ověřuje `scripts/check_sensor_dropout.sh` bez Gazeba i SITL: scan se publikuje
  z příkazové řádky a pak se zastaví, což je přesně to, co node vidí při
  odpojeném senzoru. `simple_indoor_autonomy` přejde z 0.5 m/s na 0.0 a
  `obstacle_monitor` mlčení nahlásí, místo aby jen přestal psát.

# Rozhraní simulace vs. reálný dron

## Základní pravidlo

Python ROS 2 nody nemají poznat, jestli běží proti Gazebo simulaci nebo proti reálnému dronu. Rozdíly se mají řešit přes launch parametry, remapping a malé adapter nody.

## Stabilní topic názvy

Držet tyto logické názvy:

| Logický topic | Simulace | Reálný dron |
| --- | --- | --- |
| `/openipc_cinewhoop/imu` | Gazebo IMU nebo AP_DDS IMU | ArduPilot DDS/MAVLink IMU |
| `/openipc_cinewhoop/range/down` | Gazebo range sensor | MicoAir MTF-02P rangefinder |
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

## Přechodový checklist

- [ ] simulační topic má stejný typ zprávy jako reálný topic
- [ ] frame_id odpovídá stejnému TF stromu
- [ ] jednotky jsou stejné
- [ ] znaménka os jsou ověřená
- [ ] timestampy používají konzistentní čas
- [ ] QoS je vhodné pro sensor data
- [ ] při výpadku senzoru node přejde do bezpečného stavu

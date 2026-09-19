# Pozdější rozšíření

Struktura projektu má počítat s tím, že ROS 2 nody napsané pro simulaci půjdou později s minimálními změnami použít na skutečném OpenIPC cinewhoopu.

## Stihne pozemní počítač rekonstruovat místnost?

Pásmo ani výpočet ne. LD06 vzorkuje pevných 4500 Hz, při 10 otáčkách za sekundu
tedy **450 bodů na otáčku** s rozlišením 0.8 stupně.

| | |
| --- | ---: |
| Syrový protokol LD06 | 17.6 kB/s = **141 kbit/s** |
| Kapacita UART 230400 | 23.0 kB/s |
| Jako ROS `LaserScan` | 36.0 kB/s = **288 kbit/s** |
| Podíl na lince wfb-ng | **2.0 %** |
| Podíl na tom, co zbývá po videu | **4.7 %** |

> **Oprava.** První dva řádky tu stály jako 13.5 kB/s a 108 kbit/s, a poslední
> jako 3.6 % z 8 Mbit/s videa. Obojí bylo optimistické. Skutečné číslo vypadlo
> z formátu paketu LD06 — 12 bodů v paketu po 47 B dává 375 paketů/s a
> **141 kbit/s** — a linka wfb-ng při výchozím MCS1 a 20 MHz nese ~7 Mbit/s pro
> **oba směry dohromady**, ne 8 Mbit/s dolů. Pořád to sedí, jen s menší
> rezervou. Rozpad v [Kudy se sken dostane do ROS 2](./realna_stavba_dronu/09_kudy_do_ros.md).

Výpočetně je 450 bodů na 10 Hz pro SLAM Toolbox na notebooku nic - běžné 2D
lidary dávají násobně víc bodů rychleji.

Latence taky ne. Při 40 až 100 ms, což je řád OpenIPC, se dron v demo rychlosti
0.5 m/s posune **2 až 5 cm**. To je pro mapování v pohodě; pro regulační smyčku
už ne, ale ta na zemi běžet nemá.

### Čím to skutečně padá

**Není naplánovaná datová cesta.** V kusovníku je ELRS, jehož telemetrie zvládá
stovky bajtů za sekundu, a OpenIPC WiFi. Lidar musí jet po **WiFi lince vedle
videa** - wfb-ng datový kanál umí, ale nikdo to zatím nerozhodl ani neověřil.

**Náklon dronu.** SLAM předpokládá vodorovný 2D řez. Nakloněný dron řeže
místnost šikmo a bere do skenu podlahu, viz
[troubleshooting](../workflow/troubleshooting.md). Pro zastavování před
překážkou to je nepříjemnost; **pro SLAM je to horší**, protože mapa se
integruje v čase a špatné skeny ji trvale poškodí. Kompenzace náklonu je
podmínka, ne vylepšení.

**Drift odometrie.** 2D SLAM potřebuje odhad pohybu. Uvnitř ho dá optical flow s
dolním rangefinderem přes EKF ArduPilotu, a ten driftuje.

**Výška řezu se hýbe.** Když dron stoupá a klesá, 2D řez putuje po stěnách a
nábytku. Co bylo v jedné výšce zeď, je v jiné volný prostor.

**wfb-ng ztrácí pakety schválně.** Vysílá bez potvrzování s dopřednou korekcí,
takže část skenů prostě nedorazí. SLAMu to nevadí, ale kanál se musí nastavit.

Shrnuto: **stihne to snadno**, a jestli z toho vyleze použitelná mapa, rozhoduje
kompenzace náklonu a odometrie, ne výkon ani linka.

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

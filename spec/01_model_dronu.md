# Fyzikální a senzorický model dronu

## Cílový reálný prototyp

- Typ: 3" cinewhoop
- Rámová třída: GEPRC CineLog30 V3
- Konfigurace: quad X
- Motory: 4x GEPRC SPEEDX2 1404, 3850 KV
- Vrtule: 3", průměr přibližně 76.2 mm
- Baterie: 4S LiHV Tattu 750 mAh
- Kamera: RunCam WiFiLink 2 / OpenIPC, vpředu
- Flight controller: MicoAir H743 V2 45A AIO, cílově ArduPilot
- Další senzory: IMU, barometr, optical flow, dolní rangefinder/lidar, přední obstacle lidar

## Počáteční simulační parametry

| Parametr | Hodnota pro první model | Poznámka |
| --- | ---: | --- |
| Celková hmotnost | 0.240 kg | cílová hodnota z požadavku |
| Wheelbase | 0.128 m | GEPRC uvádí pro CineLog30 V3; původní odhad byl 0.126 m |
| Rameno od středu k motoru | 0.064 m | half wheelbase pro quad X diagonálu |
| Souřadnice motoru vůči středu | +/-0.04525 m X/Y | `0.064 / sqrt(2)` |
| Průměr vrtule | 0.0762 m | 3" |
| Poloměr vrtule | 0.0381 m | pro vizualizaci a kolize |
| Baterie | 4S 750 mAh | simulovat hlavně hmotností a napětím |
| Nominální napětí | 15.2 V | LiHV přibližně 3.8 V na článek |
| Maximální napětí | 17.4 V | dle zadání |
| Těžiště | střed rámu | první aproximace |
| Dopředná demo rychlost | 0.5 m/s | pomalý indoor let |
| Autonomní výška | 1.0 m | jednoduché demo |
| Stop vzdálenost překážky | 0.8 m | přední lidar |

## Aproximace

Tyto hodnoty budou jasně zapsané v modelu a README, protože bez reálného měření nejde o přesný digitální twin:

- Hmotnost 240 g je jedna soustředěná hodnota pro celý dron včetně baterie, kamery a senzorů bez GoPro.
- Moment setrvačnosti bude odvozený z jednoduchého kvádru o přibližných rozměrech cinewhoopu, ne z CAD modelu rámu.
- Ducty budou v první verzi modelované jako vizuální/kolizní prstence, bez detailního modelu proudění vzduchu.
- Motory a vrtule budou mít laděné simulační koeficienty pro stabilní hover, ne měřenou thrust křivku.
- Optical flow bude simulačně publikovaný senzorický výstup nebo odvozený ROS node, podle toho, co bude v daném Gazebo/Nix stacku nejstabilnější.
- Barometr lze v první verzi reprezentovat ArduPilot SITL výstupem a výškou z odometrie; samostatný Gazebo barometer plugin je volitelný.
- Kamera bude v první verzi Gazebo RGB camera topic. OpenIPC stream se přidá později jako samostatný ROS image/video bridge.

## Navržené linky modelu

Model musí oddělit tyto linky:

- `base_link`
- `camera_link`
- `imu_link`
- `optical_flow_link`
- `rangefinder_link`
- `front_lidar_link`
- `motor_1`
- `motor_2`
- `motor_3`
- `motor_4`

Volitelné doplňkové linky pro čitelnější vizualizaci:

- `battery_link`
- `duct_1` až `duct_4`
- `prop_1` až `prop_4`

## Souřadný systém

ROS model:

- `base_link`: střed dronu, osa X dopředu, osa Y doleva, osa Z nahoru
- `camera_link`: vpředu, mírně nad středem, osa optiky podle ROS optical frame pravidel přes doplňkový `camera_optical_frame`
- `imu_link`: blízko středu, reprezentuje IMU na flight controlleru
- `optical_flow_link`: dolů, pod středem rámu
- `rangefinder_link`: dolů, pod středem rámu
- `front_lidar_link`: vpředu, horizontálně dopředu

Gazebo/ArduPilot:

- Je nutné ověřit orientaci frame mezi Gazebo ENU a ArduPilot NED.
- Převody frame musí být explicitně popsané v launch konfiguraci a TF bridge nodu.

## Motor layout quad X

Pořadí motorů musí být sladěné s ArduPilot frame definicí pro `quad X`.

První plánované rozmístění v ROS `base_link`:

| Motor | Poloha | Souřadnice vůči středu |
| --- | --- | --- |
| `motor_1` | front right | x = +0.04525, y = -0.04525 |
| `motor_2` | rear left | x = -0.04525, y = +0.04525 |
| `motor_3` | front left | x = +0.04525, y = +0.04525 |
| `motor_4` | rear right | x = -0.04525, y = -0.04525 |

Toto je pracovní pořadí. Během ověření ArduPilot SITL se musí potvrdit, že směr rotace a mixer odpovídají pluginu. Pokud se dron převrací, první diagnostika je mapování motorů a znaménka momentů.

## Senzory

IMU:

- topic v Gazebo a bridge do ROS 2 jako `sensor_msgs/msg/Imu`
- frame `imu_link`
- ověření přes `ros2 topic echo /openipc_cinewhoop/imu`

Optical flow:

- frame `optical_flow_link`, směr dolů
- první verze může publikovat demonstrativní ROS topic odvozený z Gazebo ground truth pohybu a výšky
- pozdější verze nahradí výstup skutečným optical flow pluginem nebo kamerovým zpracováním

Dolní rangefinder:

- frame `rangefinder_link`, směr dolů
- ROS typ: `sensor_msgs/msg/Range`
- rozsah například 0.05 m až 5.0 m

Přední lidar:

- frame `front_lidar_link`, směr dopředu
- ROS typ: `sensor_msgs/msg/LaserScan`
- úzký nebo střední FOV, například 60 stupňů
- rozsah například 0.10 m až 8.0 m
- demo stop threshold: 0.8 m

Kamera:

- frame `camera_link` + `camera_optical_frame`
- Gazebo RGB camera
- ROS typy: `sensor_msgs/msg/Image` a `sensor_msgs/msg/CameraInfo`
- OpenIPC stream až v pozdější fázi

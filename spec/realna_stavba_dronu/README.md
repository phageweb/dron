# Reálná stavba OpenIPC cinewhoopu

Tato větev popisuje fyzickou stavbu plánovaného 3" cinewhoopu. Je oddělená od obecné ROS 2 části, protože hardware má jiné otázky: mechanika, napájení, firmware, pájení, bezpečnost a postupné oživování.

## Cílová konfigurace

- Rám: GEPRC CineLog30 V3
- Typ: 3" ducted cinewhoop
- Konfigurace: quad X
- Motory: 4x GEPRC SPEEDX2 1404 3850 KV
- Vrtule: 3", přibližně 76.2 mm
- FC/ESC: MicoAir H743 V2 45A AIO
- Firmware: cílově ArduPilot
- Baterie: 4S LiHV Tattu 750 mAh
- RC: ExpressLRS, SpeedyBee ELRS Nano RX
- Video: RunCam WiFiLink 2 s OpenIPC
- Indoor senzory: MicoAir MTF-02P optical flow + downward rangefinder/lidar
- Volitelný obstacle sensor: přední lidar/depth/range sensor pro ROS 2, konkrétní
  díl zatím **nevybraný**, viz [varianty](./03_komponenty.md)

## Cíl reálné větve

Postavit fyzický dron tak, aby:

- bezpečně letěl jako ručně ovladatelný cinewhoop
- měl ArduPilot na reálném flight controlleru
- poskytoval data použitelná pro ROS 2 companion computer
- měl stejné nebo snadno remapovatelné ROS topics jako simulace
- umožnil pozdější SLAM, VIO, OpenCV a OpenIPC experimenty

## Co sem nepatří

- obecné učení ROS graphu
- obecné publisher/subscriber demo
- čistě simulační Gazebo fyzika
- Nix flake jako jediný problém

Tyto věci jsou ve větvi [ROS 2 na NixOSu](../ros2_nixos/README.md).

## Bezpečnostní zásada

Všechny bench testy flight controlleru, ESC, motorů, ArduPilot konfigurace a ROS komunikace se dělají bez vrtulí. Vrtule se nasazují až po ověření směru motorů, failsafe, arm/disarm, RC linku a základního režimu letu.

## Dokumenty této větve

- [Plán stavby](./01_plan_stavby.md) - fáze od potvrzení komponent po první let
- [Rozhraní simulace vs. reálný dron](./02_rozhrani_sim_real.md) - co se nesmí lišit
- [Tabulka komponent](./03_komponenty.md) - hmotnosti, napětí, konektory, datová rozhraní
- [Bench checklist bez vrtulí](./04_bench_checklist.md) - celé oživení až po první nasazení vrtulí

## Návaznost na simulaci

Reálná stavba má držet stejné logické rozhraní jako simulace:

```text
/openipc_cinewhoop/imu
/openipc_cinewhoop/range/down
/openipc_cinewhoop/scan/front
/openipc_cinewhoop/camera/image_raw
/openipc_cinewhoop/odom
/ap/*
```

Detaily jsou v [rozhraní simulace vs. reálný dron](./02_rozhrani_sim_real.md).

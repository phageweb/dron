# ROS 2 na NixOSu

Tato větev je obecná výuková cesta pro ROS 2 na NixOSu. Je záměrně oddělená od reálné stavby dronu, aby šlo nejdřív zvládnout nástroje, build a diagnostiku bez řešení hardwarových rizik.

## Cíl

Po dokončení této větve máš umět:

- vstoupit do reprodukovatelného ROS 2 shellu přes `nix develop`
- založit a buildnout ROS 2 workspace přes `colcon`
- spouštět ROS 2 nody
- číst a publikovat topics
- pracovat se zprávami jako `LaserScan`, `Imu`, `Odometry`, `Image`
- zobrazit TF strom v RViz2
- spustit Gazebo Harmonic
- bridgeovat Gazebo topics do ROS 2 přes `ros_gz_bridge`
- rozumět tomu, kde do systému vstupuje ArduPilot SITL a DDS

## Výstup této větve

Minimální obecné demo:

```text
Nix shell
└── ROS 2 workspace
    ├── talker/listener nebo vlastní Python publisher/subscriber
    ├── jednoduchý TF strom
    ├── Gazebo test world
    ├── RViz2 konfigurace
    └── bridge sensor topicu z Gazeba do ROS 2
```

Teprve potom se stejné principy použijí na `openipc_cinewhoop`.

## Co sem nepatří

- výběr reálné baterie
- pájení flight controlleru
- motorové testy
- ArduPilot parametry pro skutečný frame
- OpenIPC hardware stream
- bezpečnostní pravidla pro let s vrtulemi

To je samostatně v [reálné stavbě dronu](../realna_stavba_dronu/README.md).

## První příkazy

Po vytvoření `flake.nix` bude očekávaný vstup:

```bash
nix develop
ros2 --help
colcon --help
gz sim --versions
rviz2 --help
```

## Návaznost na simulaci dronu

Jakmile fungují obecné kroky, pokračuje se dokumenty:

- [Stack a rozsah simulace](../00_stack_a_rozsah.md)
- [Struktura projektu](../02_struktura_projektu.md)
- [Iterační implementační plán simulace](../03_iteracni_plan.md)

# Demo nody a autonomie

## `obstacle_monitor.py`

Účel:

- praktická ukázka ROS 2 subscriberu
- práce se zprávou `sensor_msgs/msg/LaserScan`
- čitelný výpis vzdálenosti nejbližší překážky před dronem

Vstup:

```text
/openipc_cinewhoop/scan/front
sensor_msgs/msg/LaserScan
```

Chování:

- subscribuje na přední lidar
- z `ranges` odstraní `nan`, `inf` a hodnoty mimo `range_min`/`range_max`
- spočítá minimum
- pravidelně loguje nejbližší překážku v metrech
- pokud není platné měření, loguje varování s omezenou frekvencí

Parametry:

| Parametr | Default | Účel |
| --- | ---: | --- |
| `scan_topic` | `/openipc_cinewhoop/scan/front` | topic předního lidaru |
| `warn_distance_m` | `0.8` | hranice blízké překážky |
| `log_period_s` | `0.5` | omezení log spamu |

Příklad budoucího spuštění:

```bash
ros2 run openipc_cinewhoop_demo obstacle_monitor --ros-args \
  -p scan_topic:=/openipc_cinewhoop/scan/front \
  -p warn_distance_m:=0.8
```

## `simple_indoor_autonomy.py`

Účel:

- názorné demo komunikace ROS 2 -> ArduPilot SITL
- základní subscriber + service clients + publisher
- pomalý indoor let se zastavením před překážkou

Vstupy:

```text
/openipc_cinewhoop/scan/front
/ap/status
/ap/pose/filtered
```

Výstupy/služby:

```text
/ap/prearm_check
/ap/mode_switch
/ap/arm_motors
/ap/experimental/takeoff
/ap/cmd_vel
```

Stavový automat:

```text
WAIT_FOR_ROS
WAIT_FOR_LIDAR
WAIT_FOR_ARDUPILOT
SET_GUIDED
PREARM_CHECK
ARM
TAKEOFF_1M
FLY_FORWARD
OBSTACLE_STOP
TURN
FLY_FORWARD
LAND_OR_HOLD
```

První verze může skončit ve stavu `HOLD` po první detekci překážky. Otočení a pokračování je druhá iterace.

Parametry:

| Parametr | Default | Účel |
| --- | ---: | --- |
| `target_altitude_m` | `1.0` | výška takeoffu |
| `forward_speed_mps` | `0.5` | pomalý indoor let |
| `stop_distance_m` | `0.8` | práh překážky |
| `turn_yaw_rate_radps` | `0.35` | pomalé otočení |
| `turn_duration_s` | `4.5` | přibližně 90 stupňů |
| `cmd_vel_topic` | `/ap/cmd_vel` | command velocity |
| `scan_topic` | `/openipc_cinewhoop/scan/front` | přední lidar |

Bezpečnostní chování:

- pokud nejsou dostupné ArduPilot služby, node nearmuje
- pokud nejsou platná lidar data, node neletí dopředu
- při překážce publikuje nulovou rychlost
- při ztrátě lidaru během letu publikuje nulovou rychlost
- rychlost drží na 0.5 m/s nebo nižší

## `trajectory_publisher.py`

Účel:

- vzít odometrii nebo pose
- publikovat `nav_msgs/msg/Path` pro RViz2

Vstup:

```text
/openipc_cinewhoop/odom
```

nebo:

```text
/ap/pose/filtered
```

Výstup:

```text
/openipc_cinewhoop/path
```

Parametry:

| Parametr | Default | Účel |
| --- | --- | --- |
| `pose_topic` | `/ap/pose/filtered` | zdroj pozice |
| `path_topic` | `/openipc_cinewhoop/path` | výstup do RViz |
| `max_points` | `2000` | omezení velikosti path |

## Minimální testy nodů

Unit testy:

- validní LaserScan vrátí správné minimum
- `nan`/`inf` se ignorují
- prázdný scan vrátí `None`
- obstacle threshold přepne stav autonomie do stop

Smoke testy v běžícím ROS:

```bash
ros2 run openipc_cinewhoop_demo obstacle_monitor
ros2 topic pub /openipc_cinewhoop/scan/front sensor_msgs/msg/LaserScan '{...}'
```

Integrační testy:

- spustit Gazebo svět
- ověřit `/openipc_cinewhoop/scan/front`
- spustit `obstacle_monitor.py`
- ručně nebo simulačně přiblížit překážku
- spustit `simple_indoor_autonomy.py` až po ověření ArduPilot služeb

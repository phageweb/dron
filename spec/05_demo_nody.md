# Demo nody a autonomie

## `obstacle_monitor.py`

Účel:

- praktická ukázka ROS 2 subscriberu
- práce se zprávou `sensor_msgs/msg/LaserScan`
- čitelný výpis vzdálenosti nejbližší překážky před dronem

Vstupy:

```text
/openipc_cinewhoop/scan/front   sensor_msgs/msg/LaserScan
/openipc_cinewhoop/range/down   sensor_msgs/msg/Range
/ap/pose/filtered               geometry_msgs/msg/PoseStamped
```

Chování:

- subscribuje na přední lidar
- z `ranges` odstraní `nan`, `inf` a hodnoty mimo `range_min`/`range_max`
- bere jen výseč kolem směru vpřed; LD06 snímá celých 360 stupňů, takže bez ní
  by se hlásila i stěna za dronem
- odečte náklon. LD06 je pevně na rámu, takže se sklopeným nosem míří přední
  paprsky do podlahy a podlaha vrátí vzdálenost jako každá jiná stěna. Návraty
  se promítnou do gravitačně srovnaného rámu podle `roll`/`pitch` z pózy a ty,
  které vyjdou jako zem, se zahodí
- výšku nad podlahou bere z dolního dálkoměru. Bez známé výšky se nezahazuje
  nic: neznámá výška nesmí začít mazat skutečné překážky
- spočítá minimum ze zbytku
- pravidelně loguje nejbližší překážku v metrech
- pokud není platné měření, loguje varování s omezenou frekvencí
- ticho lidaru hlásí sám, místo aby jen přestal psát

Stejný odečet země má i `simple_indoor_autonomy.py`. Musí ho mít oba: monitor
bez něj hlásí podlahu jako nejbližší překážku ve chvíli, kdy ji autonomie
správně ignoruje, a ty dva si pak za letu odporují.

Parametry:

| Parametr | Default | Účel |
| --- | ---: | --- |
| `scan_topic` | `/openipc_cinewhoop/scan/front` | topic předního lidaru |
| `warn_distance_m` | `0.8` | hranice blízké překážky |
| `log_period_s` | `0.5` | omezení log spamu |
| `scan_timeout_s` | `1.0` | po jaké době ticha se lidar hlásí jako mrtvý |
| `forward_sector_deg` | `60.0` | šířka výseče, která se počítá jako „vpřed“ |
| `range_topic` | `/openipc_cinewhoop/range/down` | výška nad podlahou pro odečet země |
| `pose_topic` | `/ap/pose/filtered` | náklon dronu pro odečet země |
| `ground_margin_m` | `0.25` | pod touto výškou je návrat zem, ne překážka |

Příklad spuštění:

```bash
ros2 run openipc_cinewhoop_demo obstacle_monitor --ros-args \
  -p scan_topic:=/openipc_cinewhoop/scan/front \
  -p warn_distance_m:=0.8
```

## `pose_tf_broadcaster.py`

Účel:

- zakořenit TF strom ve světě: `map` -> `base_link`
- bez něj `robot_state_publisher` ví, kde je lidar vůči dronu, a nikdo neví, kde
  je dron - takže mapu ani nic jiného ve světovém rámci není kam umístit

Vstup: `/ap/pose/filtered`. Výstup: `/tf`.

`header.frame_id` té zprávy říká `base_link` a je to prostě špatně: AP_DDS ji
plní z `get_relative_position_NED_home` převedeného do ENU, takže obsah je
poloha base_linku vůči home. Póza říkající, kde base_link je, nemůže být v
base_linku - byla by věčně nulová. Štítek se proto vědomě ignoruje.

REP 105 chce `map` -> `odom` -> `base_link`. Odhad je tady jeden a není čím ho
korigovat, takže by to byla jedna transformace napsaná dvakrát. Cena se ale
vyplatí pojmenovat: při resetu EKF `base_link` skočí, kde by oddělený `odom`
skok pohltil do `map` -> `odom`. Nic na té hladkosti dnes nestojí.

Když póza přestane chodit, nevysílá se nic. Mezera v TF znamená, že se
spotřebitel odmítne transformovat, což je správná odpověď na neznámou polohu;
stará transformace by nakreslila mapu sebejistě špatně.

Ověření: `scripts/check_map_frame.sh` porovná `map` -> `base_link` proti
ground truth z Gazeba v poloze i v yaw.

## `occupancy_mapper.py`

Účel:

- z naletěných scanů udělat 2D occupancy grid, aby po okruhu něco zůstalo
- ukázka `nav_msgs/msg/OccupancyGrid` a ray castingu

Vstupy:

```text
/openipc_cinewhoop/scan/front
/ap/pose/filtered
/openipc_cinewhoop/range/down
```

Výstup:

```text
/openipc_cinewhoop/map
```

Není to SLAM. Pozice je z EKF a nic ji tady nekoriguje, takže mapa je přesně tak
dobrá jako ta pozice: v SITL velmi dobrá, na hardwaru uvnitř budovy je to právě
ta otevřená otázka, protože ArduPilot bez GPS drží polohu jen tím, co udrží
optical flow s rangefinderem.

Mapa je vodorovný řez. Buňka říká "něco se sem vrátilo, zhruba ve výšce, ve
které byl lidar", ne že je sloupec zablokovaný od podlahy ke stropu.

Na rozdíl od zbylých dvou nodů se při výpadku vstupů nechová měkčeji, ale
tvrději: když je póza stará nebo je vypnuté odmítání podlahy, scan se zahodí
celý. Ostatním dvěma hrozí zbytečné zastavení, téhle stěna nakreslená tam, kde
dron nikdy nebyl - a ta v mapě zůstane i po tom, co se vstup vzpamatuje.

Parametry:

| Parametr | Default | Účel |
| --- | ---: | --- |
| `resolution_m` | `0.10` | velikost buňky, zhruba přesnost LD06 |
| `map_width_m` / `map_height_m` | `20.0` | pevná velikost mřížky, nezvětšuje se |
| `ground_margin_m` | `0.25` | stejné odmítání podlahy jako u zbylých nodů |
| `compensation_timeout_s` | `0.5` | stáří pózy a výšky, za kterým se přestává mapovat |
| `lidar_ahead_of_base_m` | `0.046` | odkud se paprsky vrhají; hlídá `check_model_consistency.py` |
| `lidar_above_base_m` | `0.050` | totéž ve svislé ose |

Ověření: `scripts/check_room_mapping.sh` proletí okruh s mapperem a změří
výsledek proti stěnám přečteným ze souboru světa.

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

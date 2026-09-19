# Specifikace projektu OpenIPC Cinewhoop

## Důležitá priorita projektu

Preferované nástroje a jazyky:

- NixOS jako cílový vývojový systém
- `flake.nix` a `nix develop` jako primární způsob reprodukovatelného prostředí
- Python pro ROS 2 demo nody, integraci, rychlé prototypování a testy
- Rust pro nové samostatné nástroje, adaptéry a pomocné služby tam, kde dává smysl typová bezpečnost a robustní binárka
- C++ jen tam, kde je to přirozené pro ROS/Gazebo pluginy nebo upstream knihovny

Testovací pravidlo:

- kde je to možné, píšeme testy dopředu nebo současně s implementací
- unit testy pro čistou logiku
- integrační testy pro ROS 2 topics, services, launch soubory a bridge
- E2E testy pro celé scénáře jako Gazebo start, sensor topics, RViz/TF smoke test a autonomní demo
- každá oprava chyby má mít ideálně reprodukční test nebo alespoň zapsaný ověřovací příkaz ve `workflow/`
- pokud lze test spolehlivě automatizovat bez hardwaru nebo ruční GUI interakce, má být přidán do CI/CD pipeline

Tato složka je rozdělená na dvě praktické větve:

1. Obecné učení ROS 2 na NixOSu.
2. Reálná stavba 3" OpenIPC cinewhoop dronu.

Simulace je most mezi oběma větvemi: nejdřív se bezpečně naučí ROS 2, Gazebo, RViz2 a ArduPilot SITL, potom se stejné ROS rozhraní použije jako základ pro skutečný dron.

## Větev A: ROS 2 na NixOSu

Začni zde, pokud chceš nejdřív pochopit nástroje a workflow bez rizika rozbitého hardwaru:

- [ROS 2 na NixOSu - přehled](./ros2_nixos/README.md)
- [ROS 2 na NixOSu - plán kroků](./ros2_nixos/01_plan_kroku.md)

Tato větev řeší:

- `flake.nix` a `nix develop`
- ROS 2 workspace
- nodes, topics, publishers, subscribers
- ROS messages
- TF strom
- Gazebo a `ros_gz_bridge`
- RViz2
- ArduPilot SITL a DDS integraci
- Python demo nody

## Větev B: Reálná stavba dronu

Začni zde, pokud řešíš fyzické komponenty, zapojení a postup bezpečného oživování:

- [Reálná stavba dronu - přehled](./realna_stavba_dronu/README.md)
- [Reálná stavba dronu - plán stavby](./realna_stavba_dronu/01_plan_stavby.md)
- [Rozhraní simulace vs. reálný dron](./realna_stavba_dronu/02_rozhrani_sim_real.md)
- [Alternativy a zkušenosti uživatelů](./realna_stavba_dronu/07_alternativy_a_zkusenosti.md)

Tato větev řeší:

- rám, motory, vrtule, baterii
- MicoAir H743 V2 45A AIO
- ArduPilot na reálném flight controlleru
- ExpressLRS
- OpenIPC / RunCam WiFiLink 2
- optical flow a rangefinder
- companion computer / ROS 2 počítač
- bench testy bez vrtulí
- první bezpečné indoor testy

## Větev C: Roj v simulaci

Začni zde, pokud řešíš víc než jeden stroj současně:

- [Zmapovat prostor třemi drony - zadání](./roj/README.md)
- [Vrstva jednoho dronu](./roj/02_vrstva_drona.md) a [vrstva roje](./roj/03_vrstva_roje.md)
- [Plán a milníky M0-M5](./roj/07_plan_a_milniky.md)

Tato větev řeší:

- tři SITL instance, tři modely a jejich identitu
- kontrakt mezi jedním dronem a koordinátorem
- přidělení cílů, rozestup `d_safe` a bezpečnostní filtr
- složení jedné mapy ze tří strojů a měření pokrytí

Teorie, ze které vychází, je v rešerších [reserseRoju](../reserseRoju/README.md)
a [reserseDronu](../reserseDronu/README.md).

## Cílový dron

Primární simulační i reálný cíl je 3" OpenIPC cinewhoop:

- GEPRC CineLog30 V3 class 3" ducted quadcopter
- quad X, 4 motory, wheelbase přibližně 126 mm
- cílová simulační hmotnost 240 g
- 4S LiHV 750 mAh
- přední OpenIPC/IP kamera
- IMU, barometr, optical flow, dolní rangefinder/lidar
- přední obstacle lidar/range sensor pro ROS 2 demo
- ArduPilot SITL jako autopilot, ROS 2 nody jako companion computer

## Simulační dokumenty

Tyto dokumenty popisují konkrétní simulovaný digitální prototyp:

- [Stack a rozsah simulace](./00_stack_a_rozsah.md)
- [Fyzikální a senzorický model dronu](./01_model_dronu.md)
- [Struktura projektu](./02_struktura_projektu.md)
- [Iterační implementační plán simulace](./03_iteracni_plan.md)
- [ROS 2 rozhraní, topics a TF](./04_ros_rozhrani.md)
- [Demo nody a autonomie](./05_demo_nody.md)
- [NixOS flake plán](./06_nixos_flake.md)
- [Ověřovací checklist](./07_overovaci_checklist.md)
- [Pozdější rozšíření](./08_rozsireni.md)
- [Nástroje, GitHub odkazy a údržba](./09_nastroje_komunita.md)
- [**Implementační specifikace**](./10_implementation_spec.md) - co software
  doopravdy dělá, do posledního pravidla a čísla. Na rozdíl od dokumentů výš,
  které jsou návrh, je tenhle odvozený z postaveného a naměřeného, a je psaný
  tak, aby se podle něj dalo chování postavit znovu v jiném jazyce, aniž by se
  člověk podíval na stávající kód. Kde se rozchází s 04 nebo 05, platí on.

## Externí zdroje použité pro návrh

- ROS 2 Jazzy `ros_gz`: https://docs.ros.org/en/jazzy/p/ros_gz/
- Gazebo Harmonic ROS 2 integrace: https://gazebosim.org/docs/harmonic/ros2_integration/
- ROS 2/Gazebo kompatibilní kombinace: https://gazebosim.org/docs/jetty/ros_installation/
- ArduPilot SITL s moderním Gazebo: https://ardupilot.org/dev/docs/sitl-with-gazebo.html
- ArduPilot DDS / ROS 2 rozhraní: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/README.md
- ArduPilot JSON SITL backend: https://ardupilot.org/dev/docs/sitl-with-JSON.html

## Rozhodnutí pro první implementaci

První stabilní kombinace:

- ROS 2 Jazzy
- Gazebo Harmonic / `gz-sim8`
- `ros_gz` bridge pro ROS 2 <-> Gazebo topics
- ArduPilot SITL pro ArduCopter
- ArduPilot Gazebo plugin přes JSON SITL backend
- ArduPilot DDS přes Micro XRCE-DDS Agent pro ROS 2 služby a telemetry topics
- Python ROS 2 nody v balíčku `openipc_cinewhoop_demo`

Iris se smí použít jen jako diagnostický smoke test ArduPilot SITL + Gazebo. Výsledný model musí být vlastní `openipc_cinewhoop`.

Výběr nástrojů je kontrolovaný podle toho, jestli jsou upstream projekty aktivní, používané a mají rozumnou komunitní nebo komerční podporu. Detailní tabulka je v [nástrojích a údržbě](./09_nastroje_komunita.md).

## Doporučený postup čtení

1. Projít [ROS 2 na NixOSu - plán kroků](./ros2_nixos/01_plan_kroku.md).
2. Postavit obecné ROS 2 demo bez dronu.
3. Pokračovat simulačními dokumenty v kořeni `spec/`.
4. Paralelně držet [plán reálné stavby](./realna_stavba_dronu/01_plan_stavby.md), ale hardware oživovat až po bench checklistech.
5. Rozhraní mezi simulací a realitou držet podle [rozhraní simulace vs. reálný dron](./realna_stavba_dronu/02_rozhrani_sim_real.md).

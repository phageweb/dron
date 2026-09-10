# Bench checklist bez vrtulí

Celé oživení až po tenhle bod se dělá **bez vrtulí**. Vrtule se nasazují teprve
po kroku 9, a jen pokud každý předchozí krok skončil zeleně.

Pravidlo pro celý dokument: **když krok neprojde, další se nezačíná.** Je to
stejné pravidlo jako v [iteračním plánu](../03_iteracni_plan.md) simulace a je
tady ze stejného důvodu: neodladěná chyba se v dalším kroku jen hůř hledá.

## Co mít na stole předem

- smoke stopper
- multimetr
- nabitá 4S LiHV baterie a nabíječka s balancerem
- USB kabel k FC
- notebook s `nix develop` a MAVProxy nebo pozemní stanicí
- imbusy na rám, pinzeta
- něco, čím se dron dá **fyzicky přidržet** při prvním roztočení motorů

## 1. Vizuální kontrola před prvním připojením

- [ ] žádný cínový můstek mezi pady, kontrola proti světlu
- [ ] motorové kabely nikde neodřené o karbon
- [ ] XT30 má správnou polaritu, ověřeno multimetrem, ne podle barvy
- [ ] mezi plusem a mínusem napájení není zkrat, měřeno multimetrem
- [ ] FC nesedí přímo na karbonu bez izolace
- [ ] anténa RX není skřípnutá pod rámem

Stop podmínka: jakýkoli odpor pod cca 10 ohmů mezi plusem a mínusem znamená
zkrat. Baterii nepřipojovat.

## 2. První připojení napájení přes smoke stopper

- [ ] baterie připojena **přes smoke stopper**, ne přímo
- [ ] nic se nezahřívá, do třiceti sekund se nic nerozehřeje na dotek
- [ ] LED na FC svítí očekávaně
- [ ] napětí na 5 V větvi je 5 V +/- 0.2 V
- [ ] napětí na 12 V větvi je 12 V +/- 0.5 V, pokud se použije pro video

Stop podmínka: cokoli teplého, jakýkoli zápach, jakýkoli pokles napětí na
smoke stopperu. Odpojit a hledat zkrat.

## 3. Firmware a komunikace přes USB

- [ ] správný ArduPilot target pro MicoAir H743 V2
- [ ] FC se hlásí na USB a je vidět v MAVProxy nebo GCS
- [ ] verze firmware odpovídá tomu, co je zapsané v [rozhodnutích](../../workflow/decisions.md)
- [ ] `FRAME_CLASS` a `FRAME_TYPE` nastavené na quad X
- [ ] parametry zálohované do souboru **před** jakoukoli změnou

## 4. Senzory na FC, pořád bez vrtulí

- [ ] akcelerometr zkalibrovaný ve všech šesti polohách
- [ ] gyro se v klidu neplazí, hodnoty jsou kolem nuly
- [ ] barometr čte reálný tlak a reaguje na zvednutí ze stolu
- [ ] IMU teplota vypadá rozumně, ne desítky stupňů nad okolím
- [ ] kompas: pro indoor variantu **vypnutý**, ne kalibrovaný a ignorovaný

Pozn.: [plán stavby](./01_plan_stavby.md) říká, že GPS ani kompas nejsou pro
indoor podmínkou letu, a je důležité je nenechat viset jako neúspěšný prearm.

## 5. RC link a failsafe

- [ ] ELRS RX spárovaný
- [ ] roll, pitch, throttle, yaw jdou správným směrem
- [ ] arm/disarm přepínač funguje
- [ ] přepínač letových režimů přepíná to, co má
- [ ] radio failsafe: **vypnutí vysílačky** vede na failsafe akci, ne na nic
- [ ] throttle failsafe nastavený

Stop podmínka: pokud failsafe nefunguje bez vrtulí, s vrtulemi je to nebezpečné.

## 6. Motory bez vrtulí

Dron musí být při tomhle kroku **fyzicky přidržený nebo připoutaný**.

- [ ] motor 1 v ArduPilot motor testu roztočí fyzicky ten motor, který je v
      quad X mapování motor 1
- [ ] motor 2 odpovídá
- [ ] motor 3 odpovídá
- [ ] motor 4 odpovídá
- [ ] směry rotace odpovídají zvolenému směru vrtulí
- [ ] žádný motor se při krátkém testu nepřehřívá
- [ ] žádný motor nedrhne ani nehrká

Simulace používá tohle mapování, viz [model dronu](../01_model_dronu.md):

| Motor | Poloha | Souřadnice vůči středu |
| --- | --- | --- |
| `motor_1` | front right | x = +0.04525, y = -0.04525 |
| `motor_2` | rear left | x = -0.04525, y = +0.04525 |
| `motor_3` | front left | x = +0.04525, y = +0.04525 |
| `motor_4` | rear right | x = -0.04525, y = -0.04525 |

Stop podmínka: špatné mapování motorů je nejčastější příčina okamžitého
převrácení po vzletu; v simulaci to bylo taky první podezření, když se model
převracel.

## 7. MTF-02P: optical flow a dolní rangefinder

- [ ] senzor napájený z 5 V, odběr kolem 40 mA
- [ ] UART nastavený na 115200, protokol MAVLink
- [ ] dolní vzdálenost odpovídá skutečné výšce nad stolem, ověřeno pravítkem na
      dvou různých výškách
- [ ] rangefinder čte i nad tmavou plochou, ne jen nad světlou
- [ ] optical flow dává nenulové hodnoty při ručním posunu dronu nad stolem
- [ ] hodnoty nevypadávají, když se roztočí motory bez vrtulí (vibrace, rušení)

Pozn.: podle vendora má laser MTF-02P vyzařovací úhel 2 stupně a mrtvou zónu
2 cm, dosah 6 m při 90% odrazivosti a 1000 luxech, ale jen 4 m při 70 000 luxech.
Uvnitř to stačí; venku na slunci ne.

## 8. Přední obstacle senzor

- [ ] senzor napájený správným napětím podle [tabulky komponent](./03_komponenty.md)
- [ ] měří vzdálenost ke stěně, ověřeno pravítkem na dvou vzdálenostech
- [ ] hodnoty jsou stabilní, nekmitají o desítky centimetrů
- [ ] senzor vidí i tmavou nebo lesklou překážku, nebo je zapsané, že nevidí
- [ ] časování je stabilní, žádné dlouhé mezery mezi vzorky

## 9. ROS 2 vrstva, pořád bez vrtulí

Tohle je bod, kde se potká reálný dron s tím, co je hotové v simulaci.

- [ ] `ros2 topic list` obsahuje `/ap/` topics z reálného FC
- [ ] `ros2 service list` obsahuje ArduPilot služby
- [ ] `/openipc_cinewhoop/range/down` publikuje `sensor_msgs/msg/Range`
- [ ] `/openipc_cinewhoop/scan/front` publikuje `sensor_msgs/msg/LaserScan`
- [ ] `/openipc_cinewhoop/imu` čte v klidu **+9.81** na ose z, ne -9.81
- [ ] frame_id každého senzoru existuje v TF stromu
- [ ] `obstacle_monitor` hlásí klesající vzdálenost, když se ke stěně přiblíží
- [ ] po odpojení senzoru node do jedné sekundy nahlásí ticho

Poslední tři body jsou přesně to, co v simulaci ověřují
`scripts/check_sensor_interface.sh` a `scripts/check_sensor_dropout.sh`. Na
hardwaru se dělají ručně, ale kritérium je stejné.

- [ ] `simple_indoor_autonomy` spuštěná **s odpojenými motory nebo bez arm**
      projde stavy až do `cruising` a při překážce pod prahem pošle nulu

## 10. Teprve teď vrtule

Až sem to všechno prošlo:

- [ ] vrtule nasazené ve správném směru podle kroku 6
- [ ] první let ručně, venku z dosahu lidí nebo v prostoru, kde je co zachytit
- [ ] ROS zpočátku **jen poslouchá**, nic neposílá
- [ ] až po stabilním ručním hoveru se pouští `simple_indoor_autonomy`
- [ ] RC převzetí řízení vyzkoušené **dřív**, než se pustí jakákoli autonomie

Pořadí letových testů je v [plánu stavby](./01_plan_stavby.md), fáze 10.

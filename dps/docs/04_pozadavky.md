# Vlastní deska — co od ní chceme, z jakých obvodů a kde je najít

Sepsáno **12. 10. 2026**. Navazuje na [rešerši](./01_reserse_otevrenych_projektu.md)
a [návrh](./02_navrh.md), ale s jednou změnou: **ESP32 most na desce není.**
Wi-Fi z ESP32 má na tenhle účel malý dosah, takže sken z LD06 jde dolů přes OSD
Walksnailu ([test](../../spec/realna_stavba_dronu/15_test_linky_skenu.md)) a záloha je
přikoupený sériový Bluetooth na volném UARTu.

Tenhle dokument popisuje **desku 2** (vlastní AIO). Od 17. 10. 2026 je to
**jediná deska**: samostatná deska 1 se nevyrobí a její schéma
je teď list `vtx.kicad_sch` v [aio](../aio/README.md).

Deska je **vlastní AIO místo MicoAir H743 V2**: H743 s ArduPilotem, čtyři ESC,
napájení pro všechno, co na stroji je. Pinout se přebírá z `MicoAir743v2`, aby
stačil upravený hwdef.

## 1. Co od ní chceme

### Tvrdé požadavky — bez nich deska na stroj nejde

| # | Požadavek | Hodnota | Proč / odkud |
| --- | --- | --- | --- |
| P1 | Firmware | ArduCopter s AP_DDS, EKF3 s doubly | celý projekt; [firmware](../../firmware/README.md) |
| P2 | MCU | STM32H743, 2 MB flash | jediné jádro, na kterém AP_DDS dnes běží s rezervou; hwdef `MicoAir743v2` |
| P3 | Vstup | 4S LiHV, **max 17,4 V**, rezerva na špičky ≥ 25 V | Tattu 750/550 mAh |
| P4 | ESC | 4 kanály, **≥ 10 A špičkově**, AM32, bidirectional DShot | A1204 5200KV, [rešerše motorů](../../spec/realna_stavba_dronu/12_reserse_motoru.md) |
| P5 | Rozměr | díry **26 × 26**, obrys **≤ 36 mm** | rám Pavo20 Pro, [Pavo20](../../spec/realna_stavba_dronu/10_pavo20.md) |
| P6 | Hmotnost | **≤ 10 g** osazená, bez kabelů | MicoAir váží 10 g — horší být nesmí |
| P7 | UARTy | **6 použitých + 1 volný**, viz tabulka níž | [rozvržení UARTů](../../spec/realna_stavba_dronu/14_postup_stavby_pavo20.md#rozvržení-uartů) |
| P8 | 5 V | **≥ 1,5 A** trvale | RX, GPS, MTF-02P, LD06 (300 mA rozběh, 180 mA provoz) |
| P9 | VTX | **10 V, ≥ 2 A** (dimenzováno na DJI O3/O4, 12–16 W), spínané z FC | Spotřeba Lite+ se nečeká: větev se navrhne na třídu O3/O4, pro kterou je rám i MicoAir (12 V/2 A pro O3/O4) dělaný. 16 W na 10 V je 1,6 A. Lite+ snese 3–12,6 V; 12V BEC je 0,6 V pod stropem |
| P10 | IMU | aspoň jedna, SPI, s DRDY | ArduPilot; MicoAir má BMI088 + BMI270 |
| P11 | Baro | I2C nebo SPI | AltHold, EKF |
| P12 | Logování | microSD | bez logu se neladí notch ani gainy |
| P13 | Měření baterie | napětí + proud do ADC | `BATT_MONITOR 4`, failsafe na napětí |
| P14 | USB | USB-C, DFU bootloader, tlačítko BOOT | flashování, MAVLink na stole |

### Měkké požadavky — proč dělat vlastní, a ne koupit

| # | Požadavek | Co tím získáme |
| --- | --- | --- |
| M1 | **Konektor ZH1.5-4P pro LD06** přímo na desce | odpadá bastlený kabel ZH1.5 → JST-SH |
| M2 | **LD06 TX rozvětvený** na dva UART RX | AP_Proximity na palubě a zároveň Lua skript pro OSD linku |
| M3 | **Vlastní 5V větev pro LD06**, nebo aspoň dost kapacity, aby rozběh nesrazil RX | dnes sdílí BEC s přijímačem |
| M4 | **Měření proudu VTX** (shunt + INA226 na I2C) | spotřeba Lite+ je v kusovníku „nezměřeno" |
| M5 | **Bez analogového OSD (AT7456E)** | Walksnail je digitální, ušetří čip, SPI1 a místo |
| M6 | JST-SH konektory místo pájecích pad tam, kde se často odpojuje (GPS, flow) | servis bez páječky |
| M7 | Pady pro **sériový Bluetooth modul** (5 V/3,3 V, GND, TX, RX) | záloha linky skenu, kanál A |
| M8 | Víceznačná ploška IMU | IMU jde vyměnit podle skladu bez nového layoutu |

### UARTy a co na nich visí

| UART (MicoAir) | Zařízení | Napájení | Pozn. |
| --- | --- | --- | --- |
| USART1 | volný / Bluetooth modul (M7) | 3,3 V nebo 5 V | MAVLink |
| USART2 | Walksnail Lite+ (MSP DisplayPort) | **10 V spínané** (P9) | konektor HD VTX: 6 pin SH |
| USART3 | WS-M181 GPS + kompas na I2C1 | 5 V | JST-SH 6 pin |
| UART4 | MTF-02P | 5 V | JST-SH 4 pin |
| UART5 | LD06, jen RX | 5 V | ZH1.5-4P (M1), PWM pin LD06 uzemnit nebo na GPIO |
| USART6 | XR1 Nano (CRSF) | 5 V | pady |
| UART7 | telemetrie ESC (AM32) | — | interní spoj na desce |
| UART8 | druhý RX z LD06 (M2), nebo volný | — | |

## 2. Bloky desky a kde vzít zapojení

Pro každý blok: co v něm je, z čeho se převezme, a co se musí ověřit, než se
kreslí. „Převzít" znamená zkopírovat list schématu i layout; „vzor" znamená
podívat se, jak to udělali, a nakreslit znovu.

### 2.1 Vstup baterie a měření

| | |
| --- | --- |
| Obsahuje | pady XT30 (vodiče), bulk kondenzátor 35 V (přibalený k MicoAiru je stejného druhu), shunt + INA186 pro proud, dělič pro napětí do ADC |
| Převzít | **OpenESC-20x20**: shunt 0,2 mΩ + INA186A3, **včetně RC filtru z Rev3.2** |
| Vzor | dělič a měřítko: `HAL_BATT_VOLT_SCALE 21.12`, `HAL_BATT_CURR_SCALE 40.2` v hwdefu MicoAiru |
| Pozor | OpenESC Rev3 **vyhodil vstupní TVS** — u 30V MOSFETů a 17,4 V nechránila. Nepřidávat ji zpátky bez důvodu. |

### 2.2 ESC × 4

| | |
| --- | --- |
| Obsahuje | MCU AT32F421G8U7, driver NSG2065Q, 6× MOSFET DOY180N03T (30 V), napájení driveru 10 V |
| Převzít | **OpenESC-20x20, `ESC.kicad_sch`** — beze změny, 4× instancovaný jako v OpenAIO |
| Vzor skladby | **OpenAIO** kořenové schéma: jak skládá 4 kanály + jádro na 25,5 mm |
| Firmware | AM32, target `OPENESC_20` — hotový |
| Pozor | 40 A/kanál je jejich tvrzení, nám stačí 10 A. Nezmenšovat v rev A, viz [návrh](./02_navrh.md#co-opravíme-proti-micoair-h743-v2). Teplo v ductu je otevřené. |

### 2.3 Napájení

| Větev | Obvod | Odkud |
| --- | --- | --- |
| 10 V pro drivery ESC | LMR54406 | OpenESC-20x20 (už v listu ESC) |
| 5 V, ≥ 1,5 A | **LMR51430** (36 V vstup, 3 A) | OpenFC-Lite-Mini, list `power` |
| 10 V VTX, spínané, 3 A | LMR51430, EN na GPIO MCU (PINIO) | OpenFC-Lite-Mini U3, dělič 100k/6,49k, signál `10V_ENABLE` — ověřeno ve schématu |
| 3,3 V MCU | LDO z 5 V (TLV76733 nebo podobný) | OpenESC / OpenFC-Lite-Mini |
| 3,3 V IMU, oddělené | samostatné nízkošumové LDO | Kestrel H7 (vzor) |
| Měření VTX (M4) | INA226 + shunt na 10V větvi | datasheet TI INA226, I2C |

Datasheety: TI [LMR51430](https://www.ti.com/product/LMR51430),
[INA186](https://www.ti.com/product/INA186), [INA226](https://www.ti.com/product/INA226)
— každý má v sekci *Layout* doporučené rozložení, to se kreslí podle něj.

### 2.4 Jádro STM32H743

| | |
| --- | --- |
| Obsahuje | H743 (TFBGA-100 nebo LQFP-100), krystal 8 MHz, VCAP kondenzátory, blokování, BOOT0 tlačítko, SWD pady, reset, RGB LED, pad pro bzučák |
| Pinout | **`external/ardupilot/libraries/AP_HAL_ChibiOS/hwdef/MicoAir743v2/hwdef.dat`** — UARTy, SPI, I2C, SDMMC, PWM na TIM1, ADC na PC0/PC1 |
| Vzor zapojení | **Kestrel H7** (KiCad 10, H743VIT6, nevyrobený), **Jun-copter FlightComputer** |
| Referenční dokumenty ST | **AN4938** — Getting started with STM32H74x/H75x hardware development (napájení, VCAP, BOOT0, krystal); **AN2867** — návrh oscilátoru; datasheet STM32H743 — pinout pouzdra |
| Vzor modulu | CBUnmanned H743 Stamp — jak se vejde H743 + IMU + baro + SD na 23 × 25 mm (footprinty v EasyEDA) |
| Pozor | Pouzdro rozhoduje o ploše: LQFP-100 je 16 × 16 mm, na 36 mm se 4 ESC skoro nevejde. TFBGA-100 osadí JLC. |

### 2.5 USB

| | |
| --- | --- |
| Obsahuje | USB-C (jen USB 2.0), CC rezistory 5,1 kΩ, ESD ochrana (USBLC6-2SC6 nebo podobná), VBUS do 5V větve přes diodu |
| Vzor | OpenFC-Lite-Mini, Kestrel H7 |
| Pinout | PA11/PA12 OTG_FS |

### 2.6 Senzory

| Senzor | Volba | Sběrnice (podle MicoAiru) | Kde vzít |
| --- | --- | --- | --- |
| IMU 1 | BMI270 nebo ICM-42688-P | SPI3, CS PA15, DRDY PB7 | **víceznačná LGA-14 ploška z OpenFC-Lite-Mini** (M8) |
| IMU 2 (volitelně) | BMI088 | SPI2 | MicoAir ji má; Kestrel H7 ji má kvůli ArduPilotu |
| Baro | SPL06 / DPS310 / BMP280 | I2C, 0x77 | co bude na LCSC; ArduPilot umí všechny |
| Kompas | v GPS M181 | I2C1 externě | nic na desce |

Seznam senzorů, které ArduPilot umí: `libraries/AP_InertialSensor/` a
`libraries/AP_Baro/` v `external/ardupilot`. Orientaci IMU zapsat do hwdefu.

### 2.7 Logování

| | |
| --- | --- |
| Obsahuje | slot microSD, 4bit SDMMC1 (PC8–PC12, PD2), pull-upy |
| Vzor | Kestrel H7; pinout z hwdefu MicoAiru |
| Alternativa | SPI flash (menší, lehčí) — ArduPilot umí i `HAL_LOGGING_DATAFLASH`, ale vejde se méně |

### 2.8 Konektory a pady

| Co | Konektor | Pozn. |
| --- | --- | --- |
| HD VTX (Lite+, DJI O3/O4) | JST-SH 1,0 6 pin, pinout DJI jako MicoAir a OpenFC-Lite-Mini | 1 +10 V spínané, 2 GND, 3 TX2, 4 RX2, 5 GND, 6 RX přijímače |
| LD06 | **ZH1.5-4P** (M1) | 5 V, GND, TX → RX5 a RX8 (M2), PWM |
| GPS + kompas | JST-SH 6 pin | 5 V, GND, TX3, RX3, SDA, SCL |
| MTF-02P | JST-SH 4 pin | 5 V, GND, TX4, RX4 |
| XR1 Nano | pady | 5 V, GND, TX6, RX6 |
| Bluetooth (M7) | pady | 5 V, GND, TX1, RX1 |
| Motory | pady M1–M4 | |
| Baterie | pady + kondenzátor | |

## 3. Kde co najít — souhrn

| Potřebuju | Zdroj | Formát |
| --- | --- | --- |
| ESC kanál, proudové čidlo | [OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20) — `ESC.kicad_sch`, `AGENTS.md` s LCSC čísly a revizemi | KiCad 10 |
| Napájení 5 V a spínané VTX, IMU ploška | [OpenFC-Lite-Mini](https://github.com/OpenDrone-hw/OpenFC-Lite-Mini) — list `power` | KiCad 10 |
| Jak skládat listy do AIO | [OpenAIO](https://github.com/OpenDrone-hw/OpenAIO) — kořenové schéma | KiCad 10 |
| Symboly a footprinty OpenDrone | [OpenDrone-hw/KiCad-Library](https://github.com/OpenDrone-hw/KiCad-Library) — `PARTS-USED.md` | KiCad 10 |
| Okolí H743 | [Kestrel H7](https://github.com/HeyPCB/kestrel-fc), [Jun-copter](https://github.com/Jun-copter/FlightComputer) | KiCad |
| Pinout pro ArduPilot | `hwdef/MicoAir743v2/hwdef.dat` lokálně | text |
| Jak napsat hwdef | [ArduPilot: Porting to a new board](https://ardupilot.org/dev/docs/porting.html) | web |
| Hardware H743 | ST AN4938, AN2867, datasheet a reference manual RM0433 | PDF, st.com |
| Buck, proud, USB ESD | datasheety TI LMR51430, INA186, INA226; ST USBLC6-2 | PDF |
| Díly a sklad | [JLCPCB parts](https://jlcpcb.com/parts) / [LCSC](https://www.lcsc.com) — kvůli osazení u JLC | web |
| Pravidla výroby | DRU soubory v repozitářích OpenDrone (OpenESC 6 vrstev; OpenAIO 8 vrstev HDI 1+6+1, 1 oz, 1,0 mm) | KiCad |

Odkazy na všechno z rešerše jsou v [Zdrojích](./03_zdroje.md).

## 4. Co je potřeba rozhodnout před kreslením

| Otázka | Možnosti | Na čem to závisí |
| --- | --- | --- |
| Pouzdro H743 | TFBGA-100 / LQFP-100 | **doporučeno TFBGA-100** (17. 10.): na OpenAIO (35,4 mm) jsou MOSFETy po okrajích horní strany, budiče ESC a přijímač dole a uprostřed horní strany je na jádro asi 20 × 20 mm. RP2354A v QFN-60 tam zabírá 7 × 7, TFBGA-100 má 8 × 8 a vejde se na jeho místo. LQFP-100 má 16 × 16 bez blokovacích kondenzátorů a zabral by celé jádro |
| Jedna nebo dvě IMU | BMI270 sama / + BMI088 | místo a hmotnost; ArduPilot umí s jednou |
| microSD nebo flash | SD / SPI flash | otevřené. Na OpenAIO by slot microSD (asi 12 × 12 mm) místo neměl, ale MicoAir H743 V2 AIO má na 36 × 36 mm 4× ESC 45 A, H743 v TFBGA-100 (STM32H743VIH6), dvě IMU **i microSD** [manuál robofusion] — jde to tedy, za cenu hustšího layoutu |
| ~~VTX 9 nebo 10 V~~ | **10 V** (17. 10.) | převzít dělič z OpenFC-Lite-Mini beze změny; dimenzuje se na O3/O4, ne na změřený Lite+ |
| LD06 do dvou UARTů (M2) | ano / ne | jestli OSD linka čte LD06 sama, nebo z AP_Proximity |
| Licence | CERN-OHL-S-2.0 | převzetím listu OpenDrone je deska povinně otevřená |

## 5. Co je ověřené a co ne

| | |
| --- | --- |
| **Ověřeno** | Pinout MicoAir z hwdefu v `external/ardupilot` `8b9ea70`. Rozvržení UARTů a napájení podle [postupu stavby](../../spec/realna_stavba_dronu/14_postup_stavby_pavo20.md) a [kusovníku](../../spec/realna_stavba_dronu/11_kusovnik_pavo20.md). |
| **Ověřeno v souborech** (17. 10.) | Projekty OpenDrone otevřené v KiCadu 10 a prověřené přes ERC/DRC (`./check.sh`, výsledek v [návrhu](./02_navrh.md#erc-a-drc-převzatých-projektů)). Díly sedí na `AGENTS.md`: list `ESC.kicad_sch` má AT32F421G8U7, NSG2065Q a DOY180N03T, `power.kicad_sch` 2× LMR51430 (5 V stálý, 10 V spínaný přes `10V_ENABLE`). |
| **Odhad** | P6 ≤ 10 g, P8 ≥ 1,5 A. P9 je dimenzované na DJI O3 (12–16 W, viz [Pavo20](../../spec/realna_stavba_dronu/10_pavo20.md)), ne na změřený Lite+. |
| **Neověřeno** | Pinout HD VTX konektoru MicoAiru a Lite+, pinout konektoru LD06 — vzít z manuálů v `spec/realna_stavba_dronu/manualy` a ověřit multimetrem. |

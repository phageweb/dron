# Rešerše otevřených projektů

Ověřováno **7. 10. 2026** z README a `AGENTS.md` jednotlivých repozitářů a
proti `external/ardupilot` ve stavu `8b9ea70` (2026-09-09). Nic z toho nebylo
staženo do KiCadu a otevřeno — co projekty o sobě píšou, je tu jejich tvrzení,
ne náš nález.

## Co hledáme

Deska musí sedět na tenhle stroj, ne na obecný dron:

| Požadavek | Proč | Odkud |
| --- | --- | --- |
| **ArduPilot**, ne jen Betaflight | celý projekt stojí na ArduCopteru a AP_DDS | [firmware](../../firmware/README.md) |
| MCU s **2 MB flash** a FPU s doubly | AP_DDS a EKF3 s `HAL_WITH_EKF_DOUBLE`; dnes STM32H743 | `hwdef/MicoAir743v2` |
| **4S LiHV**, 17,4 V | baterie Tattu 750 a 550 mAh | [Nakoupeno](../../spec/realna_stavba_dronu/13_nakoupeno.md) |
| ESC na **~10 A špičkově** na motor | A1204 5200KV | [Rešerše motorů](../../spec/realna_stavba_dronu/12_reserse_motoru.md) |
| Rozteč **26 × 26** (rám), obrys **≤ 36 mm** | Pavo20 Pro; MicoAir 36 × 36 s 25,5 × 25,5 se tam vejde přes silentbloky | [Pavo20](../../spec/realna_stavba_dronu/10_pavo20.md) |
| **4 UARTy** volné | RX, MTF-02P, LD06, MSP DisplayPort k Walksnailu | [Komponenty](../../spec/realna_stavba_dronu/03_komponenty.md) |
| Cesta pro **sken z LD06 dolů** | AP_DDS dá jen 8 sektorů, Walksnail nemá datový kanál | [Kudy do ROS](../../spec/realna_stavba_dronu/09_kudy_do_ros.md) |
| Napájení VTX **pod 12,6 V** | Walksnail Lite+ snese 3–12,6 V | [Kusovník](../../spec/realna_stavba_dronu/11_kusovnik_pavo20.md) |

## Přehled

| Projekt | Co to je | MCU | KiCad | Vyrobeno / létalo | ArduPilot | Licence |
| --- | --- | --- | :-: | --- | :-: | --- |
| [OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20) | 4in1 AM32 ESC 20 × 20, 2–6S, 40 A/kanál | 4× AT32F421 | **10** | **Rev2 validovaná, Rev3.3 v produkci**, OSHWA BE000028 | — (DShot) | CERN-OHL-S-2.0 |
| [OpenESC-30x30](https://github.com/OpenDrone-hw/OpenESC-30x30) | totéž 30,5 × 30,5, 2–8S | 4× AT32F421 | ano | v prodeji | — | CERN-OHL-S-2.0 |
| [OpenRX-Lite](https://github.com/OpenDrone-hw/OpenRX-Lite) | ELRS 2,4 GHz RX, 10 × 11,5 mm | ESP32-C3 + SX1281 | ano | v prodeji, OSHWA BE000030 | — (CRSF) | CERN-OHL-S-2.0 |
| [OpenFC-Lite-Mini](https://github.com/OpenDrone-hw/OpenFC-Lite-Mini) | FC 20 × 20, 3–6S | RP2354A | **10** | **Rev2 létala**, Rev3.3 v produkci | **ne** | CERN-OHL-S-2.0 |
| [OpenAIO](https://github.com/OpenDrone-hw/OpenAIO) | AIO 25,5 × 25,5: ESC + RX + modul FC | RP2350 (OpenFC-Core) | **10** | **nevyrobeno** | **ne** | CERN-OHL-S-2.0 |
| [OpenAIO-Whoop](https://github.com/OpenDrone-hw/OpenAIO-Whoop) | 1S whoop AIO s analog VTX | RP2354A | — | **nic nenakresleno** | ne | CERN-OHL-S-2.0 |
| [Kestrel H7](https://github.com/HeyPCB/kestrel-fc) | FC 40 × 40, 6 vrstev | STM32H743VIT6 | **10** | **nevyrobeno, nelétalo** | BMI088 kvůli AP, hwdef ne | CERN-OHL-S-2 |
| [Jun-copter FlightComputer](https://github.com/Jun-copter/FlightComputer) | FC s integrovaným ELRS | STM32H743VIT6 | ano | rozkreslené schéma | cílí na vlastní hwdef | ? |
| [SAL-FC](https://github.com/salehali22/SAL-FC) | FC 40,5 × 40,5, 6 vrstev | STM32H743VIT6 | ano | ? | hwdef v repu | **HW soubory soukromé** |
| [CBUnmanned H743 Stamp](https://ardupilot.org/copter/docs/common-StampH743.html) | modul FC k připájení na vlastní nosnou desku | STM32H743 | — (EasyEDA) | **komerční, v prodeji** | **ano, v masteru** | uzavřený modul |
| [Bitcraze Crazyflie](https://github.com/bitcraze/crazyflie-electronics) | nano kvadrokoptéra | STM32F405 | ano | ano, ale archivované | ne | — |
| [DroneBridge for ESP32](https://github.com/DroneBridge/ESP32) | firmware: UART ↔ Wi-Fi/ESP-NOW most | ESP32-C3/C5/C6 | — | používá se | MAVLink / transparent | Apache-2.0 |

## Co z toho plyne

### 1. Vyrobené a létající je jen ekosystém OpenDrone — a jeho FC na ArduPilotu nepoběží

OpenDrone (Incutec, Belgie) je jediná rodina, kde se v KiCadu kreslí, vyrábí,
prodává **a** dokumentuje revize se slovem „Flown". Všechno je v KiCadu 10 se
sdílenou knihovnou, LCSC čísly u každého dílu, DRU pravidly a skripty na
`kicad-cli` ERC/DRC. Na převzetí je to nejlepší materiál, jaký existuje.

Háček je v jádru: všechny jejich FC jsou **RP2354 s Betaflightem**. ArduPilot
na RP2350 má [PR #32995](https://github.com/ArduPilot/ardupilot/pull/32995),
k 7. 10. 2026 **otevřený se změnami vyžádanými od tridge a peterbarkera**. Létá
na desce RPI_UAVFC, ale sám uvádí, že double je **asi 10× pomalejší** (RP2350
nemá double FPU) a že DShot jde jen 600. Pro EKF3 s doubly a AP_DDS to dnes
není základ, na kterém se dá stavět. Za rok možná.

### 2. Ověřené části OpenDrone se dají převzít po listech

To, co z OpenDrone na ArduPilotu nezáleží, se převzít dá, a OpenAIO ukazuje jak:
jeho kořenové schéma skládá **listy** z jiných desek — `esc_channel` ×4
z OpenESC-20x20, `rx_esp32c3_sx1281` z OpenRX-Lite, napájení a plošky
z OpenFC-Lite-Mini. My můžeme udělat totéž, jen s jiným jádrem.

**OpenESC-20x20, jeden kanál** (`ESC.kicad_sch`, instancovaný 4×):

| Funkce | Díl | Pozn. |
| --- | --- | --- |
| MCU | AT32F421G8U7, QFN-28 | AM32 target `OPENESC_20` |
| Driver | NSG2065Q, QFN-24 | UVLO 4,5 V, napájení 5–20 V |
| MOSFETy | 6× DOY180N03T, PowerDI3333-8 | **30 V VDSS** — strop je 6S |
| Proud | INA186A3 100 V/V na 0,2 mΩ, celá deska | 20 mV/A, 165 A plný rozsah |
| Napájení | LMR54406 → 10 V → TLV76733 → 3,3 V | |
| Deska | 6 vrstev, 1,6 mm, 2 oz vnější | 31,2 × 33,0 mm |

Revize jsou poučné samy o sobě: Rev3 **vyhodila vstupní TVS**, protože u napětí
tak blízko VDSS MOSFETů nechrání ničím; Rev3.2 přidala RC filtr na vstup
proudového zesilovače proti souhlasnému rušení z high-side. Obojí jsou chyby,
které bychom jinak udělali taky.

**OpenRX-Lite** je hotový ESP32-C3 + SX1281 v 10 × 11,5 mm se dvěma keramickými
anténami: jednou pro ELRS, druhou pro Wi-Fi ESP32. Pro nás je cenný hlavně
**layout ESP32-C3 s keramickou anténou a keepoutem**. ESP32 most pro LD06 je ale
od 12. 10. 2026 vyřazený (malý dosah Wi-Fi), takže z OpenRX-Lite nepřebíráme nic.

### 3. Otevřené H743 desky v KiCadu existují, ale žádná nelétala

Kestrel H7, Jun-copter i SAL-FC mají STM32H743VIT6 v LQFP-100 a ani jedna
nemá doloženou výrobu a let; SAL-FC navíc schéma zavřel. Jako vzor zapojení
H743 (napájení, krystal, USB, SDMMC, oddělené LDO pro IMU) jsou použitelné,
jako šablona k převzetí ne. LQFP-100 má navíc 16 × 16 mm s vývody, což na
desce, kde mají být i čtyři ESC kanály, zabere skoro třetinu plochy.

Pro ArduPilot je přitom nejcennější zdroj **hwdef v našem vlastním
`external/ardupilot`**: `MicoAir743v2/hwdef.dat` je kompletní pinout desky,
která už u nás leží — 8 UARTů, BMI088 na SPI2, BMI270 na SPI3, AT7456E na SPI1,
SDMMC1, SPL06 na I2C, PWM 1–4 na TIM1 s BIDIR. Vlastní H743 deska, která tenhle
pinout převezme, potřebuje jen upravený hwdef, ne nový port.

### 4. Stamp je zkratka k ArduPilotu, ale ne na tenhle rám

CBUnmanned H743 Stamp je modul se vším kolem H743 (IMU, baro, SD) k připájení na
vlastní nosnou desku, s hwdefem v masteru (`CBU-H7-Stamp`, `CBU-H7-LC-Stamp`).
Varianta Low Cost: 23 × 25 mm, 3 g, STM32H743VIH6, jedna ICM-42670, BMP280,
8 UARTů, £90. Přesně ten vzor, který OpenAIO dělá s OpenFC-Core, jen pro
ArduPilot.

Na 36mm desku se ale 23 × 25 mm modul vedle čtyř ESC kanálů nevejde — OpenAIO
na to má 15 × 15 mm jádro. Stamp dává smysl pro dvoudeskový stack (FC + ESC),
který Pavo20 s jedinou roztečí 26 × 26 neumí, nebo pro jiný, větší drak.
Footprinty jsou v EasyEDA, ne v KiCadu.

## Co je ověřené a co ne

| | |
| --- | --- |
| **Ověřeno** | Specifikace a revize OpenDrone z jejich `AGENTS.md` a README k 7. 10. 2026. Stav PR #32995 tamtéž. Pinouty `MicoAir743v2` a `CBU-H7-LC-Stamp` z `external/ardupilot` `8b9ea70`. XR1 Nano je LR1121, tedy dvoupásmový 2,4 GHz + 900 MHz, z karet prodejců. |
| **Tvrzení projektů** | „Flown", „validated build", proudy 40 A/kanál. Nic z toho jsme neviděli ani neměřili. |
| **Neověřeno** | Žádný KiCad projekt jsme neotevřeli, neprošli ERC/DRC ani nespočítali BOM. Zda se OpenESC-20x20 kanál vejde čtyřikrát na 32 mm s H743 — OpenAIO to zkouší na 35,4 mm a hotové to není. Zda Pavo20 Pro unese i rozteč 20 × 20 (pak by šel stack s hotovým OpenESC-20x20). |

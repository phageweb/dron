# AIO H743 — popis návrhu

Co je na desce, kde to je ve schématu, odkud každá část pochází a proč je
zapojená právě takhle. Stav **17. 10. 2026, schéma rev A**. Tabulky na konci
generuje `tabulky.py` z netlistu, text píše člověk.

Značení zdrojů: **[Zn]** odkazuje na seznam [Zdroje](#zdroje) níž. Úroveň jistoty:

- **převzato**: zkopírované z vyrobeného a ověřeného návrhu beze změny,
- **podle dokumentu**: nakreslené podle datasheetu, aplikační poznámky nebo hwdefu,
- **naše volba**: rozhodli jsme sami, důvod je napsaný,
- **otevřené**: nenakreslené, rozhodne se ručně.

## 1. Co deska je

Jedna deska místo MicoAir H743 V2 45A AIO, které je dnes na Pavo20 Pro
([kusovník](../../spec/realna_stavba_dronu/11_kusovnik_pavo20.md)). Obsahuje:
řídicí počítač STM32H743 s ArduPilotem, čtyři ESC s AM32, napájení pro všechno
na dronu a konektory pro video vysílač a lidar.

| Parametr | Hodnota | Proč / odkud |
| --- | --- | --- |
| Obrys | 35,4 × 35,4 mm | obrys OpenAIO [Z1] beze změny, o 0,6 mm menší než MicoAir AIO (36 × 36) [Z9] |
| Díry | ⌀3 mm na 25,5 × 25,5, jako OpenAIO a MicoAir | rozteč FC rámu Pavo20 Pro je 26 × 26 [Z11]. Šroub M2 sedne díky vůli, oválné díry nejdou, viz kap. 4.1 |
| Vstup | 4S LiHV, max. 17,4 V | baterie Tattu ([kusovník](../../spec/realna_stavba_dronu/11_kusovnik_pavo20.md)). Převzaté obvody snesou 3S–6S [Z1] |
| MCU | STM32H743VIH6, TFBGA-100 | stejný čip jako MicoAir [Z9], ArduPilot na něm má hotový target [Z5]. Pouzdro se vejde na místo jádra OpenAIO, LQFP-100 by se nevešel ([požadavky, kap. 4](../docs/04_pozadavky.md)) |
| Vrstvy | 8, HDI 1+6+1, 1 oz, 1,0 mm | tak je vyrobený OpenAIO [Z1], ze kterého je převzatý layout ESC |
| Licence | CERN-OHL-S-2.0 | převzaté listy OpenDrone jsou pod ní [Z1], viz [LICENSE](../LICENSE) |

## 2. Soubory a listy

```text
aio.kicad_sch (kořen) ─┬─ ESC1..ESC4  esc_channel.kicad_sch   převzato
                       ├─ Power       fc_power.kicad_sch      převzato
                       ├─ IMU         fc_imu.kicad_sch        převzato
                       ├─ VTX a LD06  vtx.kicad_sch           nové
                       └─ MCU H743    mcu_h743.kicad_sch      nové
aio.kicad_pcb    layout OpenAIO, svázaný se schématem (F8)
lib.kicad_sym, lib.pretty   knihovna OpenAIO (všechny jejich díly), + standardní knihovny KiCadu
tabulky.py       přegeneruje tabulky v tomto dokumentu
gen/gen_aio.py   vygeneruje všechny listy schématu (desku nepřepisuje)
```

Reference podle listu: 1–199 OpenAIO (původní čísla), **2xx** list VTX, **3xx** list MCU.

## 3. Napájení

```text
baterie (U24 pad 1) ── Rsense2 0,2 mΩ ── +BATT ─┬─ 4× ESC (MOSFETy)                       převzato [Z1]
                       └ U25 INA186 → ESC_CURRENT ├─ U3 LMR51430 → +10V  (budiče ESC)        převzato [Z1]
                                                 ├─ U4 LMR51430 → +5V   3 A                  převzato [Z1]
                                                 ├─ U201 LMR51430 → +10V_VTX → HD VTX   nové
                                                 └─ R303/R304 → VBAT_SENSE (ADC)             nové
+5V ──┬─ D2 ─┐                         USB-C J301 → +5V_USB ── D3 ─┤
      │      └─ +4v5 ─┬─ U7 TLV76733 → +3.3V 1 A (H743, AT32 ×4, INA186, BMI270 IO)   převzato [Z1]
      │               └─ U6 LP5912 → +1.8V_GYRO (BMI270)                                       převzato [Z1]
      └─ LD06/D500 (pady TP201, TP202)
```

| Větev | Obvod | Zátěž, co víme | Zdroj | Proč |
| --- | --- | --- | --- | --- |
| +10V | U3, list Power | 4× budič NSG2065Q | převzato [Z1] | budiče ESC potřebují 8–20 V [Z1]. **Nesmí se vypínat**, proto VTX nevisí na ní |
| +10V_SW / +10V_VTX | U201, list VTX | HD VTX: DJI O3 12–16 W [Z12], Lite+ neměřený | kopie U3 [Z1], dělič 100k/6,49k = 9,84 V | 10 V je uprostřed rozsahu Lite+ 3–12,6 V [Z13] a v rozsahu DJI. Buck dá 3 A, O3 při 16 W bere 1,6 A. Vlastní buck, aby šel VTX vypnout bez vypnutí motorů |
| +5V | U4, list Power | LD06/D500 rozběh 540 mA, provoz 290 mA [Z14]; GPS, MTF-02P, přijímač, LDO 3,3 V — neměřeno | převzato [Z1] | 3 A [Z6]. MicoAir AIO má 5 V/2 A [Z9] |
| +3.3V | U7 TLV76733, list Power | H743, 4× AT32F421, senzory | převzato [Z1] | 1 A LDO z +4v5 |
| +1.8V_GYRO | U6 LP5912, list Power | BMI270 VDD | převzato [Z1] | oddělené napájení gyra |
| +5V_USB | J301, list MCU | — | podle OpenAIO [Z1] | USB napájí logiku bez baterie. D3 v listu Power ho OR-uje do +4v5, takže USB nenapájí +5V ani motory |

## 4. Listy jeden po druhém

### 4.1 Kořen `aio.kicad_sch`

| Co | Ref | Jistota | Zdroj | Proč |
| --- | --- | --- | --- | --- |
| Obrys s pady baterie a motorů | U24 `lib:AIO_outline` | převzato beze změny, rozhodnuto 18. 10. | OpenAIO [Z1] | pad 1 baterie +, pad 2 GND, pady 12–23 fáze motorů. Obrys 35,4 × 35,4 mm: o 0,6 mm menší než MicoAir, a 36 mm bylo v plánu jen podle něj. Díry ⌀3 mm na 25,5 × 25,5: vyzkoušeno 18. 10.: ovál 25,5–26 zasáhne v levém horním rohu 8 ze 40 prokovů CSA+, které vedou proud baterie a díru obtáčejí zvenku. Šroub M2 na rozteči 26 projde dírou ⌀3 na 25,5 s rezervou 0,15 mm (posun 0,25 mm na osu, 0,35 mm úhlopříčně), jako u MicoAiru [Z9] |
| Shunt všech ESC | Rsense2 0,2 mΩ 2512 | převzato | OpenAIO [Z1] | proud do všech ESC |
| Zesilovač proudu | U25 INA186A3, C104 | převzato | OpenAIO [Z1], TI INA186 [Z8] | 100 V/V × 0,2 mΩ = 20 mV/A. Výstup ESC_CURRENT jde do PC1 (ADC) |
| Testovací body | TP13, TP20–TP23 | převzato | OpenAIO [Z1] | proud a DShot čtyř motorů |
| Mapování motorů | sítě 1A–4C | převzato | OpenAIO [Z1] | pořadí fází na padech je z OpenAIO, smysl otáčení se nastaví v AM32 |

### 4.2 ESC1–ESC4 `esc_channel.kicad_sch`

**Převzato beze změny** z OpenAIO, kde je to kanál OpenESC-20x20 [Z1][Z2]:
AT32F421G8U7 (AM32), budič NSG2065Q a 6× MOSFET DOY180N03T (30 V). Vstupem
je `dshot` (MOTORn) a výstupem fáze A/B/C.

Proč převzít a neměnit: OpenESC je vyrobený a v prodeji [Z2]. Na 4S LiHV
(17,4 V) mají 30V MOSFETy rezervu. MicoAir AIO používá stejný ESC procesor,
firmware `AM32_F4A_4IN1_F421` [Z9]. Zmenšovat kanál na potřebných 10 A
nedává smysl, je to už holý trojfázový můstek ([návrh](../docs/02_navrh.md)).

### 4.3 Power `fc_power.kicad_sch`

**Převzato beze změny** z OpenAIO [Z1], původem z OpenFC-Lite-Mini [Z3].
Obsahuje U3 (+10V), U4 (+5V), D2/D3 (OR na +4v5), U7 (+3.3V), U6 (+1.8V_GYRO)
a LED na větvích. ERC/DRC převzatých projektů je v [návrhu](../docs/02_navrh.md#erc-a-drc-převzatých-projektů).

### 4.4 IMU `fc_imu.kicad_sch`

**Převzato beze změny**: BMI270 U8 na SPI, VDD z +1.8V_GYRO, VDDIO z +3.3V [Z1].
Připojení k H743 je podle hwdefu MicoAiru [Z5]: SPI3 (PB3 SCK, PD6 MOSI, PB4
MISO), CS na PA15, INT1 na PB7 (DRDY). Pin `CLKIN` listu vede na INT2 BMI270.
MicoAir ho nepoužívá, proto je na kořenovém listu **nezapojený**.

Proč BMI270: ArduPilot ho podporuje a MicoAir ho má jako druhou IMU [Z5][Z9].
Orientaci (`ROTATION_…`) je potřeba zapsat do vlastního hwdefu podle toho, jak
bude čip na desce otočený.

### 4.5 VTX a LD06 `vtx.kicad_sch` — nové

| Co | Ref | Jistota | Zdroj | Proč |
| --- | --- | --- | --- | --- |
| Buck 10 V pro VTX | U201, L201, C201–C203, R201, R202 | převzato zapojení | kopie U3 z OpenAIO [Z1], TI LMR51430 [Z6] | viz napájení výš. Stejné díly a dělič jako ověřený U3 |
| EN | R203 1k, R204 100k | naše volba | — | R204 drží VTX vypnutý, dokud ho MCU nezapne (`VTX_EN`, PD13, `RELAYn_DEFAULT 1` ho zapne při startu). Propojka JP201 „VTX vždy zapnutý“ je od 18. 10. pryč: na desku se nevešla a MicoAir ji nemá |
| Proud VTX | — | vypuštěno 18. 10. | — | INA226 s bočníkem 20 mΩ (U202, R205, C204) se na desku nevešel a MicoAir měření proudu VTX nemá. Výstup bucku jde přímo na J201 |
| HD VTX | J201 SH1.0-6P, JP202 | podle dokumentu | pinout DJI, stejný mají MicoAir [Z5] i OpenAIO [Z1] | 1 +10V_VTX, 2 GND, 3 VTX_TX, 4 VTX_RX, 5 GND, 6 SBUS z DJI přes JP202 na RC_RX. Pasuje DJI O3/O4 přímo, Lite+ přes redukci 6P → 4P. JP202 je standardně rozpojená, protože RX6 patří přijímači na J305. MicoAir má pin 6 a pad RX6 spojené natvrdo a dva vysílače by se na jedné lince praly |
| LD06 / D500 | pady TP201 Tx, TP202 PWM, 5V a GND na TP320/TP321, R206 0R | podle dokumentu, rozhodnuto 18. 10. | manuál LD19 / Waveshare ([test linky](../../spec/realna_stavba_dronu/15_test_linky_skenu.md)), MicoAir [Z27] | na pady jako u MicoAiru, ZH1.5-4P (požadavek M1) se na desku nevešel. Tx lidaru → LIDAR_TX (UART5 RX), PWM, GND, +5V. PWM musí být uzemněné, pokud se otáčky neřídí: R206. Když se R206 vyjme, řídí otáčky MCU přes LIDAR_PWM (PB0, TIM3_CH3) |

### 4.6 MCU H743 `mcu_h743.kicad_sch` — nové

**Nakreslené (podle dokumentu):**

| Co | Ref | Zdroj | Proč |
| --- | --- | --- | --- |
| STM32H743VIH6 | U301 | symbol a footprint ze standardní knihovny KiCadu (`STM32H743VIHx`, `TFBGA-100_8x8mm_Layout10x10_P0.8mm`) [Z10] | kuličky jsou ze symbolu KiCadu, ne přepsané ručně |
| Blokování VDD | C301–C303 100 nF, C304 4,7 µF | AN4938 kap. 2.2 [Z4] | „100 nF na každý VDD pin a jeden 4,7 µF pro pouzdro“. TFBGA-100 má 3 VDD (D2, F5, K1) |
| VDDLDO | C305 4,7 µF | AN4938 [Z4] | „VDDLDO … 4,7 µF“ |
| VCAP | C306, C307 2,2 µF, VCAP1+VCAP2 spojené | AN4938 [Z4] | „obě VCAP 2,2 µF s nízkým ESR (< 100 mΩ), doporučeno spojit VCAP1 a VCAP2“. ERC to hlásí jako dva spojené výstupy, je to záměr |
| VDDA | C308 100 nF + C309 1 µF, přímo na +3.3V | AN4938 [Z4] | „VDDA 100 nF + 1 µF“. VREF+ je u TFBGA-100 uvnitř spojená s VDDA. Ferit mezi VDD a VDDA AN4938 připouští, nedali jsme ho, ADC měří jen baterii a proud |
| VDD33USB | C310 100 nF + C311 1 µF, z +3.3V | AN4938 obr. 1 [Z4] | USB transceiver z VDD, „100 nF + 1 µF“ |
| VBAT | C312 100 nF, na +3.3V | AN4938 [Z4] | bez záložní baterie „VBAT na VDD přes 100 nF“ |
| NRST | C313 100 nF, TP305 | AN4938 [Z4] | filtr resetu, pad pro SWD |
| PDR_ON | R301 10k na +3.3V | AN4938 tab. 9 [Z4] | zapnutý vnitřní napěťový dozor (PDR_ON vysoko) |
| BOOT0 | R302 10k na GND, TP301 | AN4938 tab. 9 [Z4] | normálně start z flash. DFU: TP301 spojit s TP302 (+3.3V) při zapnutí, potřeba jen pro první nahrání bootloaderu |
| SWD | TP303 SWDIO (PA13), TP304 SWCLK (PA14), TP305 NRST, TP306 GND, TP302 +3.3V | hwdef [Z5] | ladění a záchrana přes ST-Link |
| USB-C | J301 TYPE-C 16P, R307/R308 5,1k na CC | převzato z OpenAIO [Z1] (stejný konektor C5187472 a CC rezistory) | 5,1k na CC je podmínka, aby USB-C zdroj pustil 5 V. Sériové 30R z OpenAIO vynecháno, byly pro RP2354 a OTG_FS je nepotřebuje |
| Napětí baterie | R303 100k, R304 10k, C314 100 nF → PC0 | dělič jako OpenAIO [Z1] | 25,2 V (6S) → 2,29 V, pod 3,3 V. ArduPilot `BATT_VOLT_MULT 11.0` |
| I2C2 pull-upy | R305, R306 2,2k | naše volba | vnitřní I2C (bus 0) má baro. 2,2k je obvyklá hodnota pro 400 kHz, žádný jiný pull-up na sběrnici není |
| Přiřazení pinů | všechny štítky na U301 | hwdef MicoAir743v2 [Z5] | stejné piny jako MicoAir, takže vlastní hwdef vznikne úpravou jeho hwdefu. Celá mapa je v tabulce níž |
| Volné GPIO | VTX_EN = PD13 (PWM8), LIDAR_PWM = PB0 (PWM6) | naše volba v rámci hwdefu | jsou to výstupy, které MicoAir AIO vyvádí jako PWM5–8 [Z9]. PB0 má časovač, takže umí PWM pro lidar |
| Krystal 8 MHz | Y301 YXC X32258MOB4SI (C2682775), C322/C323 15 pF C0G | naše volba podle AN4938/AN2867 [Z4][Z18][Z19] | 8 MHz čeká hwdef (`OSCILLATOR_HZ`). CL 12 pF: C = 2 × (CL − Cstray) = 2 × (12 − 5) = 14 → 15 pF. Kontrola strmosti: gm_crit = 4·ESR·(2πf)²·(C0+CL)² ≈ 0,5 mA/V při ESR 180 Ω a C0 ≤ 5 pF, mez H743 je Gmcritmax 1,5 mA/V. Nízké CL je tu schválně, s krystalem 20 pF by vyšlo přes 1 mA/V |
| Baro | U302 SPL06-001 nebo DPS310, C317 | rozhodnuto 17. 10.: ploška pro oba [Z15][Z16] | obě mají pouzdro LGA-8 2 × 2,5 mm s roztečí 0,65 mm a stejné piny jako BMP280, proto symbol a footprint BMP280. Relativní přesnost obou ±0,06 hPa, šum v režimu vysoké přesnosti SPL06 0,3–0,6 Pa RMS, DPS310 ±0,2 Pa. CSB a SDO na 3,3 V → I2C, adresa 0x77. Osadí se podle skladu JLC, v hwdefu je SPL06 (čipy mají stejné ID, viz kap. 6). Footprint Bosch: velikost plošek ověřit proti doporučení SPL06/DPS310 |
| Druhá IMU | U303 BMI088, C318/C319 | rozhodnuto 17. 10.: ano, jako MicoAir [Z17] | SPI2 jako MicoAir: PS na GND = SPI, SDO1 a SDO2 spojené do MISO (výstup neaktivního čipu je ve vysoké impedanci, ERC to hlásí, je to záměr), CS akcelerometru PD4, gyra PD5, INT1 → PC14, INT3 → PC15, INT2 a INT4 nezapojené podle datasheetu |
| GPS + kompas | J303 SH1.0-6P boční, R314/R315 4,7k | rozhodnuto 18. 10.: jako MicoAir [Z27] | 1 GND, 2 5V, 3 TX3 (PD8), 4 RX3 (PD9), 5 SCL, 6 SDA (I2C1). Pořadí MicoAiru, aby seděl kabel GPS z MicoAiru. MicoAir v tabulkách píše pin 6 první: v README ArduPilotu je pin 1 DJI konektoru 12 V, tedy poslední řádek. **Na desku se zatím nevešel**, kap. 7 |
| UART4 (MTF-02P) | J304 SH1.0-4P boční | rozhodnuto 18. 10.: jako MicoAir [Z27] | 1 GND, 2 5V, 3 TX4 (PA0), 4 RX4 (PA1). Stejné pořadí uvádí i manuál MTF-02P [Z20]. Na desce vzadu u pravé hrany jako u MicoAiru |
| UART1 + UART6 (přijímač, telemetrie) | J305 SH1.0-6P boční | rozhodnuto 18. 10.: jako MicoAir [Z27] | 1 GND, 2 5V, 3 TX1, 4 RX1, 5 TX6, 6 RX6. Přijímač (XR1 Nano) na UART6 přes kabel jako u MicoAiru, místo dřívějších padů TP307–TP312. **Na desku se zatím nevešel**, kap. 7 |
| Pady | TP313–TP321 | naše volba | UART8 pro Bluetooth nebo cokoli dalšího, volné PWM5, 7, 9, 10, 11, 5V a GND (i pro LD06) |
| RGB LED | D301–D303 XINGLIGHT XL-1005 0402, R316 330R, R317 150R, R318 75R | rozhodnuto 17. 10. [Z23][Z24] | ArduPilot `GPIO_LED_RGB` svítí nulou (`HAL_GPIO_LED_ON` 0, MicoAir ho nemění), proto anody na +3.3V a katody na PE3/PE2/PE4. Zelená XL-1005UGC (C965793) a modrá XL-1005UBC (C22355736) jsou díly OpenAIO, modrá i s jejím 75R. Červená XL-1005SURC (C965790) ze stejné řady. Proud odhadem 3–5 mA na barvu (Vf při malém proudu: R ~1,9 V, G ~2,7 V, B ~2,9 V), mez pinu 20 mA. Než MCU nastaví piny, jsou ve vysoké impedanci a LED nesvítí |
| Bzučák | Q301 AP1606 (C2849580), R319 100k, pady TP322 BZ+ / TP323 BZ− | rozhodnuto 17. 10., upraveno 18. 10. [Z23][Z25] | `BUZZ_ON_LVL` je výchozí 1, takže spínač v nule: N-MOSFET mezi BZ− a GND, aktivní 5V (piezo) bzučák na padech jako u MicoAiru. AP1606 je tranzistor z OpenAIO (Q1): Vgs(th) 1,2 V, 700 mA, DFN 1,0 × 0,6 mm. Původní AO3400A v SOT-23 se na desku nevešel, 2N7002 (Vgs(th) do 2,5 V) by z 3,3 V spínal nejistě. R319 drží hradlo dole během resetu a v bootloaderu. Dioda D304 je pryč jako u MicoAiru: piezo ji nepotřebuje |
| microSD | J302 TF-021B-H265 (C498185), R309–R313 47k, C320 100 nF, C321 4,7 µF | rozhodnuto 17. 10.: microSD jako MicoAir | slot z OpenAIO [Z1], ve footprintu doplněné pady 1 a 8 (kap. 7). 4bitové SDMMC1 jako MicoAir [Z5], pull-upy 47k na CMD a D0–D3 (specifikace SD chce 10–100k), CLK bez pull-upu |

**Otevřené (rozhodne se ručně):** viz kap. 8.

## 5. Konektory a pady

| Konektor | Ref | Pinout | Stav |
| --- | --- | --- | --- |
| Baterie + motory | U24 | 1 +, 2 GND, 12–23 fáze | převzato, obrys 35,4 mm a díry 25,5 beze změny |
| HD VTX | J201 SH1.0-6P | 1 +10V_VTX, 2 GND, 3 TX (PA2), 4 RX (PA3), 5 GND, 6 RC_RX (PC7) | hotovo |
| LD06 / D500 | TP201, TP202 + TP320/TP321 | Tx → PB5, PWM, 5V, GND | pady jako MicoAir |
| USB | J301 USB-C | USB 2.0, VBUS → +5V_USB | hotovo |
| SWD a BOOT0 | TP301–TP306 | BOOT0, +3.3V, SWDIO, SWCLK, NRST, GND | hotovo, pady 1,0 × 1,4 mm |
| GPS + kompas | J303 SH1.0-6P | 1 GND, 2 5V, 3 TX3, 4 RX3, 5 SCL, 6 SDA | schéma hotové, na desku se nevešel |
| UART4 (MTF-02P) | J304 SH1.0-4P | 1 GND, 2 5V, 3 TX4, 4 RX4 | hotovo, na desce |
| UART1 + UART6 | J305 SH1.0-6P | 1 GND, 2 5V, 3 TX1, 4 RX1, 5 TX6, 6 RX6 | schéma hotové, na desku se nevešel |
| Bluetooth / volný UART | TP313, TP314 | UART8 (PE1/PE0) | hotovo |
| Volné PWM | TP315–TP319 | PWM5, 7, 9, 10, 11 | hotovo |
| Bzučák | TP322 BZ+, TP323 BZ− | BZ+ = +5V, BZ− spíná Q301 (PD15) | hotovo, aktivní 5V bzučák |

## 6. ArduPilot

Hwdef desky je hotový v [`hwdef/Pavo20AIO`](./hwdef/README.md) a ArduPilot
z něj sestaví bootloader i ArduCopter (1,44 MB, 268 kB flash volno), viz
`dps/aio/hwdef/sestav.sh`. Vychází z `MicoAir743v2` [Z5],
což je cíl, na kterém běží dnešní MicoAir AIO 45A (board ID 1179, viz
[firmware](../../firmware/README.md)). Piny UARTů, SPI, I2C, PWM, ADC a SDMMC
zůstaly stejné. Mění se:

| Co | MicoAir743v2 | Naše deska | Proč |
| --- | --- | --- | --- |
| APJ_BOARD_ID | AP_HW_MicoAir743v2 (1179) | 25026, soukromé | uploader nesmí nahrát cizí firmware. Rozsah 1000–19999 přiděluje ArduPilot přes PR |
| OSD AT7456E (SPI1, PB12) | ano | **vypustit** | Walksnail je digitální, OSD jde přes MSP DisplayPort |
| BMI088 (SPI2) | ano | ano, U303 | jako MicoAir |
| Baterie | VOLT_SCALE 21.12, CURR_SCALE 40.2 | `HAL_BATT_VOLT_SCALE 11.0`, `HAL_BATT_CURR_SCALE 50.0` | dělič 100k/10k. INA186 20 mV/A → 50 A/V |
| Relé pro VTX | — | `RELAY1_PIN 57`, `RELAY1_DEFAULT 1` | PD13 = GPIO 57 |
| Kompas | QMC5883L na desce | jen v GPS, `HAL_I2C_INTERNAL_MASK 1` | na desce kompas není |
| Baro | SPL06 0x77 | SPL06 0x77, pro DPS310 vyměnit řádku | SPL06 i DPS310 vrací ID 0x10 v registru 0x0D [Z15][Z16], ArduPilot je nerozezná. Dvě řádky `BARO` by vytvořily dva ovladače na jednom čipu |
| Orientace IMU | ROLL_180 | `ROTATION_NONE`, doplnit podle layoutu | |

| SERIALn | UART | Piny | Zařízení |
| --- | --- | --- | --- |
| 0 | USB OTG_FS | PA11/PA12 | MAVLink na stole |
| 1 | USART1 | PA9/PA10 | volné / Bluetooth |
| 2 | USART2 | PA2/PA3 | HD VTX, MSP DisplayPort |
| 3 | USART3 | PD8/PD9 | GPS WS-M181 |
| 4 | UART4 | PA0/PA1 | MTF-02P |
| 5 | UART5 | PB5 (RX) | LD06 / D500, 230400 |
| 6 | USART6 | PC6/PC7 | XR1 Nano na J305, CRSF |
| 7 | UART7 | PE8/PE7 | volné (MicoAir: telemetrie ESC) |
| 8 | UART8 | PE1/PE0 | volné / Bluetooth |

## 7. Deska (PCB)

`aio.kicad_pcb` je layout OpenAIO [Z1] aktualizovaný ze schématu (18. 10.,
`gen/aktualizuj_desku.sh`). Převzaté díly (ESC, napájení, IMU, kořen) jsou svázané
se schématem přes UUID a zůstaly na místě i s vodiči. Co se změnilo:

- **Odstraněno** 145 footprintů vypuštěných listů (RP2354A, přijímač, OSD, pady, SD)
  a 845 kusů mědi (vodiče, prokovy, zóna +1.1V) jejich 70 sítí.
- **Přejmenováno** 10 sítí, které vedou dál k převzatým dílům: MOTOR1–4, CURR → ESC_CURRENT
  a sběrnice IMU (CS, INT, SPI). Jejich vodiče zůstaly, v místě jádra RP2354 končí naprázdno
  (44 visících vodičů v DRC) a dotrasují se k H743.
- **Přidáno** 93 dílů listů MCU, VTX a kořene, později upravené (níž).
- **Konektory jako MicoAir743-AIO** (18. 10.) [Z27], SH1.0 boční, ústím ven přes hranu.
  Pady motorů jsou jen vpředu, každý motor na jedné hraně, a horní hranu zabírají pady
  baterie. Hledání po mřížce 0,25 mm našlo čtyři místa na hraně, kde nepřekáží žádný
  převzatý díl, a ESC proto přeskládat nebylo potřeba: **J201 VTX vpředu dole** (místo SH-6
  z OpenAIO), **J303 GPS vpředu vpravo** pod motorem 4, **J305 UART1+UART6 vzadu vpravo**,
  **J304 UART4 vzadu dole**. Proti MicoAiru jsou jinde, protože pady motorů má jinde; pinouty
  a pořadí jsou jeho.
- **Pady jako MicoAir**: footprint `lib:Pad_1.0x1.4mm` (pad 1,0 × 1,4 mm, courtyard
  1,2 × 1,6) místo kruhových 1 mm s courtyardem 2 × 2. LD06 na padech TP201, TP202
  a 5V/GND z TP320/TP321: ZH1.5-4P (požadavek M1) potřeboval 86 mm² v jednom kuse.
- **Kvůli místu vypuštěno** (MicoAir nic z toho nemá): INA226 s bočníkem (U202, R205, C204),
  propojka JP201 „VTX vždy zapnutý“ a dioda bzučáku D304. Q301 je místo AO3400A (SOT-23)
  AP1606 z OpenAIO v DFN 1,0 × 0,6 mm.
- **Rozmístění** (`aktualizuj_desku.sh --rozmisti --znovu`, skript `gen/rozmisti.py`): kotvy
  na místa dílů OpenAIO, které nahrazují (H743 na místo RP2354 otočený o 180°, aby kuličky
  USB a SDMMC mířily k USB-C a slotu; USB-C a microSD na místa stejných footprintů; baro na
  místo BMP580; pady SWD na místa malých padů), konektory na místa výš. Blokovací
  kondenzátory H743 vzadu pod ním, ostatní co nejblíž pinům, se kterými sdílí síť. Překážkou
  je courtyard, pady, díry (na obou stranách) a měď na vnějších vrstvách, kterou nové díly
  nepoužívají (vnitřek ESC, +BATT, pole prokovů CSA+). **Není to layout**, jen výchozí bod.
- **Úklid mědi** (`aktualizuj_desku.sh --vycisti`, skript `gen/vycisti_med.py`): smaže
  visící zbytky po RP2354 a vodiče a prokovy, které DRC hlásí v kolizi s novými díly;
  CSA+ a +BATT nikdy.
- **Nevešly se U303 (BMI088, courtyard 5,3 × 3,7 mm) a U201 (buck VTX, 3,6 × 3,4 mm)**:
  na desce nezbylo volné místo 3,3 × 3,3 mm ani na jedné straně. Leží mimo desku, kap. 8.
- **DRC** (18. 10.): kromě 163 nepropojených spojů jen varování převzatá z OpenAIO.
  Nové díly nejsou trasované.
- Potisk desky má ještě popisky padů OpenAIO (cam, LED, gnd…), opraví se při layoutu.

Footprint microSD slotu `TF-SMD_TF-021B-H265` v OpenAIO **neměl pady 1 (DAT2) a 8
(DAT1)**. OpenAIO kartu čte po SPI a nepotřebuje je, my máme 4bitové SDMMC. Konektor
všech 8 kontaktů má: footprint v EasyEDA pro C498185 [Z26] je má po 1,1 mm na x = 3,775
a −3,925 mm. Doplněné jsou podle něj, do mezer, které pro ně v potisku zůstaly.

## 8. Otevřené otázky

| Co | Kde | Proč není rozhodnuté |
| --- | --- | --- |
| Pin 1 konektorů | J303, J304, J305 | pořadí z tabulek MicoAiru, pin 1 = GND podle README ArduPilotu. Před prvním zapnutím ověřit multimetrem proti kabelu z MicoAiru |
| LCSC čísla | díly s „—“ v kusovníku | vybrat podle skladu JLC |
| Místo pro BMI088 a buck VTX | U303, U201 | na desku se nevejdou (kap. 7). Uvolnit místo přesunem dílů ESC nebo napájení OpenAIO, nebo vypustit další funkci |
| Trasování | aio.kicad_pcb | 163 nepropojených spojů nových dílů, únik z BGA H743 na HDI. Potisk OpenAIO přepsat |

## 9. Kontrola

```sh
nix develop ./dps
kicad-cli sch erc --severity-error dps/aio/aio.kicad_sch    # 18 chyb, všechny vysvětlené
python3 dps/aio/tabulky.py                                  # přegeneruje tabulky níž
```

| Počet | Chyba | Proč je v pořádku |
| ---: | --- | --- |
| 16 | `pin_not_driven` v ESC1–4 | převzaté z OpenAIO/OpenESC: piny kondenzátorů jsou v jejich knihovně typu *input* |
| 1 | `pin_to_pin` VCAP E7–F8 | dva výstupy LDO spojené, přesně jak doporučuje AN4938 [Z4] |
| 1 | `pin_to_pin` SDO1–SDO2 BMI088 | oba výstupy na MISO, jak předepisuje datasheet pro SPI [Z17] |

## Zdroje

| | Zdroj | Na co |
| --- | --- | --- |
| Z1 | [OpenAIO](https://github.com/OpenDrone-hw/OpenAIO) `986ce1e`, soubory a `AGENTS.md` | ESC, napájení, IMU, kořen, USB-C, layout |
| Z2 | [OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20) `dba7828` | původ kanálu ESC, vyrobený a v prodeji |
| Z3 | [OpenFC-Lite-Mini](https://github.com/OpenDrone-hw/OpenFC-Lite-Mini) `d8a10ee` | původ napájení (LMR51430) |
| Z4 | ST AN4938 rev 6, *Getting started with STM32H74xI/G and STM32H75xI/G MCU hardware development*, kap. 2.2, 5.2, tab. 8–9 ([st.com](https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-hardware-development-stmicroelectronics.pdf)) | napájení, VCAP, BOOT0, PDR_ON, NRST |
| Z5 | ArduPilot `8b9ea70`: `libraries/AP_HAL_ChibiOS/hwdef/MicoAir743v2/hwdef.dat`, `AP_BattMonitor_INA2xx.cpp` | přiřazení pinů, INA226 |
| Z6 | [TI LMR51430](https://www.ti.com/product/LMR51430) | buck 36 V, 3 A |
| Z7 | [TI INA226](https://www.ti.com/product/INA226) | měření proudu VTX |
| Z8 | [TI INA186](https://www.ti.com/product/INA186) | měření proudu ESC |
| Z9 | [MicoAir743v2-AIO-45A](https://micoair.com/flightcontroller_micoair743v2_aio_45a/), [manuál robofusion](https://docs.robofusion.net/flight-controllers/h743-aio-user-manual), parametry od prodejce | 36 × 36, 25,5 díry, H743VIH6, BMI088+BMI270, BEC 5 V/2 A a 12 V/2 A, AM32 F421 |
| Z10 | KiCad 10 standardní knihovny (`MCU_ST_STM32H7`, `Package_BGA`, `Sensor_Energy`, `Connector_JST`) | symbol a footprint H743, INA226, JST |
| Z11 | [BETAFPV Pavo20 Pro II frame](https://betafpv.com/products/pavo20-pro-ii-brushless-whoop-frame), [hobbydrone.cz](https://www.hobbydrone.cz/cs/frame-betafpv-pavo20-for-o3-air-unit-clear-grey/) | rozteč FC 26 × 26 |
| Z12 | [Pavo20, kap. termika](../../spec/realna_stavba_dronu/10_pavo20.md) | DJI O3 12–16 W |
| Z13 | [Kusovník](../../spec/realna_stavba_dronu/11_kusovnik_pavo20.md) | Lite+ 3–12,6 V |
| Z14 | [Test linky skenu](../../spec/realna_stavba_dronu/15_test_linky_skenu.md) | pinout LD19/LD06, rozběh D500 540 mA |
| Z15 | [Goertek SPL06-001](https://media.digikey.com/pdf/Data%20Sheets/Goertek%20Microelectronics%20PDFs/SPL06-001.pdf), [JLC C2684428](https://jlcpcb.com/partdetail/Goertek-SPL06001/C2684428) | piny, adresa, přesnost, šum |
| Z16 | [Infineon DPS310](https://files.seeedstudio.com/products/101020812/res/DPS310-datasheet.pdf), [JLC C130156](https://jlcpcb.com/partdetail/InfineonTechnologies-DPS310/C130156) | piny, adresa, přesnost |
| Z17 | [Bosch BMI088 rev 1.9](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi088-ds001.pdf), kap. 7 | piny a zapojení SPI |
| Z18 | [YXC X32258MOB4SI, JLC C2682775](https://jlcpcb.com/partdetail/2777872-X32258MOB4SI/C2682775) | 8 MHz, CL 12 pF, ESR 180 Ω |
| Z19 | [ST DS12110 (STM32H743xI datasheet)](https://cdn.sparkfun.com/assets/e/4/e/c/a/STM32H743VI_Datasheet.pdf), HSE: Gmcritmax 1,5 mA/V | strmost oscilátoru |
| Z20 | [MicoAir MTF-02P](https://micoair.com/optical_range_sensor_mtf-02p/) (obrázek konektoru), [manuál robofusion](https://docs.robofusion.net/sensors/mtf-02-02p-user-manual) | SH1.0-4P, Tx Rx 5V GND, 5 V, 100 mA, UART 3,3 V 115200 |
| Z21 | [Caddx WS-M181](https://www.caddxfpv.com/products/walksnail-ws-m181gps), [potisk modulu (DrFrantic77)](https://blog-drfrantic77.de/pinout-gps-modul-walksnail-ws-m181/) | TX RX GND 5V SCL SDA, IST8310, 5 V, 115200 |
| Z22 | [RadioMaster XR1 Nano, manuál](https://images.amainhobbies.com/images/resources/RM-BR0157.XR1-900/Manuals/1-RM-BR0157.XR1-900_RadioMaster_XR1_Nano_Multi-Frequency_ELRS_Receiver%20-%20Manual.pdf) | pady 5V, G, TX, RX |
| Z23 | ArduPilot `8b9ea70`: `libraries/AP_Notify/PixRacerLED.cpp`, `Buzzer.cpp`, `AP_Notify.cpp` | LED svítí `HAL_GPIO_LED_ON` (výchozí 0), bzučák `BUZZ_ON_LVL` (výchozí 1) |
| Z24 | XINGLIGHT XL-1005: [SURC C965790](https://jlcpcb.com/partdetail/XINGLIGHT-XL1005SURC/C965790), [UGC C965793](https://www.lcsc.com/product-detail/C965793.html), [UBC C22355736](https://www.lcsc.com/product-detail/C22355736.html) | 0402, R 2,3 V / G 3 V / B 3,3 V při 20 mA |
| Z25 | [AP1606 C2849580](https://jlcpcb.com/partdetail/C2849580), dříve [AO3400A C20917](https://jlcpcb.com/partdetail/C20917), pro srovnání [2N7002 C8545](https://jlcpcb.com/partdetail/C8545) | AP1606: N-MOSFET, Vgs(th) 1,2 V, 700 mA, 20 V, DFN 1,0 × 0,6; 2N7002 Vgs(th) 2,5 V |

## 10. Tabulky ze schématu

### Mapa pinů H743

<!-- tabulky:piny -->
| Kulička | Pin | Síť | Funkce (hwdef MicoAir743v2) | Kam vede |
| --- | --- | --- | --- | --- |
| G2 | PA0 | FLOW_TX | UART4_TX, SERIAL4 | J304 |
| H2 | PA1 | FLOW_RX | UART4_RX, SERIAL4 | J304 |
| J2 | PA2 | VTX_TX | USART2_TX, SERIAL2 | J201 |
| K2 | PA3 | VTX_RX | USART2_RX, SERIAL2 | J201 |
| G3 | PA4 | — |  | nezapojeno |
| H3 | PA5 | — |  | nezapojeno |
| J3 | PA6 | — |  | nezapojeno |
| K3 | PA7 | — |  | nezapojeno |
| D9 | PA8 | — |  | nezapojeno |
| C9 | PA9 | UART1_TX | USART1_TX, SERIAL1 | J305 |
| D10 | PA10 | UART1_RX | USART1_RX, SERIAL1 | J305 |
| C10 | PA11 | USB_DM | OTG_FS_DM, SERIAL0 | J301 |
| B10 | PA12 | USB_DP | OTG_FS_DP, SERIAL0 | J301 |
| A10 | PA13 | SWDIO | SWD | TP303 |
| A9 | PA14 | SWCLK | SWD | TP304 |
| A8 | PA15 | IMU_CS | BMI270_CS | R25, U8 |
| J4 | PB0 | LIDAR_PWM | PWM6, TIM3_CH3, GPIO 55 | R206, TP202 |
| K4 | PB1 | PWM5 | PWM5, TIM3_CH4, GPIO 54 | TP315 |
| G5 | PB2 | — |  | nezapojeno |
| A7 | PB3 | IMU_SPI.SCK | SPI3_SCK | U8 |
| A6 | PB4 | IMU_SPI.MISO | SPI3_MISO | U8 |
| C5 | PB5 | LIDAR_TX | UART5_RX, SERIAL5 | TP201 |
| B5 | PB6 | UART5_TX | UART5_TX, SERIAL5 | jen štítek, čeká na zapojení |
| A5 | PB7 | IMU_INT | DRDY3_BMI270 | U8 |
| B4 | PB8 | EXT_SCL | I2C1_SCL (bus 1) | J303, R314 |
| A4 | PB9 | EXT_SDA | I2C1_SDA (bus 1) | J303, R315 |
| J7 | PB10 | SCL | I2C2_SCL (bus 0) | R306, U302 |
| K7 | PB11 | SDA | I2C2_SDA (bus 0) | R305, U302 |
| K8 | PB12 | — |  | nezapojeno |
| J8 | PB13 | — |  | nezapojeno |
| H10 | PB14 | — |  | nezapojeno |
| G10 | PB15 | — |  | nezapojeno |
| F1 | PC0 | VBAT_SENSE | ADC1 ch10, BATT_VOLTAGE_SENS | C314, R303, R304 |
| F2 | PC1 | ESC_CURRENT | ADC1 ch11, BATT_CURRENT_SENS | TP13, U25 |
| E2 | PC2_C | IMU2_MISO | SPI2_MISO | U303 |
| F3 | PC3_C | IMU2_MOSI | SPI2_MOSI | U303 |
| G4 | PC4 | — |  | nezapojeno |
| H4 | PC5 | — |  | nezapojeno |
| F10 | PC6 | RC_TX | USART6_TX, SERIAL6 | J305 |
| E10 | PC7 | RC_RX | USART6_RX, SERIAL6 | J305, JP202 |
| F9 | PC8 | SD_D0 | SDMMC1_D0 | J302, R310 |
| E9 | PC9 | SD_D1 | SDMMC1_D1 | J302, R311 |
| B9 | PC10 | SD_D2 | SDMMC1_D2 | J302, R312 |
| B8 | PC11 | SD_D3 | SDMMC1_D3 | J302, R313 |
| C8 | PC12 | SD_CK | SDMMC1_CK | J302 |
| A2 | PC13 | — |  | nezapojeno |
| A1 | PC14 | IMU2_ACC_INT | DRDY2_BMI088_A | U303 |
| B1 | PC15 | IMU2_GYR_INT | DRDY1_BMI088_G | U303 |
| D8 | PD0 | — |  | nezapojeno |
| F7 | PDR_ON | PDR_ON | napěťový dozor | R301 |
| E8 | PD1 | — |  | nezapojeno |
| B7 | PD2 | SD_CMD | SDMMC1_CMD | J302, R309 |
| C7 | PD3 | IMU2_SCK | SPI2_SCK | U303 |
| D7 | PD4 | IMU2_ACC_CS | BMI088_A_CS | U303 |
| B6 | PD5 | IMU2_GYR_CS | BMI088_G_CS | U303 |
| C6 | PD6 | IMU_SPI.MOSI | SPI3_MOSI | U8 |
| D6 | PD7 | — |  | nezapojeno |
| K9 | PD8 | GPS_TX | USART3_TX, SERIAL3 | J303 |
| J9 | PD9 | GPS_RX | USART3_RX, SERIAL3 | J303 |
| H9 | PD10 | — |  | nezapojeno |
| G9 | PD11 | — |  | nezapojeno |
| K10 | PD12 | PWM7 | PWM7, TIM4_CH1, GPIO 56 | TP316 |
| J10 | PD13 | VTX_EN | PWM8 jako GPIO 57 (RELAYn_PIN 57) | R203 |
| H8 | PD14 | PWM11 | PWM11, TIM4_CH3, GPIO 60 (LED pad) | TP319 |
| G8 | PD15 | BUZZER | BUZZER, GPIO 61 | Q301, R319 |
| D4 | PE0 | UART8_RX | UART8_RX, SERIAL8 | TP314 |
| C4 | PE1 | UART8_TX | UART8_TX, SERIAL8 | TP313 |
| A3 | PE2 | LED_G | LED_GREEN, GPIO 1 | D302 |
| B3 | PE3 | LED_R | LED_RED, GPIO 0 | D301 |
| C3 | PE4 | LED_B | LED_BLUE, GPIO 2 | D303 |
| D3 | PE5 | PWM9 | PWM9, TIM15_CH1, GPIO 58 | TP317 |
| E3 | PE6 | PWM10 | PWM10, TIM15_CH2, GPIO 59 | TP318 |
| H5 | PE7 | UART7_RX | UART7_RX, SERIAL7 | jen štítek, čeká na zapojení |
| J5 | PE8 | UART7_TX | UART7_TX, SERIAL7 | jen štítek, čeká na zapojení |
| K5 | PE9 | MOTOR4 | PWM4, TIM1_CH1 | R96, TP23 |
| G6 | PE10 | — |  | nezapojeno |
| H6 | PE11 | MOTOR3 | PWM3, TIM1_CH2, BIDIR DShot | R77, TP22 |
| J6 | PE12 | — |  | nezapojeno |
| K6 | PE13 | MOTOR2 | PWM2, TIM1_CH3 | R58, TP21 |
| G7 | PE14 | MOTOR1 | PWM1, TIM1_CH4, BIDIR DShot | R39, TP20 |
| H7 | PE15 | — |  | nezapojeno |
| C1 | PH0 | HSE_IN | OSC_IN, 8 MHz | C322, Y301 |
| D1 | PH1 | HSE_OUT | OSC_OUT | C323, Y301 |
| D5 | BOOT0 | BOOT0 | BOOT0 | R302, TP301 |
| E1 | NRST | NRST | reset | C313, TP305 |
| B2 | VBAT | +3.3V |  | napájecí síť (56 dílů) |
| E7 | VCAP | VCAP | výstup LDO jádra | C306, C307 |
| F8 | VCAP | VCAP | výstup LDO jádra | C306, C307 |
| D2 | VDD | +3.3V |  | napájecí síť (56 dílů) |
| F5 | VDD | +3.3V |  | napájecí síť (56 dílů) |
| K1 | VDD | +3.3V |  | napájecí síť (56 dílů) |
| H1 | VDDA | +3.3V |  | napájecí síť (56 dílů) |
| F4 | VDDLDO | +3.3V |  | napájecí síť (56 dílů) |
| C2 | VSS | GND |  | napájecí síť (136 dílů) |
| E4 | VSS | GND |  | napájecí síť (136 dílů) |
| E5 | VSS | GND |  | napájecí síť (136 dílů) |
| E6 | VSS | GND |  | napájecí síť (136 dílů) |
| J1 | VSS | GND |  | napájecí síť (136 dílů) |
| G1 | VSSA | GND |  | napájecí síť (136 dílů) |
| F6 | VDD33_USB | +3.3V |  | napájecí síť (56 dílů) |
<!-- /tabulky:piny -->

### Sítě mezi listy

<!-- tabulky:site -->
| Síť | Listy | Součástky |
| --- | --- | --- |
| +1.8V_GYRO | /IMU/, /Power/ | C27, C29, U6, U8 |
| +10V | /ESC1/, /ESC2/, /ESC3/, /ESC4/, /Power/ | C23, C43, C50, C57, C64, L2, R17, R21, U14, U16 … (+2) |
| +3.3V | /, /ESC1/, /ESC2/, /ESC3/, /ESC4/, /IMU/, /MCU H743/, /Power/ | C28, C30, C39, C46, C53, C60, C104, C301, C302, C303 … (+47) |
| +5V | /MCU H743/, /Power/ | C24, D2, J303, J304, J305, L3, R19, R22, TP30, TP320 … (+1) |
| +5V_USB | /MCU H743/, /Power/ | D3, J301 |
| +BATT | /, /ESC1/, /ESC2/, /ESC3/, /ESC4/, /MCU H743/, /Power/, /VTX a LD06/ | C18, C19, C90, C91, C92, C93, C94, C95, C96, C97 … (+27) |
| 1A | /, /ESC1/ | C40, Q3, Q4, R47, U14, U24 |
| 1B | /, /ESC1/ | C41, Q5, Q6, R50, U14, U24 |
| 1C | /, /ESC1/ | C42, Q7, Q8, R53, U14, U24 |
| 2A | /, /ESC2/ | C47, Q9, Q10, R66, U16, U24 |
| 2B | /, /ESC2/ | C48, Q11, Q12, R69, U16, U24 |
| 2C | /, /ESC2/ | C49, Q13, Q14, R72, U16, U24 |
| 3A | /, /ESC3/ | C54, Q15, Q16, R85, U18, U24 |
| 3B | /, /ESC3/ | C55, Q17, Q18, R88, U18, U24 |
| 3C | /, /ESC3/ | C56, Q19, Q20, R91, U18, U24 |
| 4A | /, /ESC4/ | C61, Q21, Q22, R104, U20, U24 |
| 4B | /, /ESC4/ | C62, Q23, Q24, R107, U20, U24 |
| 4C | /, /ESC4/ | C63, Q25, Q26, R110, U20, U24 |
| ESC_CURRENT | /, /MCU H743/ | TP13, U25, U301 |
| IMU_CS | /IMU/, /MCU H743/ | R25, U8, U301 |
| IMU_INT | /IMU/, /MCU H743/ | U8, U301 |
| IMU_SPI.MISO | /IMU/, /MCU H743/ | U8, U301 |
| IMU_SPI.MOSI | /IMU/, /MCU H743/ | U8, U301 |
| IMU_SPI.SCK | /IMU/, /MCU H743/ | U8, U301 |
| LIDAR_PWM | /MCU H743/, /VTX a LD06/ | R206, TP202, U301 |
| LIDAR_TX | /MCU H743/, /VTX a LD06/ | TP201, U301 |
| MOTOR1 | /, /ESC1/, /MCU H743/ | R39, TP20, U301 |
| MOTOR2 | /, /ESC2/, /MCU H743/ | R58, TP21, U301 |
| MOTOR3 | /, /ESC3/, /MCU H743/ | R77, TP22, U301 |
| MOTOR4 | /, /ESC4/, /MCU H743/ | R96, TP23, U301 |
| RC_RX | /MCU H743/, /VTX a LD06/ | J305, JP202, U301 |
| VTX_EN | /MCU H743/, /VTX a LD06/ | R203, U301 |
| VTX_RX | /MCU H743/, /VTX a LD06/ | J201, U301 |
| VTX_TX | /MCU H743/, /VTX a LD06/ | J201, U301 |
<!-- /tabulky:site -->

### Kusovník podle listů

<!-- tabulky:kusovnik -->

**/** (9 dílů)

| Ref | Hodnota | Pouzdro | LCSC |
| --- | --- | --- | --- |
| C104 | 100nF | C_0201_0603Metric | C181043 |
| Rsense2 | 0.2mR | R_2512_6332Metric | C695806 |
| TP13 | TestPoint | TestPoint_Pad_D1.0mm | — |
| TP20 | TestPoint | TestPoint_Pad_D1.0mm | — |
| TP21 | TestPoint | TestPoint_Pad_D1.0mm | — |
| TP22 | TestPoint | TestPoint_Pad_D1.0mm | — |
| TP23 | TestPoint | TestPoint_Pad_D1.0mm | — |
| U24 | AIO_outline | AIO_outline | — |
| U25 | INA186A3IDCKR | SOT-363_SC-70-6 | C2058245 |

**/ESC1/** (39 dílů)

| Ref | Hodnota | Pouzdro | LCSC |
| --- | --- | --- | --- |
| C37 | 100nF | C_0201_0603Metric | C181043 |
| C38 | 100nF | C_0201_0603Metric | C181043 |
| C39 | 100nF | C_0201_0603Metric | C181043 |
| C40 | 100nF | C_0402_WIDE | C307331 |
| C41 | 100nF | C_0402_WIDE | C307331 |
| C42 | 100nF | C_0402_WIDE | C307331 |
| C43 | 100nF | C_0201_0603Metric | C181043 |
| C90 | C | C_0805_2012Metric | — |
| C91 | C | C_0805_2012Metric | — |
| C92 | C | C_0805_2012Metric | — |
| Q3 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q4 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q5 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q6 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q7 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q8 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| R35 | 15R | R_0201_0603Metric | C473542 |
| R36 | 15R | R_0201_0603Metric | C473542 |
| R37 | 10k | R_0201_0603Metric | C106225 |
| R38 | 10k | R_0201_0603Metric | C106225 |
| R39 | 220R | R_0201_0603Metric | C226468 |
| R40 | 10R | R_0201_0603Metric | C106226 |
| R41 | 15R | R_0201_0603Metric | C473542 |
| R42 | 15R | R_0201_0603Metric | C473542 |
| R43 | 15R | R_0201_0603Metric | C473542 |
| R44 | 15R | R_0201_0603Metric | C473542 |
| R45 | 10k | R_0201_0603Metric | C106225 |
| R46 | 1k | R_0201_0603Metric | C270365 |
| R47 | 10k | R_0201_0603Metric | C106225 |
| R48 | 10k | R_0201_0603Metric | C106225 |
| R49 | 1k | R_0201_0603Metric | C270365 |
| R50 | 10k | R_0201_0603Metric | C106225 |
| R51 | 10k | R_0201_0603Metric | C106225 |
| R52 | 1k | R_0201_0603Metric | C270365 |
| R53 | 10k | R_0201_0603Metric | C106225 |
| TP1 | TestPoint | TestPoint_Pad_D1.0mm | — |
| TP2 | TestPoint | TestPoint_Pad_D1.0mm | — |
| U13 | AT32F421G8U7 | QFN-28_L4.0-W4.0-P0.40-TL-EP2.4 | C2765098 |
| U14 | NSG2065Q | QFN-24_L4.0-W4.0-P0.50-TL-EP2.8 | C41414478 |

**/ESC2/** (39 dílů)

| Ref | Hodnota | Pouzdro | LCSC |
| --- | --- | --- | --- |
| C44 | 100nF | C_0201_0603Metric | C181043 |
| C45 | 100nF | C_0201_0603Metric | C181043 |
| C46 | 100nF | C_0201_0603Metric | C181043 |
| C47 | 100nF | C_0402_WIDE | C307331 |
| C48 | 100nF | C_0402_WIDE | C307331 |
| C49 | 100nF | C_0402_WIDE | C307331 |
| C50 | 100nF | C_0201_0603Metric | C181043 |
| C93 | C | C_0805_2012Metric | — |
| C94 | C | C_0805_2012Metric | — |
| C95 | C | C_0805_2012Metric | — |
| Q9 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q10 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q11 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q12 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q13 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q14 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| R54 | 15R | R_0201_0603Metric | C473542 |
| R55 | 15R | R_0201_0603Metric | C473542 |
| R56 | 10k | R_0201_0603Metric | C106225 |
| R57 | 10k | R_0201_0603Metric | C106225 |
| R58 | 220R | R_0201_0603Metric | C226468 |
| R59 | 10R | R_0201_0603Metric | C106226 |
| R60 | 15R | R_0201_0603Metric | C473542 |
| R61 | 15R | R_0201_0603Metric | C473542 |
| R62 | 15R | R_0201_0603Metric | C473542 |
| R63 | 15R | R_0201_0603Metric | C473542 |
| R64 | 10k | R_0201_0603Metric | C106225 |
| R65 | 1k | R_0201_0603Metric | C270365 |
| R66 | 10k | R_0201_0603Metric | C106225 |
| R67 | 10k | R_0201_0603Metric | C106225 |
| R68 | 1k | R_0201_0603Metric | C270365 |
| R69 | 10k | R_0201_0603Metric | C106225 |
| R70 | 10k | R_0201_0603Metric | C106225 |
| R71 | 1k | R_0201_0603Metric | C270365 |
| R72 | 10k | R_0201_0603Metric | C106225 |
| TP3 | TestPoint | TestPoint_Pad_D1.0mm | — |
| TP4 | TestPoint | TestPoint_Pad_D1.0mm | — |
| U15 | AT32F421G8U7 | QFN-28_L4.0-W4.0-P0.40-TL-EP2.4 | C2765098 |
| U16 | NSG2065Q | QFN-24_L4.0-W4.0-P0.50-TL-EP2.8 | C41414478 |

**/ESC3/** (39 dílů)

| Ref | Hodnota | Pouzdro | LCSC |
| --- | --- | --- | --- |
| C51 | 100nF | C_0201_0603Metric | C181043 |
| C52 | 100nF | C_0201_0603Metric | C181043 |
| C53 | 100nF | C_0201_0603Metric | C181043 |
| C54 | 100nF | C_0402_WIDE | C307331 |
| C55 | 100nF | C_0402_WIDE | C307331 |
| C56 | 100nF | C_0402_WIDE | C307331 |
| C57 | 100nF | C_0201_0603Metric | C181043 |
| C96 | C | C_0805_2012Metric | — |
| C97 | C | C_0805_2012Metric | — |
| C98 | C | C_0805_2012Metric | — |
| Q15 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q16 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q17 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q18 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q19 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q20 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| R73 | 15R | R_0201_0603Metric | C473542 |
| R74 | 15R | R_0201_0603Metric | C473542 |
| R75 | 10k | R_0201_0603Metric | C106225 |
| R76 | 10k | R_0201_0603Metric | C106225 |
| R77 | 220R | R_0201_0603Metric | C226468 |
| R78 | 10R | R_0201_0603Metric | C106226 |
| R79 | 15R | R_0201_0603Metric | C473542 |
| R80 | 15R | R_0201_0603Metric | C473542 |
| R81 | 15R | R_0201_0603Metric | C473542 |
| R82 | 15R | R_0201_0603Metric | C473542 |
| R83 | 10k | R_0201_0603Metric | C106225 |
| R84 | 1k | R_0201_0603Metric | C270365 |
| R85 | 10k | R_0201_0603Metric | C106225 |
| R86 | 10k | R_0201_0603Metric | C106225 |
| R87 | 1k | R_0201_0603Metric | C270365 |
| R88 | 10k | R_0201_0603Metric | C106225 |
| R89 | 10k | R_0201_0603Metric | C106225 |
| R90 | 1k | R_0201_0603Metric | C270365 |
| R91 | 10k | R_0201_0603Metric | C106225 |
| TP5 | TestPoint | TestPoint_Pad_D1.0mm | — |
| TP6 | TestPoint | TestPoint_Pad_D1.0mm | — |
| U17 | AT32F421G8U7 | QFN-28_L4.0-W4.0-P0.40-TL-EP2.4 | C2765098 |
| U18 | NSG2065Q | QFN-24_L4.0-W4.0-P0.50-TL-EP2.8 | C41414478 |

**/ESC4/** (39 dílů)

| Ref | Hodnota | Pouzdro | LCSC |
| --- | --- | --- | --- |
| C58 | 100nF | C_0201_0603Metric | C181043 |
| C59 | 100nF | C_0201_0603Metric | C181043 |
| C60 | 100nF | C_0201_0603Metric | C181043 |
| C61 | 100nF | C_0402_WIDE | C307331 |
| C62 | 100nF | C_0402_WIDE | C307331 |
| C63 | 100nF | C_0402_WIDE | C307331 |
| C64 | 100nF | C_0201_0603Metric | C181043 |
| C99 | C | C_0805_2012Metric | — |
| C100 | C | C_0805_2012Metric | — |
| C101 | C | C_0805_2012Metric | — |
| Q21 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q22 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q23 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q24 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q25 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| Q26 | DOY180N03T | Diodes_PowerDI3333-8 | C49441966 |
| R92 | 15R | R_0201_0603Metric | C473542 |
| R93 | 15R | R_0201_0603Metric | C473542 |
| R94 | 10k | R_0201_0603Metric | C106225 |
| R95 | 10k | R_0201_0603Metric | C106225 |
| R96 | 220R | R_0201_0603Metric | C226468 |
| R97 | 10R | R_0201_0603Metric | C106226 |
| R98 | 15R | R_0201_0603Metric | C473542 |
| R99 | 15R | R_0201_0603Metric | C473542 |
| R100 | 15R | R_0201_0603Metric | C473542 |
| R101 | 15R | R_0201_0603Metric | C473542 |
| R102 | 10k | R_0201_0603Metric | C106225 |
| R103 | 1k | R_0201_0603Metric | C270365 |
| R104 | 10k | R_0201_0603Metric | C106225 |
| R105 | 10k | R_0201_0603Metric | C106225 |
| R106 | 1k | R_0201_0603Metric | C270365 |
| R107 | 10k | R_0201_0603Metric | C106225 |
| R108 | 10k | R_0201_0603Metric | C106225 |
| R109 | 1k | R_0201_0603Metric | C270365 |
| R110 | 10k | R_0201_0603Metric | C106225 |
| TP7 | TestPoint | TestPoint_Pad_D1.0mm | — |
| TP8 | TestPoint | TestPoint_Pad_D1.0mm | — |
| U19 | AT32F421G8U7 | QFN-28_L4.0-W4.0-P0.40-TL-EP2.4 | C2765098 |
| U20 | NSG2065Q | QFN-24_L4.0-W4.0-P0.50-TL-EP2.8 | C41414478 |

**/IMU/** (4 dílů)

| Ref | Hodnota | Pouzdro | LCSC |
| --- | --- | --- | --- |
| C29 | 100n | C_0201_0603Metric | C76939 |
| C30 | 100n | C_0201_0603Metric | C76939 |
| R25 | 10k | R_0201_0603Metric | C106225 |
| U8 | BMI270 | LGA-14_L3.0-W2.5-P0.50-BR | C2836813 |

**/MCU H743/** (70 dílů)

| Ref | Hodnota | Pouzdro | LCSC |
| --- | --- | --- | --- |
| C301 | 100n | C_0201_0603Metric | C76939 |
| C302 | 100n | C_0201_0603Metric | C76939 |
| C303 | 100n | C_0201_0603Metric | C76939 |
| C304 | 4.7uF | C_0402_1005Metric | C23733 |
| C305 | 4.7uF | C_0402_1005Metric | C23733 |
| C306 | 2.2uF | C_0402_1005Metric | — |
| C307 | 2.2uF | C_0402_1005Metric | — |
| C308 | 100n | C_0201_0603Metric | C76939 |
| C309 | 1uF | C_0402_1005Metric | — |
| C310 | 100n | C_0201_0603Metric | C76939 |
| C311 | 1uF | C_0402_1005Metric | — |
| C312 | 100n | C_0201_0603Metric | C76939 |
| C313 | 100n | C_0201_0603Metric | C76939 |
| C314 | 100n | C_0201_0603Metric | C76939 |
| C317 | 100n | C_0201_0603Metric | C76939 |
| C318 | 100n | C_0201_0603Metric | C76939 |
| C319 | 100n | C_0201_0603Metric | C76939 |
| C320 | 100n | C_0201_0603Metric | C76939 |
| C321 | 4.7uF | C_0402_1005Metric | C23733 |
| C322 | 15pF C0G | C_0402_1005Metric | — |
| C323 | 15pF C0G | C_0402_1005Metric | — |
| D301 | XL-1005SURC | LED_0402_1005Metric | C965790 |
| D302 | XL-1005UGC | LED_0402_1005Metric | C965793 |
| D303 | XL-1005UBC | LED_0402_1005Metric | C22355736 |
| J301 | TYPE-C 16P QTWT | USB-TYPE-C-SMD_TYPE-C-16P-QTWT | C5187472 |
| J302 | TF-021B-H265 | TF-SMD_TF-021B-H265 | C498185 |
| J303 | GPS (UART3+I2C1) | JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal | C160405 |
| J304 | UART4 (MTF-02P) | JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal | — |
| J305 | UART1+UART6 (RX, telemetrie) | JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal | C160405 |
| Q301 | AP1606 | DFN-3L_L1.0-W0.6-P0.65-BR | C2849580 |
| R301 | 10k | R_0201_0603Metric | — |
| R302 | 10k | R_0201_0603Metric | — |
| R303 | 100k | R_0201_0603Metric | C270364 |
| R304 | 10k | R_0201_0603Metric | — |
| R305 | 2.2k | R_0201_0603Metric | — |
| R306 | 2.2k | R_0201_0603Metric | — |
| R307 | 5.1k | R_0201_0603Metric | C270344 |
| R308 | 5.1k | R_0201_0603Metric | C270344 |
| R309 | 47k | R_0201_0603Metric | — |
| R310 | 47k | R_0201_0603Metric | — |
| R311 | 47k | R_0201_0603Metric | — |
| R312 | 47k | R_0201_0603Metric | — |
| R313 | 47k | R_0201_0603Metric | — |
| R314 | 4.7k | R_0201_0603Metric | — |
| R315 | 4.7k | R_0201_0603Metric | — |
| R316 | 330R | R_0201_0603Metric | — |
| R317 | 150R | R_0201_0603Metric | — |
| R318 | 75R | R_0201_0603Metric | — |
| R319 | 100k | R_0201_0603Metric | C270364 |
| TP301 | BOOT0 | Pad_1.0x1.4mm | — |
| TP302 | +3.3V | Pad_1.0x1.4mm | — |
| TP303 | SWDIO | Pad_1.0x1.4mm | — |
| TP304 | SWCLK | Pad_1.0x1.4mm | — |
| TP305 | NRST | Pad_1.0x1.4mm | — |
| TP306 | GND | Pad_1.0x1.4mm | — |
| TP313 | UART8 TX | Pad_1.0x1.4mm | — |
| TP314 | UART8 RX | Pad_1.0x1.4mm | — |
| TP315 | PWM5 | Pad_1.0x1.4mm | — |
| TP316 | PWM7 | Pad_1.0x1.4mm | — |
| TP317 | PWM9 | Pad_1.0x1.4mm | — |
| TP318 | PWM10 | Pad_1.0x1.4mm | — |
| TP319 | PWM11 | Pad_1.0x1.4mm | — |
| TP320 | 5V | Pad_1.0x1.4mm | — |
| TP321 | GND | Pad_1.0x1.4mm | — |
| TP322 | BZ+ | Pad_1.0x1.4mm | — |
| TP323 | BZ- | Pad_1.0x1.4mm | — |
| U301 | STM32H743VIH6 | TFBGA-100_8x8mm_Layout10x10_P0.8mm | — |
| U302 | SPL06-001 / DPS310 | Bosch_LGA-8_2x2.5mm_P0.65mm_ClockwisePinNumbering | C2684428 |
| U303 | BMI088 | Bosch_LGA-16_4.5x3mm_P0.5mm_LayoutBorder7x1y_ClockwisePinNumbering | — |
| Y301 | 8MHz 12pF X32258MOB4SI | Crystal_SMD_3225-4Pin_3.2x2.5mm | C2682775 |

**/Power/** (35 dílů)

| Ref | Hodnota | Pouzdro | LCSC |
| --- | --- | --- | --- |
| C18 | 4.7uF 50v | C_0805_2012Metric | C98192 |
| C19 | 4.7uF 50v | C_0805_2012Metric | C98192 |
| C20 | 100n | C_0201_0603Metric | C76939 |
| C21 | 100n | C_0201_0603Metric | C76939 |
| C23 | 22uF | C_0603_1608Metric | C2762594 |
| C24 | 22uF | C_0603_1608Metric | C2762594 |
| C25 | 4.7uF | C_0402_1005Metric | C23733 |
| C26 | 100n | C_0201_0603Metric | C76939 |
| C27 | 22uF | C_0402_1005Metric | C415703 |
| C28 | 22uF | C_0402_1005Metric | C415703 |
| C102 | C | C_0805_2012Metric | — |
| C103 | C | C_0805_2012Metric | — |
| C105 | C | C_1206_3216Metric | — |
| C106 | C | C_1206_3216Metric | — |
| D2 | DSK24 | SOD-123_L2.8-W1.8-LS3.7-RD | C64890 |
| D3 | DSK24 | SOD-123_L2.8-W1.8-LS3.7-RD | C64890 |
| D4 | LED_1_Green | LED_0402_1005Metric | C965793 |
| D5 | LED_1_Green | LED_0402_1005Metric | C965793 |
| D6 | LED_1_Green | LED_0402_1005Metric | C965793 |
| D7 | LED_1_Green | LED_0402_1005Metric | C965793 |
| L2 | XRTC303020D4R7MBCA | IND-SMD_L3.0-W3.0_AFE303020S | C39846837 |
| L3 | XRTC303020D4R7MBCA | IND-SMD_L3.0-W3.0_AFE303020S | C39846837 |
| R17 | 100k | R_0201_0603Metric | C270364 |
| R18 | 6.49k | R_0201_0603Metric | C2107920 |
| R19 | 100k | R_0201_0603Metric | C270364 |
| R20 | 13.7k | R_0201_0603Metric | C320695 |
| R21 | 7.5k | R_0201_0603Metric | C474437 |
| R22 | 2.4k | R_0201_0603Metric | C166281 |
| R23 | 6.49k | R_0201_0603Metric | C2107920 |
| R24 | 510R | R_0201_0603Metric | C57784 |
| TP30 | TestPoint | TestPoint_Pad_D1.0mm | — |
| U3 | LMR51430YFDDCR | SOT-23-6_L2.9-W1.6-P0.95-LS2.9-BL | C5219261 |
| U4 | LMR51430YFDDCR | SOT-23-6_L2.9-W1.6-P0.95-LS2.9-BL | C5219261 |
| U6 | LP5912-1.8DRVR | WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm_ThermalVias | C2876234 |
| U7 | TLV76733DRVR | WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm | C2848334 |

**/VTX a LD06/** (14 dílů)

| Ref | Hodnota | Pouzdro | LCSC |
| --- | --- | --- | --- |
| C201 | 4.7uF 50v | C_0805_2012Metric | C98192 |
| C202 | 100n | C_0201_0603Metric | C76939 |
| C203 | 22uF | C_0603_1608Metric | C2762594 |
| J201 | HD VTX | JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal | C160405 |
| JP202 | SBUS z DJI | SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm | — |
| L201 | XRTC303020D4R7MBCA | IND-SMD_L3.0-W3.0_AFE303020S | C39846837 |
| R201 | 100k | R_0201_0603Metric | C270364 |
| R202 | 6.49k | R_0201_0603Metric | C2107920 |
| R203 | 1k | R_0201_0603Metric | — |
| R204 | 100k | R_0201_0603Metric | C270364 |
| R206 | 0R | R_0201_0603Metric | — |
| TP201 | LD06 TX | Pad_1.0x1.4mm | — |
| TP202 | LD06 PWM | Pad_1.0x1.4mm | — |
| U201 | LMR51430YFDDCR | SOT-23-6_L2.9-W1.6-P0.95-LS2.9-BL | C5219261 |
<!-- /tabulky:kusovnik -->
| Z26 | [EasyEDA: TF-021B-H265 (C498185)](https://easyeda.com/component/da54a9e9dc5d41c3aeb4074d4ae8aee7), data přes `easyeda.com/api/products/C498185/components` | 8 signálových padů 1,2 × 0,7 mm po 1,1 mm |
| Z27 | ArduPilot `8b9ea70`: `hwdef/MicoAir743-AIO/README.md` a `MicoAir743-AIO_Ports_Connection.jpg` | konektory GPS (UART3+I2C1), DJI VTX, UART1+UART6, UART4 a pady AIO; pin 1 DJI = 12 V |

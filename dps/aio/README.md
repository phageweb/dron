# AIO H743 pro Pavo20 Pro

Jedna deska místo MicoAir H743 AIO: STM32H743 s ArduPilotem, 4× ESC s AM32,
napájení VTX a LD06. Vychází z [OpenAIO](https://github.com/OpenDrone-hw/OpenAIO)
`986ce1e` (CERN-OHL-S-2.0), viz [návrh](../docs/02_navrh.md) a [požadavky](../docs/04_pozadavky.md).

Stav **17. 10. 2026: schéma rev A bez jádra H743.** Převzaté a jisté části jsou
nakreslené, list `mcu_h743.kicad_sch` je prázdný a kreslí se ručně.

```sh
nix develop ./dps
kicad dps/aio/aio.kicad_pro
```

## Listy

| List | Soubor | Stav | Odkud |
| --- | --- | --- | --- |
| kořen | `aio.kicad_sch` | nakreslený | vstup baterie, shunt 0,2 mΩ + INA186A3 (proud všech ESC), obrys s pady U24, testovací body z OpenAIO |
| ESC1–ESC4 | `esc_channel.kicad_sch` | **převzatý beze změny** | OpenAIO = kanál OpenESC: AT32F421 + NSG2065Q + 6× DOY180N03T, AM32 |
| Power | `fc_power.kicad_sch` | **převzatý beze změny** | +10V pro budiče ESC (stálé), +5V 3 A, USB OR na +4v5, 3,3 V TLV76733 1 A, 1,8 V pro gyro |
| IMU | `fc_imu.kicad_sch` | **převzatý beze změny** | BMI270 na SPI, napájení 1,8 V |
| VTX a LD06 | `vtx.kicad_sch` | nový | spínaných 10 V pro HD VTX (kopie bucku U3), INA226, HD VTX SH1.0-6P s pinoutem DJI, LD06 ZH1.5-4P |
| MCU H743 | `mcu_h743.kicad_sch` | **prázdný, kreslíš ty** | rozhraní jsou hierarchické štítky, seznam toho, co sem patří, je přímo v listu |

Vypuštěné z OpenAIO, protože patří k RP2354A nebo je nepotřebujeme: `fc_rp2350a`
(jádro), `rx_esp32c3_sx1281` (přijímač, máme XR1 Nano), `fc_osd` (analogové OSD),
`fc_pads` (pady, konektor SH-6, baro BMP580), `fc_blackbox` (microSD na SPI).

Proč vlastní buck pro VTX: v OpenAIO napájí `+10V` zároveň budiče ESC i konektor
VTX. Kdyby se vypínal VTX, vypnuly by se i motory. Proto má VTX vlastní kopii
stejného bucku s EN z MCU.

## Deska

`aio.kicad_pcb` je layout OpenAIO beze změny: 35,4 × 35,4 mm, 8 vrstev HDI 1+6+1,
1 oz. Footprinty převzatých dílů jsou se schématem svázané přes UUID, takže
**schéma jde dál libovolně měnit** a do desky se propíše klávesou **F8** (Tools →
Update PCB from Schematic):

- Prvním F8 zmizí 145 footprintů z vypuštěných listů a přibude 16 dílů listu VTX.
  ESC, napájení a IMU zůstanou na místě i s vodiči.
- `kicad-cli pcb drc --schematic-parity aio.kicad_pcb` ukáže, co ještě nesedí.

## Kontrola

```sh
kicad-cli sch erc --severity-error dps/aio/aio.kicad_sch   # 34 chyb, všechny vysvětlené níž
```

| Počet | Co | Proč |
| ---: | --- | --- |
| 16 | `pin_not_driven` v ESC1–4 | převzaté z OpenAIO/OpenESC: piny kondenzátorů v jejich knihovně mají typ *input* |
| 16 | `label_dangling` | hierarchické štítky prázdného listu MCU H743 |
| 1 | `power_pin_not_driven` +5V_USB | USB konektor patří do listu MCU H743 |
| 1 | `pin_not_driven` SCL u INA226 | I2C řídí MCU H743 |

## Co je na tobě

V listu `mcu_h743.kicad_sch`:

- H743 v TFBGA-100 (STM32H743VIH6, jako MicoAir), okolí podle ST AN4938
- USB-C → `+5V_USB`
- baro, pull-upy I2C, logování (microSD jako MicoAir, nebo flash)
- druhá IMU ano/ne
- konektory GPS, MTF-02P, XR1 Nano, Bluetooth: pořadí pinů ověřit z dokumentace modulů
- dělič napětí baterie do ADC, `ESC_CURRENT` do ADC

A mimo list:

- **Obrys a díry.** `lib:AIO_outline` má rozteč děr 25,5 mm, Pavo20 potřebuje 26 × 26 ([P5](../docs/04_pozadavky.md)).
- **Layout jádra**, až bude list MCU nakreslený.
- **LCSC čísla** nových dílů v listu VTX: R203, R205, R206, U202 INA226, J202, JP201.

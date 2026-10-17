# AIO H743 pro Pavo20 Pro

Jedna deska místo MicoAir H743 AIO: STM32H743 s ArduPilotem, 4× ESC s AM32,
napájení VTX a LD06. Vychází z [OpenAIO](https://github.com/OpenDrone-hw/OpenAIO)
`986ce1e` (CERN-OHL-S-2.0), viz [návrh](../docs/02_navrh.md) a [požadavky](../docs/04_pozadavky.md).

Stav **17. 10. 2026: schéma rev A.** Převzaté a jisté části jsou nakreslené,
včetně jádra H743 (napájení podle AN4938, piny podle hwdefu MicoAiru), krystalu,
barometru, BMI088, microSD a konektorů periferií. RGB LED a bzučák jsou otevřené.

- **[NAVRH.md](./NAVRH.md)**: celý návrh, co je kde, proč a odkud, mapa pinů, kusovník.
- **[hwdef/](./hwdef/README.md)**: popis desky pro ArduPilot (firmware, bootloader, výchozí parametry).
- **Interaktivní schéma**: `nix develop ./dps -c python3 dps/aio/web/build.py` vytvoří
  `web/schema.html` (listy s klikacími bloky, texty v `web/obsah.py`).

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
| MCU H743 | `mcu_h743.kicad_sch` | nakreslený kromě RGB LED a bzučáku | H743 s blokováním, krystal, BOOT0, SWD, USB-C, dělič baterie, I2C2 s barometrem, BMI088, microSD. Ostatní piny mají štítky podle hwdefu |

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

- Prvním F8 zmizí 145 footprintů z vypuštěných listů a přibudou díly listů VTX a MCU.
  ESC, napájení a IMU zůstanou na místě i s vodiči.
- `kicad-cli pcb drc --schematic-parity aio.kicad_pcb` ukáže, co ještě nesedí.

## Kontrola

```sh
kicad-cli sch erc --severity-error dps/aio/aio.kicad_sch   # 18 chyb, všechny vysvětlené níž
```

| Počet | Co | Proč |
| ---: | --- | --- |
| 16 | `pin_not_driven` v ESC1–4 | převzaté z OpenAIO/OpenESC: piny kondenzátorů v jejich knihovně mají typ *input* |
| 1 | `pin_to_pin` VCAP E7–F8 | VCAP1 a VCAP2 spojené, jak doporučuje ST AN4938 |
| 1 | `pin_to_pin` SDO1–SDO2 BMI088 | oba výstupy na MISO, jak předepisuje datasheet BMI088 pro SPI |

## Co je na tobě

Seznam s důvody je v [NAVRH.md, kap. 8](./NAVRH.md#8-otevřené-otázky): RGB LED a
bzučák, obrys 36 × 36 s dírami 26 × 26, layout, LCSC čísla nových dílů a ověření
pinu 1 u konektorů GPS a MTF-02P. Krystal, baro, microSD, BMI088 a konektory
periferií jsou od 17. 10. nakreslené.

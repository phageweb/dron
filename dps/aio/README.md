# AIO H743 pro Pavo20 Pro

Jedna deska místo MicoAir H743 AIO: STM32H743 s ArduPilotem, 4× ESC s AM32,
napájení VTX a LD06. Vychází z [OpenAIO](https://github.com/OpenDrone-hw/OpenAIO)
`986ce1e` (CERN-OHL-S-2.0), viz [návrh](../docs/02_navrh.md) a [požadavky](../docs/04_pozadavky.md).

Stav **20. 10. 2026: schéma rev A, hlavní deska 22 nespojených / 0 DRC chyb.**
Probíhá přechod k opakovatelnému postupu a referenci MicoAir743v2-AIO-45A;
připravená varianta má samostatné schéma, desku a hwdef, viz
[AUTOMATIZACE.md](./AUTOMATIZACE.md). Převzaté a jisté části jsou nakreslené,
včetně jádra H743 (napájení podle AN4938, piny podle hwdefu MicoAiru), krystalu,
barometru, druhé IMU ICM-42688-P, microSD, konektorů periferií, RGB LED a spínače bzučáku.

- **[NAVRH.md](./NAVRH.md)**: celý návrh, co je kde, proč a odkud, mapa pinů, kusovník.
- **Schéma se generuje**: `nix develop ./dps -c python3 dps/aio/gen/gen_aio.py` přepíše všechny
  listy (`*.kicad_sch`) se stálými UUID. Schéma se proto mění v `gen/gen_aio.py`, ne v KiCadu.
  Desku, pravidla, projekt a `lib.pretty` generátor nepřepisuje, ty se upravují v KiCadu.
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
| VTX a LD06 | `vtx.kicad_sch` | nový | spínač TPS22810 z +10V pro HD VTX, HD VTX SH1.0-6P s pinoutem DJI, pady LD06 |
| MCU H743 | `mcu_h743.kicad_sch` | nakreslený | H743 s blokováním, krystal, BOOT0, SWD, USB-C, dělič baterie, I2C2 s barometrem, ICM-42688-P na SPI2, microSD, RGB LED, bzučák. Ostatní piny mají štítky podle hwdefu |

Vypuštěné z OpenAIO, protože patří k RP2354A nebo je nepotřebujeme: `fc_rp2350a`
(jádro), `rx_esp32c3_sx1281` (přijímač, máme XR1 Nano), `fc_osd` (analogové OSD),
`fc_pads` (pady, konektor SH-6, baro BMP580), `fc_blackbox` (microSD na SPI).

Proč spínač pro VTX: v OpenAIO napájí `+10V` zároveň budiče ESC i konektor
VTX. Kdyby se vypínala celá větev, vypnuly by se i motory. Proto VTX visí na `+10V`
až za spínačem TPS22810 s EN z MCU. Do 18. 10. tu byla kopie bucku U3, ale na desku
se nevešla.

## Deska

`aio.kicad_pcb` vychází z layoutu OpenAIO: 35,4 × 35,4 mm, 8 vrstev HDI 1+6+1, 1 oz.
Od 18. 10. odpovídá schématu: díly vypuštěných listů a jejich měď jsou pryč,
ESC, napájení, IMU a kořen zůstaly na místě i s vodiči. Nové díly mají **hrubé
rozmístění** (`aktualizuj_desku.sh --rozmisti --znovu`, pak `--vycisti`). Všechny čtyři
konektory periferií jako na MicoAir743-AIO jsou na hraně. Všech 82 nových dílů je na desce
(od 18. 10., kdy buck VTX nahradil spínač a BMI088 ICM-42688-P).
Po trasování zbývá 22 spojů ([NAVRH kap. 7](./NAVRH.md#7-deska-pcb)).

Schéma se do desky propisuje bez GUI (dělá totéž co F8, viz hlavička skriptu):

```sh
nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh       # --dry-run jen vypíše změny
kicad-cli pcb drc --schematic-parity --refill-zones dps/aio/aio.kicad_pcb
```

Před spuštěním zavři desku v KiCadu, jinak ji při uložení přepíše svou kopií.
Pro opakované kontroly a varianty použij `aktualizuj_desku.sh --auto`; pracuje na
kopii a uchová skutečné ERC/DRC reporty. Výsledky včetně známých výjimek jsou
popsané v [automatickém postupu](./AUTOMATIZACE.md).

## Kontrola

```sh
kicad-cli sch erc --severity-error dps/aio/aio.kicad_sch   # 18 chyb, všechny vysvětlené níž
```

| Počet | Co | Proč |
| ---: | --- | --- |
| 16 | `pin_not_driven` v ESC1–4 | převzaté z OpenAIO/OpenESC: piny kondenzátorů v jejich knihovně mají typ *input* |
| 1 | `pin_to_pin` VCAP E7–F8 | VCAP1 a VCAP2 spojené, jak doporučuje ST AN4938 |
| 1 | `pin_to_pin` QOD–VOUT U201 | QOD spojený s VOUT, aby se výstup po vypnutí vybil, podle datasheetu TPS22810 |

## Co je na tobě

Seznam s důvody je v [NAVRH.md, kap. 8](./NAVRH.md#8-otevřené-otázky): layout,
LCSC čísla nových dílů a ověření pinu 1 u konektorů GPS a MTF-02P. Schéma je od
17. 10. nakreslené celé. Obrys 35,4 mm a díry 25,5 zůstávají z OpenAIO (18. 10.),
oválné díry na 26 by zasáhly prokovy přívodu baterie.

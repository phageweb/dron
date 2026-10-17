# Co převezmeme, opravíme a vylepšíme

Navazuje na [rešerši](./01_reserse_otevrenych_projektu.md). Navrhuje **dvě
desky v pořadí**, protože každá řeší jinou věc a první z nich je potřeba hned,
zatímco druhá je optimalizace. Co přesně od vlastní desky chceme a odkud vzít
každý obvod, je v [Požadavcích](./04_pozadavky.md).

**ESP32 na desce nebude** (rozhodnuto 12. 10. 2026). Wi-Fi z ESP32 má na tenhle
účel malý dosah. Sken z LD06 jde na zem přes OSD Walksnailu, který má dosah
videa, viz [Test linky pro sken](../../spec/realna_stavba_dronu/15_test_linky_skenu.md);
záloha je přikoupený sériový Bluetooth na volném UARTu.

| | Deska 1: **napájení** | Deska 2: **AIO H743** |
| --- | --- | --- |
| Co to je | přídavná destička k MicoAir H743: napájení VTX a LD06, konektor LD06 | vlastní AIO místo MicoAir: H743 + 4× AM32 ESC + napájení z desky 1 |
| Řeší | 12V BEC u stropu Lite+; rozběh LD06 na stejném BEC jako RX; kabel ZH1.5; měření spotřeby VTX | integraci, hmotnost, plochu; nepoužitý analog OSD |
| Vychází z | OpenFC-Lite-Mini (buck LMR51430), datasheet INA226 | OpenAIO (skladba listů), OpenESC-20x20 (kanál ESC), `MicoAir743v2` hwdef, Kestrel H7 (okolí H743) |
| Vrstvy | 2–4 | 8 HDI 1+6+1 jako OpenAIO (1 oz na všech vrstvách, 1,0 mm); OpenESC a OpenFC-Lite-Mini mají 6 |
| Riziko | malé — nic na ní nedrží stroj ve vzduchu | velké — BGA, výkon, první revize skoro jistě nepoletí |
| Kdy | ~~samostatně se nevyrobí~~ (17. 10.): je to list napájení v AIO | hned po rozhodnutích v [požadavcích](./04_pozadavky.md), MicoAir mezitím létá |

## Deska 1 — napájení

### Proč právě tohle

Na dnešní stavbě jsou otevřené tři věci, které jsou čistě napájecí a dají se
vyřešit bez zásahu do FC: Lite+ visí na 12V BEC jen 0,6 V pod svým stropem
12,6 V, LD06 se 300 mA rozběhem sdílí 5V BEC s přijímačem a flow senzorem, a
kabel z konektoru ZH1.5 na desku se musí bastlit. Deska 1 je zároveň první
kus desky 2 — její schéma se tam přenese jako list.

### Zapojení

```text
VBAT 4S ─┬─► buck 5 V (LMR51430) ─► LD06 P5V        (300 mA rozběh, 180 mA provoz)
         └─► buck 10 V / 3 A (LMR51430), EN z PINIO FC ─► shunt + INA226 ─► HD VTX SH1.0-6P   (Lite+ strop 12,6 V; dimenzováno na O3/O4)

LD06 TX ─► ZH1.5 na desce ─► FC UART5 RX ─► AP_Proximity_LD06 + Lua skript pro OSD linku
INA226  ─► I2C FC (BATT2, INA2xx)
```

### Co přebíráme

- **Buck LMR51430 z OpenFC-Lite-Mini** — 36 V vstup, 3 A, tam použitý dvakrát
  (10 V spínaný pro VTX a 5 V stálý). Přesně ty dvě větve potřebujeme, **beze
  změny děliče**: 10 V a 3 A stačí na DJI O3/O4 (12–16 W, tedy 1,6 A), takže
  se nemusí čekat na změřenou spotřebu Lite+.
- **INA226** podle doporučeného zapojení z datasheetu TI. ArduPilot ho čte jako
  druhý monitor baterie (INA2xx na I2C), takže FC vidí proud VTX bez nového kódu.

### Co tím opravíme proti dnešní stavbě

| Dnes | S deskou 1 |
| --- | --- |
| Lite+ na 12V BEC, 0,6 V pod stropem | vlastní 10V větev, 2,6 V rezerva, VTX jde vypnout na stole; utáhne i DJI O3/O4 |
| LD06 (300 mA rozběh) na stejném 5V BEC jako RX a flow | vlastní 5V větev, rozběh lidaru nesráží přijímač |
| Kabel ZH1.5T-4P → JST-SH se musí bastlit | konektor ZH1.5 přímo na desce |
| Spotřeba Lite+ nezměřená | shunt + INA226 na 10V větvi, čte FC |

Poslední řádek zavírá položku „Nezměřeno" z
[kusovníku](../../spec/realna_stavba_dronu/11_kusovnik_pavo20.md) — největší
spotřebič mimo motory, který dnes nikdo nezná.

### Na co si dát pozor

- **Hmotnost.** Cíl ≤ 1,5 g osazená deska bez kabelů. Do kusovníku přibude,
  a 13,36 g na kabeláž je odhad, ze kterého něco ubude (adaptér kabelu LD06).
- **Spínání VTX** potřebuje volný GPIO na MicoAiru jako PINIO — najít v hwdefu
  a na padech; když žádný není, EN natvrdo na vstup a VTX bez vypínání.
- **Pin PWM u LD06** — podle datasheetu buď uzemnit, nebo vést na pad pro
  řízení otáček. Rozhodnout při kreslení, s datasheetem v ruce.

### Jak se ověří bez dronu

Na stole z laboratorního zdroje na 17,4 V: 10V větev do odporové zátěže 2 A (O3/O4 ve špičce),
5V větev s D500 a `lidar/lidar_web.py` přes CP2102 — sken se nesmí rozpadat ani
při rozběhu. INA226 přes USB-I2C převodník nebo rovnou na MicoAiru proti
multimetru. Dron k tomu není potřeba.

## Deska 2 — vlastní AIO H743

### Skladba

Převzít **architekturu OpenAIO** — kořenové schéma, které skládá ověřené listy —
a vyměnit jádro:

| List | Odkud | Změna |
| --- | --- | --- |
| `esc_channel` ×4 | OpenESC-20x20 `ESC.kicad_sch` | **žádná**. AT32F421 + NSG2065Q + 6× DOY180N03T, AM32. Na 4S LiHV (17,4 V) je 30V MOSFET s rezervou. |
| proudové čidlo | OpenESC-20x20 | INA186 včetně RC filtru z Rev3.2 |
| jádro FC | **nové**: STM32H743, okolí podle Kestrel H7, pinout podle `MicoAir743v2` | místo OpenFC-Core (RP2350) |
| napájení VTX a LD06 | deska 1 | integrované |
| napájení | OpenFC-Lite-Mini `power` | 5 V stálý, 10 V spínaný přes PINIO |
| RX | — | **nepřebírat** OpenRX-Lite: XR1 Nano je dvoupásmový, integrovaný SX1281 by nás zamkl na 2,4 GHz |

### Co opravíme proti OpenAIO

- **RP2350 → STM32H743.** Jediný důvod, proč OpenAIO nejde vzít celé.
  ArduPilot na RP2350 je otevřený PR s 10× pomalými doubly; až se mergne a
  ověří, stojí za to se k OpenFC-Core vrátit, protože by se převzalo všechno.
- ~~Rozteč 25,5 → 26 × 26~~: zůstává 25,5, M2 na rámu 26 × 26 projde dírou ⌀3 s vůlí 0,15 mm.
  Oválné díry by zasáhly prokovy přívodu baterie ([AIO, NAVRH kap. 4.1](../aio/NAVRH.md)).
- **Bez 2,4GHz RX na desce**, viz výše.

### Co opravíme proti MicoAir H743 V2

- **Bez AT7456E.** Walksnail je digitální a OSD dostává přes MSP DisplayPort;
  analogový OSD čip na MicoAiru je mrtvá váha a SPI1 navíc.
- **10V větev místo 12 V** pro VTX, spínaná, dimenzovaná na DJI O3/O4.
- **Konektor LD06 na desce**, ne na kabelech.
- **ESC dimenzovaný blíž potřebě** je lákavé (motor bere 10,2 A špičkově,
  MicoAir má 45 A), ale OpenESC kanál už je na minimu — 6 MOSFETů je holý
  trojfázový můstek, dva na fázi, bez paralelních kusů. Ušetřit se dá jen menším
  pouzdrem MOSFETu, a to je změna ověřeného návrhu. **Nedělat v rev A.**

### Jádro H743 — rozhodnutí, která tu zůstávají otevřená

| Otázka | Možnosti | Kloníme se k |
| --- | --- | --- |
| Pouzdro | LQFP-100 (16 × 16 s vývody, ručně opravitelné) / TFBGA-100 8 × 8 (jako LC Stamp) | TFBGA-100, jinak se na ~34 mm se 4 ESC nevejde; osazuje JLC |
| IMU | BMI270 / ICM-42688-P / BMI088 | víceznačná LGA-14 ploška z OpenFC-Lite-Mini — IMU jde vyměnit bez změny layoutu |
| Baro | SPL06 (jako MicoAir) / DPS310 / BMP280 | to, co bude na LCSC skladem; ArduPilot umí všechny |
| Log | SDMMC 4bit / SPI flash | microSD na SDMMC1 jako MicoAir, piny z hwdef |

### Firmware

Vlastní `hwdef.dat` odvozený z `MicoAir743v2` (stejné MCU, většina pinů
převzatá), uložený vedle desky v `dps/` a sestavený přes
[firmware flake](../../firmware/README.md). Board ID jiný než MicoAir, aby
uploader nikdy nenahrál cizí firmware. Simulace se nemění — SITL o desce neví.

### Rizika

- Šestivrstvá deska s BGA a 2 oz mědí: první revize skoro jistě poletí až
  ve druhé. Počítat se dvěma objednávkami.
- **Teplo v ductu.** OpenAIO ho sám vede jako nevyřešenou otázku.
- Je to hodně práce za věc, která dnes **nic neblokuje**. Deska 2 je
  optimalizace a učení, deska 1 je oprava.

## ERC a DRC převzatých projektů

`nix run ./dps#check` (KiCad 10.0.7) naklonuje OpenESC-20x20 `dba7828`,
OpenFC-Lite-Mini `d8a10ee`, OpenAIO `986ce1e` a KiCad-Library `a0173b7` do
`external/opendrone` a projede je. 17. 10. 2026:

| Projekt | Vrstvy | ERC chyby | DRC chyby (se zalitím zón) | Co to je |
| --- | ---: | ---: | ---: | --- |
| OpenESC-20x20 | 6 | 28 | 0 | `pin_not_driven` na kondenzátorech s piny typovanými jako vstup, chybějící PWR_FLAG — typování v knihovně, ne chyba zapojení |
| OpenFC-Lite-Mini | 6 | 8 | 3 | ERC: chybějící PWR_FLAG (+4v5, +10V, +1.8V_GYRO). DRC: L4 (+1.1V) 0,01 mm od NPTH díry USB-C, dvě vůle 0,09 mm — **vše v okolí RP2350/USB, které nepřebíráme**; list `power` je čistý |
| OpenAIO | 8 | 31 | 2 | ERC: totéž typování v kanálech ESC, navíc `hier_label_mismatch` a 3× `bus_to_net_conflict`. DRC: +5V u J30 nedotažený na L8 — skutečná chyba layoutu |

Varování (stovky `pin_to_pin`, `footprint_symbol_field_mismatch`,
`solder_mask_bridge`) jsou hlavně neshody knihovny a kosmetika. Číst je až
ve chvíli, kdy se převezme konkrétní list. **Závěr: list `power` z OpenFC-Lite-Mini
a list ESC z OpenESC jdou převzít tak, jak jsou.** OpenAIO se nepřebírá, je to jen
vzor skladby listů a má v layoutu otevřenou chybu.

## Licence

OpenDrone je **CERN-OHL-S-2.0**, silně reciproční: deska, která převezme jejich
list (OpenESC kanál, napájení z OpenFC-Lite-Mini), musí být při šíření zveřejněná se zdrojáky
pod stejnou licencí. Pro tenhle projekt to nevadí, ale do `dps/` pak patří
`LICENSE` a v každé desce uvedený původ převzatých listů.

## Pořadí práce

1. ~~KiCad 10 do vlastního flaku `dps/`~~ — hotovo 17. 10.: `nix develop ./dps`.
2. ~~Naklonovat OpenDrone a projít ERC/DRC~~ — hotovo 17. 10.: `nix run ./dps#check`,
   výsledek níž.
**Změna 17. 10. 2026: všechno na jedné desce.** Deska 1 se jako samostatná
destička nevyrobí. Její schéma je list `vtx.kicad_sch` v [aio](../aio/README.md), list napájení
pro AIO (deska 2) a pokračuje se rovnou AIO.

3. ~~Napájení 10 V / 5 V / INA226~~ — schéma rev A, 17. 10., jako budoucí list AIO.
4. Rozhodnutí před kreslením AIO ([požadavky, kap. 4](./04_pozadavky.md#4-co-je-potřeba-rozhodnout-před-kreslením)):
   pouzdro H743 podle hrubého rozmístění na 36 mm, jedna nebo dvě IMU, SD nebo flash.
5. ~~Kořenové schéma AIO: 4× ESC, napájení, IMU, VTX~~ (17. 10., [aio](../aio/README.md)). Zbývá jádro H743, kreslí se ručně.
6. Layout, JLC s osazením, oživení na stole se zdrojem a D500, pak let.
7. Do té doby létá MicoAir. Měření 12V BEC, rozběhu D500 a spotřeby Lite+ z
   [testu linky](../../spec/realna_stavba_dronu/15_test_linky_skenu.md) dají čísla pro dimenzování AIO.

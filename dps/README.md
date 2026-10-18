# DPS — vlastní desky plošných spojů

Návrhy vlastních DPS pro stavbu [Pavo20 Pro](../spec/realna_stavba_dronu/10_pavo20.md).
Kreslí se v **KiCadu**, a pokud to jde, nekreslí se od nuly: vychází se
z otevřených projektů, které už někdo vyrobil a létal.

Stav **17. 10. 2026**: rešerše a požadavky hotové. KiCad je ve flaku
(`nix develop ./dps`), projekty OpenDrone jsou naklonované a prověřené přes ERC/DRC
(`nix run ./dps#check`, výsledek v [návrhu](./docs/02_navrh.md#erc-a-drc-převzatých-projektů)).
**Všechno na jedné desce** (rozhodnuto 17. 10.): vlastní AIO s H743 místo MicoAiru.
**Schéma rev A je v [aio](./aio/README.md)**: převzaté listy OpenAIO (4× ESC,
napájení, IMU), nový list VTX a LD06 a prázdný list pro jádro H743, které se
kreslí ručně. Deska je layout OpenAIO svázaný se schématem a mění se klávesou F8.

Větev pro VTX je **dimenzovaná na DJI O3/O4** (10 V za spínačem 3 A, 12–16 W), ne na
spotřebu Lite+, kterou nikdo nezměřil. Konektor HD VTX má pinout DJI.

| Dokument | O čem |
| --- | --- |
| [Rešerše otevřených projektů](./docs/01_reserse_otevrenych_projektu.md) | co existuje v KiCadu, co z toho je vyrobené a létalo, a co na tom poběží ArduPilot |
| [Co převezmeme, opravíme a vylepšíme](./docs/02_navrh.md) | dvě desky, v jakém pořadí, z čeho každá vychází a co se na ní mění |
| [Požadavky a obvody](./docs/04_pozadavky.md) | co od vlastní desky chceme, z jakých bloků se skládá a kde vzít zapojení každého |
| [Zdroje](./docs/03_zdroje.md) | odkazy, ze kterých rešerše čerpá |
| [AIO](./aio/README.md) | projekt KiCad: listy, co je převzaté, co je nakreslené a co zbývá |

**ESP32 na desce nebude** — Wi-Fi má malý dosah. Sken z LD06 jde na zem přes
OSD Walksnailu, viz
[Test linky pro sken](../spec/realna_stavba_dronu/15_test_linky_skenu.md);
záloha je přikoupený Bluetooth modul na volném UARTu.

## Závěr v jedné větě

**Cíl je jedna vlastní AIO s H743, která nahradí MicoAir.** Napájení pro VTX
(10 V, dimenzované na DJI O3/O4) a LD06 je nakreslené a ESC se převezme z
[OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20), které je
vyrobené a v prodeji. Nové je jen jádro H743, s pinoutem podle `MicoAir743v2`.

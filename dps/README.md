# DPS — vlastní desky plošných spojů

Návrhy vlastních DPS pro stavbu [Pavo20 Pro](../spec/realna_stavba_dronu/10_pavo20.md).
Kreslí se v **KiCadu**, a pokud to jde, nekreslí se od nuly: vychází se
z otevřených projektů, které už někdo vyrobil a létal.

Stav **12. 10. 2026**: rešerše a požadavky, žádná deska není nakreslená.

| Dokument | O čem |
| --- | --- |
| [Rešerše otevřených projektů](./docs/01_reserse_otevrenych_projektu.md) | co existuje v KiCadu, co z toho je vyrobené a létalo, a co na tom poběží ArduPilot |
| [Co převezmeme, opravíme a vylepšíme](./docs/02_navrh.md) | dvě desky, v jakém pořadí, z čeho každá vychází a co se na ní mění |
| [Požadavky a obvody](./docs/04_pozadavky.md) | co od vlastní desky chceme, z jakých bloků se skládá a kde vzít zapojení každého |
| [Zdroje](./docs/03_zdroje.md) | odkazy, ze kterých rešerše čerpá |

**ESP32 na desce nebude** — Wi-Fi má malý dosah. Sken z LD06 jde na zem přes
OSD Walksnailu, viz
[Test linky pro sken](../spec/realna_stavba_dronu/15_test_linky_skenu.md);
záloha je přikoupený Bluetooth modul na volném UARTu.

## Závěr v jedné větě

**Cíl je vlastní AIO s H743, a jako první krok k němu malá napájecí deska
k MicoAiru.** Ta řeší, co je dnes na stavbě skutečně otevřené — 12V BEC je jen
0,6 V pod stropem Walksnailu, LD06 sdílí 5V BEC s přijímačem a spotřebu VTX
nikdo nezměřil — a stojí na bucku ověřeném v
[OpenFC-Lite-Mini](https://github.com/OpenDrone-hw/OpenFC-Lite-Mini).
Vlastní AIO s H743 přijde až potom, a jeho ESC část se převezme z
[OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20), které je
vyrobené a v prodeji.

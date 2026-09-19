# Kudy se sken dostane do ROS 2

Kusovník nemá palubní počítač a [nález vedle](./07_alternativy_a_zkusenosti.md)
říká proč to vadí: **AP_DDS nepublikuje žádný LaserScan ani proximity topic**,
takže na skutečném železe se sken z LD06 nemá do ROS jak dostat. V simulaci to
není vidět, protože tam scan teče z Gazeba rovnou do ROS přes `ros_gz_bridge`.

Tenhle dokument ty cesty ven proměřuje. Ověřováno **13. 9. 2026** proti
`external/ardupilot` ve stavu `8b9ea70` (2026-09-09).

## Co je ověřené ve zdrojáku, ne v dokumentaci

Topic table `libraries/AP_DDS/AP_DDS_Topic_Table.h` má 19 položek: `time`,
`navsat`, `tf_static`, `battery`, `imu/experimental/data`, `pose/filtered`,
`twist/filtered`, `airspeed`, `rc`, `geopose/filtered`, `goal_lla`, `clock`,
`/clock`, `gps_global_origin/filtered`, `status`, `joy`, `tf`, `cmd_vel`,
`cmd_gps_pose`. **Žádný scan, žádná proximity, žádný range.** Grep na
`LaserScan|Proximity|PointCloud|Range` v celém `AP_DDS` vrací čtyři zásahy a
všechny čtyři jsou komentáře `// @Range:` u parametrů.

Vygenerované IDL typy jsou jen `BatteryState`, `Imu`, `Joy`, `NavSatFix`,
`NavSatStatus`. `LaserScan.idl` mezi nimi není.

Autopilot přitom **LD06 nativně umí** — `libraries/AP_Proximity/AP_Proximity_LD06.cpp`
existuje a `spec` s ním počítá. Ten senzor se tedy na palubě přečte. Problém
není čtení, problém je export.

## Proč fork AP_DDS ten problém neřeší

Nabízí se dopsat do AP_DDS publisher, který vezme, co už `AP_Proximity` má.
Jenže to, co má, je tohle:

```
AP_Proximity_Boundary_3D.h:33:  #define PROXIMITY_MAX_DIRECTION 8
AP_Proximity_Boundary_3D.h:22:  #define PROXIMITY_NUM_SECTORS   8
AP_Proximity_Boundary_3D.h:137: static_assert(PROXIMITY_NUM_SECTORS == 8, ...)
```

`get_horizontal_distances()` vrací **osm vzdáleností po 45 stupních**, ne sken.
Není to laditelná konstanta — je na ni `static_assert`.

Z 4,5 kHz dat z LD06 by tedy přes AP_DDS prolezlo osm čísel. To stačí na dnešní
reaktivní demo, které se ptá „je něco blíž než 1,40 m v koridoru", ale **končí
tím SLAM Toolbox** — a kvůli SLAM byl LD06 podle
[rozhodnutí o senzoru](../../workflow/decisions.md) vybraný. Fork by musel
sáhnout pod `AP_Proximity` přímo na backend a vést si vlastní buffer celé
otáčky; to už není publisher, to je druhý ovladač uvnitř autopilota.

**Fork se tím pádem jako cesta k SLAM ruší.** Zůstává jako levná cesta
k reaktivnímu demu, pokud by se SLAM vzdalo.

## Čtvrtá cesta, kterou backlog nepočítal

Backlog nabízí tři možnosti: palubní počítač, fork, nebo ROS na zemi. Ta třetí
má ale skrytý předpoklad — **něco na palubě musí ten surový sken poslat dolů**,
a autopilot umí poslat jen těch osm sektorů. Takže „ROS na zemi" bez dalšího
železa nefunguje.

Jenže další železo tam už je: **video jednotka je Linux.** OpenIPC běží na
SigmaStar SoC, má UARTy a přímo pro tenhle vzorec existují hotové nástroje:

- **`OpenIPC/mavfwd`** — „simplest MAVLink serial port to UDP forwarder in pure C";
- **`OpenIPC/msposd`** se takhle běžně spouští:
  `msposd --master /dev/ttyS2 --baudrate 115200 --out 127.0.0.1:14550`.

Podporované baudy OpenIPC zahrnují **230400**, což je přesně rychlost LD06.
Jde tedy o to samé schéma, jen s jiným zdrojem na UARTu a ROS uzlem na druhém
konci místo OSD.

**Váhový a peněžní rozpočet téhle varianty je nula** — jednotka je v kusovníku
tak jako tak.

### Vejde se to do linky

| Veličina | Hodnota |
| --- | ---: |
| LD06: 4 500 měření/s, 12 bodů v paketu po 47 B | 375 paketů/s |
| Užitečná data | **141 kbit/s** |
| Na lince UART 8N1 (10 bit/B) | 176 kbit/s |
| wfb-ng při výchozím MCS1, 20 MHz, half-duplex | ~7 Mbit/s obousměrně |
| Z toho video 720p | ~4 Mbit/s |
| Sken jako podíl celé linky | **2,0 %** |
| Sken jako podíl toho, co zbývá po videu | **4,7 %** |

Backlog odhadoval 108 kbit/s; skutečné číslo z formátu paketu LD06 je **141 kbit/s**.
Pořád to sedí, ale rezerva je menší, než se psalo — linka je ~7 Mbit/s pro
**oba směry dohromady**, ne 8 Mbit/s dolů.

Jeden detail rozhoduje o tom, jestli to poletí: wfb-ng má i IPv4 tunel, a jeho
vlastní dokumentace říká, že tunel má horší coding rate a **patří na SSH, ne na
datové toky** — na ty se mají použít syrové UDP streamy. `mavfwd` posílá UDP,
což je ta správná strana téhle hranice. Kdo by sken protlačil tunelem, narazí.

## Čtyři cesty vedle sebe

| Cesta | Gramy | Peníze | Dá SLAM? | Co ji drží zpátky |
| --- | ---: | ---: | :-: | --- |
| **Palubní počítač** | +10 až +30 | +1 000 až 2 500 Kč | ano | mimo hmotnostní rozpočet, viz níž; Pi Zero 2 W má 512 MB a to je na ROS 2 Jazzy málo |
| **Fork AP_DDS** | 0 | 0 | **ne** | osm sektorů po 45°, `static_assert` |
| **ROS na zemi, sken přes video jednotku** | **0** | **0** | ano | neověřeno na železe; smyčka vyhýbání jde přes rádio |
| ROS na zemi bez čehokoli dalšího | 0 | 0 | ne | sken se z paluby nemá jak dostat |

## Hmotnostní rozpočet to rozhoduje za nás

Podle [tabulky komponent](./03_komponenty.md) je sestava s Wyvernem
**227,2 g s baterií a bez lidaru**. LD06 váží kolem 42 g, a CAD cílí na **294 g**
— tedy lidar plus držáky a kabeláž ten rozdíl přesně vyčerpají. **V 294 g není
na palubní počítač místo.**

Pi Zero 2 W váží 10 g, ale má 512 MB RAM a zdroje se shodují, že na ROS 2 Jazzy
s ovladačem lidaru se sahá po Pi 4 nebo 5. Deska, která to skutečně utáhne
(Radxa Zero 3W, Orange Pi Zero 2W), je i s chlazením spíš 20 až 30 g. To je
**víc, než kolik dělá celý rozdíl mezi Wyvernem a RunCamem** (11 g), o který se
v kusovníku vede řeč.

Palubní počítač tedy není přílepek k rozpočtu. Je to přepočet celé sestavy:
tah/váha, doba letu na 750 mAh i gainy, které
[backlog](../../workflow/backlog.md) už jednou váže na 0,306 kg.

## Co z toho plyne

1. **Fork AP_DDS škrtnout jako cestu k SLAM.** Zůstává jako záloha pro reaktivní
   demo, kdyby všechno ostatní padlo.
2. **Nejdřív vyzkoušet přeposílání přes video jednotku.** Stojí nula gramů a nula
   korun, a je to jediná varianta, která nechává hmotnostní rozpočet na pokoji.
   Otevřené je, jestli má zvolená jednotka volný UART — u Wyvernu se to stejně
   musí ověřit kvůli spotřebě a hloubce v držáku.
3. **Palubní počítač neobjednávat, dokud bod 2 nepadne.** Kdyby padl, je to
   nákup **a** přepočet hmotnosti, ne jen položka do košíku.
4. **Bezpečnostní výhrada k oběma pozemním variantám:** smyčka vyhýbání se
   překlopí na zem a přes rádio. Stroj má sice hlídač zvětralého skenu, ale
   výpadek linky znamená, že se nikdo nedívá. Pro let v bytě na 1 m to je
   přijatelné jen s tím hlídačem zapnutým a s krátkým timeoutem.

## Co ověřené není

- Jestli má EMAX Wyvern Link Alpha (ani RunCam WiFiLink 2) volný UART vyvedený
  a přístupný v sestaveném rámu.
- Jestli `mavfwd` nebo `msposd` snesou 230400 baud trvale vedle enkodéru videa,
  a co to udělá s teplotou jednotky, která se podle fóra i tak přehřívá.
- Jestli OpenIPC build pro zvolenou jednotku ty nástroje vůbec obsahuje —
  OpenIPC používá jen podmnožinu wfb-ng.
- Kolik LD06 skutečně váží. Číslo 42 g je z katalogu, ne z váhy.

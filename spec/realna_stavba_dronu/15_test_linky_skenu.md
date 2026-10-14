# Test linky pro sken — Bluetooth a OSD

Kudy dostat sken z LD06 na zem **jen se současnými čipy**, bez nové desky a bez
palubního počítače. Proč je to potřeba, je v
[Kudy se sken dostane do ROS 2](./09_kudy_do_ros.md#dodatek-7-10-2026-walksnail-a-současné-čipy).
Tenhle dokument je plán testu: co se měří, čím, a co kam zapojit.

Sepsáno **7. 10. 2026**. Všechna čísla propustnosti jsou odhady, které má test
nahradit. Proběhla jen fáze 0, a ta kanál A na naší desce **zavřela**: MicoAir
H743 V2 **AIO** Bluetooth nemá — viz [výsledek fáze 0](#fáze-0--je-tam-bluetooth-hotovo-7-10-2026-ne).
Hlavní kanál je teď B, OSD.

## Dva kanály, jeden skript

Oba kanály staví na tom, že **H743 sken přečte sám** a na zem pošle zmenšený.
Na surových 176 kbit/s nemá ani jeden kanál; na sken po 2,5° stačí zlomek.

```text
LD06 ─UART5─► H743, Lua skript ─┬─► AP_Proximity (Scripting backend, 8 sektorů, vyhýbání na palubě)
                                ├─► A: MAVLink OBSTACLE_DISTANCE ─► UART8 ─► Bluetooth ─► notebook
                                └─► B: znaky v OSD ─► UART2 ─► Lite+ ─rádio─► VRX Pro ─UVC─► notebook
                                                                                  │
                                         zem: dekodér ─► /scan (LaserScan) ─► SLAM Toolbox
```

| | A: Bluetooth na MicoAiru | B: OSD přes Walksnail |
| --- | --- | --- |
| Hardware | **na AIO není**; jen jako přikoupený modul (HC-05 apod.) na pady UART8 | Lite+ a VRX Pro, oba koupené |
| Směr | **obousměrný** — i telemetrie, i povely | jen dolů |
| Formát | standardní `OBSTACLE_DISTANCE`, 72 vzdáleností v cm | vlastní kódování do znaků OSD |
| Dosah | Bluetooth, jednotky až nízké desítky metrů | jako video |
| Propustnost | do ~90 kbit/s z UARTu; skutečnost neznámá | odhad 5–10 kbit/s |
| Na čem to padne | nový díl, +1–2 g; dosah v bytě | jestli VRX dává OSD do UVC, jak často ho překresluje |
| 4.7.1 stačí? | ano: `mavlink:send_chan`, `serial:find_serial`, `readstring` ověřené v `bindings.desc` 4.7.1 | ne celé: `osd:write` je až v masteru; na 4.7.1 musí Lua mluvit MSP k VTX sama |

**B je teď první**, protože jako jediný jede na koupených dílech. A zůstává
jako levná varianta s přikoupeným modulem: je obousměrný a používá standardní
zprávu, ale už to není „nula dílů".

### Kolik dat to je

| Varianta skenu | Bitů na otáčku | Při 10 Hz |
| --- | ---: | ---: |
| `OBSTACLE_DISTANCE`, 72 × 5°, jedna zpráva ~180 B | 1 440 | **14 kbit/s** |
| `OBSTACLE_DISTANCE`, 144 × 2,5°, dvě zprávy | 2 880 | **29 kbit/s** |
| `OBSTACLE_DISTANCE`, 360 × 1°, pět zpráv | 7 200 | 72 kbit/s |
| OSD, 144 × 2,5° po 9 bitech + hlavička | ~1 330 | 13 kbit/s |

Pro OSD: ArduPilot hlásí HD plátno **50 × 18** (`msp_process_out_osd_canvas`).
Pruh dvou řádků je 100 znaků; s abecedou 64 znaků po 6 bitech a 32 bity na
pořadové číslo a CRC zbude ~560 užitečných bitů na snímek. Při 10 překresleních
za sekundu je to **~4 skeny/s** po 2,5°, se čtyřmi řádky ~8.

## Fáze 0 — je tam Bluetooth? Hotovo 7. 10. 2026: ne

**Výsledek.** AIO na USB, ArduCopter 4.7.1 (`dbe79216`), `SERIAL8_PROTOCOL 2`,
`SERIAL8_BAUD 115`. Dvě hledání `bluetoothctl` po 40–45 s, jedno se stisknutým
BOOT: nic s názvem MicoAir a nic se signálem, jaký by měla deska vedle
notebooku. Nejsilnější neznámé zařízení (−56 dBm) neslo výrobce 0x004c, Apple.

Proč: Bluetooth na UART8 má **MicoAir743v2 FC**, ne AIO. AIO sdílí jen firmware
target, odtud `SERIAL8` přednastavený na MAVLink. Stránka výrobce a manuál AIO
uvádějí jediné tlačítko BOOT0 a UART8 **vyvedený na pady** TX8/RX8 (PE1/PE0),
bez Bluetooth modulu. Tvrzení prodejce, že ho AIO má, je chyba — a byla to
chyba i v první verzi tohohle dokumentu.

Co z toho zbývá: pady TX8/RX8 s MAVLink2 na 115200 jsou připravené pro
**přikoupený** sériový Bluetooth modul. Postup níž platí pro něj.

Původní postup:

1. Připojit USB. **BOOT nedržet při zapojování** — to je DFU režim.
2. Až deska naběhne, podržet BOOT asi 2 s — tím se podle manuálu MicoAir
   Bluetooth zapíná [dok].
3. `bluetoothctl scan on` a hledat `MicoAir743v2-xxxxxx`.
4. Zapsat: našlo se? Klasický Bluetooth, nebo BLE? (`bluetoothctl info <MAC>` —
   UUID `00001101-…` je SPP; služba Nordic UART `6e400001-…` je BLE.)

| Výsledek | Dál |
| --- | --- |
| klasický SPP | `rfcomm connect /dev/rfcomm0 <MAC> 1`, pak `mavproxy.py --master=/dev/rfcomm0,115200` |
| BLE | most přes `bleak` do pty; pomalejší, počítat spíš s 14 kbit/s variantou |
| nic | modul není — **to je náš výsledek** |

## Fáze 1 — propustnost Bluetooth (bez lidaru)

Jen s přikoupeným modulem na padech TX8/RX8. Skript na notebooku připojí MAVLink přes BT a:

- nastaví `SR8_*` streamy postupně výš (`SR8_RAW_SENS`, `SR8_EXTRA1`–`3` na
  10, 25, 50 Hz) a měří přijaté bajty/s a mezery v `seq` MAVLinku;
- zjistí **strop**: rychlost, kdy přestanou chodit všechny zprávy;
- s deskou na stole chodí po bytě a zapisuje ztráty a latenci (`TIMESYNC`)
  v každé místnosti.

**Projde, když:** ≥ 30 kbit/s užitečných dat trvale, ztráta < 2 %, latence
< 100 ms, a to všude, kde se bude létat.

## Fáze 2 — OSD kanál (bez FC)

Notebook hraje FC: posílá MSP DisplayPort přímo do Lite+ a zpátky čte obraz
z VRX Pro. Měří se samotná linka, bez Lua a bez ArduPilotu.

### Zapojení

```text
                  lab. zdroj 9,0 V, limit 1,0 A
                     │ +        │ −
Lite+ 4pin SH1.0 ── VCC ────────┘── GND ──┐
                    TX ───────────► RX  ──┤ USB-UART 3,3 V ─USB─► notebook
                    RX ◄─────────── TX    │
                                    GND ──┘  (společná zem!)

VRX Pro ── DC 5,5 × 2,1, 12 V adaptér
        └─ USB-C (data) ─► notebook, /dev/videoN (UVC)
```

Místo samostatného USB-UART jde použít **MicoAir jako převodník**: na USB,
`SERIAL_PASS1 0`, `SERIAL_PASS2 2`, `SERIAL_PASSTIMO 0`, `SERIAL2_BAUD 115`.
Pak se Lite+ zapojí datovými vodiči do HD VTX konektoru jako ve stavbě a USB
z MicoAiru je rovnou UART2. Napájení Lite+ ale i tak z laboratorního zdroje —
12V BEC na USB neběží.

### Konektory

| Spoj | Strana A | Strana B | Kabel | Máme? |
| --- | --- | --- | --- | --- |
| Lite+ napájení + UART | JST SH1.0 4pin na VTX | zdroj (VCC, GND) + USB-UART (TX, RX, GND) | **SH1.0 4P pigtail** s volnými konci; nebo kabel z příslušenství Lite+ | zjistit, co je v balení |
| Lite+ ↔ MicoAir (varianta) | SH1.0 4pin | **SH1.0-6P HD VTX** na MicoAiru: RX6 · GND · RX2 · TX2 · GND · 12V, 12 V na pinu 1 [dok] | redukce 4P → 6P, nebo pigtaily | ne |
| Napájení Lite+ | VCC, GND z pigtailu | lab. zdroj | krokosvorky / banánky | ano |
| Anténa Lite+ | IPEX-1 | anténa z kitu | — | ano |
| VRX Pro napájení | DC 5,5 × 2,1, 7,4–25,2 V | 12V adaptér ≥ 1 A, **střed plus — ověřit multimetrem** | — | zjistit |
| VRX Pro → notebook | USB-C | USB-A/C | **datový** kabel, ne nabíjecí | ano |
| USB-UART | 3,3 V logika, **ne 5 V** | dupont | — | CP2102 od D500 zřejmě vede jen RX lidaru; počítat s novým nebo s MicoAirem |

**Pořadí pinů na 4pin kabelu Lite+ nikde publikované není.** Přečíst ze
Quick Start Guide v krabici nebo z potisku u konektoru, a před prvním zapnutím
ověřit multimetrem, kam vede VCC. Prohozené VCC a TX zabije UART.

### Pravidla na stole

- **Anténa vždycky dřív než napájení**, u Lite+ i u VRX.
- Lite+ bez proudu vzduchu se přehřívá — ventilátor na stůl, sezení krátká,
  nejnižší výkon VTX.
- 9,0 V místo 12: jsme uprostřed rozsahu 3–12,6 V a nic neriskujeme.
- Odběr ze zdroje zapsat — **to je zároveň první měření spotřeby Lite+**, které
  kusovník vede jako nezměřené.

### Co dělá notebook

1. **Emulátor FC** (`pyserial`, 115200 8N1): odpovídá na MSP dotazy VTX tak jako
   ArduPilot (`MSP_FC_VARIANT` → `ARDU`, `MSP_OSD_CANVAS` → 50 × 18, …) a
   **loguje každý dotaz, který od VTX přijde**. Posílá MSP DisplayPort:
   `CLEAR_SCREEN`, `WRITE_STRING` po ≤ 25 znacích, `DRAW_SCREEN`.
2. **Kalibrace:** jednou vypíše všech 64 znaků abecedy na známá místa;
   z UVC snímku se vyříznou šablony.
3. **Měření:** pruh 2, 4, 8 řádků a celá obrazovka; snímky s pořadovým
   číslem, časem notebooku a CRC; frekvence 5, 10, 20, 30 Hz.
4. **Dekodér** (`opencv`, `v4l2`): čte UVC, porovná buňky se šablonami,
   ověří CRC.

### Co se zapíše

| Veličina | Jak |
| --- | --- |
| OSD v UVC výstupu? | ano / ne — **rozhoduje o všem** |
| OSD v HDMI výstupu? | ano / ne |
| doručené snímky/s | unikátní pořadová čísla za sekundu, pro každou frekvenci |
| roztržené snímky | podíl s chybným CRC |
| latence | čas dekódování minus čas v rámci |
| užitečná propustnost | bity v platných rámcích za sekundu |
| odběr Lite+ | ampérmetr zdroje |

**Projde, když:** OSD je v UVC, ≥ 6 kbit/s užitečných dat, chybných rámců
< 5 %, latence < 150 ms.

## Fáze 3 — celý řetězec s D500

Teprve když fáze 1 nebo 2 projde. D500 je doma a protokolem je to LD19, tedy
LD06 — ArduPilotův ovladač i parser v `lidar/lidar_web.py` ho čtou.

```text
D500 ZH1.5T-4P: TX ─► RX5 MicoAir   (SERIAL5_PROTOCOL 28 Scripting, SERIAL5_BAUD 230)
                5V ◄── 5V BEC MicoAir
                GND ── GND
MicoAir ◄── XT30 ── lab. zdroj 16,0 V, limit 0,5 A (bez motorů)
```

| Spoj | Kabel | Máme? |
| --- | --- | --- |
| D500 → MicoAir | **ZH1.5T-4P pigtail** na pady UART5 | ne — je to tentýž kabel, který kusovník chce pro LD06 |
| MicoAir napájení | **XT30 samice → banánky** | ne — už je v seznamu do dílny v [Nakoupeno](./13_nakoupeno.md) |

Lua skript na H743 čte UART5, skládá otáčku do binů po 2,5° a:

- volá `handle_script_distance_msg` pro `PRX1_TYPE` Scripting — palubní
  vyhýbání jede dál;
- pro A posílá dvě `OBSTACLE_DISTANCE` za otáčku přes `mavlink:send_chan` na
  kanál UART8;
- pro B píše pruh do OSD — na 4.7.1 vlastním MSP na UART2, na masteru přes
  `osd:write`.

Na zemi uzel převede příchozí data na `sensor_msgs/LaserScan`. Kontrola proti
pravdě: stejná scéna nahraná přes CP2102 a `lidar_web.py` před testem a po něm.
Sledovat zátěž Lua (`SCR_DEBUG_OPTS`) a podle potřeby zvednout `SCR_VM_I_COUNT`.

**Software pro kanál B je hotový a ověřený v SITL (8. 10. 2026)**, viz
[`lidar/osd/`](../../lidar/osd/README.md). Rámec je 77 znaků, tři rámce na
otáčku, jeden rámec každých 100 ms, tedy **3,3 otáčky/s** při dvou řádcích;
naměřeno 3,17. Chyba vzdálenosti po přenosu je na záznamech z D500 u 95 %
výsečí do 10 mm. Skript se vejde do výchozího `SCR_VM_I_COUNT`. Z hardwaru
zbývá ověřit to, co rozhoduje fáze 2: jestli OSD dojde do UVC a jestli
v obraze nebliká.

## Schéma zapojení

Signály jsou pojmenované, ne číslované: **pořadí pinů na 4pin kabelu Lite+
není publikované** a čte se z Quick Start Guide. Šipka ukazuje směr dat.

### Fáze 1 — jen s přikoupeným Bluetooth modulem

```text
MicoAir H743 V2 AIO ── USB-C ──► notebook        (napájí i desku; baterie NE)
   pady TX8 ──► RX  ┐
        RX8 ◄── TX  │ sériový BT modul, 3,3 V logika
        5V  ──► VCC │ (podle modulu 3,3 nebo 5 V)
        GND ──► GND ┘ ~~ 2,4 GHz ~~► notebook, rfcomm
```

### Fáze 2a — OSD bez FC, s USB-UART

```text
 Laboratorní zdroj 9,0 V, limit 1,0 A
   (+) ─────────────────────────────┐
   (−) ───────────────────────┐     │
                              │     │      Walksnail Lite+ (VTX)
                              │     └────► VCC  ┐
                              ├──────────► GND  │  JST SH1.0 4P
 USB-UART 3,3 V               │                 │
   GND ───────────────────────┘                 │
   RX  ◄──────────────────────────────── TX     │
   TX  ─────────────────────────────────► RX    ┘
   USB ──► notebook   /dev/ttyUSB0, 115200 8N1  (emulátor FC)
                                     IPEX-1 ── anténa  ← nasadit PŘED napájením
                                         ~~ 5,8 GHz ~~
                                               ▼
 12V adaptér, DC 5,5 × 2,1, střed + ──► Walksnail Ascent VRX Pro ── antény
                                          └─ USB-C (datový) ──► notebook  /dev/videoN (UVC)
```

GND zdroje a GND USB-UART se spojují **na straně Lite+** — bez společné země
UART nefunguje.

### Fáze 2b a 3 — přes MicoAir, s D500

```text
 Laboratorní zdroj 16,0 V, limit 0,5 A ── XT30 ──► MicoAir VBAT
                                                  (motory nezapojené)
 MicoAir USB-C ──► notebook   MAVLink, nebo SERIAL_PASS na UART2 pro fázi 2b

 MicoAir HD VTX, SH1.0-6P                   Walksnail Lite+, SH1.0 4P
   pin 1  12V ─────────────────────────────► VCC   ← nejdřív změřit naprázdno;
          GND ─────────────────────────────► GND     nad 12,3 V napájet Lite+
          TX2 ─────────────────────────────► RX      ze zdroje jako ve 2a
          RX2 ◄───────────────────────────── TX
          GND, RX6  nezapojeno

 MicoAir pady UART5                         LDRobot D500, ZH1.5T-4P
          RX5 ◄───────────────────────────── TX     230400, jen tímhle směrem
          TX5   nezapojeno
          5V  ─────────────────────────────► P5V    D500: rozběh 540 mA, provoz 290 mA
          GND ─────────────────────────────► GND
          GND ─────────────────────────────► PWM    uzemnit — bez externího řízení
                                                    otáček „must be grounded" [LD19 manuál]

```

Pořadí pinů na lidaru (STL-19P i LD19, podle Waveshare a manuálu LD19):
**1 Tx, 2 PWM, 3 GND, 4 P5V**. Kabel z D500 kitu má na druhém konci k CP2102
desce **jiný konektor**, který žádná dokumentace kitu neuvádí — kabel nechat
celý pro USB a na MicoAir použít vlastní ZH1.5 pigtail.

Kde přesně jsou pady UART5, ukazuje obrázek zapojení v manuálu AIO; před
pájením porovnat s potiskem na desce. Parametry: `SERIAL5_PROTOCOL 28`,
`SERIAL5_BAUD 230`, `SERIAL2_PROTOCOL 42`, `SERIAL2_BAUD 115`, `PRX1_TYPE`
Scripting.

## Co koupit kvůli testu

| Díl | Pro fázi | Pozn. |
| --- | --- | --- |
| XT30 samice → banánky | 3 | už v seznamu do dílny |
| ZH1.5T-4P s vodiči | 3 | už v kusovníku pro LD06 |
| JST SH1.0 4P a 6P s vodiči | 2 | levné, několik kusů |
| USB-UART 3,3 V (CP2102 / CH340) | 2 | jen když nepůjde MicoAir jako převodník |
| 12V adaptér 5,5 × 2,1 | 2 | jen když doma žádný není |

Fáze 1 potřebuje navíc sériový Bluetooth modul (klasický SPP, 3,3 V logika) — jen pokud OSD padne.

## Co je ověřené a co ne

| | |
| --- | --- |
| **Ověřeno ve zdrojáku** | Lua binding `serial:find_serial`, `readstring`, `writestring`, `mavlink:send_chan`, `AP_Proximity_Backend:handle_script_distance_msg` v 4.7.1 (`dbe7921`); `osd:write` jen v masteru (`8b9ea70`). HD plátno 50 × 18 v `AP_MSP_Telem_Backend.cpp`. `DEFAULT_SERIAL8_PROTOCOL MAVLink2`, 115200 v hwdef `MicoAir743v2`. |
| **Ověřeno na desce** | AIO Bluetooth nevysílá (fáze 0). |
| **Z dokumentace** [dok] | AIO: jediné tlačítko BOOT0, UART8 na padech, bez Bluetooth — stránka MicoAir. Bluetooth na UART8 má jen MicoAir743v2 FC. Pinout HD VTX konektoru AIO a 12 V/2 A BEC z manuálu robofusion. Lite+ 3–12,6 V, JST 1.0 4pin. VRX Pro 7,4–25,2 V, DC 5,5 × 2,1, UVC. |
| **Neověřeno** | Jestli VRX Pro dává OSD do UVC. Jak často Walksnail OSD překresluje. Pořadí pinů 4pin kabelu Lite+. Zátěž Lua při 230400 baud. Všechna čísla propustnosti. |

## Zdroje

- [MicoAir: 743v2-AIO-45A](https://micoair.com/flightcontroller_micoair743v2_aio_45a/) — jediné tlačítko BOOT0, UART8 na padech
- [MicoAir743v2 FC manuál: Bluetooth na UART8 — platí pro FC, ne AIO](https://micoair.cn/en/docs/flight-controller/micoair743/micoair743v2-flight-controller-manual)
- [robofusion: MicoAir H743 AIO manuál — 743v2-AIO-45A](https://docs.robofusion.net/flight-controllers/h743-aio-user-manual)
- [Rotorama: MicoAir H743 V2 45A AIO AM32](https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32)
- [Caddx: Walksnail Ascent HD Lite+ Kit](https://www.caddxfpv.com/products/walksnail-ascent-hd-lite-plus-kit)
- [Caddx: Walksnail Ascent FPV VRX Pro](https://www.caddxfpv.com/products/walksnail-ascent-fpv-vrx-pro)
- [IntoFPV: Sending data to GogglesX](https://intofpv.com/t-sending-data-to-gogglesx) — MSP DisplayPort je jediný vstup dat do systému Walksnail; VTX ho přenáší do brýlí
- [IntoFPV: Walksnail resources](https://intofpv.com/t-walksnail-avatar-system-resources-and-links) — root na VTX zavřený šifrováním firmwaru
- `external/ardupilot/libraries/AP_Scripting/generator/description/bindings.desc`, `AP_MSP/`, `AP_SerialManager/AP_SerialManager.cpp`

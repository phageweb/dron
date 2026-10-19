# Firmware letového kontroléru

Firmware pro **MicoAir H743 V2 45A AIO** ve stavbě Pavo20 Pro a nástroje, jak
ho nahrát přes USB. Všechno je ve vlastním flaku, nezávislém na ROS shellu
v kořeni repa.

| | |
| --- | --- |
| Firmware | ArduCopter **4.7.1** stable, oficiální build |
| Target | `MicoAir743v2` |
| Zdroj | `firmware.ardupilot.org/Copter/stable-4.7.1/MicoAir743v2/` |
| Commit | `dbe792162d06cab66c3475fd5556bf7a120f119e` |

Vedle něj je připnutý i **master (4.8.0-dev)**, nejnovější noční build, viz
[Master na desce](#master-na-desce).

Soubory jsou připnuté hashem, takže každé nahrání zapíše stejné bajty.
Simulace běží na ArduPilotu 4.8.0-dev z `external/ardupilot` — deska dostává
stable, ne to, co se letělo v SITL.

```sh
nix build ./firmware          # result/ — arducopter.apj, arducopter_with_bl.{hex,bin}
nix run ./firmware#flash      # deska s ArduPilot bootloaderem
nix run ./firmware#flash-dfu  # deska v DFU režimu (BOOT + USB)
nix develop ./firmware        # flash, flash-dfu, mavproxy, lsusb
nix develop ./firmware#gcs    # qgroundcontrol (builds from source, takes long)
```

Flake je uvnitř gitu, takže Nix vidí jen soubory, které git zná — nový soubor
ve složce je potřeba aspoň `git add`.

## Postup

Deska se napájí z USB. **Baterie ani zdroj nepřipojovat**, vrtule nenasazené.

### 1. Co je na desce

Připojit USB a podívat se, jak se hlásí:

```sh
nix develop ./firmware -c lsusb
ls -l /dev/serial/by-id/
```

| Hlásí se jako | Co tam je | Dál |
| --- | --- | --- |
| `/dev/serial/by-id/usb-ArduPilot_MicoAir743v2_…` | ArduPilot | krok 2a |
| `0483:5740` STMicroelectronics Virtual COM Port | nejspíš Betaflight | krok 2b |
| `0483:df11` STM32 BOOTLOADER | DFU režim | krok 2b |
| nic | špatný kabel (jen nabíjecí), nebo mrtvá deska | jiný kabel |

### 2a. Deska už má ArduPilot

```sh
nix run ./firmware#flash
```

Uploader najde port sám (`/dev/serial/by-id/usb-Ardu*`), restartuje desku do
bootloaderu a nahraje `arducopter.apj`. Kontroluje board ID, takže firmware pro
jinou desku odmítne. Vlastní port: `nix run ./firmware#flash -- --port /dev/ttyACM0`.

Uživatel musí být ve skupině `dialout` (je).

### 2b. Betaflight z výroby, nebo deska nereaguje — DFU

Tohle přepíše i bootloader, takže to je cesta, která funguje vždycky.

1. Odpojit USB. Držet tlačítko **BOOT** na desce, připojit USB, pustit.
2. `lsusb` musí ukázat `0483:df11 STMicroelectronics STM BOOTLOADER`.
3. Nahrát:

   ```sh
   nix run ./firmware#flash-dfu
   ```

`dfu-util` potřebuje přístup k USB zařízení. Bez pravidla pro udev skončí na
`Cannot open DFU device` — buď jednou přes `sudo`:

```sh
sudo $(nix build ./firmware#flash-dfu --print-out-paths --no-link)/bin/flash-dfu
```

nebo natrvalo v konfiguraci NixOSu:

```nix
services.udev.extraRules = ''
  # STM32 v DFU režimu (letový kontrolér)
  SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="df11", MODE="0660", GROUP="dialout"
'';
```

Po `:leave` deska sama naběhne do ArduPilotu. Když ne, odpojit a připojit USB.
Další aktualizace už jdou cestou 2a.

### 3. Ověřit

```sh
nix develop ./firmware#gcs -c qgroundcontrol
```

QGroundControl se má připojit sám a ukázat **ArduCopter V4.7.1**. Bez
QGroundControlu stačí:

```sh
nix develop ./firmware -c mavproxy.py --master /dev/serial/by-id/usb-ArduPilot_*
```

Když se QGC nepřipojí a port se objevuje a mizí, port obsazuje ModemManager —
zastavit ho (`sudo systemctl stop ModemManager`) nebo na stole vypnout.

Dál pokračuje [postup stavby, krok 1](../spec/realna_stavba_dronu/14_postup_stavby_pavo20.md#1-firmware--jen-přes-usb):
`FRAME_CLASS 1`, `FRAME_TYPE 1`, restart, parametry uložit do souboru, kalibrace.

## Master na desce

`lidar/osd/scan_osd.lua` potřebuje z Lua psát do OSD (`osd:write`) a to 4.7.1
neumí. Umí to master. Flake proto má i druhý build:

| | |
| --- | --- |
| Firmware | ArduCopter **4.8.0-dev**, oficiální noční build z 12. 10. 2026 |
| Zdroj | `firmware.ardupilot.org/Copter/2026-10/2026-10-12-07:10/MicoAir743v2/` |
| Commit | `113108bd69954dfe9faed49f025601ffcaff2886` |
| Board ID | 1179, stejné jako 4.7.1, takže uploader ho na desku pustí |

V buildu jsou ověřené, podle `features.txt` a symbolů v `arducopter.elf`, Lua
(`AP_SCRIPTING_ENABLED`), funkce pro OSD z Lua (`osd:write`, `flush`,
`draw_screen`), MSP DisplayPort, proximity ze skriptu a ovladač LD06.

```sh
nix build ./firmware#firmware-master     # result/ — stejné soubory jako u 4.7.1
nix run ./firmware#flash-master          # deska s ArduPilotem, cesta 2a
nix run ./firmware#flash-dfu-master      # DFU, cesta 2b
```

Před nahráním **uložit parametry** do `params/`. Přechod z 4.7.1 na master
by je měl zachovat, ale vývojová verze může některé přejmenovat. QGroundControl
má po nahrání ukázat **ArduCopter V4.8.0-dev**. Zpátky na 4.7.1 vede
`nix run ./firmware#flash` a nahrání uložených parametrů.

Je to vývojová verze, ne vydání. Až vyjde 4.8 stable, přepnout na ni
(4.7.2 z 11. 10. `draw_screen` pořád nemá).

**Noční buildy server po zhruba měsíci maže.** Původní pin, `8b9ea70` z 9. 9.
— stejný commit jako `external/ardupilot` a SITL — 14. 10. už nešel stáhnout,
proto je pin posunutý a deska teď běží na novějším masteru než simulace.
Aby se soubory neztratily i z Nix store, nechat `nix build ./firmware#firmware-master
-o firmware/result-master`: symlink je gcroot. Až build ze serveru zmizí,
posunout pin na nejnovější `Copter/<rok-měsíc>/…` podle
[Nová verze](#nová-verze).

Master mezi 9. 9. a 12. 10. přejmenoval další parametry: `SYSID_THISMAV` →
`MAV_SYSID`, `SYSID_MYGCS` → `MAV_GCS_SYSID`, `SRn_*` → `MAVn_*`,
`TELEM_DELAY` → `MAV_TELEM_DELAY`.

## Zálohy parametrů

`params/` — co bylo na desce, vyčtené přes MAVLink:

- `tovarni_2026-10-02.parm` — z výroby, ArduCopter 4.6.2, 1236 parametrů.
  Deska přišla s ArduPilotem, nahrávalo se cestou 2a.
- `po_flashi_4.7.1_2026-10-02.parm` — hned po nahrání 4.7.1, nic nezměněno.
- `ramec_quadx_2026-10-02.parm` — `FRAME_CLASS 1`, `FRAME_TYPE 1`, po restartu.
  Výchozí stav pro kalibraci.
- `pred_masterem_4.7.1_2026-10-10.parm` — stav těsně před nahráním masteru.
  Proti `ramec_quadx` se liší jen teplotou kalibrace gyra.
- `po_flashi_master_2026-10-10.parm` — hned po nahrání 4.8.0-dev, nic
  nezměněno. Parametry ze 4.7.1 přechod zachoval.
- `konfigurace_master_2026-10-10.parm` — porty a výchozí nastavení podle
  postupu stavby, kroky 4–8: `AHRS_ORIENTATION 7`, RCIN na UART6, MTF-02P na
  UART4, GPS na UART3, DisplayPort na UART2 s `OSD1_TXT_RES 1`, DShot600,
  baterie a failsafe. Bez kalibrací.
- `deska2_tovarni_2026-10-14.parm` — **druhá deska** (USB sériové číslo
  `49002F000F51333336373039`), z výroby ArduCopter 4.6.2, 1236 parametrů.
  Proti první desce se liší jen kalibrací gyra, tlakem a počítadly.
- `deska2_po_flashi_master_2026-10-14.parm` — druhá deska hned po nahrání
  4.8.0-dev `113108bd`, nic nezměněno.

4.7 přejmenovala část parametrů na jednotky SI (`ANGLE_MAX` → `ATC_ANGLE_MAX`
ve stupních, `ATC_ACCEL_*_MAX` → `ATC_ACC_*_MAX`, `CIRCLE_RADIUS` →
`CIRCLE_RADIUS_M`, `ARMING_CHECK` → `ARMING_SKIPCHK`). Tovární soubor proto
na 4.7.1 zpátky nahrávat nejde jedna k jedné.

## Parametry ze simulace

`ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params_pavo20.parm` je
vyladěný v SITL na 4.8.0-dev. **Nenahrávat celý najednou.** Obsahuje i
parametry, které jsou jen pro simulaci, a některé nemusí ve 4.7.1 existovat.
Brát z něj jednotlivé hodnoty tak, jak je postup stavby uvádí.

## Co tady není

- **AM32 na ESC části AIO.** Má vlastní firmware, aktualizuje se přes
  passthrough z FC (AM32 configurator). Dokud ESC jede a motory se točí
  správným směrem, nechat ho být.
- **ELRS v XR1.** Aktualizuje se přes Wi-Fi přijímače nebo z ExpressLRS
  Configuratoru. Hlavní verze se musí shodovat s TX15.

## Nová verze

1. Ve `flake.nix` v `builds.stable` (nebo `builds.master`) změnit `version`,
   `commit` a `base` (commit je v `…/MicoAir743v2/git-version.txt`).
2. Nové hashe: `nix store prefetch-file <url>` pro `arducopter.apj`,
   `arducopter_with_bl.hex` a `uploader.py` z toho commitu.
3. `nix build ./firmware`, pak nahrát a **parametry si předtím uložit.**

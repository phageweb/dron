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

Soubory jsou připnuté hashem, takže každé nahrání zapíše stejné bajty.
Simulace běží na ArduPilotu 4.8.0-dev z `external/ardupilot` — deska dostává
stable, ne to, co se letělo v SITL.

```sh
nix build ./firmware          # result/ — arducopter.apj, arducopter_with_bl.{hex,bin}
nix run ./firmware#flash      # deska s ArduPilot bootloaderem
nix run ./firmware#flash-dfu  # deska v DFU režimu (BOOT + USB)
nix develop ./firmware        # flash, flash-dfu, qgroundcontrol, mavproxy, lsusb
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
nix develop ./firmware -c qgroundcontrol
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

## Zálohy parametrů

`params/` — co bylo na desce, vyčtené přes MAVLink:

- `tovarni_2026-10-02.parm` — z výroby, ArduCopter 4.6.2, 1236 parametrů.
  Deska přišla s ArduPilotem, nahrávalo se cestou 2a.
- `po_flashi_4.7.1_2026-10-02.parm` — hned po nahrání 4.7.1, nic nezměněno.
- `ramec_quadx_2026-10-02.parm` — `FRAME_CLASS 1`, `FRAME_TYPE 1`, po restartu.
  Výchozí stav pro kalibraci.

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

1. Ve `flake.nix` změnit `version` a `commit` (commit je v
   `…/stable-<verze>/MicoAir743v2/git-version.txt`).
2. Nové hashe: `nix store prefetch-file <url>` pro `arducopter.apj`,
   `arducopter_with_bl.hex` a `uploader.py` z toho commitu.
3. `nix build ./firmware`, pak nahrát a **parametry si předtím uložit.**

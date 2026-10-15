# Obraz z VRX Pro na PC

`vrx.py` ukáže na notebooku obraz z Walksnail Ascent VRX Pro **i s OSD**
a umí ho nahrávat.

```sh
nix run .#vrx                 # okno
nix run .#vrx -- --record     # okno a nahrávání od startu
nix run .#vrx -- --headless   # jen nahrávání, Ctrl+C zastaví
```

| Klávesa | Co dělá |
| --- | --- |
| Q, Esc | konec |
| F, F11 | celá obrazovka |
| S | snímek obrazovky |
| R | začít / zastavit nahrávání |
| H | skrýt / ukázat stavový řádek |
| L | skrýt / ukázat radar lidaru |
| A | hláška VRX je v pořádku, ztišit alarm |
| I | údaje zařízení na USB: verze, model, teplota, firmware, SN, HW, stav |

Snímky a záznamy jdou do `~/Videos/vrx` (`--out` jinam). Snímek je JPEG
přímo z VRX a záznam je jeho MJPEG zkopírovaný do `.mkv`, nic se znovu
nekóduje. 1080p30 MJPEG je asi 6–7 MB/s, minuta záznamu tedy ~400 MB.
Odpojení VRX program neukončí, počká, až se vrátí.

## Lidar z OSD

Když na dronu běží `lidar/osd/scan_osd.lua`, program čte sken lidaru ze
spodních dvou řádků OSD v obraze a kreslí poslední otáčku jako radar
vpravo (`lidar/osd/osdvideo.py`). Ve stavovém řádku jsou otáčky za sekundu
a počet přečtených rámců. Šablony znaků, které se cestou doučí, ukládá do
`~/Videos/vrx/glyphs_vrx.npz`. Pro dron se `scan_osd.lua` z doby před
15. 10. 2026 je potřeba `--old-alphabet`.

Hotový záznam převede pro webovou stránku lidaru (video i lidar synchronně)
`nix run .#osdvideo -- ~/Videos/vrx/vrx_….mkv --session lidar/sessions`,
viz [Sken lidaru přes OSD](../lidar/osd/README.md#čtení-z-obrazu-vrx).

## Alarm na hlášky VRX

VRX píše varování do rámečku dole uprostřed, třeba „Standby Mode, low rf
power“ nebo „Transmitter is disconnected“. Při přehřátí VTX tam má být
hláška o teplotě, ale **jak přesně vypadá, nevíme**: číslo teploty VRX
v obraze neukazuje a hlášku o přehřátí jsme zatím neviděli. Program proto
text nečte. Pamatuje si hlášky, které jsi klávesou **A** označil za
v pořádku, a na **každou jinou** spustí alarm: blikající červený rámeček,
nápis a pípání. Zároveň uloží snímek obrazovky, takže je hláška zachycená.

Napoprvé tedy zazvoní i běžné hlášky. Každou stačí jednou potvrdit
klávesou A. Potvrzené hlášky jsou jako obrázky v `~/Videos/vrx/known_messages/`.
Smazáním souboru se hláška zase stane neznámou.

Nad meze 85 °C (varování) a 95 °C (stop nahrávání) z firmwaru Walksnail
se tak dostaneš jen nepřímo, přes hlášku VRX. Teplotu jako číslo to
neukáže.

Ověřeno na skutečné hlášce „Transmitter is disconnected“ a na dokreslených
hláškách. Na skutečném přehřátí ne.

## Teplota

Teplotu VRX Pro a Lite+ program čte po USB protokolem OTRA
([otra_protokol.md](otra_protokol.md)) a ukazuje ji vpravo nahoře, každé
2 s. Od 75 °C žlutě, od 85 °C červeně s rámečkem a pípáním. Meze se mění
přes `--warn` a `--alarm`. 85 °C je mez, od které Walksnail sám hlásí
přehřátí.

Teplotu VTX program zná jen tehdy, když je Lite+ v USB vlastním kabelem,
tedy na stole. Za letu zbývá alarm na hlášky VRX výš.

```sh
python3 vrx/otra.py     # jednorázový výpis: verze, model, teplota, firmware, SN, HW
```

## Latence

Číslo v ms dole na obrazovce VRX měří Walksnail sám: kamera → VTX →
rádio → VRX. Cestu z VRX po USB do PC v něm **není**. Tu změří:

```sh
nix run .#vrx -- --latency        # 30 bliknutí, Esc skončí dřív
```

Obrazovka bliká černě a bíle a kamera Lite+ se na ni musí dívat (střed
obrazu = obrazovka, VTX spárovaný). Program měří čas od přepnutí barvy do
příchodu prvního snímku z VRX, který změnu ukazuje. V čísle je tedy
monitor, kamera, rádio, VRX, jeho kódování do MJPEG a USB.

Co se z toho počítá:

- **přidáno cestou přes PC** ≈ naměřený medián − latence ukázaná VRX
  − zpoždění monitoru (u běžného LCD 5–15 ms),
- **co vidíš v okně** ≈ naměřený medián + ~12 ms na rozbalení a zmenšení
  snímku (změřeno: 9 ms dekódování JPEG 1080p, 3 ms zmenšení).

UVC jede jen 30 snímků/s, takže samo čekání na další snímek přidá
0–33 ms, v průměru ~17 ms.

Ověřeno na simulaci s 120 ms zpožděním a snímky po 30 fps: medián 138 ms,
rozsah 121–154 ms. Se skutečným Lite+ zatím neměřeno.

## ROS 2: balíček `openipc_vrx`

Uzel `vrx_bridge` (`ros_ws/src/openipc_vrx`) dělá na zemi totéž co tenhle
program, jen do ROS 2. Témata mají stejné názvy jako v simulaci:

| Téma | Typ | Co |
| --- | --- | --- |
| `/openipc_cinewhoop/camera/image_raw/compressed` | `CompressedImage` | MJPEG z VRX beze změny, rámec `camera_optical_frame` |
| `/openipc_cinewhoop/camera/camera_info` | `CameraInfo` | jen s `camera_info_file`, tedy po kalibraci přes VRX |
| `/openipc_cinewhoop/scan/front` | `LaserScan` | sken z OSD, 144 výsečí po 2,5°, rámec `front_lidar_link` |
| `/diagnostics` | `DiagnosticArray` | info a teplota VRX a Lite+, stav obrazu |

```sh
ros2 launch openipc_vrx vrx_bridge.launch.py latency_ms:=80 scan_source:=msp:tcp:127.0.0.1:5772
```

- Časy zpráv jsou čas příchodu minus `latency_ms` (změří `vrx.py --latency`).
- Sken zatím jen z MSP DisplayPort (`msp:tcp:…` pro SITL, `msp:/dev/tty…` pro
  odbočku ze sériové linky). Čtení z obrazu umí `vrx.py` a `osdvideo.py`,
  do uzlu zapojené ještě není.
- `otra.py` a `osdscan.py` jsou v balíčku odkazy na `vrx/` a `lidar/osd/`,
  kód je jen jednou.
- Obraz může číst jen jeden program: `vrx.py` a `vrx_bridge` ne současně.
- Převod výsečí na úhly ROS (lidar měří po směru hodinových ručiček, ROS
  proti) hlídá `test/test_scan.py`.

**Neověřeno:** uzel se zatím nespustil. ROS 2 v tomhle počítači není
sestavené a 13. 10. 2026 na to nebylo místo na disku.

## Co VRX po USB-C nabízí (zjištěno 13. 10. 2026)

USB `1d77:a4a2` „AscentVRX VRX Gadget (RNDIS+UVC+ACM)“:

| Funkce | Na notebooku | Co tam je |
| --- | --- | --- |
| UVC | `/dev/video4` (+ `video5` s metadaty) | MJPEG **1920 × 1080 @ 30** a 1280 × 720 @ 60 |
| RNDIS | síť, VRX na `fe80::deff:fead:beef` | otevřený jen TCP 22, ssh |
| ACM | `/dev/ttyACM0` | protokol OTRA: informace o zařízení a teplota |

UVC je **celá obrazovka VRX**: obraz z kamery, OSD z dronu a vlastní
překryv VRX (napětí, Mbps, latence, vzdálenost, RSSI obou antén, stav SD).
V režimu 720p VRX ukazuje jen nápis „please select 1080p mode“, proto
program vždycky žádá 1080p.

Tím je zodpovězená hlavní otázka fáze 2 v
[Testu linky pro sken](../spec/realna_stavba_dronu/15_test_linky_skenu.md):
překryv VRX v UVC je. Že tam bude i OSD z letového počítače, se ověří
až s Lite+ a MSP DisplayPort.

## Když VRX nedává obraz (15. 10. 2026)

Když se VRX restartuje se zapojeným USB, nebo se kabel pohne, UVC ve VRX
se zasekne. Kernel pak každou sekundu hlásí
`uvcvideo: Failed to set UVC probe control : -71` (nebo `-110`) a ffmpeg
v `vrx.py` visí bez jediného snímku. Restart programu ani nové otevření
zařízení nepomůže. Pomohlo jen **vytáhnout USB-C, nechat VRX úplně
nabootovat a teprve pak kabel zapojit**, přímo do notebooku, ne přes hub.
Při `device not accepting address … error -71` už notebook VRX ani
nepřipojí; to byl kabel nebo port.

## Lite+ přímo na USB (13. 10. 2026)

USB `1d76:0101` „Vendor SerialGadget“, sériové číslo `CX24`, uvnitř Linux
5.10 (bcdDevice 5.10). V PC jako `/dev/ttyACM1` (cdc_acm). Na USB 3 portu
se nepřipojil („Cannot enable. Maybe the USB cable is bad?“), na USB 2
hubu ano.

Mluví binárním protokolem `OTRA`, popis je v [otra_protokol.md](otra_protokol.md).

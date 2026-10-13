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
| A | hláška VRX je v pořádku, ztišit alarm |

Snímky a záznamy jdou do `~/Videos/vrx` (`--out` jinam). Snímek je JPEG
přímo z VRX a záznam je jeho MJPEG zkopírovaný do `.mkv`, nic se znovu
nekóduje. 1080p30 MJPEG je asi 6–7 MB/s, minuta záznamu tedy ~400 MB.
Odpojení VRX program neukončí, počká, až se vrátí.

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

## Lite+ přímo na USB (13. 10. 2026)

USB `1d76:0101` „Vendor SerialGadget“, sériové číslo `CX24`, uvnitř Linux
5.10 (bcdDevice 5.10). V PC jako `/dev/ttyACM1` (cdc_acm). Na USB 3 portu
se nepřipojil („Cannot enable. Maybe the USB cable is bad?“), na USB 2
hubu ano.

Mluví binárním protokolem `OTRA`, popis je v [otra_protokol.md](otra_protokol.md).

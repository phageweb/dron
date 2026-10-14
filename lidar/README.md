# D500 lidar – živé zobrazení na webu

LDRobot D500 (protokol LD19/STL-19P) přes CP2102 → `/dev/ttyUSB0`, 230400 Bd.
Bez závislostí, jen standardní Python.

```sh
nix run .#lidar                       # pak otevři http://localhost:8000
nix run .#lidar -- --port /dev/ttyUSB1 --http 8080 --bind 0.0.0.0   # i z jiného počítače v síti
python3 lidar/lidar_web.py            # totéž bez nixu
```

- `/` stránka (canvas, kolečko = zoom, tažení = posun)
- `/stream` Server-Sent Events, jedna zpráva = jedna otáčka
- `/scan.json` poslední otáčka

Zpráva: `{"t", "hz", "n", "crc_errors", "pts": [úhel°, vzdálenost mm, intenzita, …]}`.
Úhel roste po směru hodinových ručiček od předku lidaru; vzdálenost 0 = neplatné měření.
Na stránce se dá nastavit stopa (kolik otáček nechat dohasínat), minimální intenzita,
otočení a zrcadlení podle toho, jak je lidar namontovaný.

## Přehrávání záznamů z telefonu

Záznamy aplikace LidarCam (`android/lidarcam`) leží v `lidar/sessions/<datum_čas>/`
(`video.mp4`, `lidar.jsonl`, `meta.json`). Stránka je sama vypíše v seznamu **záznamy…**,
stačí vybrat. Tlačítko **stáhnout z telefonu** (telefon připojený přes USB s laděním,
nebo přes bezdrátové ladění) stáhne nové dokončené záznamy, totéž dělá
`lidar/pull_sessions.sh [cílová složka]`. Pod `nix run` se záznamy hledají v
`./lidar/sessions` vůči aktuální složce, jinde se dá zadat `--sessions DIR`.
Odkaz `http://localhost:8000/#<záznam>&map` otevře rovnou daný záznam s půdorysem.

Stejně se přehrají i záznamy z VRX, kde lidar přišel přes OSD.
`nix run .#osdvideo -- ~/Videos/vrx/vrx_….mkv --session lidar/sessions` z nich udělá
záznam `vrx_<datum_čas>`, viz [Sken lidaru přes OSD](osd/README.md#čtení-z-obrazu-vrx).

Přehrávání: video vpravo dole, lidar synchronně s ním, posuvník,
mezerník = play/pauza, šipky = ±0,1 s. Bez serveru (`index.html` otevřený jako soubor)
jde záznam načíst přes **otevřít složku…**.

### Půdorys

Zaškrtnout **půdorys**: stránka poskládá všechny otáčky do jedné mapy (2D SLAM bez
odometrie – každá otáčka se ICP bod–přímka zarovná na mapu složenou z předchozích)
a ukáže stěny, celou cestu a právě přehrávanou otáčku na místě, kde vznikla.
Body blíž než 0,5 m se vynechávají (to je člověk, který lidar nese); voxely viděné
jen jednou jsou slabší. **uložit JSON** v tomto režimu uloží PNG půdorysu.
Otočení a zrcadlení se do půdorysu promítnou (přepočítá se). Bez uzavírání smyček,
takže na dlouhé trase se chyba sčítá.

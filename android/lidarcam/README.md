# LidarCam – kamera + D500 lidar na Pixelu 9a

Nahrává zároveň video ze zadní kamery a otáčky lidaru D500 (připojeného do USB-C
telefonu) a umí záznam přehrát: nahoře video, dole lidar ze stejného okamžiku.

## Sestavení a instalace

Telefon: zapnout *Možnosti pro vývojáře → Ladění přes USB*, připojit k počítači.

```sh
cd android/lidarcam
nix develop ../..#android --command gradle installDebug
```

(APK samotné: `gradle assembleDebug` → `app/build/outputs/apk/debug/app-debug.apk`.
Testy parseru na skutečných datech z D500: `gradle testDebugUnitTest`.)

## Použití

1. Odpojit telefon od počítače, zapojit lidar (CP2102 deska přímo do USB-C, případně přes OTG redukci).
2. Android nabídne otevřít LidarCam – potvrdit (s „vždy“ už se příště neptá).
3. **● Nahrávat** / **■ Zastavit**. Během nahrávání displej nezhasne.
4. **Záznamy** → vybrat → přehrávání (posuvník, ▶, pinch = zoom lidaru), případně smazat.

Bez povolení kamery nebo bez kamery se nahraje jen lidar; přehrávač pak jede podle vlastních hodin.
Zvuk se nenahrává.

## Záznam

Složka `Android/data/cz.dron.lidarcam/files/sessions/<datum_čas>/`:

| soubor | obsah |
|---|---|
| `video.mp4` | kamera, 1080p (nebo nejbližší nižší) |
| `lidar.jsonl` | jedna otáčka na řádek: `{"t_ns", "hz", "n", "pts": [úhel°, mm, intenzita, …]}` |
| `meta.json` | `video_start_ns` a popis záznamu |

`t_ns` i `video_start_ns` jsou `SystemClock.elapsedRealtimeNanos()`; otáčka je v čase
`(t_ns − video_start_ns) / 1e9` s videa a `t_ns` je okamžik, kdy byla otáčka dokončena.
Začátek videa se odhaduje z CameraX (čas − nahraná délka), přesnost řádově desítky ms.

## Přehrání na PC

```sh
nix run .#lidar                 # http://localhost:8000 → „stáhnout z telefonu“ → vybrat ze „záznamy…“
lidar/pull_sessions.sh          # nebo stáhnout jen skriptem do lidar/sessions/
```

Zaškrtnutím „půdorys“ se z otáček složí mapa místa i s cestou (viz `lidar/README.md`).
Prohlížeč umí přehrávat i bez serveru – stačí otevřít `lidar/index.html` jako soubor.
Mezerník = play/pauza, šipky = ±0,1 s.

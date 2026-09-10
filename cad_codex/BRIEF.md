# Zadání pro Codex: CAD model celého dronu

Nezávislá varianta modelu, který je v [`cad_claude/`](../cad_claude/). Smyslem
je porovnat dva postupy, takže **soubor z `cad_claude/` needituj ani neopisuj** -
ať to vznikne znovu ze stejného zadání.

## Co postavit

Model celého dronu v OpenSCADu (nebo v Blenderu, pokud je to výhodnější) do
téhle složky. Nemá to být výrobní výkres, má to zodpovědět mechanické otázky
dřív, než se díly koupí.

## Souřadnice

- počátek ve středu horní desky rámu
- **X dopředu, Y doleva, Z nahoru**, milimetry
- motory quad X na `±45.25 mm` v X i Y (půl rozvoru 128 mm děleno √2)

Je to schválně stejná konvence jako v ROS modelu, aby šly hodnoty přenášet.

## Díly a rozměry

Kompletní seznam je v
[`spec/realna_stavba_dronu/05_cad_dily.md`](../spec/realna_stavba_dronu/05_cad_dily.md).
Ověřené rozměry používej, **neověřené si nevymýšlej** - označ je v kódu jako
placeholder a vizuálně odliš, aby z obrázku bylo poznat, čemu se dá věřit.

Sestava: rám s ducty, 4× motor 1404 s vrtulí 76 mm, FC MicoAir H743 V2 45A AIO,
video jednotka EMAX Wyvern Link Alpha, RX SpeedyBee ELRS Nano, optical flow
MicoAir MTF-02P dolů, baterie Tattu 4S 750 a **LDRobot LD06 vpředu**.

## Otázky, které má model zodpovědět

Podle nich se pozná, jestli je k něčemu:

1. Kam LD06, aby viděl dopředu, minul ducty a **nezasahoval do rovin vrtulí**
2. Kde skončí těžiště a jak ho vyváží poloha baterie
3. Jestli má MTF-02P čistý výhled dolů, nezastíněný deskou ani baterií
4. Jestli kamera video jednotky nekouká do ductu
5. Jestli je po smontování přístupné USB na FC

## Výstup

- zdroj modelu
- tři rendery: izometrie, půdorys, bokorys
- krátké `README.md`: jak to renderovat, co z modelu vyplynulo, co je odhad

Bokorys je důležitý - výškové vůle na půdorysu vidět nejsou.

# Kontrola po opravě — Pavo20 Pro / Lite+ / D500

Aktualizováno 13. 10. 2026. **Dvě nalezené montážní kolize jsou opravené
v modelu i exportovaných STL.** Rozměry kamery, skutečné montážní prvky,
pevnost a vibrace stále vyžadují fyzické ověření.

## Opravy

- `1-base.stl` má zadní vaničku pro WS-M181: vnitřek 18,8 × 18,8 mm,
  stěny 1,6 mm, nízký 2mm lem. Modul 18 × 18 × 4,6 mm sedí na 1mm
  nevodivé lepicí podložce. Vpředu je 14mm otevření pro kabel/konektor.
  Vaničku nesou dvě 4mm široká ramena a tiskne se se základnou bez podpěr
  pod touto novou částí. Lepicí podložka zajišťuje svislé držení; nejde o zacvakávací objímku.
- GPS je na `[0,49,6.5]` mm: o 7 mm vzadu a 0,5 mm výše než dříve.
  GPS i vyhrazený prostor pro konektor 12 × 4 × 3 mm jsou bez průniku
  se základnou a modelovanou anténou. Vodič vést podél bočního ramena;
  skutečný konektor a délku kabelu ověřit na zakoupeném modulu.
- Rozteč mostu se změnila z 26 × 36 na **26 × 34 mm** v obou dílech.
  Kolem hlav rámových šroubů Ø4,2 mm je nyní radiální vůle **0,5 mm**.
  Automatická kontrola navíc požaduje 0,4mm rezervu.
- **Použít novou základnu i nový most společně.** Starý a nový díl mají
  odlišnou rozteč a nelze je kombinovat. Upevnění samotného D500 zůstává stejné.
- `2-camera_insert.stl` zachovává původní dutinu 14,3 × 12,3 × 4,8 mm.
  Chybí skutečná tloušťka těla kamery bez objektivu; údaj 4,5 mm je odhad.
  Bez měření nelze tvrdit, že kamera fyzicky zacvakne. Použít TPU, boční
  šrouby nejvýše s 1,5mm záběrem a ověřit jejich skutečnou délku.

## Výsledky ověření

- Všechny tři STL: jeden uzavřený souvislý povrch, konzistentní orientace,
  kladný objem; nové exporty ze současného SCAD.
- **12/12 konfigurací** (550/750, lidar ano/ne, kamera 0/20/40°) bez
  testovaných kolizí; nyní včetně GPS, konektorové obálky, hlav rámových
  šroubů a referenční kamery.
- **4/4 kontrol skutečných STL** bez průniku: most/hlavy, GPS/základna,
  GPS/anténa, prostor konektoru/základna.
- Negativní kontroly úspěšně detekují návrat staré polohy GPS, staré rozteče
  mostu a chybně zvýšené roviny vrtulí. Kolize mají nenulový objem.
- Nezávislý přepočet hmotností a momentů v Pythonu souhlasí s OpenSCAD;
  kontrola zahrnuje i ručně vystředěnou baterii a natočení kamery/mostu.
- Prázdná koplanární dosedací plocha se v kontrolách potlačuje pouze
  tolerancí 0,02 mm na karbonu a spodní ploše hlavy rámového šroubu.

## Nový odhad vyvážení

| Baterie | D500 | Hmotnost | Baterie dopředu | Baterie doleva | CG Z |
| --- | --- | ---: | ---: | ---: | ---: |
| 750 mAh | ne | 174.41 g | 3.49 mm | 0.41 mm | -15.26 mm |
| 750 mAh | ano | 227.40 g | 3.49 mm | 0.41 mm | -2.43 mm |
| 550 mAh | ne | 162.41 g | 4.22 mm | 0.50 mm | -13.68 mm |
| 550 mAh | ano | 215.40 g | 4.23 mm | 0.50 mm | -0.52 mm |

Hmotnost držáku GPS je součástí integrované základny. Objemové vlastnosti
se při `python3 refresh_model.py` automaticky obnoví ze STL; kamera a anténa
mají těžiště transformované podle natočení. Výsledky jsou odhady a nulové
vodorovné CG vzniká dopočtem polohy baterie.

[Výpočet a předpoklady](VYVAZENI.md) · [strojový výstup](balance_report.json)
· [kontroly a otisky souborů](audit_report.json) · [náhled zezadu](holder_rear.png)

## Opakování

```sh
python3 refresh_model.py
QT_QPA_PLATFORM=offscreen bash render.sh
```

`audit_mounting.scad` používá skutečné exportované STL. Očekává prázdný
průnik (OpenSCAD vrací 1 s textem `Current top level object is empty.`);
`refresh_model.py` odlišuje tento stav od chyb a varování.

Původní nálezy jsou zachované v
[archivu kontroly](archiv/pred_opravou_KONTROLA_MODELU.md).
Rozměry WS-M181 odpovídají [specifikaci CADDX](https://www.caddxfpv.com/products/walksnail-ws-m181gps).
Další výrobní podklady jsou v [README.md](README.md).

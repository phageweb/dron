# Podklady rešerše layoutu V2, 21. 10. 2026

Hlavní výstup: [rešerše](../RESERSE_LAYOUTU_V2.md) a
[předávka pro implementaci](../PREDAVKA_LAYOUTU_V2.md).

- `baseline-v2.tar.gz`: celý dosavadní V2 projekt s 21 nespojenými; není výrobní výstup.
- `baseline-manifest.json`: SHA256 archivu a všech souborů uvnitř.
- `geometry.json`: naměřené polohy a simulované rotace ze stejné základní desky.
- `measure_geometry.py`: zdroj měření, změny rotace pouze v paměti, bez uložení PCB.
- `placement-experiment.drc.json`: konečný DRC odloženého pokusu s přesunem
  R301/TP304/TP319; 21 nespojených, žádné zlepšení celkového počtu.

**Omezení měření:** `courtyard: null` znamená chybějící mechanický podklad.
Prázdné `sd_rotations.*.overlaps` proto nedokládá bezkolizní umístění.
Kontrola neřeší těla nad protější stranou desky, kabely, kartu ani rám.
`plane_signal_tracks` sčítá přímé segmenty bez GND; neobsahuje polygony ani
oblouky a nezaručuje souvislé zemní plochy. `pads` uvádí jednu polohu pro každé
číslo padu; u duplicitních čísel není úplným seznamem všech fyzických padů.

Opakování měření z kořene repozitáře:

```sh
nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --python \
  dps/aio/research-v2/measure_geometry.py \
  build/aio/micoair-route-20261021/project/aio.kicad_pcb \
  /tmp/aio-v2-geometry.json
```

Archiv pochází z vlastního projektu odvozeného od OpenAIO; původ a licence
jsou uvedené v [hlavním README](../README.md). Zdrojové revize použité při
rešerši: OpenAIO `986ce1e63276c17eba373f826e2b1e700c04003b`, ArduPilot
`8b9ea7004582267d79a97858e4fda1dd4fe18305`. KiCad při auditu: 10.0.7.

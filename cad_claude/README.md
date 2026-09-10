# CAD model dronu - varianta Claude

OpenSCAD, protože model má být parametrický, textový a verzovatelný vedle
zbytku repa. Blender by dal hezčí obrázek a horší odpověď.

## Render

```bash
nix develop
cd cad_claude
openscad -o drone.png      --imgsize=1400,1000 --camera=0,0,10,62,0,30,420 drone.scad
openscad -o drone_top.png  --imgsize=1200,1200 --camera=0,0,10,0,0,0,330   drone.scad
openscad -o drone_side.png --imgsize=1400,900  --camera=0,0,26,90,0,0,320  drone.scad
```

`openscad` je v dev shellu. `-D show_checks=true` přikreslí kruhy vrtulí, výhled
lidaru dopředu a kužel optical flow dolů.

| Pohled | Soubor |
| --- | --- |
| Izometrie | `drone.png` |
| Půdorys | `drone_top.png` |
| Bokorys | `drone_side.png` |
| Elektronika, rozstřelená | `electronics.png` |

Elektroniku zakrývá baterie, takže detail potřebuje odklidit ji i ducty:

```bash
openscad -o electronics.png --imgsize=1400,1000 --camera=0,0,16,60,0,28,200 \
  -D show_battery=false -D show_ducts=false -D explode=14 drone.scad
```

## Desky

Nejsou to kvádry. Každá deska má substrát, **vyříznuté montážní díry**,
osazení a konektory, protože ty rozhodují o tom, co se kam vejde:

- **FC MicoAir H743 V2 45A AIO** - deska 36 × 36 na roztečích 25.5, MCU, dvě
  gyra, barometr, **USB-C na hraně** a čtyři UART konektory nahoře; zespodu
  zapouzdřený ESC blok a motorové pady. Jestli po smontování zůstane USB
  dosažitelné, je jedna z otázek, kvůli kterým model vznikl.
- **Video EMAX Wyvern Link Alpha** - stojí na distančních sloupcích nad FC, takže
  výška stacku vychází z nich a ne z odhadu. Kamerový modul je zvlášť, na nose.
- **RX SpeedyBee ELRS Nano** - deska 10.4 × 18.4, SX1280, IPEX a anténa, která
  taky musí někde skončit mimo karbon.
- **MTF-02P** - optika dolů: flow kamera vedle laseru, oboje na spodní straně.

## Co model říká

1. **LD06 musí nad rovinu vrtulí.** V každé výšce, kde jeho tělo zasahuje do
   kruhů vrtulí, do nich narazí - je 38.6 mm široký a přední vrtule sahají do
   x = 83 mm. Vynucuje to stožár, a ten zvedá těžiště.
2. **Je velký.** Na bokorysu je zhruba stejně vysoký jako baterie a sedí na
   nose. To není chyba kreslení, to je ta volba senzoru.
3. **Baterie patří nahoru a dozadu.** Pod deskou by visela níž než ducty a byla
   by první, co potká zem. Vzadu zároveň vyvažuje lidar vpředu; `batt_x` je na
   to parametr, ale skutečnou polohu určí váha, ne výkres.

## Průhledné díly jsou odhady

Co je průsvitné, není měřené: ducty, kanopa, deska Wyvernu a **celý LD06**.
Rozměry k dohledání jsou vypsané v
[spec/realna_stavba_dronu/05_cad_dily.md](../spec/realna_stavba_dronu/05_cad_dily.md);
nejdůležitější je montážní výkres LD06 a geometrie ductu od GEPRC, protože ty
dva rozhodují o všech vůlích.

## Souřadnice

Stejné jako ROS model: X dopředu, Y doleva, Z nahoru, počátek ve středu horní
desky. V milimetrech, tedy 1000x hodnoty z `physical_params.yaml`.

**Až budou skutečné rozměry, přenášejí se odsud do simulace, ne naopak.** CAD je
třetí místo, kde se geometrie může rozejít - první dvě už hlídá
`scripts/check_model_consistency.py`.

# Nezávislý CAD koncept dronu

Model je samostatně vytvořená obalová studie sestavy z `BRIEF.md`. Souřadnice
jsou v milimetrech, počátek je uprostřed horní plochy karbonové desky, **X
dopředu, Y doleva, Z nahoru**. Model není výrobní výkres.

## Renderování

Vyžaduje OpenSCAD 2021.01 nebo novější. Na stroji bez grafického displeje skript
použije dostupný `xvfb-run`, případně jej spustí přes Nix:

```bash
./cad_codex/render.sh
```

Vzniknou `isometric.png`, `top.png` a `side.png`. Ve `drone.scad` lze přepnout
`battery_variant` mezi `"compact"` (60 × 31 × 27 mm) a `"long"` (76 × 17 ×
28 mm). OpenSCAD při každém překladu vypíše odhad hmotnosti, těžiště a svislou
vůli LD06.

## Co z modelu vychází

1. **LD06:** navržený střed je `[47, 0]` a spodek `z = 22 mm`. Ověřená rovina
   vrtulí je v modelu na `z = 14,8 mm`, takže nominální vůle je **7,2 mm**;
   současně je spodek 2 mm nad odhadovaným vrškem ductu (`z = 20 mm`).
   Půdorys LD06 se s předními vrtulemi překrývá; musí proto být celý nad jejich
   rovinou. Optické okno je výš než ducty a přímý dopředný paprsek vede středovou
   mezerou. Čistých 360° ale na tomto rámu nebude: boční a zadní sektory zastíní
   ducty, baterie a nástavba. Před koupí je nutné ověřit vibrace držáku a skutečný
   obrys ductů.
2. **Těžiště:** s LD06 na `x = +47 mm` vyvažuje kompaktní baterie se středem na
   `x = −28 mm` předozadní moment téměř přesně. Z publikovaných hmotností a 27,3 g
   přiznaného odhadu kabeláže/montáže vychází přibližně **294 g** a těžiště
   `[0,0; 0,0; 17,1] mm`. Posun baterie o 10 mm posune celkové těžiště asi o
   2,4 mm. Jde o orientační výsledek; rozhodne vážení hotové sestavy.
3. **MTF-02P:** je pod deskou u středu, ne pod baterií. Model počítá s vyhrazeným
   otvorem v desce a ukazuje 42° kužel dolů. V této poloze je výhled čistý;
   skutečný rám ale musí mít otvor nebo průhledné okno a je třeba doměřit polohu
   optiky a děr senzoru.
4. **Kamera:** objektiv je před středovým zúžením mezi předními ducty a modelovaný
   50° kužel do nich nevstupuje. Průměr objektivu 19 mm je známý, tělo kamery,
   jeho vyložení a přesný FOV jsou odhady. Závěr je proto návrh polohy, ne potvrzení
   kompatibility.
5. **USB FC:** při šipce FC směrem +X je USB-C na levém (+Y) okraji. Tyrkysová
   servisní obálka ukazuje přímý kabel a červeně jeho konflikt s odhadovaným
   ductem. Se smontovanou horní baterií tedy nelze spoléhat na běžný rovný kabel;
   doporučený je předem osazený krátký 90° USB-C prodlužovací kabel vyvedený pod
   boční okraj. Přesný závěr vyžaduje výkres nebo změření rámu a canopy.

## Jistota rozměrů

Normální barvy značí publikované obálky: rozvor a polohy motorů, desku tlustou
2,5 mm, motory 18,2 × 13,8 mm, vrtule 76 mm, FC 36 × 36 × 8 mm s roztečí 25,5
mm, RX 18,4 × 10,4 mm, MTF-02P 21,6 × 16 × 6,5 mm, obě baterie a LD06 38,59 ×
38,59 × 33,5 mm. LD06 používá také průměr věžičky 35,29 mm a výšku optického
okna 7,8 mm z montážního výkresu.

**Purpurová** geometrie je placeholder: přesný obrys desky, průměr a výška
ductů, držák LD06 a otvor pro MTF-02P. **Oranžová** je neověřená obálka/pozice
Wyvern Link Alpha, tělo kamery a některé drobné výšky. Červené průsvitné disky
jsou roviny vrtulí, zelené objemy zorná pole, tyrkysový objem servisní prostor
USB a žlutý kříž odhadnuté těžiště.

Rozměry LD06 jsou z jeho datasheetu; rozvor, tloušťka desky a montážní rozteče
rámu z podkladů GEPRC; rozměry FC a MTF-02P z podkladů MicoAir. Přesná geometrie
rámu a Wyvernu nebyla výrobcem v použitých podkladech publikována, proto nebyla
domýšlena jako ověřená.

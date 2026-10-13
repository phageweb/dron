# Vyvážení Pavo20 Pro s Lite+ a modulárním D500

Aktualizováno 13. 10. 2026 po opravě kolizí a doplnění držáku GPS.
**Jde o výpočet z odhadovaných hmotností a poloh, nikoli fyzické měření.**

## Aktuální výsledky

| Baterie | D500 | Hmotnost | Baterie dopředu | Baterie doleva | CG Z |
| --- | --- | ---: | ---: | ---: | ---: |
| 750 mAh | ne | 174.41 g | 3.49 mm | 0.41 mm | -15.26 mm |
| 750 mAh | ano | 227.40 g | 3.49 mm | 0.41 mm | -2.43 mm |
| 550 mAh | ne | 162.41 g | 4.22 mm | 0.50 mm | -13.68 mm |
| 550 mAh | ano | 215.40 g | 4.23 mm | 0.50 mm | -0.52 mm |

Souřadnice: X doprava, Y dozadu, Z nahoru; Z=0 je horní plocha karbonu.
Posun baterie je vůči středu čtyř motorů, nikoli vůči kraji držáku.
Záporné X/Y v JSON tedy znamená doleva/dopředu. Setiny mm jsou jen výstup
výpočtu, ne požadovaná přesnost montáže.

D500 s mostem přidává **52,99 g**. Svislé těžiště zvedá o **12,83 mm**
s 750mAh packem a **13,16 mm** s 550mAh packem. S lidarem je CG přibližně
**13,07 / 14,98 mm nad modelovanou rovinou vrtulí** (z=−15,5 mm).
Senzor nad středem motorů má malý podélný moment, ale přidává hmotnost
ve výšce; výpočet CG neověřuje tuhost, vibrace ani letové chování.

S baterií přesně uprostřed by s D500 vyšlo CG:

- 750 mAh: X=+0,13 mm, Y=+1,06 mm.
- 550 mAh: X=+0,13 mm, Y=+1,12 mm.

Automatický posun baterie právě tyto momenty kompenzuje. Nulové X/Y
v automatickém režimu neznamená změřené dokonalé vyvážení.

## Co je nově započítáno

- GPS je na `[0,49,6.5]` mm. Vanička a dvě nosná ramena jsou součástí
  `1-base.stl`; jejich hmotnost a moment jsou zahrnuté v integraci základny.
- Pod GPS se počítá s 1mm nevodivou lepicí podložkou. Její odhad 0,2 g
  je odečten z rezervy 13,36 g na kabeláž a montáž a umístěn pod GPS,
  takže není započítaný dvakrát.
- Kamera se svým odhadovaným těžištěm otáčí při změně úhlu. Výchozí
  těžiště kamery je 3 mm před osou otáčení v lokálních souřadnicích.
- Objímka přebírá těžiště ze STL a používá stejnou transformaci jako model.
- Anténa má těžiště v polovině své modelované délky 32 mm a otáčí se
  spolu s objímkou. Skutečné hmotové rozložení antény je třeba ověřit.
- Most D500 používá správnou inverzi tiskového otočení. Senzor má
  samostatně nastavitelné `lidar_cg_x_offset`, `lidar_cg_y_offset`
  a `lidar_cg_z_offset`.
- Hmotnosti výtisků a jejich lokální těžiště už nejsou ručně přepisované
  konstanty v hlavním modelu. `refresh_model.py` exportuje STL, integruje
  jejich objem a první moment a vytvoří `print_mass_properties.scad`.

## Hmotový rozpočet

| Položka | Hmotnost | Jistota |
| --- | ---: | --- |
| Rám bez původního O3 držáku | 28,70 g | Projektový kusovník; střed odhadnutý. |
| Čtyři motory | 24,80 g | Publikováno v kusovníku. |
| Vrtule | 2,32 g | Publikováno v kusovníku. |
| FC | 10,00 g | Publikováno v kusovníku. |
| RX | 1,60 g | Publikováno v kusovníku. |
| MTF-02P | 1,50 g | X=19 mm; samostatný držák stále není navržený. |
| GPS WS-M181 | 4,30 g | Publikovaný údaj, nová poloha v zadní vaničce. |
| Lite+ kit | 10,50 g | Rozdělení kamera 2 / VTX 8 / anténa 0,5 g je odhad. |
| Kabeláž, montáž a lepicí podložka GPS | 13,36 g | Rezerva; 0,2 g z ní je umístěno pod GPS. |
| Základna včetně vaničky GPS | 7,385 g | Plný objem STL × 1,25 g/cm³. |
| TPU objímka | 0,941 g | Plný objem STL × 1,20 g/cm³. |
| Most D500 | 5,989 g | Plný objem STL × 1,25 g/cm³. |
| D500 | 47,00 g | Konzervativní projektový odhad; zvážit s letovým kabelem. |
| Tattu 750 mAh 4S HV | 69,00 g | Koupený pack 77 × 18 × 28 mm; publikovaný údaj. |
| Tattu 550 mAh 4S HV | 57,00 g | Koupený pack 68 × 16 × 26 mm; publikovaný údaj. |

Těžiště základny: `[0,13.72201,2.98528]` mm. Těžiště mostu v sestavě:
`[0,0.08474,18.70549]` mm. U D500 zůstává odhad `[0,0,42.5]` mm.
Nová základna váží odhadem o 2,63 g více než před opravou, převážně vzadu;
proto potřebuje baterie větší posun dopředu než v původním výpočtu.

Všechny hmotnosti jsou neověřené vážením. Skutečný infill a materiál
změní hmotnost výtisků. Pro zvážené výtisky zadej kladné hodnoty
`base_measured_mass`, `insert_measured_mass`, `lidar_mount_measured_mass`;
nula znamená odhad z objemu. Přepnutí hmotnosti zachovává geometrické
objemové těžiště dílu (předpoklad rovnoměrného rozložení materiálu).

## Výpočet a nastavení

`CG = součet(m_i * poloha_i) / součet(m_i)`.
Cílová poloha baterie v každé vodorovné ose:
`p_bat = −součet(m_i * p_i bez baterie) / m_bat`.

Podélný posun je omezen na ±10 mm. Boční rozsah je odvozen z 20mm slotu,
šířky baterie a 0,2mm rezervy: ±0,8 mm pro 750 a ±1,8 mm pro 550.
Při nedostatečném rozsahu se poloha omezí, vypíše varování a CG si zachová
zbytkovou odchylku. Ruční režim `auto_balance_battery=false` používá
`battery_manual_x` a `battery_manual_y`; výsledek se dále skutečně počítá.

Poloha GPS je sdílená mezi geometrií a výpočtem. Rozměrové změny tištěných
dílů vyžadují **nový export a integraci**; samotné přestavení Customizeru
nepřepočítá již uložené objemové vlastnosti. Pro přepočet změň výchozí
parametry v SCAD a spusť:

```sh
python3 refresh_model.py
```

Skript obnoví všechny tři STL, `mesh_report.json`, `print_mass_properties.scad`,
`balance_report.json`, `audit_report.json` a `clearance_report.txt`.
Tato textová tabulka je snímek současné revize; po dalších změnách jsou
rozhodující aktuální JSON výstupy. `balance_report.json` obsahuje pro každou
variantu i celý pojmenovaný hmotový rozpočet a CG při baterii uprostřed.

Skript kontroluje 12 konfigurací, čtyři průniky skutečných exportovaných STL,
nezávislý součet hmotností a momentů v Pythonu, ruční polohu baterie a
transformace kamery/mostu. Záměrně vrácená stará poloha GPS a rozteč mostu
musejí znovu vyvolat objemovou kolizi; test tak nespoléhá jen na prázdný výstup.

## Doladění na hotovém dronu

1. Zvaž hotové výtisky, GPS/D500, packy a kompletní dron; uprav rozpočet.
2. Zkontroluj skutečný rozměr kamery, konektor GPS, hlavy a délky šroubů.
3. Ověř vůle na rámu a vůči celému rozsahu vrtulí, včetně kabelů a jejich průhybu.
4. S odpojeným napájením dolaď podélné a boční vyvážení baterií a označ polohy.
5. Zopakuj pro oba packy s lidarem i bez něj. Tuhost mostu a vibrace ověř samostatně.

Zdroje a montáž: [README.md](README.md). Výsledky kontroly:
[KONTROLA_MODELU.md](KONTROLA_MODELU.md).

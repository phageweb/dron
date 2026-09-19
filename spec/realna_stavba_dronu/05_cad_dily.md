# Díly pro CAD model

Tohle není kusovník - ten je v [tabulce komponent](./03_komponenty.md) a řeší
hmotnosti, napětí a rozhraní. Tady jde o **geometrii**: co je jak velké, kde má
díry a kam to na rámu patří, aby z toho šel postavit model.

## Souřadnice

Stejné jako v ROS modelu, aby se ty dva nerozešly:

- počátek v `base_link`, tedy geometrický střed rámu v rovině horní desky
- **X dopředu**, **Y doleva**, **Z nahoru**
- motory v quad X na `±45.25 mm` v X i Y, což je půl rozvoru 128 mm děleno
  odmocninou ze dvou — to je **CineLog30 V3**; varianta Pavo20 má rozvor 93,7 mm,
  tedy `±33.13 mm`, a celý tenhle dokument je psaný pro CineLog

## Jistota

Sloupec říká, odkud číslo je. **Rozměry označené `sim`** jsou z dnešního Gazebo
modelu, kde jsem je odhadl, aby model vypadal jako cinewhoop - **nejsou měřené a
do CADu se nemají opisovat jako fakt**. Sloužily jen k tomu, aby fyzika měla
rozumné bloky.

## Ověřené rozměry

| Díl | Rozměry | Uchycení | Zdroj |
| --- | --- | --- | --- |
| Rozvor | 128 mm mezi protilehlými motory | - | **GEPRC, stránka rámu V3** |
| Karbonová deska | tloušťka 2.5 mm | - | GEPRC V3 |
| Rám - uchycení FC | - | 25.5 × 25.5 mm | GEPRC V3 |
| Rám - uchycení VTX | - | **20 × 20 mm i 25.5 × 25.5 mm** | GEPRC V3 |
| Rám - uchycení motoru | - | **9 × 9 mm** | GEPRC V3 |
| Rám - uchycení kamery | - | 20 mm | GEPRC V3 |
| Motor GEPRC SPEEDX2 1404 | ⌀18.2 × 13.8 mm, hřídel ⌀1.5 mm, vývody 160 mm | 9 × 9 mm, viz rám | vendor |
| Vrtule HQ DT76MMX3 V2 | ⌀76 mm, 3 listy | náboj na ⌀1.5 mm hřídel | vendor |
| FC MicoAir H743 V2 45A AIO | 36 × 36 × 8 mm | **25.5 × 25.5 mm** | vendor |
| RX SpeedyBee ELRS Nano | 10.4 × 18.4 mm | lepený/stahovací | vendor |
| Anténa RX | T-anténa 54 × 78 mm | IPEX1 | vendor |
| MicoAir MTF-02P | 21.6 × 16 × 6.5 mm | neověřeno | prodejce |
| Baterie Tattu 4S LiHV 750 | dvě provedení: 60 × 31 × 27 mm, nebo „long" 76 × 17 × 28 mm | pásek | prodejci |
| **LDRobot LD06** | celkem 38.59 × 38.59 × 33.30 mm; rotující hlava ⌀35.29 × 12.60 mm | **28.20 × 28.20 mm, díry ⌀2.5**, z toho 2× ⌀4.8 hlubší | [datasheet](https://www.inno-maker.com/wp-content/uploads/2020/11/LDROBOT_LD06_Datasheet.pdf), montážní výkres |
| LD06 - optické okno | pás vysoký 6.0 mm, horní hrana 7.6 mm pod vrškem, **střed 22.7 mm nad základnou** | nesmí být ničím zastíněné | tamtéž |
| LD06 - konektor | ZH1.5T-4P, rozteč 1.5 mm, na boku základny | - | tamtéž |

## Rozměry, které chybí

Tyhle se z webu vytáhnout nedaly a **do modelu je potřeba je doplnit z
datasheetu nebo změřit**, až díly dorazí:

| Díl | Co chybí | Kde to vzít |
| --- | --- | --- |
| **EMAX Wyvern Link Alpha** | rozměr desky (uchycení 25.5 × 25.5 je známé), rozměr kamerového modulu, vyložení objektivu | manuál EMAX; objektiv je 19 mm |
| Rám GEP-CL30 V3 | vnitřní a vnější průměr ductu, výška ductu, obrys spodní desky, rozmístění stojin, prostor pod kanopou | výkres GEPRC, nebo změřit; V3 stránka je neuvádí |
| Motor 1404 | rozteč montážních děr (obvykle 9 × 9 mm u 1404, neověřeno) | datasheet |
| MTF-02P | poloha a průměr montážních děr | MicoAir |

Bez rámu je model stejně jen sestava komponent ve vzduchu, takže **duct a spodní
deska jsou to nejdůležitější, co zbývá dohledat**. LD06 už dohledaný je: jeho
rozměry, rozteče i výška okna jsou v tabulce výš, z montážního výkresu
v datasheetu. Ten výkres je v PDF jako obrázek, takže z něj text nevytáhne -
stránku je potřeba vyrenderovat a přečíst očima.

## Pozor na záměnu V1 a V3

Prodejci vedou pod jménem „GEP-CL30" i **starší rám**, a jeho čísla jsou jiná:
rozvor **126 mm**, desky 2.0 mm nahoře i dole a 3.0 mm ramena, hmotnost 62.6 g,
celkově 180 × 180 × 38 mm a **vnitřní průměr ductu 79 mm**.

Pro V3 platí čísla z tabulky výš, tedy rozvor 128 mm, desky 2.5 mm a 78 g. Ta
jediná věc, která se ze staršího listu hodí, je **vnitřní průměr ductu 79 mm** -
vrtule je u obou stejná 3", takže se dá převzít jako odhad, dokud GEPRC nevydá
výkres V3. V modelu je proto duct označený jako odhad, i když to číslo odněkud
je.

## Co model musí zodpovědět

Kvůli tomu se staví, ne kvůli obrázku:

1. **Kam LD06.** Musí vidět dopředu mimo ducty a nesmí zasahovat do roviny
   vrtulí. To je otevřená otázka, která může celou volbu senzoru zabít, viz
   [rozhodnutí](../../workflow/decisions.md).
2. **Těžiště.** Baterie nahoře nebo dole, a jak daleko dozadu, aby vyvážila LD06
   vpředu.
3. **Výhled MTF-02P dolů** bez stínění spodní deskou nebo baterií.
4. **Kam kamera Wyvernu**, aby nekoukala do ductu.
5. **Přístup k USB** na FC, když je všechno smontované.

## Poznámka k rozměrům v simulaci

Bloky v `models/openipc_cinewhoop/model.sdf` jsou přibližné: tělo
105 × 105 × 18 mm, kamera 26 × 22 × 20 na x = 68, rangefinder na x = 20,
z = -16. Vznikly proto, aby model vypadal a choval se jako cinewhoop, ne
z výkresu.

**Lidar mezi ně už nepatří.** Stálo tu „18 × 30 × 14 na x = 73", což byl
placeholder; dnes je to skutečná kostka LD06 **38,6 × 38,6 × 33,3 mm** na
x = 46, z = 50 — tedy na stožáru, protože tělo senzoru překrývá disky vrtulí
v jakékoli výšce a musí je minout celé. Ta hmotnost navíc visí na
`front_lidar_link`, ne v `base_link`, aby Gazebo složilo setrvačnost z místa,
kde senzor doopravdy je.

Až bude CAD stát na skutečných rozměrech, mají se **hodnoty přenést do simulace**,
ne naopak. Hlídat to umí `scripts/check_model_consistency.py`, který dnes drží
shodu URDF a SDF - CAD by byl třetí místo, kde se geometrie může rozejít.

## Kde ty CAD modely jsou

Tenhle dokument vznikl dřív, než nějaký model existoval. Dnes jsou v repu tři
a je mezi nimi rozdíl v tom, co si smí nárokovat:

| Adresář | Drak | Co to je |
| --- | --- | --- |
| `cad_claude/` | CineLog30 V3 | koncepční model |
| `cad_codex/` | CineLog30 V3 | nezávislý koncept postavený proti stejnému zadání |
| `cad_pavo20/` | Pavo20 Pro | **obalová studie**, ne výrobní výkres |

`cad_pavo20/drone.scad` stojí jen na rozměrech z kusovníku a barevně odlišuje
jistotu údaje — co je fialové, se musí změřit na plastu. Přesto chytil dvě věci,
které tabulky ukázat nemohly: lidar nemůže sedět tam, kam ho posadí výpočet
těžiště, protože rovina skenu pak míří pod baterii; a baterie se montuje zespodu
do duktové sestavy, což sráží těžiště **5 mm pod rovinu vrtulí** proti
CineLogovým 2,3 mm nad ní. Obojí je zapsané jako oprava v
[Pavo20 jako nosič LD06](./10_pavo20.md), ne vyretušované.

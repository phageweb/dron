# Kontrola Pavo20 Pro / Ascent Lite+ / D500 — 13. 10. 2026

**Verdikt: STL sítě jsou v pořádku, sestava ale potřebuje dořešit montážní
kolize a přeměřit kameru. Výpočet těžiště je matematicky správný pro zadané
odhady, nikoli potvrzené vyvážení skutečného dronu.**

Kontrolovány `1-base.stl`, `2-camera_insert.stl`, `3-d500_module.stl`
a jejich zdrojové SCAD. Tiskové díly ani původní výpočty nebyly změněny.
Přidán je tento protokol, `audit_mounting.scad` a `audit_report.json`.

## Nálezy před finálním tiskem

### 1. Sloupky mostu zasahují do prostoru hlav rámových šroubů

Rámové otvory jsou v X=±13, Y=±22,8 mm; sloupky mostu v X=±13,
Y=±18 mm. Vzdálenost středů je jen **4,8 mm**. Sloupek má poloměr
3,2 mm. S hlavou šroubu Ø3,8 mm vzniká přesah **0,3 mm**, s Ø4,2 mm
**0,5 mm**. Platí pro hlavy nad základnou a válcovou obálku hlavy;
skutečný profil a způsob montáže je třeba porovnat s použitým šroubem.

Průnik skutečného STL mostu se čtyřmi hlavami Ø3,8 × 1,4 mm je nenulový,
celkem přibližně **1,833 mm³**. Původní kontrola hlavy rámových šroubů
nezahrnuje. Bez vůle by se sem vešla nejvýše válcová hlava Ø3,2 mm.

Možná úprava: rozteč sloupků `lidar_dock_y` z 36 na 34 mm **v základně
i mostu**, nebo místní vybrání pro hlavy. Rozteč 34 mm by podle vzdálenosti
os poskytla 0,5 mm vůle pro Ø4,2 mm. Po úpravě je nutný nový export obou
dílů, kontrola zbylých stěn, kolizí a aktualizace hmotností. Návrh úpravy
nebyl v tomto auditu realizován ani pevnostně ověřen.

### 2. GPS koliduje s držákem antény i s anténou

GPS obálka 18 × 18 × 4,6 mm na `[0,42,6]` zasahuje do zadního úchytu
v `1-base.stl`. Objem průniku je přibližně **19,921 mm³**. Samotná
modelovaná anténa protíná GPS také, přibližně **2,577 mm³**.

Změnit polohu a doplnit reálné upevnění GPS; nyní je to pouze referenční
obálka. Potom změnit současně vykreslení i `mass_items`. Posun GPS o 4 mm
dozadu by sám vyžadoval další posun baterie dopředu asi o 0,25 mm (750)
nebo 0,30 mm (550), bez hmotnosti případného nového držáku.

### 3. Objímka kamery zatím nemá ověřenou dutinu pro skutečné tělo

Dutina má **14,3 × 12,3 × 4,8 mm** mezi zarážkami. Vychází z odhadu
těla 14 × 12 × 4,5 mm. Výrobce uvádí celé rozměry 12 × 14 × 15,8 mm,
nikoli tloušťku těla bez objektivu. Proto samotný soulad s celkovými
rozměry kamery nestačí k potvrzení, že se kamera vejde a zacvakne.

Objímka má vnější šířku 19,8 mm a v nové základně mezeru 20 mm, tedy
0,1 mm na každé straně. Za slepým otvorem pro boční šroub zbývá nominálně
1,25 mm materiálu. Záběr M2×4 vychází 1,5 mm při bočnici 2,4 mm a mezeře
0,1 mm — přesně do navržené hloubky, bez rezervy pro stlačení TPU.
Přeměřit kameru, zarážky vůči součástkám a skutečné šrouby. Použít TPU.

## Co prošlo

- Všechny tři STL mají jednu souvislou komponentu, uzavřené hrany,
  konzistentní orientaci a kladný objem. Tato kontrola sama není obecný
  důkaz absence všech samoprůniků nebo mechanické pevnosti.
- Nové exporty všech tří dílů ze současných SCAD mají totožné množiny
  trojúhelníků jako dodané STL.
- Rozteč rámu **26 × 45,6 mm** odpovídá výkresu BETAFPV.
- VTX **20 × 20 mm, M2**, obálka 23,5 × 23,5 × 8 mm odpovídá CADDX.
- D500: rozteč dvojice otvorů **46,8 mm**, třetí otvor **31,92 mm**
  od jejich řady odpovídají výkresu STL-19P. Modelované díry Ø2,6 mm
  v mostu jsou pro průchozí M2; senzor má podle výkresu otvory Ø2,5 mm.
- Původní `check_clearances.scad` znovu prošel všech **12 kombinací**:
  baterie 550/750, lidar ano/ne, kamera 0/20/40°. Testuje modelované
  obálky a vybrané dvojice; nálezy výše záměrně doplňují jeho rozsah.
- Dodatečný průnik referenční kamery včetně objektivu a kabelového vývodu
  se základnou a mostem je při výchozích 20° prázdný.
- Mezi horní obálkou VTX a spodkem platformy je **7,6 mm**. Kabely,
  konektory a montážní materiál mohou tuto mezeru zmenšit.

| STL | Rozměry v tiskové poloze X × Y × Z | Objem | Odhad hmotnosti |
| --- | --- | ---: | ---: |
| 1-base | 33 × 75,90 × 18 mm | 3 807,34 mm³ | 4,76 g PETG |
| 2-camera_insert | 19,8 × 15,1 × 6,4 mm | 784,28 mm³ | 0,94 g TPU |
| 3-d500_module | 53,8 × 48,095 × 21,8 mm | 4 754,57 mm³ | 5,94 g PETG |

Hmotnosti předpokládají plný objem a hustoty 1,25 / 1,20 g/cm³;
skutečný výtisk závisí na materiálu a sliceru.

## Těžiště

Souřadnice: X doprava, Y dozadu, Z nahoru. Z=0 je vršek karbonu.
Následující čísla platí pro **současnou nezměněnou sestavu**, včetně
zatím kolidující polohy GPS a odhadovaných hmotností/poloh.

| Baterie | D500 | Hmotnost | Posun baterie dopředu | Posun doleva | CG Z |
| --- | --- | ---: | ---: | ---: | ---: |
| 750 mAh | ne | 171,78 g | 1,14 mm | 0,41 mm | −15,55 mm |
| 750 mAh | ano | 224,72 g | 1,15 mm | 0,41 mm | −2,51 mm |
| 550 mAh | ne | 159,78 g | 1,38 mm | 0,50 mm | −13,96 mm |
| 550 mAh | ano | 212,72 g | 1,39 mm | 0,50 mm | −0,57 mm |

Lidar s mostem přidává **52,94 g**. Protože leží nad středem motorů,
změna podélného vyvážení je v tomto modelu malá. Svislé těžiště se ale
zvedne o **13,05 mm** (750) nebo **13,39 mm** (550). S lidarem vychází
CG asi **13,0 / 14,9 mm nad modelovanou rovinou vrtulí**. Nulové X/Y
vzniká automatickým dopočtem baterie; není to změřená přesnost.

Hmotové rozdělení D500, rozdělení hmotnosti kamera/VTX/anténa, kabeláž,
skutečné výtisky i polohy spodní elektroniky jsou odhady. Hmotnost a držáky
GPS/MTF-02P je potřeba doplnit podle skutečné montáže. Změna kamery v úhlu
nemění současnou aproximaci jejího těžiště v `mass_items`. Tvrdě zadané
hmotnosti a těžiště výtisků se při změně rozměrů SCAD samy nepřepočítají.

Po odstranění kolizí zvážit sestavu a packy a doladit podélné/boční vyvážení
posunem baterie. Pevnost, rezonance a letové chování nejsou tímto auditem
ověřené. Přesný karbon, ducty, silentbloky, konektory a vodiče nejsou
zastoupeny výrobními modely.

## Opakování nalezených kolizí

```sh
openscad -D 'part="check"' -D 'audit_case="frame_heads_bridge"' -o /tmp/pavo-heads.stl audit_mounting.scad
openscad -D 'part="check"' -D 'audit_case="gps_base"' -o /tmp/pavo-gps-base.stl audit_mounting.scad
openscad -D 'part="check"' -D 'audit_case="gps_antenna"' -o /tmp/pavo-gps-antenna.stl audit_mounting.scad
```

Na kontrolovaných souborech všechny tři příkazy vytvoří **neprázdný**
průnik (návratový kód 0). Nejde o úspěšnou kontrolu vůle: dokládají kolize.
Používají skutečné STL základny/mostu a výchozí polohy sestavy;
po změně parametrů je nutné nejprve aktualizovat STL.

## Ověřené podklady

- [BETAFPV — výkres držáku a rozteče rámu](https://cdn.shopify.com/s/files/1/1778/6615/files/O3_Air_Unit_Bracket_diagram.jpg?v=1742891989).
- [BETAFPV — rozměry celého Pavo20 Pro](https://cdn.shopify.com/s/files/1/1778/6615/files/Pavo20_Pro_Frame_diagram_with_O3.jpg?v=1742891989).
- [CADDX — Ascent HD Lite+](https://www.caddxfpv.com/products/walksnail-ascent-hd-lite-plus-kit).
- [LDROBOT — STL-19P datasheet, PDF strana 7](https://files.waveshare.com/wiki/D500-LiDAR-Kit/LDROBOT_STL-19P_Datasheet_EN_v1.0%281%29.pdf).
- Místní kusovník `../spec/realna_stavba_dronu/13_nakoupeno.md` a
  původní `VYVAZENI.md`; nejde o záznamy fyzického vážení.

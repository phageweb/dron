> Archiv původní vložky, nahrazený kompletní sestavou. Aktuální návod: [README.md](README.md). Původní STL 19/20 mm jsou jen samostatné vložky.

# Pavo20 Pro – držák kamery Walksnail Ascent Lite+

Parametrická TPU objímka do **stávajících bočnic držáku kamery** Pavo20 Pro.
Nejde o náhradu celé canopy ani držák VTX. Kamera se zasouvá zezadu,
čtyři drobné přední a zadní zarážky drží její rohy. Uprostřed přední
i zadní strany zůstává otvor pro objektiv, mikrofon a kabel.
Náklon se nastavuje natočením celé objímky v původním držáku.

**Stav: rozměrový prototyp, fyzické usazení zatím neověřeno.**

## Soubory a použití

- `pavo20_pro_walksnail_lite_plus.scad`: zdroj pro OpenSCAD, bez knihoven.
- `archiv/pavo20_pro_walksnail_lite_plus_20mm.stl`: varianta pro mezeru 20 mm.
- `archiv/pavo20_pro_walksnail_lite_plus_19mm.stl`: varianta pro mezeru 19 mm.
- `preview.png`: náhled samotného držáku.

Otevři SCAD v OpenSCADu. `view="print"` zobrazí díl v tiskové poloze,
přední stranou dolů. F6 provede render a potom lze exportovat STL.
`view="assembly"` v F5 přidá orientační obálku kamery a bočnic.
Tyto šedé referenční objekty se neexportují. `preview_angle` mění jen
náhled, geometrie držáku nemá pevně daný úhel.

## Co ověřit posuvkou před tiskem

| Parametr | Výchozí hodnota | Podklad |
| --- | --- | --- |
| `mount_width` | 20 mm, druhý export 19 mm | Výrobce rámu uvádí 19/20 mm; změř skutečnou mezeru bočnic. |
| `camera_width` | 14 mm | Předpokládané přiřazení os publikovaných rozměrů. |
| `camera_height` | 12 mm | Předpokládané přiřazení os publikovaných rozměrů. |
| `body_depth` | 4,5 mm | **Odhad**, tloušťka obdélníkového těla bez objektivu; nutno změřit. |
| `camera_clearance` | 0,3 mm celkem | Návrhová vůle, není na každou stranu. |
| `screw_pilot` | 1,7 mm | Návrhový slepý otvor pro M2 do TPU. |
| `screw_depth` | 1,5 mm | Maximální zasunutí šroubu do objímky. |

Výrobce kamery uvádí celkové rozměry **12 × 14 × 15,8 mm**, ale na
produktové stránce nepřiřazuje osy a nekótuje tloušťku těla ani polohu
mikrofonu. Rozměr 15,8 mm proto **není** použit jako hloubka kapsy.
Předpokládaný průměr objektivu 10 mm slouží pouze pro náhled.
Zkontroluj, že rohové zarážky dosedají na pevný obal, nezakrývají mikrofon
a nedotýkají se součástek nebo konektoru. Podle potřeby uprav
`corner_length` a `lip_overlap`.

Uchycení počítá s jedním bočním šroubem z každé strany. Změř skutečnou
mezeru bočnic a ověř dostupnost vhodných původních otvorů; varianty O3/O4
se liší. Celková vůle mezi držákem a bočnicemi je 0,2 mm.
Pro 20mm variantu je obálka dílu 19,8 × 15,1 × 6,4 mm;
pro 19mm variantu 18,8 × 15,1 × 6,4 mm.

## Tisk a montáž

Navržený výchozí materiál: **TPU 95A**, vrstva 0,16–0,20 mm,
tryska 0,4 mm, 4 perimetry, plná výplň. Tiskni jako v `view="print"`,
obvykle bez podpor; zadní zarážky přečnívají jen 0,55 mm.
Jde o výchozí nastavení, nikoliv odzkoušený tiskový profil.
Objímka spoléhá na pružnost TPU při vložení kamery; pro PLA/PETG není
zacvakávací konstrukce ověřena.

1. Změř tělo kamery a mezeru bočnic, případně změň parametry a exportuj STL.
2. Zasuň kameru zezadu přes pružné zarážky bez tlaku na objektiv či kabel.
3. Do slepých bočních otvorů použij M2 šrouby se záběrem maximálně 1,5 mm
   **uvnitř adaptéru**. Délku zvol podle tloušťky bočnic a případných
   podložek; původní dlouhé šrouby nemusí vyhovovat. Šroub nesmí prorazit
   vnitřní stěnu a dotknout se kamery. Nepřetahuj závit v TPU.
4. Nastav náklon a ověř, že držák udrží úhel, kamera se nemůže vysunout,
   kabel má vůli a původní bočnice nejsou v obraze. Rozsah úhlu a kolize
   se skutečnou canopy je nutné ověřit na sestavě.

Vysílač není součástí modelu. Pro jeho případné další uchycení výrobce
uvádí 23,5 × 23,5 × 8 mm a rozteč 20 × 20 mm pro M2.

## Podklady

- [CADDX: Walksnail Ascent HD Lite+ Camera](https://www.caddxfpv.com/products/walksnail-ascent-hd-lite-camera)
- [CADDX: Ascent Lite+ Kit, rozměry kamery a VTX](https://www.caddxfpv.com/products/walksnail-ascent-hd-lite-plus-kit)
- [BETAFPV: Pavo20 Pro frame, kamera 19/20 mm](https://betafpv.com/products/pavo20-pro-brushless-whoop-frame)

Podklady ověřeny 12. 10. 2026. Model je určen pro **Ascent Lite+**;
rozměry kamery Avatar Mini 1S Lite nejsou v návrhu použity.

## Ověření geometrie

Obě STL byla vyrenderována v OpenSCAD 2021.01 (CGAL, `Simple: yes`).
Kontrola exportovaných sítí: každá má 896 trojúhelníků, jeden souvislý
uzavřený povrch a každou hranu sdílejí právě dva trojúhelníky.
Objemy jsou přibližně 688 mm³ (19 mm) a 784 mm³ (20 mm).
To ověřuje export, nikoliv fyzickou kompatibilitu nebo pevnost výtisku.

Opakovaný export:

```sh
openscad --export-format asciistl -D 'part="insert"' -o archiv/pavo20_pro_walksnail_lite_plus_20mm.stl pavo20_pro_assembly.scad
openscad --export-format asciistl -D 'part="insert"' -D 'mount_width=19' -o archiv/pavo20_pro_walksnail_lite_plus_19mm.stl pavo20_pro_assembly.scad
```

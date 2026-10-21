# Podklady pro rozmístění V2 (krok 2 předávky)

21. 10. 2026, Claude. Pracovní kopie: `build/aio/layout-v2-work/project/`, vybalená
z `baseline-v2.tar.gz` (SHA256 desky `7cd789d5…dd88` souhlasí s manifestem).

## Doplněné courtyardy

V desce chyběl courtyard u 42 instancí devíti pouzder, ne jen u U8, U303, J301 a J302.
Doplnil se obdélník = pady ∪ obrys těla (silk/fab) + 0,25 mm, zaokrouhlený ven na 0,05 mm,
do knihovny pracovní kopie i do instancí. Poloha byla u každé instance ověřena proti padům
(shoda všech padů, včetně duplicitních čísel u PowerDI3333). Bez courtyardu zůstává jen
`U24` (obrys desky, záměrně).

| Pouzdro | Instance | Courtyard (lokálně, mm) |
| --- | --- | --- |
| Diodes_PowerDI3333-8 | Q3–Q26 | −2,55…2,10 × −2,25…1,95 |
| QFN-28 4×4 | U13, U15, U17, U19 | −2,45…2,40 × −2,45…2,40 |
| QFN-24 4×4 EP2.8 | U14, U16, U18, U20 | −2,85…2,45 × −2,50…2,45 |
| LGA-14 3×2,5 | U8, U303 | −1,90…2,15 × −1,70…1,70 |
| IND 3×3 | L2, L3 | −1,90…1,90 × −2,10…2,10 |
| SOT-23-6 | U3, U4 | −2,25…1,90 × −1,95…1,95 |
| TF-021B (J302) | J302 | −6,45…6,40 × −3,45…3,55 |
| USB-C 16P QTWT (J301) | J301 | −5,95…6,05 × −3,15…5,45 |
| DFN-3L | Q301 | (už měl) |

Pravidla `missing_courtyard`, `malformed_courtyard`, `courtyards_overlap` a
`copper_edge_clearance` jsou v pracovní kopii zapnutá jako **warning**. Výchozí stav:
199 překryvů courtyardů, 41 `copper_edge_clearance` (všechny motorové/bateriové pady
a GND na hraně, záměrné), 1 `missing_courtyard` (U24).

Většina překryvů je důsledek obdélníkových obrysů v hustém ESC (QFN s 0201 kolem,
MOSFETy těsně vedle sebe), převzatém z OpenAIO. Kontrola na úrovni padů a těl
(bez montážní rezervy) nenašla kolizi těl kromě artefaktů obdélníku v rozích
(J301×J302, J302×Q3/Q5/Q7). Skutečné tělo J302 podle výkresu SOFNG je 0,76 mm
od padů Q3/Q5/Q7.

## microSD J302: otočení na 270° se nedoporučuje

Výkres SOFNG TF-021B (str. 2, „Circuit board size“): kontakty 1–8 jsou u **zadní**
hrany těla, karta vystupuje 9,70 mm za **přední** hranu (na opačné straně než kontakty),
celkem 15,2 mm od zadní hrany. V lokálních souřadnicích footprintu leží kontakty
na y = −1,25, tělo y −1,80…3,70 a vysunutá karta y 3,70…13,40.

- **Nyní (90°):** karta leží nad MCU, x 70,51…80,21, y 60,56…71,56. Pod ní je jen nízké
  osazení: U301 (TFBGA100), 0201, testovací pady a ploché pady J303. Stejně je karta
  nad MCU i na fotografii MicoAiru V2: tvar těla (zářez na zadní hraně) odpovídá TF-021B.
  **Ověřit na vzorku:** výška spodní plochy karty v patici proti max. výšce TFBGA100.
- **270° (návrh předávky):** karta by šla na západ, x 53,4…63,1, tedy 4,3 mm **přes okraj
  desky** a nad MOSFETy Q3/Q5/Q7 a pady motoru 1 s připájenými dráty. Zamítnuto.

J302 tedy zůstává na místě; kontakty mířící od MCU jsou dané typem patice a jsou
stejné i u MicoAiru.

## Pásmo pod kartou (y 60,6…71,6, x 70,5…80,2)

Pady pro připájení drátů (UART8, LD06, PWM) do tohoto pásma nepatří: drát by blokoval
kartu. SWD/NRST pady pod kartou vadí jen při ladění bez karty.

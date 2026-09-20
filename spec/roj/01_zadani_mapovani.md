# 01 – Zadání a kritéria

## 1. Úloha

Tři drony startují z různých míst v `cluttered_room.sdf`, letí nejvýše 130 s
(stejný rozpočet jako dnešní jednodronová kontrola) a vytvoří **jednu společnou
occupancy mapu** místnosti včetně vnitřku ohrady za dveřmi.

Svět se nemění. Je vybraný právě proto, že už jednou odmítl dvě jiné geometrie
za to, že nic neskrývaly — komentář v `scripts/check_room_coverage.sh:1-35` to
popisuje — a protože rozlišuje dvě různé úlohy: pilíř vrhá stín, který se sám
zaplní pohybem, zatímco do ohrady se musí vletět.

## 2. Co znamená „zmapováno"

Jedno číslo nestačí, protože pokrytí samo o sobě neříká, jestli byla cesta
dobrá. Měří se čtyři věci, všechny už dnes existujícím kódem:

| Veličina | Kde se počítá dnes | Význam pro roj |
| --- | --- | --- |
| podíl volné podlahy místnosti v mapě | `check_room_coverage.sh`, `MIN_ROOM_COVERAGE 0.40` | hrubá míra, snadno se nasytí |
| podíl vnitřku ohrady | tamtéž, bez horní meze při vletu dovnitř | **hlavní metrika**, jen sem se musí letět |
| délka každé dosažitelné stěny v mapě | `MIN_WALL_COVERAGE 0.80` | chytá mapu, která je jen mrak bodů |
| každá překážka má v mapě obsazené buňky | tamtéž | chytá mapu bez obsahu |

K nim tenhle úkol přidává tři, které s jedním dronem nemají smysl:

| Veličina | Jak se získá | Proč |
| --- | --- | --- |
| minimální skutečná vzdálenost dvojice | z ground truth v Gazebu | jediné bezpečnostní číslo, které nelze průměrovat |
| překryv práce | podíl buněk, které poprvé viděl víc než jeden agent v témže okně | měří, jestli přidělení cílů vůbec funguje |
| čas do pokrytí | kdy pokrytí poprvé překročí baseline jednoho dronu | jediná věc, kterou roj slibuje |

## 3. Baseline

> **NEPLATNÉ od 20. 9. 2026.** Tabulka níž je změřená na **CineLogu**, ne na
> Pavo20. `model://` se řeší přes `SDF_PATH`, který kontrolní skripty
> nenastavovaly, takže běh s `OPENIPC_AIRFRAME=pavo20` načetl CineLog model a
> odlétal ho s parametry Pavo20. Skripty jsou opravené; baseline se musí
> změřit znovu. Rozbor v `workflow/troubleshooting.md`, „The Airframe Switch
> Did Not Switch the Airframe". Čísla nechávám, protože jako **CineLog
> baseline** platí a rozptyl mezi běhy je použitelný odhad šumu měření.

Změřeno 19. 9. 2026, tři běhy `scripts/check_room_coverage.sh`, všechny
zelené. Plné znění v `workflow/log.md`.

| | run 1 | run 2 | run 3 | rozptyl |
| --- | ---: | ---: | ---: | ---: |
| podlaha místnosti | 94 % | 93 % | 93 % | 1 bod |
| vnitřek ohrady | 96 % | 95 % | 94 % | 2 body |
| stěna x− z dosažitelné části | 93 % | 97 % | 97 % | 4 body |
| stěna y+ | 92 % | 92 % | 92 % | 0 |
| pozice uvnitř ohrady | 16 % | 17 % | 16 % | 1 bod |
| nejhlubší dosažené y uvnitř | +1,04 m | +1,20 m | +1,17 m | 0,16 m |

**Šum je tedy asi 2 body na ohradě a 4 body na jedné stěně.** Rozdíl menší než
tohle není výsledek — a to je hlavní produkt M0, ne samotná čísla pokrytí.

Jedna věc z toho plyne pro K2: run 1 má nejlepší ohradu a zároveň nejmenší
průnik dovnitř, takže pokrytí ohrady není přímočará funkce toho, jak hluboko se
vletělo. Výsledek roje se musí číst spolu s dráhou, ne sám.

## 4. Meze přijetí

Zapsané **před** experimentem, jak to žádá
[`reserseRoju/04 §10`](../../reserseRoju/04_navrh_pro_tento_projekt.md):

| # | Kritérium | Mez |
| --- | --- | --- |
| K1 | minimální vzdálenost libovolné dvojice za celý let | nikdy pod `d_safe` z [03](./03_vrstva_roje.md) |
| K2 | pokrytí vnitřku ohrady | ≥ baseline jednoho dronu, na stejném rozpočtu času |
| K3 | pokrytí místnosti a stěn | ≥ dnešní meze, tj. 0,40 a 0,80 |
| K4 | čas do dosažení baseline | < 130 s; ideál je zlomek, ale slib to není |
| K5 | žádná ztracená identita | žádný povel nedorazí jinému agentovi, než kterému patří |
| K6 | reprodukovatelnost | tři běhy se zapsaným seedem, všechny splní K1–K3 |

K1 je jediné kritérium, které se nevyhodnocuje průměrem a nemá toleranci. Jedno
podlezení pod `d_safe` je neúspěch celého běhu, i kdyby mapa byla dokonalá.

## 5. Kdy úkol skončí neúspěchem

Předem pojmenované způsoby, jak tohle může dopadnout špatně, aby se pak
nepřevyprávěly jako úspěch:

- **Tři drony pokryjí méně než jeden.** Reálná možnost: bezpečnostní filtr může
  strávit většinu času brzděním, když jsou tři stroje v místnosti zhruba 8 × 6 m s
  koridorem 0,667 m (`CORRIDOR_WIDTH_M` v kontrole pokrytí). Pak je výsledkem
  číslo a závěr, že tahle místnost je na tři stroje malá — což je platný
  výsledek, ale musí se říct.
- **Mapa se rozejde.** Každý agent má vlastní EKF a vlastní drift z optického
  toku. Složená mapa pak má dvě stěny tam, kde je jedna. Viz [06](./06_slozena_mapa.md).
- **Simulace to neutáhne.** Tři SITL instance, tři modely s 360bodovým lidarem a
  tři mappery na jednom stroji. Rozpočet CPU je v [05](./05_infrastruktura_simulace.md)
  a je to riziko, ne jistota.
- **Výsledek nepůjde přičíst.** Když se vrstvy prolnou, nepůjde říct, jestli za
  to může koordinátor, nebo ladění jednoho stroje. Proto [04](./04_rozhrani.md).

## 6. Rozhodnutí

Odůvodnění je v [08](./08_rozhodnuti.md).

- **R1 — drak: Pavo20 Pro 4S**, rozhodnuto 19. 9. 2026. Menší kolizní obálka:
  geometrické minimum dvojice 0,1221 m proti 0,1667 m.
- **R2 — vzlet:** sekvenčně, v pořadí v1, v2, v3; chyba ruší další vzlety.
- **R3 — rozpočet:** 130 s zůstává kvůli srovnatelnosti, a vedle toho se měří
  čas do dosažení baseline.

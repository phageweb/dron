# Zmapovat prostor třemi drony v simulaci

Zadání: **tři drony společně zmapují `cluttered_room.sdf` v Gazebu** a výsledkem
je jedna mapa, jedno měření pokrytí a jedno číslo, které se dá porovnat s tím,
co dnes zvládne jeden stroj.

Tahle složka není rešerše. Rešerše už v repozitáři jsou dvě —
[`reserseRoju`](../../reserseRoju/README.md) pro koordinaci a
[`reserseDronu`](../../reserseDronu/README.md) pro stroj pod ní. Tohle je jejich
zúžení na jeden konkrétní úkol: co se musí postavit, co se musí změřit a v jakém
pořadí.

## Proč zrovna mapování

Protože ho repozitář umí měřit. `scripts/check_room_coverage.sh` už dnes
vyhodnocuje pokrytí místnosti a zvlášť vnitřek ohrady za dveřmi, má napsané meze
(`MIN_ROOM_COVERAGE 0.40`, `MIN_WALL_COVERAGE 0.80`, `MAX_COVERAGE_FROM_OUTSIDE
0.88`) a letí 130 s. Roj, který nemá s čím porovnat, je demo. Roj, který musí
porazit existující číslo na existující trati, je experiment.

Formace se tady nedělá. Tři drony, které drží trojúhelník, jsou hezčí na video a
řeší méně: mapování vynucuje **rozdělení práce, sdílenou mapu a vzájemné
rozestupy**, tedy přesně ty tři věci, kvůli kterým roj existuje.

## Hranice, kterou tenhle dokument zavádí

Celá složka stojí na jednom rozdělení:

```text
          vrstva roje              spec/roj/03_vrstva_roje.md
  koordinátor, přidělení cílů, složená mapa, rozestupy
                  |
                  |  cíl + omezení  (kontrakt, 04_rozhrani.md)
                  v
          vrstva jednoho dronu     spec/roj/02_vrstva_drona.md
  stav, rychlostní smyčka, vyhýbání zdi a podlaze, failsafe
```

Šev je konkrétní: roj posílá **cíl** a **omezení rychlosti**, povel do
autopilota skládá agent sám. Kdyby roj psal `cmd_vel` přímo, obešel by tím
vyhýbání zdi a podlaze — viz [08 R19](./08_rozhodnuti.md).

Pravidlo, které se nesmí porušit: **vrstva roje nikdy nesahá pod kontrakt.**
Neposílá motorové povely, nespoléhá na to, že zpráva dorazila, a nepředpokládá,
že agent její povel splní — smí předpokládat jen to, co kontrakt vyjmenovává.
Obráceně platí, že vrstva jednoho dronu nesmí vědět, že nějaký roj existuje:
každý agent musí projít stejnými `check_*.sh` sám, jako by byl jediný.

Důvod není estetický. Jakmile se ty dvě vrstvy prolnou, nejde odpovědět na
otázku „proč to spadlo" — a s třemi stroji ta otázka přijde.

## Obsah

- [01 – Zadání a kritéria](./01_zadani_mapovani.md): co přesně znamená
  „zmapováno", jaká je baseline jednoho dronu, jaké jsou meze přijetí a kdy
  experiment skončí neúspěchem.
- [02 – Vrstva jednoho dronu](./02_vrstva_drona.md): co musí platit o každém
  agentovi samostatně, co z toho už v repozitáři je a co chybí.
- [03 – Vrstva roje](./03_vrstva_roje.md): koordinátor, přidělení frontier cílů,
  rozestup `d_safe`, bezpečnostní filtr a chování při poruše.
- [04 – Rozhraní mezi vrstvami](./04_rozhrani.md): jmenné prostory, témata,
  frames, timeouty, epochy mise. Tohle je ta hranice, napsaná jako kontrakt.
- [05 – Infrastruktura simulace](./05_infrastruktura_simulace.md): co v
  repozitáři konkrétně brání třem instancím, s odkazy na soubory a řádky.
- [06 – Složená mapa](./06_slozena_mapa.md): jak ze tří dronů vznikne jedna
  mapa a jak se na ní měří pokrytí.
- [07 – Plán a milníky](./07_plan_a_milniky.md): M0–M5, každý s výstupem a
  kritériem ukončení.
- [08 – Rozhodnutí](./08_rozhodnuti.md): odpovědi na otázky z 01–06, s důvody.
  Otevřené zůstaly čtyři a žádné neblokuje M0.

## Co se v tomhle úkolu nedělá

- **Žádné železo.** Cíl je SITL a Gazebo. Fyzický roj má v
  [`reserseRoju/04 §13`](../../reserseRoju/04_navrh_pro_tento_projekt.md) sedm
  otevřených rozhodnutí a čtyři z nich nejsou zodpovězené.
- **Žádný decentralizovaný roj.** Koordinátor běží na zemi jako jeden uzel.
- **Žádný multi-robot SLAM.** Mapa se skládá z poloh, které dává EKF každého
  agenta; korekce smyčky ani vzájemná detekce dronů se neřeší.
- **Žádná formace.** Rozestup je omezení, ne cíl.
- **Žádné učení.** Nejdřív musí existovat měřitelná klasická baseline.

## Stav

Založeno 19. 9. 2026. Zatím je hotové zadání a rozhodnutí; žádný kód pro víc než
jednu instanci v repozitáři není a `05` vyjmenovává proč. Roj poletí na
**Pavo20 Pro 4S** (rozhodnuto 19. 9. 2026). Otevřené zůstávají shoda originů
EKF, `d_safe` jako číslo, práh konfliktních buněk a rozpočet CPU — všechno v
[08](./08_rozhodnuti.md), a nic z toho neblokuje M0.

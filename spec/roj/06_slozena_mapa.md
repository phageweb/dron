# 06 – Složená mapa

Tři drony, jedna mapa. Tohle je ta část úkolu, která je vlastním obsahem
zadání — všechno ostatní jen zajišťuje, aby k ní vůbec došlo.

## 1. Dvě varianty a proč se má vybrat první

| | A: mapuje agent, skládá koordinátor | B: mapuje koordinátor ze scanů |
| --- | --- | --- |
| co posílá agent | `OccupancyGrid` ~1 Hz | `LaserScan` 10 Hz |
| pásmo | malé | trojnásobek dnešního lidaru |
| kde vzniká drift | u agenta, lokálně | centrálně, ale ze tří poloh |
| co se stane při výpadku spojení | agent mapuje dál | agent nemapuje nic |
| změna dnešního kódu | prakticky žádná | mapper musí umět tři zdroje |
| skládání | slučování mřížek | přirozené, jedna mřížka |

**Doporučení: A.** `occupancy_mapper` dnes existuje, má mřížku 20 × 20 m při
0,10 m, frame `map` a bere témata jako parametry — tři instance jsou otázka
konfigurace. Slučovací uzel je nový kód, ale malý a testovatelný bez simulace,
na uložených mřížkách.

Varianta B je čistší v teorii a dražší v každém ohledu, který se tady měří.

## 2. Slučovací pravidlo

Všechny tři mřížky sdílejí rozlišení, rozměr i frame, takže slučování je
buňka po buňce a nepotřebuje registraci:

| v1 | v2 | výsledek |
| --- | --- | --- |
| neznámá | cokoli | to druhé |
| volná | volná | volná |
| obsazená | obsazená | obsazená |
| volná | obsazená | **rozhodnout** |

Poslední řádek je celý problém. Tři možnosti:

1. **Konzervativně:** obsazená vyhrává. Bezpečné, ale jeden falešný odraz
   zanese do mapy překážku, kterou už nikdo neodstraní.
2. **Podle stáří:** vyhrává novější měření. Chová se rozumně, když se něco
   pohnulo — třeba jiný dron.
3. **Pravděpodobnostně:** log-odds, jak to dělá klasický occupancy mapping.
   Správně, ale znamená to změnu dnešního mapperu.

Pro první verzi stačí 1 s tím, že se do logu zapíše, kolikrát ke konfliktu
došlo. Ten počet je sám o sobě měření kvality lokalizace.

## 3. Dron jako překážka v cizí mapě

Lidar jednoho agenta uvidí druhého a zanese ho do mapy jako stěnu. V místnosti,
kterou tři stroje přelétají 130 s, to není okrajový jev.

Řešení, seřazená podle poctivosti:

- **Maskovat podle známých poloh.** Koordinátor ví, kde jsou všichni tři;
  zahodit returny do koule `r_rotor + rezerva` kolem cizí polohy. Funguje jen
  tak dobře, jak dobře znají svou polohu — což je zase [04 §3](./04_rozhrani.md).
- **Nechat je tam a měřit.** Spočítat, kolik obsazených buněk zmizí po
  maskování; to je číslo, které nikdo v tomhle repozitáři nezná.
- **Ignorovat.** Přijatelné jen do M3, a jen když je to napsané.

Rešerše varuje před opačným předpokladem — že lidar souseda spolehlivě **uvidí**
a půjde na tom stavět vyhýbání. Tady jde o opak: uvidí ho dost na to, aby to
mapu pokazilo, a málo na to, aby se tomu dalo věřit.

## 4. Měření pokrytí

`check_room_coverage.sh` čte dnes jedno téma mapy a jednu dráhu. Pro tři agenty
se musí rozšířit, ale **jeho metrika se měnit nesmí** — jinak přestane platit
srovnání s baseline, kvůli kterému celý úkol existuje.

- [ ] Číst `/swarm/map` místo `/openipc_cinewhoop/map`, jinak tentýž výpočet.
- [ ] Číst tři dráhy a vyhodnotit „byl někdo uvnitř ohrady" jako sjednocení.
- [ ] Přidat minimální vzdálenost dvojice z ground truth (K1).
- [ ] Přidat překryv práce: buňky, které se poprvé objevily u víc než jednoho
      agenta v témž okně.
- [ ] Nechat prahy `MIN_ROOM_COVERAGE`, `MIN_WALL_COVERAGE` a
      `MAX_COVERAGE_FROM_OUTSIDE` beze změny.

## 5. Rozhodnutí

Odůvodnění je v [08](./08_rozhodnuti.md).

- **R16 — mřížka 20 × 20 m při 0,10 m zůstává.** Velikost problém není. Problém
  je, že mřížka je vystředěná na počátek frame (`occupancy_mapper.py:94-98`),
  kterým je origin EKF daného agenta: tři různé originy znamenají tři mřížky
  vystředěné na tři různá místa, všechny pojmenované `map`. **Změřit v M2.**
- **R17 — rozejití map** se sleduje podílem konfliktních buněk z §2. Počítá se
  při každém sloučení, práh se zapíše před prvním během M5.
- **R18 — složená mapa se agentům neposílá.** Dostávají hotové cíle a nic
  jiného s ní nedělají.

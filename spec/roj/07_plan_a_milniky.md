# 07 – Plán a milníky

Šest milníků. Každý má jeden výstup a jedno kritérium, po kterém se pozná, že
je hotový. Milník bez měření není hotový, i když kód běží.

Plán je zúžením fází A–F z
[`reserseRoju/04 §9`](../../reserseRoju/04_navrh_pro_tento_projekt.md) na tenhle
konkrétní úkol; fáze F (fyzické stroje) sem nepatří vůbec.

## M0 — baseline jednoho dronu

**Proč první:** bez ní nemá výsledek roje s čím být porovnán.

- [x] Potvrdit drak: **Pavo20 Pro 4S**, rozhodnuto 19. 9. 2026.
- [x] Třikrát `OPENIPC_AIRFRAME=pavo20 scripts/check_room_coverage.sh`, zapsat
      všechna čtyři čísla.
- [x] Zapsat rozptyl mezi běhy.

*Hotovo* 19. 9. 2026. Tabulka je v `workflow/log.md` a v
[01 §3](./01_zadani_mapovani.md); šum je 2 body na ohradě a 4 na jedné stěně.
Vedlejší nález, který půjde s sebou do M2: sekvenční běhy potřebují mezi sebou
`ros2 daemon stop`, jinak druhý běh uvidí uzel prvního, který už neběží —
`workflow/troubleshooting.md`.

## M1 — chybějící čísla jednoho dronu

**Proč druhý:** `d_safe` má pět členů a tři z nich nikdo nezná
([03 §3](./03_vrstva_roje.md)).

- [x] Brzdná dráha pro 0,25 / 0,5 / 1,0 m/s, ground truth z Gazeba.
- [x] End-to-end latence povel → pohyb, včetně jitteru.
- [x] Chyba sledování rychlosti na kroku a rampě.
- [x] Drift polohy proti ground truth — ve visu i přes celou sortu.
- [x] Z brzdné dráhy odvodit `GUID_TIMEOUT`: vychází 0,5 s proti výchozím 3 s.

*Hotovo* 20. 9. 2026, `scripts/check_dynamic_limits.sh` a
`scripts/measure_dynamic_limits.py`. `d_safe` je **1,30 m + rezerva** při
1 m/s a 0,58 m při 0,5 m/s, s rozepsanými členy v
[03 §3](./03_vrstva_roje.md).

Přeneseno do M2, protože obojí mění chování existujících kontrol: zapsat
`GUID_TIMEOUT 0,5` do parametrového souboru a znovu proletět všechny
kontroly.

## M2 — dvě instance bez letu

**Proč dvě a ne rovnou tři:** všechny problémy identity se ukážou už na dvou a
ladí se o polovinu snáz.

- [x] P5 z [05](./05_infrastruktura_simulace.md): dvě SITL instance, `MAV_SYSID`
      1 a 2, `DDS_USE_NS 1`, témata `/ap/v1/...` a `/ap/v2/...`.
      `scripts/check_multi_instance_dds.sh`, hotovo 20. 9. 2026; jeden agent
      obslouží oba klienty.
- [ ] P1–P3: dva pojmenované modely v jednom světě, most na agenta.
- [ ] P4: dva můstky aktuátorů.
- [ ] TF: `map` → `v1/base_link`, `v2/base_link`.
- [ ] Startovní pozice podle [08 R15](./08_rozhodnuti.md), svět beze změny.
- [ ] Ověřit proti ground truth, že se spawn pozice modelu a home pozice SITL
      shodují (nevyřešený předpoklad z [04 §3](./04_rozhrani.md)). Mřížka mapy
      je vystředěná na origin EKF, takže na tomhle stojí celé slučování —
      [08 R16](./08_rozhodnuti.md).
- [ ] Arbiter (G9): autonomie publikuje nominální povel, arbiter ho ořezává a
      jako jediný píše `/ap/v<i>/cmd_vel`. Otestovat, že při mlčení omezení
      ořezává konzervativně.
- [x] Restart jedné instance nezmění identitu druhé — součást téže kontroly.

*Hotovo, když:* oba stroje vzlétnou, drží vlastní bod a `check_guided_takeoff.sh`
projde pro každý zvlášť.

## M3 — tři instance a rozpočet stroje

- [ ] Třetí instance.
- [ ] RTF pro 1, 2 a 3 instance, zapsaný i se strojem, na kterém se měřilo.
- [ ] Rozhodnout, co se vypíná, když se to nevejde (kamera první).
- [ ] Per-agent přejímka z [02 §4](./02_vrstva_drona.md), třikrát.

*Hotovo, když:* tři stroje současně visí, RTF je zapsaný a žádná kontrola
neselhala kvůli tomu, že jich je víc.

## M4 — koordinátor bez letu

Všechno, co jde otestovat offline, se offline otestuje.

- [ ] Slučování mřížek na uložených mapách, včetně počítání konfliktů.
- [ ] Přidělení frontier cílů na uložené mapě: tři agenti, žádný dvakrát týž cíl.
- [ ] Bezpečnostní filtr na syntetických trajektoriích: čelní sblížení,
      dohánění, tři stroje v jednom bodě.
- [ ] Sledování stáří stavu a epocha mise.
- [ ] Testy kontraktu z [04 §6](./04_rozhrani.md) — aspoň záměna identit a
      ztichnutí.

*Hotovo, když:* filtr prokazatelně zabrání srážce na syntetických datech a
přidělení nedá dvěma agentům týž cíl.

## M5 — mapování třemi drony

- [ ] Sekvenční vzlet tří strojů.
- [ ] Mapování s přidělováním cílů, 130 s.
- [ ] `/swarm/map` a rozšířená kontrola pokrytí z [06 §4](./06_slozena_mapa.md).
- [ ] Tři běhy se zapsaným seedem.
- [ ] Vyhodnotit K1–K6 z [01 §4](./01_zadani_mapovani.md).

*Hotovo, když:* je zapsané, jestli tři drony porazily jeden — **včetně případu,
že ne.**

## Co se odkládá za M5

- Vstřikování poruch nad rámec ztichnutí a zastaralého stavu.
- Formace jakéhokoli druhu.
- Čtyři a více agentů.
- Cokoli na železe.

## Vedení záznamů

Každý milník končí zápisem ve `workflow/log.md` ve stejném stylu jako dosud:
co se měřilo, co vyšlo, co z toho neplatí. Rozhodnutí — drak, varianta mapy,
pravidlo konfliktu, hodiny — patří do `workflow/decisions.md`. Čísla, která
zůstala nezměřená, patří do `workflow/backlog.md`, ne do textu jako výhrada.

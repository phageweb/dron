# 02 – Vrstva jednoho dronu

Tahle vrstva **neví, že existuje roj**. Je to jeden stroj se svým EKF, svou
kaskádou, svými senzory a svým failsafe. Roj z ní nesmí nic ubrat: každý agent
musí projít stejnými kontrolami sám, jako by letěl jediný.

Vrstva je z velké části hotová. Tenhle dokument říká, co přesně z ní roj bude
potřebovat, co je změřené a co ne.

## 1. Co agent garantuje

Co smí koordinátor předpokládat — a nic víc. Přesná témata a timeouty jsou v
[04](./04_rozhrani.md); tady je věcný obsah.

| # | Garance | Dnešní stav |
| --- | --- | --- |
| G1 | publikuje svou filtrovanou polohu a orientaci | `/ap/pose/filtered` z AP_DDS, ověřeno |
| G2 | přijme omezenou rychlostní referenci a sleduje ji | `/ap/cmd_vel`, ověřeno `check_sitl_dds_control.sh` |
| G3 | při ztichnutí reference sám zastaví | `GUID_TIMEOUT`, výchozí 3 s — **neodvozeno pro tenhle stroj** |
| G4 | nevletí do zdi, i kdyby mu to bylo přikázáno | `obstacle_monitor` + `simple_indoor_autonomy`, stop 0,8 m, brzdná 0,6 m |
| G5 | neodmítne podlahu jako překážku a neklesne pod ni | odmítání podlahy s chybovou úsečkou, `check_leaning_scan.sh` |
| G6 | při slabé baterii sám přistane | `BATT_FS_*`, `check_low_battery_landing.sh` |
| G7 | při výpadku senzoru se zachová definovaně | `check_sensor_dropout.sh` |
| G8 | jeho identita se restartem nezmění | **neexistuje**, dnes je instance jen jedna |
| G9 | přijme omezení rychlosti a dodrží ho, i když mu autonomie velí jinak | **neexistuje**, je to arbiter z [08 R19](./08_rozhodnuti.md) |

G3, G8 a G9 jsou jediné tři, které se kvůli roji musí dodělat. Zbytek se jen
zopakuje pro každou instanci.

G9 je nový uzel — **arbiter** — mezi `simple_indoor_autonomy` a `/ap/cmd_vel`.
Autonomie napříště publikuje nominální povel a arbiter ho ořízne podle omezení
od roje; při mlčení koordinátoru ořezává konzervativně. Je to jediný způsob, jak
dát roji brzdu, aniž by obešel G4 a G5. Téma `cmd_vel` je v uzlu parametr, takže
autonomie se kvůli tomu nemění.

## 2. Co je na tomhle stroji změřené

Čísla, o která se roj může opřít, protože je někdo naměřil v tomhle repozitáři:

| Veličina | Hodnota | Zdroj |
| --- | --- | --- |
| mez rate gainu | 0,065 čisté, 0,080 rozkmitané | `sweep_rate_gains.sh` na obou dracích |
| letový rate gain | 0,040, rezerva 0,62 | parametrové soubory |
| RMS chyba orientace | 0,74–0,86° přes mřížku zisků | `check_attitude_estimate.sh` |
| nejhorší náklon při vzletu | 15,5° (Pavo20) / 15,6° (CineLog) proti limitu 25° | `check_guided_takeoff.sh` |
| odstup od zdi za letu vpřed | 1,39 m, vůle špičky 0,93 m | `check_forward_flight.sh` |
| úhlová autorita v rollu | 689 rad/s² (CineLog), 583 (Pavo20) | výpočet z modelu, ověřený sweepem |

## 3. Co roj potřebuje a co změřeno není

Tohle je ta část, kterou nelze obejít. Rozestup dvou strojů je součet čísel a
tři z nich dnes nikdo nezná:

| Chybí | Proč to roj potřebuje | Jak to změřit |
| --- | --- | --- |
| **brzdná dráha** pro sadu rychlostí | je přímo sčítanec v `d_safe` | rychlostní krok na povel stop, ground truth z Gazeba |
| **end-to-end latence** povel → pohyb, včetně jitteru | druhý sčítanec v `d_safe` | časová značka povelu proti první reakci pozice |
| **chyba sledování rychlosti** | říká, jak moc se agent odchýlí od toho, co mu bylo řečeno | step a rampa bez překážek |
| **drift polohy** z optického toku za 130 s | rozhoduje, jestli jde mapy vůbec složit | ground truth proti `/ap/pose/filtered` |
| odvozený `GUID_TIMEOUT` | G3 dnes stojí na výchozí hodnotě, ne na výpočtu | z brzdné dráhy: při 1 m/s znamenají 3 s nejméně 3 m doletu |

Poslední řádek je konkrétní problém, ne formalita: v místnosti 8 × 6 m je 3 m
doletu půl místnosti.

## 4. Per-agent přejímka

Než se spustí cokoli rojového, musí **každá ze tří instancí samostatně** projít:

- [ ] `check_guided_takeoff.sh`
- [ ] `check_forward_flight.sh`
- [ ] `check_front_lidar.sh` a `check_leaning_scan.sh`
- [ ] `check_sitl_dds_control.sh`
- [ ] `check_room_mapping.sh`
- [ ] `check_sensor_dropout.sh` a `check_low_battery_landing.sh`

Ne jednou pro „ten model" — třikrát, pro instance 1, 2 a 3, protože rozdíl mezi
nimi je právě to, co se tímhle chytá. Skripty dnes ale předpokládají jedinou
instanci; co to obnáší, je v [05](./05_infrastruktura_simulace.md).

## 5. Co se do téhle vrstvy nesmí přidat

- **Nic o sousedech.** Kdyby `simple_indoor_autonomy` uměl uhnout druhému dronu,
  přestane se dát změřit, co dělá bezpečnostní filtr roje.
- **Nic o misi.** Agent neví, jestli mapuje, nebo letí domů.
- **Žádná změna zisků kvůli roji.** Zisky jsou naměřené; roj je vstupní signál,
  ne důvod k přeladění.

## 6. Rozhodnutí

Odůvodnění je v [08](./08_rozhodnuti.md).

- **R4 — mapuje agent**, koordinátor jen slučuje. `occupancy_mapper` běží na
  každém agentovi beze změny kódu.
- **R5 — `frontier_explorer` se na agentovi nespouští.** Volbu cíle přebírá
  koordinátor i s jeho cenovou funkcí. Uzel zůstává, je to baseline.
- **R6 — `corridor_margin_m 0.25` beze změny.** Je to rezerva vůči zdi, ne vůči
  sousedovi; zvětšit ji kvůli roji by započítalo totéž dvakrát.

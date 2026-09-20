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
| G9 | přijme omezení rychlosti a dodrží ho, i když mu autonomie velí jinak | `arbiter`, hotovo 20. 9. 2026 |

G3 a G8 zbývají; G9 je hotové. Jsou to jediné tři, které se kvůli roji musí
dodělat. Zbytek se jen
zopakuje pro každou instanci.

G9 je nový uzel — **arbiter** — mezi `simple_indoor_autonomy` a `/ap/cmd_vel`.
Autonomie publikuje nominální povel a arbiter ho ořízne podle omezení od roje;
je to jediný způsob, jak dát roji brzdu, aniž by obešel G4 a G5. Téma `cmd_vel`
je v uzlu parametr, takže autonomie se kvůli tomu nemění.

Hotovo 20. 9. 2026 (`openipc_cinewhoop_demo/arbiter.py`). Dvě rozhodnutí v něm
stojí za přečtení, protože obě jdou proti prvnímu nápadu:

- **Mlčení koordinátoru neznamená stop, ale pomalu** (výchozí 0,25 m/s).
  Zastavený agent se nedostane ani z deadlocku, a od zastavení při skutečně
  ztracené lince je tu `GUID_TIMEOUT`, tedy G3. Explicitní `stop` od
  koordinátoru se ale s mlčením neplete a je respektovaný okamžitě.
- **Arbiter je opt-in.** Když neběží, autonomie publikuje přímo na
  `/ap/cmd_vel` přesně jako dnes, takže všechny jednodronové kontroly létají
  beze změny. Rojový běh ho spustí, jednodronový ne.

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

## 3. Co roj potřebuje — přeměřeno 20. 9. 2026 na skutečném Pavo20

Původní měření bylo z CineLogu: kontrolní skripty nenastavovaly `SDF_PATH`,
takže `OPENIPC_AIRFRAME=pavo20` načetl cizí model (viz
`workflow/troubleshooting.md`). Skripty jsou opravené, model taky — měl
zděděný `multiplier`, kvůli kterému se nemohl zvednout — a tabulky níž jsou
z prvního běhu, který skutečně letěl tenhle drak.

M1 je hotové. `scripts/check_dynamic_limits.sh` odlétá jednu sortu v prázdném
`room_test` a měří všechno proti ground truth z Gazeba, ne proti odhadu, který
je sám předmětem měření. Dva běhy, Pavo20:

| Povel | Ustálená rychlost | Brzdná dráha | Brzdný čas | CineLog pro srovnání |
| ---: | ---: | ---: | ---: | ---: |
| 0,25 m/s | 0,266 | 0,174 m | 1,18 s | 0,144 m |
| 0,50 m/s | 0,532 | 0,426 m | 1,92 s | 0,331 m |
| 1,00 m/s | 0,990 | **1,001 m** | 2,35 s | 0,770 m |

| Veličina | Hodnota |
| --- | --- |
| latence povel → pohyb | 0,324–0,408 s přes tři shodné pokusy |
| chyba ustálené rychlosti | do 6 % (na 0,25 m/s), do 1 % na 1 m/s |
| drift odhadu ve visu | 0,012 m vodorovně, 0,000 m svisle za 60 s |

**Pavo20 brzdí výrazně hůř než CineLog** — z 1 m/s potřebuje 1,00 m proti
0,77 m, tedy o 30 % víc. To jde přímo do `d_safe` a je to hlavní důvod, proč
rozestup vyšel větší.

Tři poznámky, bez kterých se ta čísla dají snadno použít špatně:

1. **Latence není přenosové zpoždění.** Je to čas do prvního pohybu nad
   0,05 m/s, takže je v ní i vlastní rozjezd stroje omezený jerkem. Pro
   `d_safe` je to ta správná veličina — zajímá nás, kdy se stroj začne hýbat —
   ale jako „zpoždění linky" se citovat nedá.
2. **Naměřená brzdná dráha při 0,5 m/s je 0,33 m, zatímco projekt počítá s
   0,60 m.** Ta hodnota v `simple_indoor_autonomy` a `check_forward_flight.sh`
   je odvozená z `PSC` parametrů, ne změřená. Rezerva je tedy dvojnásobná
   proti skutečnosti, což je bezpečný směr, ale je to rezerva.
3. **Drift 1 cm za minutu je výsledek simulace, ne stroje.** EKF tu dostává
   bezšumové senzory. Skutečný optický tok bude řádově horší a tohle číslo je
   jediný člen `d_safe`, na který simulace odpovědět neumí. Do rozestupu se
   bere jako dolní mez, ne jako hodnota.

Zbývá `GUID_TIMEOUT`, který je pořád na výchozích 3 s. Z měření plyne, co to
stojí: při 1 m/s ujede stroj za 3 s ticha 3 m a teprve pak začne brzdit svých
0,77 m. Rozsah parametru je 0,1–5 s, roj bude posílat povel 10–20× za sekundu,
takže **0,5 s** tolerují pět až deset ztracených zpráv a stojí 0,5 + 0,77 m.
Změna se sem ale nepíše jako hotová věc: přepsat ji v parametrovém souboru
znamená znovu proletět všechny existující kontroly, protože každá pauza v
publikování `cmd_vel` delší než půl sekundy se stane zastavením. Patří to do
M2.

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

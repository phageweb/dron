# 03 – Vrstva roje

Jeden uzel na zemi, který vidí stavy všech tří agentů a posílá jim omezené
rychlostní reference. Nic víc. Všechno, co je rychlé nebo bezpečnostně kritické,
zůstalo pod kontraktem v [02](./02_vrstva_drona.md).

Architektura je hierarchická a centralizovaná, jak doporučuje
[`reserseRoju/04 §2`](../../reserseRoju/04_navrh_pro_tento_projekt.md).
Decentralizace není cílem tohoto úkolu.

## 1. Rozklad koordinátoru

Čtyři části, které se dají testovat zvlášť. To je celý důvod, proč je jich
několik a ne jedna:

```text
  /v1..v3 stavy         sdilena mapa (06)
        |                      |
        v                      v
   +----------------+   +--------------+
   | sledování roje |-->| přidělení    |   kdo letí kam
   | (kdo je živý)  |   | frontier cílů|
   +----------------+   +--------------+
                               |
                               v
                        +--------------+
                        | bezpečnostní |   smí změnit povel
                        | filtr        |
                        +--------------+
                               |
                               v
             /v<i>/explore/target + /v<i>/swarm/constraint
                               |
                               v
                   arbiter agenta  -->  /ap/v<i>/cmd_vel
```

Koordinátor nepíše `cmd_vel`. Posílá cíl a omezení; povel skládá agent. Proč
tak, je v [08 R19](./08_rozhodnuti.md) — jinak by roj obešel vyhýbání zdi a
podlaze, které jsou garance agenta.

| Část | Odpovědnost | Testuje se |
| --- | --- | --- |
| sledování roje | stáří stavu každého agenta, jeho režim, epocha mise | vstříknutým zpožděním a výpadkem |
| přidělení cílů | každý frontier nejvýš jednomu agentovi | offline, na uložené mapě |
| bezpečnostní filtr | udržet `d_safe` mezi každou dvojicí | offline, na syntetických trajektoriích |
| výstup | cíl a omezení na agenta | proti mezím z [04](./04_rozhrani.md) |

Přidělení a filtr musí jít spustit **bez simulace**, na uložených datech. Bez
toho se každá chyba v nich hledá 130 s dlouhým letem.

## 2. Přidělení frontier cílů

Dnešní `frontier_explorer` vybírá cíl sám, s cenou `lookahead_m 1.4`,
`target_hold_m 1.0` a `turn_cost_m_per_rad 1.25`. Se třemi agenty by si tři
kopie vybraly totéž — všichni vidí tutéž mapu a tutéž nejbližší hranici.

Návrh verze 1, záměrně nudný:

1. Koordinátor vezme frontier buňky ze **složené** mapy.
2. Shlukne je (souvislé hranice, ne jednotlivé buňky).
3. Spočítá cenu `agent × shluk` — vzdálenost plus `turn_cost` z dnešního uzlu.
4. Přiřadí jedno na jedno, hladově nebo maďarskou metodou. Tři agenti a desítky
   shluků jsou triviální úloha; optimalita tu nikoho nezajímá.
5. Přiřazení drží po `target_hold_m`, aby agenti neoscilovali mezi cíli.

Co se tím měří: **překryv práce** z [01 §2](./01_zadani_mapovani.md). Když je
vysoký, přidělení nefunguje, i kdyby mapa vyšla.

## 3. `d_safe`, a proč to není konstanta

Rozklad je z [`reserseRoju/04 §6`](../../reserseRoju/04_navrh_pro_tento_projekt.md);
tady dosazený do čísel tohoto repozitáře:

```text
d_safe = 2 * r_rotor + 2 * e_pozice + v_max * t_latence + s_brzdna + rezerva
```

| Člen | CineLog | Pavo20 | Odkud |
| --- | ---: | ---: | --- |
| `r_rotor` dosah špičky | 0,08335 m | 0,06107 m | model, `check_room_coverage.sh:431` |
| `2 * r_rotor`, geometrické minimum | 0,1667 m | 0,1221 m | tamtéž |
| `e_pozice` chyba odhadu | **neznámá** | **neznámá** | optický tok, nezměřeno |
| `t_latence` | **neznámá** | **neznámá** | [02 §3](./02_vrstva_drona.md) |
| `s_brzdna` při 0,5 m/s | **neznámá** | **neznámá** | [02 §3](./02_vrstva_drona.md) |
| rezerva | volba | volba | zapsat před testem |

Tři z pěti členů chybí. To není důvod nezačít — je to důvod, proč M1 v
[07](./07_plan_a_milniky.md) je měření a ne kód. Do té doby se smí použít
pracovní `d_safe` s hrubou rezervou, ale musí být v konfiguraci a v logu, ne
v kódu.

## 4. Bezpečnostní filtr, verze 1

Nejjednodušší věc, která může fungovat, a záměrně ne CBF ani ORCA:

- Filtr dostane polohy a rychlosti všech tří agentů.
- Pro každou dvojici spočítá vzdálenost a předpovídanou vzdálenost za
  `t_horizont` při současných rychlostech.
- Klesne-li předpověď pod `d_safe`, pošle **oběma** agentům omezení rychlosti;
  pod tvrdší mez omezení „stop". Ořezání provede arbiter na agentovi.
- Priorita při rovnosti je pevná podle ID, aby dva agenti neuhýbali proti sobě.
- Každý zásah se loguje: čas, dvojice, vzdálenost, co filtr změnil.

Počet zásahů a čas strávený v omezeném režimu jsou metriky, ne vedlejší efekt.
Roj, který pokryje místnost a filtr v něm zasáhl 400krát, je špatně naladěný
roj, i když K1 prošlo.

ORCA a CBF mají smysl teprve tehdy, až tahle verze prokazatelně brzdí zbytečně.

## 5. Chování při poruše

Stavový automat na agenta, ne na roj. Důvod je v
[`reserseRoju/04`](../../reserseRoju/04_navrh_pro_tento_projekt.md): „všichni
přistaňte" je v husté skupině nebezpečný povel, protože tři stroje klesají skrz
prostor, který si navzájem nevidí.

| Událost | Postižený agent | Ostatní |
| --- | --- | --- |
| stav agenta zastaral | přejde na hold svým vlastním failsafe (G3) | koordinátor mu přestane přidělovat cíle a rozšíří kolem něj `d_safe` |
| agent hlásí vlastní failsafe | jedná podle své vrstvy, roj do toho nemluví | drží odstup, mise pokračuje |
| koordinátor spadne | všichni tři zastaví přes G3 | — |
| dva agenti blízko a oba zastavili (deadlock) | nižší ID couvne o pevnou vzdálenost | druhý čeká |

Automatický návrat do aktivního stavu po failsafe **není**. Po vážné poruše
rozhoduje operátor.

## 6. Co tahle vrstva nesmí

- Posílat cokoli rychlejšího než rychlostní referenci.
- Předpokládat doručení zprávy nebo pořadí zpráv.
- Přebírat vyhýbání zdi a podlaze — to je G4 a G5 agenta.
- Pokračovat ve staré misi po rozpojení a návratu spojení bez nové epochy.

## 7. Rozhodnutí

Odůvodnění je v [08](./08_rozhodnuti.md).

- **R7 — čas:** roj používá výhradně stampy z `pose/filtered`, tedy ArduPilotí
  UTC. Žádné `use_sim_time`; `/clock` v téhle simulaci nechodí.
- **R8 — `d_safe` se vyhodnocuje ve 3D**, ale létá se v jedné výšce, protože 2D
  lidar musí řezat tutéž rovinu, jinak se mřížky neslučují.
- **R9 — konec mapování:** žádný frontier shluk nad `min_frontier_cells` po dobu
  10 s, a zároveň nevyčerpaný rozpočet času.
- **R19 — šev:** koordinátor posílá cíl a omezení, nikoli `cmd_vel`.

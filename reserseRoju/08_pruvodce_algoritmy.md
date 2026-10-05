# Průvodce algoritmy koordinátoru: co máme, na co se dívat, co už nepotřebujeme

Stav: **5. 10. 2026** (§7 rozhodnuto). Navazuje na [06](./06_algoritmy_koordinatora.md) a
[07](./07_koordinator_revizni_reserse.md); ty říkají, co literatura nabízí.
Tahle kapitola říká, **co z toho je v kódu, proč, kde to najít a kterou
část článku si přečíst**, aby kód dával smysl. Na konci je seznam toho, co
po této implementaci **už není potřeba** sledovat.

## 0. Mapa: pět vrstev, pět otázek

Koordinátor (`ros_ws/src/openipc_swarm`) každých 0,2 s odpoví na pět otázek.
Každá vrstva má svůj modul a svůj přepínač, takže se dají měnit a měřit zvlášť:

| Vrstva | Otázka | Modul | Přepínač | Výchozí |
| --- | --- | --- | --- | --- |
| 1. Kandidáti | Kam má smysl letět? | `allocation.viewpoint_candidates` | `viewpoint_spacing_m`, `min_gain_cells` | pozorovací body á 1 m |
| 2. Přidělení | Kdo poletí kam? | `allocation.allocate_*` | `allocator` | `utility` |
| 3. Průchody | Kdo smí do úzkého místa? | `passages.Reservations` | `reserve_passages` | vypnuto (od 5. 10.), viz §7 bod 3 |
| 4. Bezpečnost | Jak se nesrazit a nezaseknout? | `safety` (skalár), `velocity_barrier` (vektor) | `safety_filter` | `vector` (od 5. 10.) |
| 5. Měření | Pomohlo to? | `scripts/replay_swarm_run.py` | — | T50/T80/T90 |

Ve zkušebním letu se přepínají proměnnými prostředí:

```sh
OPENIPC_AIRFRAME=pavo20 \
OPENIPC_ALLOCATOR=utility \          # clusters | iterative | hungarian | minpos | utility
OPENIPC_SAFETY_FILTER=vector \       # scalar | vector
OPENIPC_RESERVE_PASSAGES=true \
  scripts/check_swarm_mapping.sh 3
python3 scripts/replay_swarm_run.py   # replay.html + time_to_coverage.json
```

## 1. Kandidáti: pozorovací body místo těžiště otvoru

**Co to dělá.** Otvor (frontier – hranice známé podlahy a neznáma) se rozdělí
na body aspoň 1 m od sebe. Každý bod je buňka samotného otvoru, dost daleko od
zdi. Ke každému se odhadne, co by z něj bylo vidět: paprsky přes známou
podlahu, nejvýš 1 m do neznáma, zeď paprsek zastaví. Body, ze kterých je vidět
méně než 10 buněk, se zahodí – to jsou proužky, které v mapě nechává líc zdi.

**Proč.** Dřív dostal dron těžiště celého otvoru. U zalomeného otvoru padalo
do zdi a cena se navíc počítala k **jinému** bodu, než který dron dostal
(07 §2). A hlavně: jeden dlouhý otvor dal práci jen jednomu dronu.

**Kde v kódu.** `allocation.py`: `expected_view`, `viewpoint_candidates`,
`travel_costs` (cena = délka trasy + otočka se skutečným yaw + 1 m za změnu
cíle).

**Co si přečíst.** FUEL (Zhou et al. 2021) §IV–V – pozorovací body a jejich
viditelnost; my z toho bereme jen 2D jádro. Faigl et al. 2012 §III – víc
reprezentantů jednoho otvoru.

## 2. Přidělení: pět alokátorů nad stejnými kandidáty

Všechny dostanou tutéž matici „dron × pozorovací bod“ a liší se jen tím,
jak z ní vyberou. Žádný bod nedostanou dva drony.

| `allocator` | Jak vybírá | Silná stránka | Slabina | Článek, co číst |
| --- | --- | --- | --- | --- |
| `clusters` | Celý otvor jednomu dronu, nejlevnější dvojice první. **Staré R5**, jen jako srovnání. | — | Jeden otvor = dva drony bez práce. | — |
| `iterative` | Nejlevnější dvojice dron–bod, pak nejlevnější ze zbytku. | Jednoduché, rychlé, v Faiglově srovnání skoro tak dobré jako optimum. | Nevidí, že dva body ukazují totéž. | **Faigl, Kulich, Přeučil 2012** (ČVUT), §III–IV |
| `hungarian` | Optimální přiřazení: nejmenší součet (cena − váha × zisk). | Přesné optimum pevné matice; dron může čekat. | Optimalizuje součet, ne nejpomalejšího; překryv nevidí. | Faigl 2012; algoritmus v `allocation.hungarian` |
| `minpos` | Dron jde tam, kde je mezi drony v pořadí nejblíž (první, druhý…). | Rozprostře drony i bez znalosti zisku. | Ignoruje velikost otvoru. | **Bautin, Simonin, Charpillet 2012**, §4 |
| `utility` | Postupně nejlepší (zisk − cena); co vidí přidělený bod, už pro další nemá cenu. | Jediný řeší **překryv pozorování**. | Hladové pořadí; závisí na odhadu zisku. | **Burgard et al. 2005**, §III (snižování užitku) |

**Agent bez bodu** (všechny body rozdané nebo nedosažitelné) dál dostane
cíl „pryč od ostatních“ (R5a, `assignment.spread_targets`), nově nikdy ne
v cizím rezervovaném průchodu.

### Co ukázaly lety (3. 10. 2026)

Všechna čísla jsou **130 s od chvíle, kdy je ve vzduchu poslední dron**,
a jen nad buňkami podlahy (bez buněk podél líce zdi), ze stopy koordinátoru
(`replay_swarm_run.py`). Starší čísla roje byla po ~220 s letu, protože
check čekal na vzlet pevných 90 s – opraveno, viz R3 v
[08_rozhodnuti](../spec/roj/08_rozhodnuti.md).

| Alokátor / filtr | Místnost po 130 s | Ohrada po 130 s | Ohrada T90 | Nejmenší odstup |
| --- | ---: | ---: | ---: | ---: |
| `clusters` / skalár (staré) | 89 % | 47 % | — | 0,41 m |
| `utility` / skalár | 93, 94 % | 71, 72 % | —, — | **0,07**, 0,78 m |
| `iterative` / skalár | 96, 97 % | 84, 99 % | —, 121 s | 0,75, **0,14** m |
| `utility` / vektor | 95, 94 % | 81, 77 % | —, — | 0,71, 0,59 m |
| `iterative` / vektor | 98, 94 % | 100, 77 % | 95 s, — | 0,62, 0,62 m |

Ve dvojicích je každý let zvlášť. Co z toho plyne, a jak silně:

- **Pozorovací body pomáhají jednoznačně.** Staré `clusters` zmapovalo
  ohradu na 47 %, všechny nové varianty na 71–100 %.
- **`iterative` vychází lépe než `utility`** (ohrada 77–100 % proti 71–81 %).
  Při dvou letech na variantu je to náznak, ne pořadí. Faigl et al. naměřili
  totéž: na alokátoru záleží méně než na navigaci.
- **Skalární filtr dvakrát z pěti letů pustil dvojici skoro do kontaktu**
  (0,07 a 0,14 m). Příčina je v trase: „ustupující“ dostane plazivý limit,
  protože jeho *cíl* vede od souseda, ale autonomie letí po *nose*, a ten
  vedl k sousedovi. Vektorový filtr ve čtyřech letech nešel pod 0,59 m.
  Kontakt je 0,15 m, `d_safe` 0,78 m: ani vektor `d_safe` nedrží přesně,
  protože model jednoduchého integrátoru nezná brzdění a 0,2 s periodu.
- **Oprava skalárního filtru (večer 3. 10.):** ustupující dron smí jet jen
  tehdy, když od sousedů vede jeho cíl **i nos**. Dávka 20 letů (5 neplatných
  – jeden dron v SITL nevzlétl): skalár v 8 platných letech nikdy pod 0,77 m,
  ohrada průměrně 89 % (`iterative` 85/100/84/78/100, `utility` 84/84/100).
  Vektor s γ = 2 v pěti letech 0,39–0,68 m a ohrada 55–100 %; s γ = 0,7
  v šesti platných letech nikdy pod 0,75 m, ohrada průměrně 86 %
  (`iterative` 72/65/100/81, `utility` 100/100) – rovnocenné se skalárem. **Mezi `iterative` a
  `utility` rozdíl není vidět.**
- `hungarian` a `minpos` byly letěny jen v prvním kole (se starým měřením);
  `minpos` nechával dva drony stát (ohrada 77 % i po 220 s), `hungarian` byl
  na úrovni `iterative`.

## 3. Průchody: jeden dron ve dveřích

**Co to dělá.** Najde úzká místa – volnou podlahu se zdí z obou stran
v řádku nebo sloupci blíž, než je polovina šířky, ve které se dva drony
nemohou minout (`d_safe` + 2 × odstup od zdi ≈ 1,3 m). Průchod si
„zarezervuje“ dron, jehož trasa jím vede a dorazí k němu první. Ostatním se
trasy přes něj zakážou a nesmí v něm ani čekat. Uvolní se, když ho držitel
opustí a už ho nepotřebuje, nebo po 30 s; ztracený (zastaralý) držitel ho
drží do vypršení, protože ve dveřích pořád může stát.

**Proč.** Lepší přidělení nezabrání tomu, aby se dva drony potkaly ve
dveřích, když za nimi je jediná neprozkoumaná oblast (07 §4.3, experiment E3).

**Kde v kódu.** `passages.py` (`narrow_cells`, `passages`, `Reservations`),
zákaz tras v `allocation.travel_costs(forbidden=...)`, čekání mimo dveře
v `assignment.spread_targets(avoid=...)`.

**Stav.** Vypnuto (zapnuté bylo 4.–5. 10.). Ověřeno ve světě
`cluttered_room_narrow_doors.sdf` (dveře i mezera u přepážky 1,2 m), viz
§7 bod 3 – rezervace tam neměla co řešit a jednou letu uškodila. Zapíná se
`OPENIPC_RESERVE_PASSAGES=true`.

**Co si přečíst.** Cihlářová, Pritzl, Saska 2024 (ČVUT MRS) §IV – čekání a
ústup s plánem; to je nejbližší vzor. SIPP (Phillips, Likhachev 2011) a CBS
(Sharon et al. 2015) jsou **další krok**, až rezervace nebude stačit.

## 4. Bezpečnost: z čísla na poloroviny

### 4.1 Skalární filtr (`safety_filter:=scalar`, R19, výchozí do 5. 10.)

Koordinátor pošle každému dronu jedno číslo – maximální rychlost. Arbiter
ořízne příkaz autonomie. Nemůže změnit směr, a proto dva drony proti sobě
dostanou oba nulu a stojí. Proti tomu je v `safety.py` šest záplat (ustupující
v každé skupině, únikový limit, pásmo zpomalení jen pro sbližující se,
otáčení na místě, hystereze, odeslání pryč po 2 s). Fungují, ale jsou to
kusy toho, co dává 4.2 z principu.

### 4.2 Bariérový filtr (`safety_filter:=vector`, R19a, výchozí od 5. 10.)

**Co to dělá.** Pro každého souseda jedna polorovina povolených rychlostí:
`h = |p_i − p_j|² − d_safe²` se nesmí zmenšovat rychleji než `γ·h` (γ = 0,7;
při γ = 2 se čelní dvojice kvůli zpoždění 0,4 s v letu sblížila na 0,39 m), a
každý dron nese polovinu (reciproční CBF pro jednoduchý integrátor). Arbiter
najde rychlost **nejbližší** příkazu autonomie, která leží ve všech
polorovinách – kvadratický program, ve 2D řešený přesně výčtem vrcholů. Když
filtr ubere víc než 30 % příkazu, míří vpravo (**pravidlo pravé ruky** z BVC),
takže dva proti sobě se míjejí. Vpřed nikdy rychleji, než autonomie chtěla;
do stran a dozadu nejvýš 0,25 m/s. Autonomie kontroluje zdi jen před sebou,
a proto arbiter udělá polorovinu i z každé zdi do 1 m, kterou vidí lidar
(`wall_half_planes`: nejbližší odraz v každé z 24 výsečí, smí se k ní blížit
nejvýš rychlostí `vzdálenost − 0,30 m` za sekundu). Zeď, ke které už míří
sám povel autonomie, se povolí na ten povel: brzdí jen to, co přidal filtr.
Uvnitř `d_safe` dostane nejpomalejší rychlost, která mezeru otevírá – ne
stop.

**Ověřeno offline** (`test_velocity_barrier.py`): 2, 3 i 4 drony letící
proti sobě přes střed se vždy minou, dojedou k cíli a nikdy se nepřiblíží
pod `d_safe` − 2 cm. Se skalárním filtrem by tamtéž stály. Dva drony proti
sobě v chodbě 1,4 m se minou (0,79 m) a ke zdím nejdou blíž než 0,30 m; bez
zdí ve filtru by šly na 0,19 m.

**Kde v kódu.** `openipc_cinewhoop_demo/velocity_barrier.py`
(`barrier_half_planes`, `closest_feasible`, `filter_velocity`), arbiter
`filter_mode:=vector` (`barrier_command`), koordinátor `_barrier` posílá
`/v<i>/swarm/barrier` (Float32MultiArray: a_x, a_y, b na souseda, v rámci
těla dronu).

**Co si přečíst.** **Wang, Ames, Egerstedt 2017** §III–IV (bariérové
certifikáty, reciproční dělení); **Zhou, Wang, Bandyopadhyay, Schwager 2017**
§III-D–E (pravidlo pravé ruky); **Grover, Liu, Sycara 2023** (proč reaktivní
filtry uváznou a jak vypadají rovnovážné stavy).

**Rizika, která zbývají.** Boční pohyb je ověřený jen v SITL, ne na
skutečném regulátoru a LD06; poloha souseda je stará až 0,2 s + latence
(pokrývá ji `d_safe`); poloroviny se do rámce těla otáčejí podle yaw
z koordinátoru. Zastaralý scan (> 0,5 s) vrací strop 0,15 m/s bez zdí.

### Výsledky letu s vektorovým filtrem

V tabulce v §2. Na co se dívat v přehrávači (`replay.html`): v režimu vektor
drony nestojí na hranici stopu, objíždějí se a hloučky se rozpadají. První
let s vektorem odhalil chybu v ArduPilotu (`AP_DDS` čte `linear.y` v
`base_link` jako doprava), kvůli které boční pohyby mířily zrcadlově a dva
drony se sblížily na 0,20 m; arbiter teď osu otáčí (`to_ap_body_y`).
Druhý nález: bariéra dron nikdy nezastaví, takže pravidlo „držený 2 s → pryč
od ostatních“ (R5a) se nespouštělo a tři drony mířící ke stejným dveřím se
90 s šouraly v hloučku. Nově se jako držený počítá dron pomalejší než
0,08 m/s vedle souseda (detekce nepostupujícího agenta, 07 §4.3).

## 5. Měření

`scripts/replay_swarm_run.py` počítá **T50/T80/T90** – čas, kdy byla poprvé
zmapovaná daná část podlahy – zvlášť pro místnost a ohradu, a ukládá je do
`time_to_coverage.json` (Explore-Bench, Xu et al. 2022 §IV). Souhrn letu
nově ukazuje alokátor, dobu plánování (medián ~60–80 ms při periodě 200 ms)
a nejmenší odstup dvou dronů ve vzduchu.

Dávky (`scripts/swarm_batch.py`) navíc zapisují nejbližší přiblížení
středu dronu ke zdi (`wall_m`) a `scripts/door_conflicts.py` spočítá, jak
dlouho byly dva drony současně u jednoho úzkého místa.

Co ještě chybí: kdo kterou buňku viděl první (překryv a podíl práce
jednotlivých dronů, 07 §6).

## 6. Na co se dívat a na co už ne

### Relevantní teď – číst a sledovat

| Algoritmus | Proč | Stav u nás |
| --- | --- | --- |
| Burgard 2005 – snižování užitku | výchozí alokátor `utility` | implementováno |
| Faigl–Kulich–Přeučil 2012 (ČVUT) | iterativní vs. Hungarian; rozhodující je navigace | `iterative`, `hungarian` |
| MinPos (Bautin 2012) | kontrolní alokátor | `minpos` |
| FUEL – pozorovací body | jak vybrat cíl, ne jen otvor | 2D jádro implementováno |
| CBF (Wang, Ames, Egerstedt 2017) | bariérový filtr | `velocity_barrier`, volitelné |
| BVC – pravidlo pravé ruky | jak z CBF neuváznout | v `filter_velocity` |
| Grover–Liu–Sycara – uváznutí | porozumět, proč skalární filtr stál | teorie k 4.2 |
| Cihlářová–Pritzl–Saska 2024 (ČVUT MRS) | nejbližší architektura: MCF přiřazení, čekání, ústup s plánem | čekání a rezervace průchodů |
| Explore-Bench | T90 a spol. | implementováno |

### Až později – až se změní podmínky

| Algoritmus | Kdy | Proč ne teď |
| --- | --- | --- |
| SIPP / CBS | rezervace průchodů nebude stačit (víc dronů, užší chodby) | dnes není úzké místo, kde by se potkávali |
| RACER / C²-Explorer / MTSP | víc místností, delší horizont | jedna místnost s ohradou |
| FAME (Explorer/Collector) | zůstanou skutečné díry v mapě | dnešní zbytky jsou hlavně chyby mapy u tenkých zdí |
| Hörner – registrace map | skutečné drony, nejistý start | v simulaci známe starty přesně |
| MonoSpheres | kamera OpenIPC místo lidaru | dnes lidar |
| Cross-rank (Bayer–Faigl 2025) | slabé nebo ztrátové spojení | centrální mapa funguje |
| EGO-Swarm / RMADER | sdílení trajektorií, rychlé lety | agenti nemají plánovač trajektorie |
| coExplore | levná další kontrolní varianta | nic nového oproti `minpos` + `utility` |

### Už není potřeba sledovat

| Co | Proč |
| --- | --- |
| Těžiště otvoru jako cíl | nahrazeno pozorovacími body; cena = publikovaný bod |
| „Jeden otvor jednomu dronu“ (R5 v původní podobě) | zůstává jen jako `clusters` pro srovnání |
| Ladění dalších záplat skalárního filtru (ustupující, únikový limit, …) | směr, kterým se dvojice rozejde, volí bariéra s pravou rukou; záplaty zůstávají jen pro režim `scalar` |
| Aukce, CBBA | tři drony a centrální uzel; vyjednávání nic nepřidá |
| Dec-MARVEL a jiné učené politiky | potřebují trénink a nedávají záruky; výzkumná větev |
| WFD/FFD, RRT detekce hranic | rychlost detekce není problém: celé plánování včetně detekce trvá 60–80 ms v periodě 200 ms |
| Flocking bez komunikace (Horyna et al.) | řeší let roje k objektu, ne mapování místnosti |
| SphereMap | 2D mřížka 200 × 200 stačí; plánování cest není úzké hrdlo |

## 7. Co zbývalo rozhodnout (rozhodnuto 5. 10. 2026)

Podklad: 48 letů po třech dronech, 130 s od vzletu, ve třech světech –
`cluttered_room.sdf` (3 seedy), `cluttered_room_narrow_doors.sdf`
s otvory 1,0 m (4 seedy) a 1,2 m (4 seedy) – každý seed všemi čtyřmi
kombinacemi alokátoru a filtru (`Gus`, `Guv`, `Gis`, `Giv`; u = `utility`,
i = `iterative`, s = skalár, v = vektor), plus 4 kontrolní lety bez
rezervace (`F`). Srovnává se T90 ohrady ve dvojicích „stejný svět, stejný
seed“; let, který T90 nedosáhl, prohrává.

| Svět | Varianta | T90 ohrady (s) | Medián | Nejmenší odstup | Nejblíž zdi |
| --- | --- | --- | ---: | ---: | ---: |
| místnost | `Gus` | 31, 23, 26 | 26 | 0,75 m | 0,28 m |
| | `Guv` | 22, 23, 25 | 23 | 0,78 m | 0,35 m |
| | `Gis` | 27, 60, 42 | 42 | 0,76 m | 0,31 m |
| | `Giv` | 31, 31, 33 | 31 | 0,78 m | 0,20 m |
| dveře 1,0 m | `Gus` | 87, 70, 61 (1 neplatný) | 70 | 0,75 m | 0,33 m |
| | `Guv` | 77, 62, —, 75 | 75 | 0,78 m | 0,31 m |
| | `Gis` | 73, 60, 113, 49 | 66 | 0,76 m | 0,31 m |
| | `Giv` | 125, 76, —, 58 | 76 | 0,78 m | 0,11 m |
| dveře 1,2 m | `Gus` | 44, 47, 51, 31 | 46 | 0,76 m | 0,32 m |
| | `Guv` | 44, 28, 47, 49 | 45 | 0,78 m | 0,33 m |
| | `Gis` | 71, 51, 77, — | 71 | 0,76 m | 0,32 m |
| | `Giv` | 49, 46, 49, 48 | 48 | 0,77 m | 0,30 m |
| | `F` (bez rezervace) | 34, 49, 33, 31 | 33 | 0,76 m | 0,31 m |

1. **Vektorový filtr je výchozí.** Jedinou překážkou byla boční složka
   nekontrolovaná proti zdem; tu teď kontroluje arbiter ze scanu (§4.2).
   Rychlostí je vektor se skalárem **rovnocenný** (21 párů: rychlejší 10,
   pomalejší 8, stejně 3, medián −2 s), ale jako jediný držel každou
   dvojici na `d_safe` (0,77–0,78 m proti 0,75–0,76 m). Přiblížení ke zdi
   0,11 a 0,20 m ve vektorových letech nezpůsobil filtr: sousedé byli dál
   než 1,3 m, kde filtr povel nemění, a skalární let ze 4. 10. měl 0,10 m.
   Skalár zůstává jako `safety_filter:=scalar`. Na hardwaru boční pohyb
   ověřen není.
2. **`utility` zůstává výchozí, teď podložené.** 21 párů: `utility`
   rychlejší ve 14, pomalejší ve 4, stejně ve 3 (medián −9 s, znaménkový
   test p ≈ 0,03). Náznak z 3. 10., že je `iterative` lepší, byl šum dvou
   letů na variantu.
3. **Svět s úzkými dveřmi: `cluttered_room_narrow_doors.sdf`, otvory
   1,2 m.** Co se při něm ukázalo:
   - *Okno šířek je úzké.* Koordinátor vede trasu jen buňkami, kolem
     kterých je 0,4 m **známé** volné podlahy (4 buňky po 0,1 m), takže
     dveřmi potřebuje 9 volných buněk. S otvory 1,0 m (10 buněk) stačila
     zeď nakreslená o buňku tlustší nebo neznámá buňka u zárubně, a ve 2
     z 15 letů roj zůstal stát s třetinou ohrady neprozkoumanou. Dva drony
     se v plánu koordinátoru míjejí od ~1,6 m (autonomie potřebuje 1,44 m),
     takže zkušební dveře mají mít 1,1–1,4 m; 1,2 m
     nechává mapě tři buňky rezervy.
   - *Detektor bere za úzké víc, než se psalo.* Práh je `d_safe` + 2 ×
     odstup a odstup je skutečně 0,4 m, ne 0,25 m: úzké je všechno pod
     ~1,58 m – i původní 1,6m dveře, jakmile je mapa nakreslí o buňku
     užší. Dveře se navíc přes diagonální sousedy slijí s chodbou za nimi
     (spodní chodba ohrady je 1,35 m) v jeden „průchod“ o stovkách buněk.
   - *Rezervace tu nemá co řešit.* Ve 43 platných letech s rezervací ani
     ve 4 bez ní nebyly dva drony u jednoho úzkého místa současně ani na
     tick: `utility` i `iterative` samy pošlou do ohrady jednoho.
   - *A jednou uškodila.* V jednom letu `Gis` (1,2 m) držel v1 dveře
     a uvnitř přeskakoval mezi dvěma cíli; držitel uvnitř průchodu nemá
     lhůtu, takže v2 a v3 zbytek letu stály venku a ohrada skončila na
     69 %. Bez rezervace (`F`) bylo T90 v mediánu 33 s proti 46 s se
     zapnutou (`Gus`, 4 páry – náznak).
   Odpoledne to potvrdily čtyři lety výchozí konfigurace bez rezervace
   ve stejném světě: T90 ohrady 25–29 s proti 28–49 s (medián 46 s)
   s rezervací – rezervace čas skoro zdvojnásobovala.
   **Rozhodnuto 5. 10.: rezervace je jako výchozí vypnutá**, dokud
   detektor nebude brát jen skutečné dveře (bez slévání s chodbou)
   a držitel, který v průchodu nepostupuje, nepřijde o rezervaci. Pro
   její skutečné ověření je potřeba svět, kde práce za dveřmi vyžaduje
   víc dronů najednou (větší ohrada za 1,2m dveřmi).

## 8. Doporučené pořadí čtení

1. Burgard et al. 2005 – nejkratší cesta k pochopení `utility`.
2. Faigl, Kulich, Přeučil 2012 – proč na volbě alokátoru záleží méně než na
   navigaci; potvrzují to i naše lety.
3. Wang, Ames, Egerstedt 2017 a Zhou et al. 2017 (BVC) – bariérový filtr a
   pravá ruka.
4. Cihlářová, Pritzl, Saska 2024 – jak to dělá ČVUT MRS v interiéru.
5. Grover, Liu, Sycara 2023 – až budete chtít rozumět, kdy i bariéra uvázne.

Odkazy na všechny práce jsou v [06](./06_algoritmy_koordinatora.md#zdroje) a
[07](./07_koordinator_revizni_reserse.md).

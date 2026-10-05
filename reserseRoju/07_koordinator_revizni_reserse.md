# Algoritmy koordinátoru: rozšířená rešerše ČVUT/MRS a zahraničního výzkumu

Datum: **3. 10. 2026**. Autor revize: **Codex**.
Rozsah: civilní mapování třemi drony Pavo20, ROS 2 + ArduPilot, společná 2D mapa.

Navazuje na [06 – Algoritmy koordinátoru](./06_algoritmy_koordinatora.md).
Tento samostatný dokument ověřuje její hlavní doporučení proti původním
článkům a aktuálnímu kódu a připravuje konkrétní zadání pro další práci.
**Rozšířená verze** doplňuje samostatné hledání prací ČVUT/MRS a zahraničních
týmů včetně publikací a preprintů z let 2024–2026. Oddíly 1–7 obsahují
původní audit projektu; oddíly 8–12 širší rešerši a aktualizované rozhodnutí.
Původní rešerše ani implementace se touto revizí nemění.

**Doporučení:** nejdřív sjednotit skutečný cíl s bodem, ke kterému počítáme
cenu, ověřit jeho sledování jedním dronem a doplnit měření. Potom porovnat
více pozorovacích bodů s potlačením překryvu proti dnešnímu přiřazení.
Hungarian, MinPos a minimum-cost flow jsou vhodné srovnávací varianty,
s rozdíly popsanými níže. Samotná výměna přiřazovacího
algoritmu neodstraní slabou navigaci, nedostatek užitečných cílů ani uváznutí.

## 1. Co je fakt, co návrh a proti čemu se porovnává

- **Kód:** pracovní strom nad commitem `9e03518`, včetně necommitnutých změn
  přítomných při revizi. Nálezy níže nejsou tvrzením o samotném commitu.
- **Literatura:** původní články odkazované přímo u tvrzení, ověřené online.
- **Experimenty:** výsledky v [deníku](../workflow/log.md), oddíl
  `2026-10-03 (afternoon)`. V této revizi nebyly znovu spuštěny ani
  přepočítány ze surových dat.
- **Návrh:** následující cost funkce, stavový automat a plán experimentů jsou
  doporučení pro tento projekt, nikoli hotová implementace nebo naměřený výsledek.

Deník uvádí tři poslední výsledky místnost/ohrada: **92/95, 90/93 a 87/73 %**.
Je to důvod zkoumat rozptyl, nikoli dostatečný důkaz příčiny neúspěchu nebo
statistické převahy některého algoritmu.

## 2. Zjištění v implementaci

| Oblast | Ověřeno v pracovním stromu | Důsledek pro další práci |
| --- | --- | --- |
| Přidělení | `assignment.assign_targets` seřadí všechny dvojice agent–shluk podle ceny a postupně bere volnou dvojici. | Je to globální iterativní přiřazení; není to postupné rozhodování robotů v náhodném pořadí. |
| Cena versus výstup | `Target.cell` je dosažitelná buňka; `cost_m` vychází z cesty k ní. `Target.point_m` je těžiště celého shluku a koordinátor publikuje tento bod. | Optimalizujeme cestu k jinému bodu, než který obdrží dron. Těžiště může ležet ve zdi. |
| Orientace | `Agent` podporuje `yaw_rad`, ale `_explore` vytváří `Agent(name, cell)` bez orientace. | Cena otočení používá výchozí nulu, nikoli změřený yaw. |
| Stabilita cílů | Přiřazení se přepočítává; `_spreading` drží režim ústupu. V této cestě není obecné držení frontier cíle podle `target_hold_m`. | Hystereze ústupu a stabilita průzkumných cílů jsou dvě různé věci. |
| Navigace | Agent používá cíl při zatáčení a při otáčení na místě během omezení rojem. Nevykonává BFS trasu z přiřazení. | Dosažitelnost v mřížce nezaručuje, že dron cíl navštíví. |
| Omezení pohybu | `swarm/constraint` je `Float32`; arbiter ořezává každou lineární složku zvlášť a propouští yaw. | Není to obecná mez normy rychlosti ani vektorový bezpečnostní filtr. Pro budoucí boční pohyb je nutná nová definice. |
| Mapa | `merge_grids` upřednostňuje obsazené před volnými; mezi volnými vybírá minimum. | Označení „maximum obsazenosti“ je zkratka, nikoli přesný popis celé fúze. |
| Diagnostika | `trace.jsonl` obsahuje polohy, limity, cíle a změny sloučené mapy přibližně po sekundě. | Stačí pro rekonstrukci pokrytí; samo o sobě neuchovává, který dron buňku objevil. |

Odkazy na implementaci:
[assignment.py](../ros_ws/src/openipc_swarm/openipc_swarm/assignment.py),
[coordinator.py](../ros_ws/src/openipc_swarm/openipc_swarm/coordinator.py),
[grid_helpers.py](../ros_ws/src/openipc_cinewhoop_demo/openipc_cinewhoop_demo/grid_helpers.py),
[autonomie](../ros_ws/src/openipc_cinewhoop_demo/openipc_cinewhoop_demo/simple_indoor_autonomy.py),
[arbiter.py](../ros_ws/src/openipc_cinewhoop_demo/openipc_cinewhoop_demo/arbiter.py),
[merge.py](../ros_ws/src/openipc_swarm/openipc_swarm/merge.py).

## 3. Co převzít z literatury

### 3.1 Přidělení práce: Burgard, iterativní metoda, Hungarian, MTSP

**Burgard et al. (2005)** kombinují cenu přesunu a užitek cíle. Po přidělení
snižují užitek oblasti viditelné z přiděleného cíle. Přínos je v omezení
duplicitního průzkumu. Tento princip sám nevytvoří další dosažitelné cíle,
jestliže generátor nabízí jen jeden bod.
[Původní článek](https://www.ipb.uni-bonn.de/wp-content/papercite-data/pdf/burgard05tro.pdf).

**Faigl, Kulich a Přeučil (2012)** rozlišují greedy, iterative, Hungarian a
MTSP. Dnešní `assign_targets` strukturou odpovídá jejich **iterative** metodě.
Autoři uvádějí velmi podobný výkon iterative a Hungarian; delší horizont MTSP
pomáhá v části scénářů. Upozorňují také na zásadní vliv lokální navigace.
Článek tedy nedokládá, že samotný Hungarian spolehlivě zrychlí tento roj.
Používá i více reprezentantů jedné souvislé frontier komponenty.
[Článek, §III, IV a VI–VII](https://comrob.fel.cvut.cz/papers/iros12mre.pdf).

**Důsledek pro návrh:** Hungarian přesně minimalizuje součet položek pevné
matice nákladů. Pokud užitek cíle závisí na tom, co již dostal jiný dron,
náklady už nejsou nezávislé. Doporučení „Burgard + Hungarian“ proto musí určit
konkrétní postup; nelze obě jména zaměnit za vyřešený algoritmus.

Příklad: dva odlišné cíle mohou vidět téměř stejné neznámé buňky. Jednoznačné
přiřazení bodů oběma dronům zabrání duplicitě bodu, ale nikoli duplicitě práce.

### 3.2 Kvalita cílů: FUEL

**FUEL** udržuje inkrementální informace o hranicích a generuje kolem nich
pozorovací body, jejichž viditelnost vyhodnocuje podle senzoru a překážek.
Odděluje globální pořadí návštěv, lokální volbu bodů a generování trajektorie.
[Zhou et al., FUEL, §IV–V](https://arxiv.org/pdf/2010.11561).

**Pro projekt:** převzít výběr dosažitelných pozorovacích bodů; zatím není
nutné přenášet celý 3D plánovač. Více bodů kolem jedné hranice jsou často
alternativy téhož pozorování. Dvěma dronům je přidělit současně až tehdy,
když mají dostatečně odlišný očekávaný přínos a prostor pro průlet.

### 3.3 Rozdělení větší oblasti: RACER

**RACER** rozděluje prostor pomocí hierarchické mřížky, používá párové
vyjednávání a formulaci CVRP pro rozdělení práce i tras. Lokální průzkum
navazuje na přidělenou oblast.
[Zhou, Xu a Shen, RACER](https://arxiv.org/pdf/2209.08533).

**Pro projekt:** inspirace pro více místností a větší roj. Přepis na
decentralizovanou architekturu nyní neřeší chybu ceny cíle ani navigaci.
Jednodušší mezikrok je přidělení místnosti a evidence obsazení jejích dveří.

### 3.4 Vyhýbání: CBF, ORCA a BVC

| Rodina | Co literatura poskytuje | Omezení pro náš systém |
| --- | --- | --- |
| CBF-QP | Úpravu nominálního řízení při splnění bariérových omezení; Wang et al. pracují zejména s dvojitým integrátorem. | Je nutný model dynamiky a proveditelná omezení. Rychlostní rovnice pro jednoduchý integrátor není přímou náhradou celého článku. |
| ORCA | Omezení přípustných rychlostí s recipročním rozdělením odpovědnosti. | Přenos předpokladů o provedení rychlosti a spolupráci obou robotů na dron s latencí se musí ověřit. |
| BVC | Oddělení prostoru mezi roboty pomocí zmenšených Voronoiho buněk. | Pravidlo pravé ruky je heuristika. Článek připouští livelock a řeší omezení vyšší dynamiky. |

Zdroje k jednotlivým řádkům:
[Wang, Ames a Egerstedt, 2017](https://liwanggt.github.io/files/A2_Safe_Swarm.pdf),
[ORCA, stránka autorů a původní práce](https://gamma.cs.unc.edu/ORCA/),
[Zhou et al., BVC, §III-D–E](https://msl.stanford.edu/papers/zhou_fast_2017.pdf).

**Bezkoliznost a dosažení cíle jsou rozdílné vlastnosti.** Ani CBF samo
nevylučuje uváznutí; jeho vznik analyzují
[Grover, Liu a Sycara](https://arxiv.org/abs/2206.01781).

**Návrh pro projekt:** nejdřív přidat explicitní řízení průjezdu úzkými místy
a detekci nepostupujícího agenta. Vektorový filtr vyhodnotit samostatně po
zprovoznění sledování cesty. Filtr měnící směr musí současně respektovat zdi;
boční korekce původně bezpečného dopředného povelu může mířit do překážky.

## 4. Konkrétní algoritmus pro první experiment

Následující specifikace je **návrh této revize**, inspirovaný uvedenými
pracemi. Není to přesná implementace některého z jejich algoritmů.

### 4.1 Kandidáti a cena

1. Vzít platné stavy a mapy ve společném rámci; zaznamenat stáří vstupů.
2. Z frontier shluků vzorkovat více pozorovacích bodů ve známém volném
   prostoru. Každý musí respektovat clearance a mít viditelnost na hranici.
3. Pro každý pár agent–bod ověřit cestu. Náklady počítat ke **stejnému bodu**,
   který se publikuje; nedosažitelné páry zakázat.
4. Odhadnout množinu dosud neznámých buněk `V(j)`, které by bod `j` mohl
   odhalit. Použít dosah, zorné pole a zastínění; jde o odhad, ne znalost
   skutečného prostoru za hranicí.

Pro rychlý 2D prototyp je konzervativní možností počítat první neznámou buňku
na každém paprsku. Odvážnější odhad plochy za hranicí musí být označen jako
model a vyhodnocen zvlášť. Prostý počet neznámých buněk v kruhu nadhodnocuje
užitek přes zdi.

Navržená cena přesunu v sekundách:

```text
T(i,j) = délka_cesty(i,j) / v_ref + |počáteční_otočení(i,j)| / omega_ref
```

Je to aproximace pro pohyb „otočit, potom letět“. Nepoužívat jako přesnou dobu
letu, pokud se pohyby překrývají nebo dominuje brzdění. `v_ref` a `omega_ref`
musí odpovídat měření agenta, nikoli výchozímu yaw = 0.

### 4.2 Dvě oddělené varianty přiřazení

**Varianta A – iterativní výběr s mezním užitkem, doporučený první prototyp:**

```text
A = platné zachované rezervace
covered = sjednocení V(j) již rezervovaných cílů
opakuj pro dosud nepřiřazené agenty:
    gain(j) = plocha V(j) mimo covered
    score(i,j) = gain(j) - lambda_time * T(i,j) - penalty_switch(i,j)
    vyber nejlepší přípustný pár s kladným score
    pokud žádný neexistuje, skonči
    rezervuj pár; aktualizuj covered; odeber agenta a bod z nabídky
zbylým agentům přiděl explicitní čekání nebo ústup
```

`gain` a penalizace jsou v m², `lambda_time` v m²/s. Váhy i práh přínosu
zapsat před porovnáním. Kladné score je návrhové kritérium: při příliš velké
ceně času může nechat vzdálenou hranici bez obsluhy. Proto odlišit „není
výhodný cíl“ od „není žádná hranice“ a při stagnaci umožnit přidělení jediného
dosažitelného cíle podle zvláštní politiky dokončení.

**Varianta B – Hungarian jako kontrolní experiment:** stejné body a cesty,
pevná cena `C(i,j) = T(i,j) - lambda_gain * gain(j) + switch_cost(i,j)`.
Přidat možnost čekání, zakázané páry nevynucovat. `lambda_gain` má jednotku
s/m². Překryv mezi současně vybranými cíli tato aditivní cena neřeší.

Pokud bude potřeba optimalizovat překryv společně, použít explicitní výběr
kombinace cílů. Pro tři drony a nejvýše 30 kandidátů na dron má hrubé úplné
prohledání nejvýše `30³ = 27 000` kombinací před ořezáním. To je důvod jej
změřit, nikoli tvrzení, že celý plánovací cyklus poběží pod milisekundu.

### 4.3 Rezervace, čekání a dokončení

Rezervace potřebuje stabilní ID cíle, vlastníka, dobu platnosti a důvod
uvolnění. Index shluku není stabilní ID: po změně mapy se komponenty dělí
a spojují. Zachovat cíl, dokud je dosažitelný a přínosný; přidělení měnit při
zániku cíle, poruše nebo dostatečně velkém zlepšení.

Navržené stavy: `EXPLORE`, `WAIT`, `YIELD`, `RECOVER`, `DONE`, `FAILED`.
Při nedostatku práce je čekání mimo koridor platný výsledek. Nelze zaručit
smysluplnou práci všem třem dronům, jestliže neznámý prostor vede jen přes
jedny úzké dveře. Ústup má uvolnit konkrétní konflikt a pak skončit.

Pro úzké průchody navrhuji časově omezenou rezervaci průchodu pro jednoho
agenta. Uvolňuje se až po potvrzeném opuštění; při ztrátě stavu se průchod
nepovažuje automaticky za volný. Čekající musí mít dosažitelný bod mimo něj.

Absence cíle u jednoho agenta neznamená dokončení mise. Rozlišovat chybějící
data, nedosažitelnou hranici, vyčerpaný čas a dokončení podle R9.

## 5. Rozhraní a rozhodnutí, která je nutné sladit

Základem jsou [R3, R5/R5a a R19](../spec/roj/08_rozhodnuti.md).

| Návrh | Dopad na dohodnutý stav |
| --- | --- |
| Opravit yaw, sjednotit oceněný a publikovaný bod | Oprava implementace; zachovává stávající témata. |
| Více agentů u odlišných bodů jedné hranice | Vyžaduje upřesnit jednotku přidělení: současná specifikace chrání celý shluk. Dotýká se také zamítnutého sdílení otvoru v R5a. |
| Nahradit rozptýlení čekáním nebo rezervací průchodu | Změna politiky R5a, kterou je nutné promítnout do specifikace a testů. |
| Přidat `T90` | Zachovává R3: pokrytí po 130 s zůstává a čas do cílového pokrytí jej doplňuje. |
| Sledovat cestu lokálním agentem | Zachovává princip R19, pokud nominální povel dál vzniká u agenta a prochází arbitrem. Cesta vyžaduje kontrakt nad rámec jediného bodu. |
| Vektorové omezení | Mění `Float32` rozhraní, arbitra, jednotky/rámec a pravidla stáří dat. Není to pouhá interní výměna funkce. |

Přechod na poziční setpoint ArduPilotu není sám o sobě plánováním cesty kolem
zdi. Je potřeba určit, která vrstva cestu vytváří, která ji sleduje a jak
se zachová lokální vyhýbání a failsafe. To musí být vyřešeno před porovnáním
ambicióznějších alokátorů.

## 6. Jak měřit, zda změna pomohla

Explore-Bench zavádí čas do 90 % a 99 % pokrytí, vyvážení ploch mezi roboty
a redundanci průzkumu. Jeho vzorec redundance počítá i násobné pokrytí;
není automaticky totožný s podílem buněk viděných alespoň dvěma roboty.
[Xu et al., Explore-Bench, §IV](https://arxiv.org/pdf/2202.11931).

**Projektový protokol:**

- Zachovat `coverage_130s`, zvlášť místnost a ohradu, se stejnou maskou
  hodnotitelných buněk pro všechny varianty.
- `T90` je první čas dosažení 90 % této masky. Při nedosažení hlásit
  `nedosaženo do 130 s`, nikoli úspěch v čase 130 s. Uvádět také počet úspěchů.
- `T99` použít jen při ověřené dosažitelnosti prahu danou metrikou; známá
  chyba u buněk dotýkajících se zdi může vytvářet umělý strop.
- Pro překryv navrhuji `počet buněk pozorovaných >=2 agenty / počet buněk
  pozorovaných >=1 agentem` na stejné hodnoticí masce. Označit jako vlastní
  metriku. `assignment.work_overlap` naproti tomu počítá souběžné první
  pozorování; tyto veličiny nezaměňovat.
- Logovat unikátní příspěvek každého dronu, čas čekání a ústupu, četnost
  změn cíle, dobu bez postupu, nejmenší odstup a porušení jeho mezí.
- Měřit dobu plánovacího cyklu včetně generování bodů, cest a viditelnosti;
  uvádět medián a p95, nikoli jen čas samotného přiřazení.

Ze samotné sloučené mapy nelze zpětně získat původ jednotlivých pozorování.
Pro překryv a příspěvky doplnit masku pozorovatelů nebo změny map každého
agenta. Pro `T90` používat skutečné časové značky `t`; při sekundovém záznamu
mapy uvést odpovídající časové rozlišení a explicitní počátek mapovací fáze.

Porovnání provést po krocích: dnešní baseline → opravené cíle/yaw → ověřené
sledování cesty → více bodů → varianta A versus B → řešení průchodů.
Změnu filtru měřit zvlášť. Použít shodné starty, mapy, limity a senzory;
navrhuji alespoň 10 párovaných běhů varianty pro úvodní srovnání, s mediánem,
rozptylem a počtem selhání. To je pracovní návrh, nikoli záruka statistické síly.

## 7. Předání Claudovi: pořadí a podmínky dokončení

| Krok | Konkrétní výstup | Ověření před dalším krokem |
| --- | --- | --- |
| 1. Sjednotit fakta | Doplnit revizi závěrů kapitoly 06 a zaznamenat změny R5a/R19, pokud se přijmou. | Bez tvrzení, že Hungarian nebo CBF samo řeší všechny problémy roje. |
| 2. Opravit model cíle | Stejný dosažitelný bod pro cenu i zprávu; skutečný yaw; stabilní rezervace. | Zalomená hranice, překážka mezi dronem a cílem, změna yaw a dělení shluku. |
| 3. Ověřit navigaci a měření | Jeden dron dojde k přidělenému bodu kolem překážky; log umí `T90` a původ pozorování. | Samostatně rozlišit neúspěch navigace od neúspěchu přiřazení. |
| 4. Porovnat alokátory | Více bodů, varianta A a kontrolní B pod stejným přepínačem. | Test dvou bodů se stejnou viditelností; nedosažitelné páry; méně cílů než dronů. |
| 5. Řešit uváznutí | Rezervace dveří, čekání mimo průchod, ukončitelný ústup. | Dva proti sobě, tři v jedné oblasti, výpadek vlastníka rezervace. |
| 6. Rozhodnout o vektorovém filtru | Návrh zprávy a dynamického modelu, respektování stěn a latence. | Offline scénáře s brzděním, poté oddělené SITL porovnání. |

**Text zadání k předání:**

> Navazuj na kapitolu 06 a tuto revizi. Nejdřív oprav rozdíl mezi oceněnou
> buňkou a publikovaným těžištěm a předávání yaw. Dolož sledování cíle jedním
> dronem a doplň metriky při zachování 130s baseline. Pak porovnej více
> pozorovacích bodů s mezním užitkem proti Hungarian nad stejnými kandidáty.
> Změny přidělení, lokální navigace a bezpečnostního filtru vyhodnocuj
> odděleně. Úpravy politiky R5a a rozhraní R19 zapiš výslovně do specifikace.

## 8. Jak byla širší rešerše provedena

Vyhledávání bylo rozšířeno mimo bibliografii kapitoly 06: přes
[publikace MRS](https://mrs.fel.cvut.cz/publications),
[projekty Computational Robotics Laboratory](https://comrob.fel.cvut.cz/projects/gacr22.html),
autorské weby, univerzitní repozitáře, vydavatele a arXiv. Stav ověření je
**3. 10. 2026**; rok vydání odlišuji od roku nahrání preprintu.

Hledané okruhy: `multi-robot exploration task allocation`, `CTU MRS indoor
exploration`, `decentralized exploration low-bandwidth`, `multi-UAV
exploration 2025 2026`, `trajectory planning communication delay` a
`multi-agent pathfinding safe intervals`. Z nalezených prací byly dále
dohledávány původní texty a relevantní citované metody.

Zařazení má čtyři kritéria: přímý vztah ke koordinaci průzkumu; konkrétní
algoritmus nebo systém; dostupný původní zdroj; možnost určit vstupy,
předpoklady a způsob ověření. Vedle klasických metod zahrnuji novější
náhrady, metody se slabou komunikací a jednu učící se alternativu.

**Úroveň ověření:** u hlavních rozborů níže byly čteny pasáže původního textu
o algoritmu, experimentech a omezeních, nikoli jen abstrakty. Položky
ověřené pouze z abstraktu nebo projektové stránky jsou výslovně označené.
Čtení článku neznamená reprodukci jeho výsledků. Repozitáře byly ověřeny
jako dostupné, nebyly sestaveny ani přeneseny do našeho ROS 2 projektu.

Jde o strukturovanou technickou rešerši pro tento projekt, nikoli o úplný
systematický přehled všech publikací. Výsledná volba se řídí shodou
předpokladů s naším systémem, ne pouze novostí nebo počtem citací.

## 9. Podrobnější výsledky ČVUT a MRS

### 9.1 ČVUT: přiřazení a dlouhodobější plánování

Základní srovnání Faigl–Kulich–Přeučil (2012) je rozebráno v §3.1.
Rozšířená rešerše jej doplňuje novějšími terénními systémy a srovnáním při
omezené komunikaci. Nelze považovat jediný článek z roku 2012 za přehled
současného výzkumu ČVUT.

### 9.2 Bayer a Faigl: Cross-rank a omezená komunikace (2025/2026)

**Decentralized multi-robot exploration under low-bandwidth communications**,
online 29. 12. 2025, *Autonomous Robots* 50, článek 7 (2026).
[Plný text, zejména §5–8](https://link.springer.com/article/10.1007/s10514-025-10234-3).

**Algoritmus:** z přijatých poloh ostatních vznikají lomené čáry jejich
historického pohybu. Cross-rank penalizuje cíle u těchto tras, aby roboti
na křižovatce pokračovali různými větvemi. Následuje volba podle
Spread-rank, eukleidovské aproximace nebo TSP. Nejde o filtr kolizí.

**Důkazy:** srovnání 12 metod v pěti podzemních prostředích, 600 běhů
základního benchmarku, doplňkové analýzy a nasazení tří čtyřnohých robotů.
Při sdílení map, cílů a poloh patří mezi nejlepší MTSP, MinPos a Hungarian.
Cross-rank je kompromis pro nízkou přenosovou kapacitu; testována byla také
komunikace se ztrátovostí přes 50 %.

**Pro nás:** samostatná budoucí varianta pro výpadky přenosu map. V dnešní
centralizované simulaci není důvod dobrovolně zahazovat sdílenou mapu.
Výpadek koordinátoru navíc nyní neznamená, že agent umí lokálně pokračovat.

### 9.3 Cihlářová, Pritzl a Saska: kooperativní průzkum interiéru (2024)

**Cooperative Indoor Exploration Leveraging a Mixed-Size UAV Team with
Heterogeneous Sensors**, CASE 2024.
[Původní text, §IV–V](https://arxiv.org/pdf/2407.09206).

**Algoritmus:** frontier body zájmu → dosažitelnost podle velikosti dronu
na SphereMap → bipartitní přiřazení jako minimum-cost flow (MCF) → cesta.
Nedosažitelné hrany se nevytvářejí; pomocný cíl v aktuální poloze dovoluje
čekání. Při příliš malém odstupu větší dron stojí, menší dostane ústupový
cíl s cestou plánovanou pomocí A*.

**Důkazy a limity:** simulace kanceláří a reálné experimenty se dvěma
různými UAV. Autoři popisují drift relativní lokalizace i zdržení způsobené
velkými odstupy. Používají výrazně větší platformy než Pavo20.

**Pro nás:** velmi blízký vzor architektury. Ústup není sám o sobě chyba;
potřebuje plán, prioritu a ukončení. U tří stejných dronů nelze převzít
prioritu „větší versus menší“ bez nové politiky. MCF s jednotkovými kapacitami
a aditivní cenou řeší obdobné přiřazení jako Hungarian, nikoli překryv
pozorování nebo střet cest v čase.

### 9.4 Musil, Petrlík a Saska: SphereMap (2022)

**SphereMap: Dynamic Multi-Layer Graph Structure for Rapid Safety-Aware
UAV Planning**, RA-L 2022; preprint nahrán 2023.
[Článek, §III–V](https://arxiv.org/pdf/2302.01833),
[autorský kód](https://github.com/ctu-mrs/spheremap).

**Algoritmus:** volný prostor reprezentují překrývající se koule, nad nimi
řidší topologický graf oblastí a uložené vnitřní cesty. Cena kombinuje
délku a blízkost překážek; slouží k rychlému dotazování cest k více cílům.

**Předpoklad:** jde o geometrický plánovač. Dynamická omezení dronu přenechává
lokálnímu plánování. Výsledky rychlosti jsou pro uvedené mapy a reprezentace;
nelze je přepsat jako slib zrychlení našeho BFS o stejný násobek.

**Pro nás:** převzít myšlenku ceny průchodu a topologických oblastí, až bude
větší mapa. V mřížce 200 × 200 je nejdřív potřeba změřit, zda plánování cest
vůbec tvoří významnou část cyklu. Přepis mapové reprezentace není podmínkou
správného koordinátoru.

### 9.5 Petráček et al.: skutečné průzkumné lety v jeskyních (2021)

**Large-Scale Exploration of Cave Environments by Unmanned Aerial Vehicles**,
RA-L 2021; arXiv kopie z roku 2023.
[Článek, §III–V](https://arxiv.org/pdf/2303.02972).

**Algoritmus a systém:** propojení mapování, plánování se zohledněním zorného
pole, sledování trajektorie a volitelné průzkumné politiky. Kooperativní
návrat vytváří komunikační strukturu a prodlužuje dobu průzkumu, pokud se
všichni roboti nemusí fyzicky vrátit na start.

**Důkazy:** reálné lety v Býčí skále a simulace. Kvantitativní srovnání
kooperativního návratu je v simulaci; není správné zaměnit je za skutečný
současný let celého roje v jeskyni.

**Pro nás:** důležitý požadavek rozlišit rozpočet průzkumu, přistání, návrat
a doručení map. Strategii ponechání robotů v prostředí nepřebírat automaticky
do běžného mapování místnosti, kde chceme všechny drony získat zpět.

### 9.6 Bayer, Čížek a Faigl: terénní systém SubT (2023)

**Autonomous Multi-robot Exploration with Ground Vehicles in DARPA
Subterranean Challenge Finals**, Field Robotics.
[Terénní zpráva, zejména §3.5 a 4](https://comrob.fel.cvut.cz/papers/fr23mre.pdf).

**Přínos:** propojuje volbu průzkumných bodů s průchodností terénu,
topometrickým plánováním a koordinací s omezenou komunikací. Úkol zahrnuje
i čas potřebný k předání nalezené informace základně.

**Důkazy:** heterogenní pozemní roboti, simulovaná i fyzická nasazení;
zpráva odlišuje plně autonomní provoz a režim se zásahy operátora.

**Pro nás:** kontrolní příklad, že užitek mise není jen počet obarvených
buněk. Při problémech přenosu může mít doručení mapy vyšší hodnotu než další
frontier. Dynamiku pozemních robotů a jejich průchodnost nepřenášet na UAV.

### 9.7 Musil, Petrlík a Saska: MonoSpheres (2025/2026)

**MonoSpheres: Large-Scale Monocular SLAM-Based UAV Exploration through
Perception-Coupled Mapping and Planning**, preprint 2025, RA-L 2026.
[Článek, popis metody a §VII–VIII](https://arxiv.org/pdf/2511.17299),
[autorský kód](https://github.com/ctu-mrs/monospheres).

**Algoritmus:** mapování a plánování se přizpůsobují řídké hloubce
z monokulárního SLAM, její nejistotě a potřebě paralaxy. Volba pohybu
a orientace současně podporuje vnímání prostředí.

**Důkazy:** simulace, reálné vnitřní i venkovní prostředí a ablace. Výslovná
slabina: nelze zmapovat překážku, kterou SLAM frontend vůbec nezachytí,
například některé tenké nebo rozsáhlé netexturované objekty.

**Pro nás:** novější práce MRS důležitá pro variantu s kamerou OpenIPC.
Není to algoritmus přidělování úloh roji ani důvod zaměnit kameru za
spolehlivý lidar. Koordinátor musí znát, jaké pozorování daný senzor umožňuje.

### 9.8 Další větev MRS: roj bez explicitní komunikace

Horyna et al., **Decentralized swarms of unmanned aerial vehicles for search
and rescue operations without explicit communication**, online 2022,
*Autonomous Robots* 47 (2023).
[Vydavatelský abstrakt](https://link.springer.com/article/10.1007/s10514-022-10066-5).

**Ověřeno jen z abstraktu:** vizuální interakce sousedů a detekce objektů
mění společný směr letu. Jde o flocking a navigaci k objektům zájmu.
Bez dalšího rozboru z toho nelze odvozovat metodu úplného mapování našich
místností, správu frontier rezervací ani chování v úzkých dveřích.

## 10. Další výzkumné směry a jejich použitelnost

### 10.1 MinPos: levná koordinace pomocí pořadí

Bautin, Simonin a Charpillet, **MinPos: A Novel Frontier Allocation Algorithm
for Multi-robot Exploration**, ICIRA 2012.
[Původní text, §4–5](https://perso.citi-lab.fr/osimonin/OSimonin/travaux/icira2012.pdf).

Robot vyhodnocuje své pořadí mezi ostatními podle délky cesty ke každé
hranici. Preferuje hranici, pro kterou má nejnižší pořadí; při shodě
rozhoduje vzdálenost. Cesty počítá šíření vlny z hranic. Práce zahrnuje
simulace i pozemní roboty.

**Pro nás:** jednoduchý a relevantní kontrolní alokátor nad stejnými
kandidáty. Pořadí není informační zisk; metoda sama neřeší viditelnost,
kinematiku ani bezpečný průjezd. Případ „více dronů než užitečných bodů“
stále vyžaduje explicitní politiku.

### 10.2 coExplore: co vlastně dát do matice Hungarian

Scheler a Dietrich, **coExplore: Combining multiple rankings for multi-robot
exploration**, preprint 2023.
[Článek, algoritmus 1 a §III–IV](https://arxiv.org/pdf/2303.17459).

Kombinuje normalizovanou vzdálenost po mapě, pořadí robotů u hranice a
pořadí velikostí hranic. Nad výslednou pevnou maticí používá Hungarian.
Vyhodnocení obsahuje tři simulované scénáře; nejde o důkaz reálných letů.

**Pro nás:** konkrétní reprodukovatelná alternativa k neurčitému „přidejme
Hungarian“. Pořadí velikosti tlumí extrémní odhady, ale velikost frontier
není fyzikálně přesný informační zisk. Normalizace vůči aktuálním maximům
navíc může měnit význam ceny po vzniku nového cíle — v našem experimentu
proto měřit i četnost přepínání cíle.

### 10.3 Aukce a CBBA: když se má koordinace přesunout na agenty

Choi, Brunet a How, **Consensus-Based Decentralized Auctions for Robust Task
Allocation**, T-RO 2009.
[Původní vydavatelský záznam](https://doi.org/10.1109/TRO.2009.2022423),
[popis a varianty od autorů MIT ACL](https://acl.mit.edu/projects/consensus-based-bundle-algorithm).

CBBA tvoří svazky úloh pomocí nabídek a komunikačním konsenzem řeší rozdílné
názory na vítěze. Projekt autorů popisuje i rozšíření pro asynchronní
komunikaci. **Zde ověřeno z autorského popisu, nikoli audit důkazu konvergence.**

**Pro nás:** při třech dronech a funkčním centrálním uzlu by přibylo
vyjednávání bez jasného přínosu. Před případným převzetím určit stabilní
identitu úlohy, pravidla změny nabídky po změně mapy a zotavení po rozdělení
sítě. Vyřešení konfliktu vlastnictví cíle nezaručuje bezkoliznost tras.

### 10.4 FAME: průzkumník a dokončování zbytků mapy

Bartolomei, Teixeira a Chli, **Fast Multi-UAV Decentralized Exploration of
Forests**, RA-L 2023.
[Článek, §III–IV](https://lucabartolomei.github.io/publications/RAL_2023_Multi_Robot_Forests.pdf),
[autorský kód a benchmark](https://github.com/v4rl-ucy/fast_multi_robot_exploration).

Přepíná mezi `Explorer`, který rozšiřuje prozkoumanou oblast, a `Collector`,
který místně dočišťuje malé neznámé oblasti za překážkami. Agenti koordinují
oblasti zájmu a sdílejí mapové informace, režimy a trajektorie.

**Důkazy:** benchmarky lesních prostředí, včetně realistické geometrie,
a ablace režimů. Rychlejší dokončení může být vykoupeno delší celkovou
dráhou; zde nejde o fyzické lety našeho typu stroje.

**Pro nás:** dobrá alternativa k ústupu bez průzkumného přínosu: volný dron
může zpracovat skutečně dosažitelné zbytky. Nesmí však být poslán na falešné
frontiery způsobené diskretizací stěny. Nejprve odlišit chybu mapy od
opomenuté oblasti a vyhodnotit `T90` i dokončení.

### 10.5 CBS a SIPP: koordinace cest v prostoru i čase

**CBS**, Sharon et al., *Artificial Intelligence* 2015: horní úroveň větví
podle konfliktů agentů, spodní plánuje jednotlivé cesty s přidanými
omezeními. Optimalita se vztahuje k definovanému diskrétnímu MAPF modelu
a jeho ceně.
[Původní článek](https://webdocs.cs.ualberta.ca/~nathanst/papers/sharon2015cbsjournal.pdf).

**SIPP**, Phillips a Likhachev, ICRA 2011: stav zahrnuje konfiguraci a
bezpečný časový interval. Umožňuje plánovat pohyb i čekání při známém vývoji
obsazení prostoru. Je to plánovač jednoho agenta vůči dynamickým překážkám;
sám nepřiděluje průzkumné úlohy celému roji.
[Původní článek](https://www.cs.cmu.edu/~maxim/files/sipp_icra11.pdf).

**Pro nás — návrh adaptace:** pokud rezervace dveří nestačí, porovnat
prioritizované časové plánování se SIPP proti CBS pro tři agenty. Ošetřit
obsazení vrcholů, výměnu protisměrných hran, poloměr stroje a rezervu na
zpoždění. Stojící dron obsazuje prostor i po dosažení cíle.

Pouhé převedení časů z mřížky na rychlostní povely není korektní dynamický
model. Relevantní pokračování je
[Safe Interval Path Planning With Kinodynamic Constraints (2023)](https://arxiv.org/abs/2302.00776),
zde zkontrolované pouze na úrovni abstraktu. Před implementací zvolit
konkrétní model brzdění a proveditelných přechodů. Prioritizované plánování
také může selhat kvůli pořadí agentů, i když jiné společné řešení existuje.

### 10.6 EGO-Swarm: trajektorie pro létající roj

Zhou et al., **EGO-Swarm: A Fully Autonomous and Decentralized Quadrotor
Swarm System in Cluttered Environments**, ICRA 2021.
[Článek, §III–IV](https://arxiv.org/pdf/2011.04183),
[autorský kód](https://github.com/ZJU-FAST-Lab/ego-planner-swarm).

Decentralizovaně optimalizuje hladké trajektorie s penalizací kolizí,
generuje topologické alternativy a sdílí plánované trajektorie. Zahrnuje
kompenzaci relativního lokalizačního driftu pomocí detekce agentů v hloubce.
Ověřen byl v simulaci i reálnými UAV.

**Pro nás:** reference pro budoucí lokální plánování pohybu. Nenahrazuje
výběr průzkumného cíle. Pro převzetí potřebujeme trajektorie sousedů,
odpovídající vnímání a regulátor schopný trajektorii sledovat; samotný
`PointStamped` a `Float32` toto rozhraní neposkytují.

### 10.7 RMADER: jak nezaměnit nově plánovanou a skutečně prováděnou cestu

Kondo et al., **Robust MADER: Decentralized Multiagent Trajectory Planner
Robust to Communication Delay in Dynamic Environments**, rozšířený text 2023.
[Článek, §II a IV](https://arxiv.org/pdf/2303.06222),
[autorský kód](https://github.com/mit-acl/rmader).

Odděluje navrženou a potvrzenou trajektorii. Před přechodem na novou
provádí kontrolu konfliktů po dobu, která musí pokrýt maximální zpoždění.
Zachovává dosud platnou variantu, pokud nový návrh neprojde.

**Mez záruky:** vyžaduje `max_delay <= delay_check`; úplné přerušení
komunikace neřeší. Autoři uvádějí, že některá zpoždění při fyzických
experimentech tuto mez překročila, takže tehdy formální záruka neplatila,
i když zaznamenané lety zůstaly bez kolize.

**Pro nás:** převzít hlavně protokol platnosti plánu, verzi, potvrzení
a pokračování v ověřeném plánu. Článek nedokazuje, že postačí oříznout
rychlost podle poslední známé polohy.

### 10.8 C²-Explorer: topologicky souvislé přidělení práce (2026)

Yan et al., **C²-Explorer: Contiguity-Driven Task Allocation with
Connectivity-Aware Task Representation for Decentralized Multi-UAV
Exploration**, preprint z 8. 3. 2026.
[Původní text, §IV–V](https://arxiv.org/pdf/2603.07699).

Rozděluje nespojené neznámé části jedné hrubé buňky na samostatné úlohy.
CVRP rozšiřuje o penalizaci přidělení nesousedících úloh. Cílem je omezit
přejíždění mezi oblastmi a zachovat souvislou práci v čase.

**Důkazy:** srovnání s RACER a FAME v simulacích, ablace a ukázky skutečného
průzkumu třemi UAV s 3D lidarem. Jde zde o ověřený preprint; stav recenzního
řízení nebyl doložen. PDF dostupnost kódu teprve slibuje.

**Pro nás:** přínosná myšlenka pro ohradu a místnosti: geometricky blízké
body mohou vyžadovat odlišné průchody. Výsledná procenta zrychlení z jejich
benchmarku nejsou odhadem pro naši 2D mapu. Převzít lze nejdřív stabilní
přidělení propojené oblasti, bez implementace celého CVRP.

### 10.9 Centralizované rozšíření plánovače jednoho UAV (2026)

Mendes, Basiri a Ventura, **Centralized Multi-UAV Exploration and 3D
Reconstruction Using Single-UAV Planners**, text označený ICARM 2026,
arXiv zveřejněn 30. 9. 2026.
[Původní text, §III–IV](https://arxiv.org/pdf/2609.40208).

Sdílí TSDF mapu a přehled aktivních cest. Jednotlivé plánovače generují
cesty se zohledněním ostatních; senzory filtrují ostatní UAV před integrací
do mapy. Porovnává společný a oddělený start čtyř typů plánovačů v simulaci.

**Pro nás:** architektonicky blízká kontrolní varianta: centrální mapa,
lokální vykonávání a známé aktivní cesty. Doplňuje důvod testovat startovní
konfiguraci a vznik falešných překážek. Vyhýbání podle vzdáleností bodů cest
není totéž jako úplná časová rezervace; prostorově se křížící cesty mohou
být odmítnuty i při různých časech průjezdu. Simulační výsledky nevydávat
za ověření reálného roje.

### 10.10 Dec-MARVEL: učící se koordinace s rozpočtem (2026)

**Dec-MARVEL: Decentralized Multi-Agent Exploration without Communication
under Budget Constraints**, preprint, červenec 2026.
[Původní text, §VI–VIII](https://arxiv.org/pdf/2607.09060).

Používá centralizovaný trénink a decentralizovanou politiku. Ta volí
waypoint a směr pozorování z lokálních frontier, zbývajícího rozpočtu
a vizuálně pozorovaných trajektorií spoluhráčů. Explicitně rezervuje
možnost návratu.

**Důkazy:** 900 simulovaných běhů v 2D s omezeným zorným polem a testy na
čtyřech fyzických mobilních robotech s motion capture. To není důkaz
autonomních letů čtyř UAV bez externí lokalizace.

**Pro nás:** relevantní směr, pokud později zmizí komunikace a vznikne
vhodný tréninkový simulátor. Dnes by přibyla závislost na tréninkových mapách,
detekci sousedů a přenosu politiky. Návratový rozpočet lze zavést i bez RL.
Nejde o doloženou náhradu našeho alokátoru bez dalších experimentů.

### 10.11 Co bylo nalezeno, ale nehodnoceno jako hotový kandidát

- **PC-Explorer (RA-L 2025):** vydavatelský abstrakt popisuje kompaktní
  reprezentaci známého prostoru a frontier pro omezenou komunikaci.
  Plný text se nepodařilo zpřístupnit, proto zde není audit algoritmu ani
  doporučení jej implementovat.
  [Vydavatelský záznam](https://doi.org/10.1109/LRA.2025.3592139).
- **Connectivity-Aware Graph Extension for Decentralized Multi-Robot
  Exploration (září 2026):** ověřena existence a abstrakt; téma spadá do
  rozdělení prostoru při přerušované komunikaci. Závěry výše na něm nestojí.
  [Preprint](https://arxiv.org/abs/2609.00804).
- Další obecné práce o formacích, flockingu a známém plošném pokrytí nejsou
  automaticky alternativami pro průzkum neznámé mapy. Jejich zařazení pouze
  podle slova „swarm“ by srovnání zkreslilo.

## 11. Srovnání pro náš konkrétní systém

Následující tabulka je **syntéza a doporučení autora této rešerše** z výše
citovaných prací. Obtížnost je relativní vůči dnešnímu kódu, nikoli údaj
z článků. Označení „teď“ znamená kandidáta k experimentu po opravě navigace.

| Metoda / princip | Potřebná data | Co by u nás měnila | Priorita |
| --- | --- | --- | --- |
| Iterativní přiřazení | Dosažitelné body a matice cen | Opravená baseline | Teď |
| Hungarian / MCF | Stejná matice a přípustnost párů | Lepší součet cen jedné sady přidělení | Teď jako jedna rodina baseline |
| MinPos | Ceny cest všech agentů k cílům | Rozprostření podle pořadí | Teď, malý zásah |
| Burgardův mezní užitek | Odhad viditelnosti kandidátů | Méně duplicitního pozorování | Teď, návrh §4 |
| coExplore | Cesty, pořadí a velikosti hranic | Jiná konstrukce matice cen | Levná doplňková baseline |
| MTSP / RACER / C² principy | Vztahy oblastí, cesty a workload | Delší horizont a stabilní oblasti | Po ověření více místností |
| FAME princip | Spolehlivě rozlišené zbytky mapy | Užitečný úkol pro dalšího drona | Pokud zůstávají skutečné mezery |
| Cross-rank | Historie přijatých poloh, lokální plánování | Koordinace s omezeným přenosem map | Až při změně komunikačního režimu |
| CBBA | Úlohy, nabídky, zprávy sousedů | Distribuované vlastnictví úloh | Zatím odložit |
| SphereMap | 3D volný prostor a topologické oblasti | Rychlé geometrické cesty | Až při větší/3D mapě |
| Rezervace průchodu / SIPP / CBS | Cesty, čas, rozměry a dynamika | Řešení střetů cest a čekání | Rezervace teď, ostatní podle potřeby |
| CBF / ORCA / BVC | Stavy sousedů, okolí a model pohybu | Změna přípustného pohybu | Samostatný experiment |
| EGO-Swarm / RMADER | Vlastní i cizí trajektorie a jejich platnost | Plánování a provádění pohybu | Výraznější změna architektury |
| MonoSpheres | Monokulární SLAM a jeho nejistota | Vnímání a navigace jednoho UAV | Pro kamerovou variantu |
| Dec-MARVEL | Trénink, lokální mapy a pozorování sousedů | Učená výběrová politika | Výzkumná větev, nyní odložit |

### 11.1 Co širší rešerše mění oproti původnímu doporučení

1. **Hungarian nemá být předem vítěz.** Má smysl jako přesná kontrola
   aditivního přiřazení. MCF a MinPos rozšiřují smysluplné srovnání.
2. **Ústup zůstává platnou součástí řešení.** Chyba je zaměnit dočasné
   odstranění konfliktu za trvalou průzkumnou roli bez měřitelného přínosu.
3. **Topologie a stabilita práce jsou důležitější, než naznačovala první
   verze.** Kandidáti se mají spojovat podle dosažitelného prostoru, ne
   jen podle geometrické blízkosti.
4. **Komunikace určuje vhodnou rodinu.** Výsledek dosažený bez sdílené mapy
   nemusí být lepší volbou pro systém, který sdílenou mapu už má.
5. **Bezpečnostní filtr a plán průjezdu se doplňují.** Není podložené čekat,
   že přechod na CBF/ORCA nahradí domluvu, kdo smí do jediných dveří.

### 11.2 Úprava pořadí experimentů pro Clauda

Původní §7 platí jako seznam oprav. Pro porovnání algoritmů jej doplňuje
tato konkrétní posloupnost:

**E0 — opravená baseline.** Sjednotit cílový bod a cenu, předat yaw,
ověřit sledování cesty. Uložit vstupy alokátoru a důvody odmítnutí cílů.

**E1 — porovnat výhradně přiřazení.** Stejné kandidáty, cestovní ceny,
lokální řízení a rezervace použít pro `iterative`, `hungarian_or_mcf`
a `minpos`. Pokud implementujeme Hungarian i MCF se stejným modelem,
jejich optimum má mít stejnou cenu; rozdíly v letu nejsou automaticky
důkazem jiné kvality optimalizace a mohou pocházet z rozhodování při shodě.

**E2 — porovnat informační přínos.** Nad stejnými pozorovacími body
přidat variantu A z §4 a případně `coexplore`. Vliv nového generátoru bodů
měřit odděleně od vlivu ceny a samotného přiřazení.

**E3 — prostor a čas.** Dveře s protisměrným provozem, slepá chodba,
ohrada a dvě oblasti spojené jediným průchodem. Měřit čekání, ústupy,
průchody a stagnaci. Nejprve explicitní rezervace; při jejích doložených
selháních přidat prioritizované časové plánování nebo CBS.

**E4 — souvislá práce a dokončení.** Zafixovat vlastnictví oblasti po dobu
platnosti jejího přínosu; porovnat s nezávislým přepočtem bodů. Samostatně
testovat roli dokončující zbytky mapy. Nepřidávat obě změny v jednom běhu.

**E5 — omezená komunikace.** Až má každý agent lokální plánování a fallback,
porovnat sdílení celé mapy, přírůstků a jen poloh. Ztrátu spojení a zastaralý
stav oddělit od poruchy samotného agenta. Sem patří Cross-rank.

**E6 — pohybový plánovač.** Vektorový filtr nebo sdílení trajektorií zavádět
s vlastním souborem testů. V případě časových plánů měřit skutečné odchylky
od harmonogramu a důsledky zpoždění, ne pouze bezkoliznost ideálního plánu.

### 11.3 Doplnění experimentálního protokolu

Ke kritériím §6 přidat následující podmínky. Jsou to návrhy této rešerše:

- Hlavní test zachová současný společný start. Oddělený start bude pouze
  citlivostní analýza; nesmí potají nahrazovat obtížnější původní scénář.
- Pokrytí celé mapy, kvalita rekonstrukce povrchů a nalezení objektu jsou
  různé cíle. Nesrovnávat jejich časy jako tutéž metriku.
- V offline přehrání lze porovnat cenu a validitu přiřazení. Nelze z něj
  vyvodit nové letové pokrytí: jiné cíle změní budoucí polohy i měření.
- `T90` hodnotit spolu s bezpečností, neúspěchy a spotřebou času navíc.
  Varianta, která je rychlá díky menším odstupům, není čisté zlepšení alokátoru.
- Porovnávat cenu součtu tras i nejdelší trasy. Minimalizace součtu
  nemusí minimalizovat čas posledního dokončujícího dronu.
- Uvést CPU, velikost mapy, počet kandidátů a frekvenci replánování.
  Výpočty viditelnosti a cest logovat odděleně od řešení přiřazení.
- Zavést scénář s jedním opravdu užitečným cílem. Čekání dvou dronů může
  být správné; vysoká „aktivita“ sama o sobě není úspěch koordinace.

## 12. Závěr pro výběr algoritmu a hranice rešerše

**Doporučená první kombinace pro tento projekt:** centralizovaná společná
mapa; více dosažitelných pozorovacích bodů; iterativní přidělení s mezním
informačním přínosem a stabilními rezervacemi; vykonatelná cesta na agentovi;
explicitní přednost a čekání v úzkých průchodech. Vedle ní mít MinPos
a Hungarian/MCF jako kontrolní varianty. Toto je návrh k měření, nikoli
výsledek vítězného benchmarku.

Pro větší mapy následně zkoumat přidělování souvislých oblastí a více návštěv
dopředu. Pro slabou komunikaci změnit i architekturu lokální autonomie.
Pokročilé trajektoriové plánovače řeší další vrstvu a potřebují nové kontrakty.

Rešerše nyní zahrnuje podstatně širší výběr ČVUT/MRS i zahraničních prací,
včetně výsledků zveřejněných do září 2026. Přesné limity dostupnosti jsou
u položek označené. Plný text rozsáhlé zprávy *UAVs Beneath the Surface*
nebyl přes použitý webový nástroj načten kvůli velikosti PDF; její detaily
proto nejsou použity jako samostatný důkaz. Registrace map, úplný přehled
SLAM a optimalizace detekce frontier nejsou předmětem tohoto rozšíření.

Dokument neobsahuje nové experimenty na našem roji ani tvrzení o bezpečnosti
skutečného Pavo20. Převzaté výsledky jsou vždy výsledky konkrétních autorů
na jejich platformách. Implementace ani platná rozhodnutí projektu se
samotným dopsáním této rešerše nemění.

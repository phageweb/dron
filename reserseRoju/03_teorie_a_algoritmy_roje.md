# Teorie a algoritmy řízení roje dronů

## 1. Roj je několik vrstev, ne jeden algoritmus

Literatura někdy pod slovem „swarm control“ míchá rozhodování o misi, přidělení
úloh, plánování cest, formaci, vyhýbání, komunikaci a vlastní stabilizaci letu.
Praktičtější rozklad je:

```text
L5  cíl mise a operátor
L4  přidělení úloh: kdo má kam letět a co měřit
L3  globální / lokální plánování trajektorií
L2  koordinace: formace, flocking, consensus, pokrytí
L1  bezpečnostní filtr: agent–agent, překážky, geofence, limity
L0  lokální autopilot: odhad stavu, poloha, attitude, rates, motory
```

Vrstvy mohou být sloučené, ale každá má jinou časovou škálu a jiné informace.
Přehled [UAV Swarm Intelligence: Recent Advances and Future Trends](https://doi.org/10.1109/ACCESS.2020.3028865)
podobně odděluje rozhodování, plánování, řízení a komunikaci. Nejčastější chyba
prototypu je přeskočit rozhraní mezi nimi: například vydávat flockingovou
„sílu“ přímo jako motorový povel bez dynamických limitů a bezpečnostní vrstvy.

## 2. Centralizace, decentralizace a hierarchie

### Centralizované řízení

Centrální uzel zná stav všech `N` agentů a řeší společný problém.

Výhody:

- vidí globální konflikty a může optimalizovat celek;
- jednodušší logování, reprodukce a dohled operátora;
- lze snadno vynutit priority a společné časování;
- vhodné pro malý laboratorní roj.

Nevýhody:

- jediný bod selhání;
- provoz a výpočet rostou s počtem agentů;
- stav přichází s různým zpožděním;
- výpadek linky může odříznout vysokou řídicí vrstvu.

### Decentralizované řízení

Agent `i` používá svůj stav a stav množiny sousedů `N_i`. Sousedství může být
dáno komunikačním dosahem, viditelností, `k` nejbližšími agenty nebo předem
zadanou topologií.

Výhody:

- bez nutnosti jednoho výpočetního centra;
- lokální provoz a přirozená škálovatelnost;
- schopnost pokračovat po ztrátě některých členů.

Nevýhody:

- lokálně správná rozhodnutí mohou způsobit deadlock nebo rozpad skupiny;
- každý agent musí mít konzistentní relativní data a čas;
- důkazy často předpokládají ideální komunikaci či dynamiku;
- ladění a rekonstrukce chyby z distribuovaných logů jsou těžší.

### Hierarchické/hybridní řízení

Centrum určí misi, role, regiony a hrubé trajektorie. Každý stroj lokálně
stabilizuje let, hlídá stav linky a provádí poslední bezpečnostní zásah. To je
nejvhodnější první architektura pro tento projekt: centralizace je nástroj pro
měřitelnost, lokální autopilot a watchdog omezí následek výpadku.

## 3. Graf interakcí

Komunikaci nebo měření roje popisuje orientovaný či neorientovaný graf

```text
G = (V, E),  V = {1, ..., N}.
```

Hrana `(j,i)` znamená, že agent `i` používá informaci od `j`. Matice sousednosti
má prvky `a_ij ≥ 0`, stupeň `d_i = Σ_j a_ij` a Laplaceova matice je

```text
L = D - A.
```

Pro souvislý neorientovaný graf má `L` právě jednu nulovou vlastní hodnotu a
druhá nejmenší vlastní hodnota `lambda_2` vyjadřuje algebraickou konektivitu.
Vyšší `lambda_2` obvykle znamená rychlejší konsenzus, ale také více hran,
komunikace nebo citlivosti na zpoždění.

Graf není jen matematický obrázek. Implementace musí říct:

- kdy je soused přidán a odebrán;
- jak starou zprávu lze ještě použít;
- zda jsou hrany symetrické;
- zda se topologie při pohybu přepíná;
- jak se pozná rozdělení sítě na komponenty;
- zda bezpečnost závisí na komunikaci, nebo na vlastním senzoru.

## 4. Konsenzus

Pro agenty s jednoduchou integrátorovou dynamikou `x_dot_i = u_i` je základní
zákon

```text
u_i = -k · Σ_{j in N_i} a_ij · (x_i - x_j).
```

V maticovém tvaru `x_dot = -k L x`. V souvislém neorientovaném grafu se stavy
sbližují k průměru počátečních hodnot. `x_i` může být skalár, poloha, rychlost,
odhad nebo časová korekce.

Pro dron však `u_i` není motorový povel. Když je `x_i` poloha, výsledek lze
interpretovat jako omezenou cílovou rychlost nebo jako vstup do plánovače.
Skutečná dynamika je přinejmenším druhého řádu a má saturaci a zpoždění.

### Co může porušit školní důkaz

- nesouvislý nebo rychle se přepínající graf;
- různé a časově proměnné latence;
- ztracené nebo mimo pořadí doručené zprávy;
- saturace rychlosti a akcelerace;
- každý agent v jiném souřadném rámci;
- chyba lokalizace, která vypadá jako pohyb souseda;
- normalizace vah měnící výslednou rovnováhu.

Proto musí simulace obsahovat zpoždění, dropy, drift a limity už před prvním
vícedronovým letem.

## 5. Držení formace

### Leader–follower

Vedoucí sleduje misi, následovník `i` požaduje offset `r_i`:

```text
p_i,d = p_leader + R_leader · r_i.
```

Je jednoduchý a srozumitelný. Vedoucí je ale bod selhání a chyba se může
řetězit. Lepší je posílat stav vedoucího všem relevantním členům než vytvořit
dlouhý řetěz followerů.

### Virtuální struktura

Celá formace je jedno virtuální tuhé těleso. Plánovač řídí jeho polohu a
orientaci, z nichž se odvodí cíle agentů. Výhodou je přesný tvar, nevýhodou
malá pružnost v úzkých průchodech.

### Formace z relativních offsetů

Každá hrana požaduje relativní vektor `r_ij`:

```text
u_i = -k_p Σ_j a_ij[(p_i-p_j)-r_ij]
      -k_v Σ_j a_ij(v_i-v_j).
```

Formace je invariantní vůči společnému posunu. Aby nebyla volná i vůči rotaci
nebo škálování, musí topologie a dostupná měření obsahovat dost omezení. Při
změně topologie se má kontrolovat, že požadovaná geometrie zůstává určitelná.

### Vzdálenostní formace

Místo vektoru se hlídá jen `||p_i-p_j|| = d_ij`. To se hodí pro relativní
měření vzdálenosti, ale může mít zrcadlená nebo jiná lokální minima. Rigidity
teorie určuje, zda daný graf drží tvar až na globální posun a rotaci.

## 6. Flocking

Reynoldsův model používá tři lokální pravidla:

- **separation** – odpuzování od příliš blízkých sousedů;
- **alignment** – sladění rychlosti se sousedy;
- **cohesion** – pohyb k místnímu středu skupiny.

Původní práce je [Flocks, Herds, and Schools](https://www.red3d.com/cwr/papers/1987/boids.html).
Olfati-Saber převedl podobnou intuici na grafy, umělé potenciály a analýzu
stability v práci
[Flocking for Multi-Agent Dynamic Systems](https://hal.elte.hu/~vicsek/downloads/papers/flocking_tac06-engineering.pdf).

Obecný nominální povel může vypadat

```text
u_i = w_sep·u_sep + w_align·u_align + w_coh·u_coh + w_goal·u_goal.
```

Samotný vážený součet ale **není bezpečnostní důkaz**. Když `u_goal` přetlačí
odpuzování, dojde ke kolizi. Potenciál může mít lokální minimum, úzký průchod
může roj ucpat a diskrétní vzorkování může přeskočit oblast silného odpuzování.

Reálné experimenty 30 dronů ukázaly, že je nutné explicitně zahrnout pohybové
limity, komunikaci, zpoždění, perturbace a překážky; viz
[Optimized flocking of autonomous drones in confined environments](https://doi.org/10.1126/scirobotics.aat3536).

## 7. Pokrytí a průzkum

Pro mapování není vždy žádoucí držet formaci. Úkolem může být rozdělit oblast
tak, aby každý senzor obsluhoval jinou část. Klasický přístup používá Voroného
buňky: každý bod oblasti patří nejbližšímu agentovi. Agent se pohybuje k těžišti
své buňky váženému pravděpodobností nebo informační hodnotou.

Tím vzniká decentralizovatelný gradientní algoritmus pro pokrytí. Základní
teorie je v práci
[Coverage Control for Mobile Sensing Networks](https://arxiv.org/abs/math/0212212).

Pro skutečný průzkum je potřeba doplnit:

- překážky a dosažitelnost buněk;
- rozdílné senzory a zbývající energii;
- informační zisk neprozkoumané mapy;
- komunikační konektivitu;
- slučování map a uzávěry smyček;
- pravidlo návratu nebo předání úlohy při slabé baterii.

Alternativou je frontier exploration: z mapy se vyberou hranice známého a
neznámého prostoru a cíle se přidělí aukcí nebo optimalizací nákladů. Cena může
kombinovat délku cesty, riziko, baterii a očekávaný informační zisk.

## 8. Přidělování úloh

| Rodina | Princip | Kdy se hodí | Riziko |
| --- | --- | --- | --- |
| statické role | role a region jsou předem dané | první testy | nereaguje na poruchu |
| greedy | každý vezme nejlevnější volný cíl | rychlé a jednoduché | globálně horší řešení |
| aukce / market-based | agenti nabízejí cenu za úkol | distribuovaný průzkum | latence a nekonzistentní vítěz |
| Hungarian assignment | minimum společné ceny pro matici agent–cíl | malý centralizovaný roj | vyžaduje známé náklady |
| MILP | úlohy, pořadí a omezení v jednom modelu | offline/hrubé plánování | výpočetně náročné |
| MARL | politika naučená interakcí více agentů | složité strategie | validace, generalizace, garance |

Pro první verzi je lepší deterministické přidělení s dohledatelnou cenou než
multi-agent reinforcement learning. Naučená politika může přijít jako
porovnání, až existuje bezpečný klasický baseline a automatizované scénáře.

## 9. Vyhýbání kolizím

Kolize s překážkou a kolize dvou agentů jsou rozdílné problémy: druhý agent se
aktivně pohybuje a může současně měnit plán.

### 9.1 Umělé potenciály

Přitažlivý potenciál vede k cíli a odpudivý roste u překážky nebo souseda.
Metoda je levná a plynulá, ale má lokální minima, oscilace v úzkém průchodu a
neposkytuje sama o sobě záruku při saturaci a zpoždění. Je vhodná pro nominální
flocking, ne jako jediná ochrana.

### 9.2 Velocity Obstacles a ORCA

Velocity obstacle je množina relativních rychlostí, které v časovém horizontu
vedou ke kolizi. ORCA rozdělí odpovědnost mezi dvojici agentů a pro každého
vytvoří lineární omezení povolených rychlostí; nejbližší povolená rychlost se
najde malým lineárním programem. Popis a původní práce jsou na stránce
[Optimal Reciprocal Collision Avoidance](https://gamma-web.iacs.umd.edu/ORCA/).

Silné stránky: rychlost, decentralizace a přirozené řešení mnoha sousedů.
Slabiny pro kvadrokoptéru: základní model předpokládá rychle realizovatelnou
rychlost a reciproční reakci. Akcelerační limity, komunikační zpoždění a
nekooperující agent se musí doplnit. ORCA reference tedy musí projít dynamickým
tvarováním a nouzovou vrstvou.

### 9.3 Model Predictive Control

MPC v každém kroku řeší optimalizaci přes horizont:

```text
min  tracking_error + control_effort + formation_error
s.t. dynamics, actuator_limits, obstacle_constraints,
     pairwise_separation, terminal_constraints.
```

Centralizovaný MPC vidí všechny párové konflikty, ale počet dvojic roste jako
`N(N-1)/2`. Decentralizovaný MPC plánuje každého agenta zvlášť a iteruje nebo
sdílí předpokládané trajektorie; musí řešit nekonzistentní současné změny.

### 9.4 Sdílení trajektorií

Místo současného stavu agent publikuje i budoucí, již slíbenou trajektorii.
Ostatní ji vloží do svých omezení. MADER je decentralizovaný asynchronní 3D
plánovač s check–recheck schématem
([MADER](https://arxiv.org/abs/2010.11061)); Robust MADER přidává postup pro
komunikační zpoždění
([RMADER](https://arxiv.org/abs/2209.13667)). EGO-Swarm ukazuje lehký
decentralizovaný plánovač v neznámém členitém prostředí a výslovně počítá s
nespolehlivým sdílením trajektorií
([EGO-Swarm](https://arxiv.org/abs/2011.04183)).

Tyto systémy jsou důležitá reference, ne drop-in řešení pro současný projekt:
počítají s palubním vnímáním a výpočtem, který zde zatím každý dron nemá.

Rozsah, kterého lze s lokálními daty dosáhnout, ukazuje novější práce
[Decentralized traffic management of autonomous drones](https://doi.org/10.1007/s11721-024-00241-y):
autoři předvedli 100 autonomních kvadrokoptér a simulace až s 5000 agenty.
Výsledek je ale pro otevřený prostor, převážně 2D provoz a výškové vrstvy;
autoři také výslovně neprohlašují nulové riziko v přítomnosti stochastického
šumu. Je to důkaz praktické škálovatelnosti lokální predikce, nikoli hotová
bezpečnostní záruka pro malý indoor roj.

### 9.5 Control Barrier Functions

Definujme bezpečnou množinu dvojice

```text
h_ij(p) = ||p_i - p_j||² - d_safe² >= 0.
```

Safety filter hledá povel co nejbližší nominálnímu `u_nom`, který současně
splní bariérové podmínky:

```text
min_u ||u - u_nom||²
s.t.  CBF constraints, u_min <= u <= u_max.
```

Pro jednoduchý integrátor lze použít podmínku `h_dot + alpha(h) >= 0`. Poloha
kvadrokoptéry má vůči akceleraci vyšší relativní stupeň, takže je potřeba
exponenciální/high-order CBF nebo zjednodušený model s ověřeným sledováním.
Experimentální práce
[Safe multi-agent drone control using control barrier functions and acceleration fields](https://doi.org/10.1016/j.robot.2023.104601)
ukazuje lehký dvouvrstvý přístup s CBF a QP.

CBF záruka platí pouze pro použitý model, dostupný vstup a aktuální stav. Když
se dron nedokáže včas naklonit, lokalizace má chybu nebo QP nemá řešení, papír
fyziku nezachrání. Implementace musí mít konzervativní obálku a fallback.

## 10. Jak určit bezpečný rozestup

Geometrické minimum mezi středy dvou agentů je součet jejich kolizních
poloměrů. Pro pohyb je třeba přidat nejistoty:

```text
d_safe >= r_i + r_j
          + e_loc_i + e_loc_j
          + v_close · (tau_state + tau_comm + tau_compute + tau_act)
          + d_brake_i + d_brake_j
          + margin_model.
```

Konzervativní brzdná dráha pro konstantní dosažitelné zpomalení je

```text
d_brake = v² / (2·a_brake).
```

U kvadrokoptéry ale `a_brake` nezačne okamžitě: nejdřív se musí změnit náklon.
Proto se má konečná hodnota získat z opakovaných step testů se skutečnými
limity, napětím a nákladem. Použít je vhodné například 99. percentil zastavení
plus explicitní rezervu, ne průměr nejlepšího kusu.

Pro projektovou rotorovou obálku je samotné tvrdé geometrické minimum dvou
stejných strojů přibližně `2 · 0,08335 = 0,1667 m`. To **není doporučený letový
rozestup**; chybí v něm všechny členy z rovnice výše a ducts mohou přesahovat
rotorovou obálku.

## 11. Lokalizace a společný rámec

Pro absolutní formaci musí všechna `p_i` znamenat totéž. Nestačí, že každý
publikuje topic `pose`: jeho lokální `odom` může mít jiný počátek, orientaci i
drift.

Každý stav roje má obsahovat:

- `agent_id`;
- čas měření, ne pouze čas přijetí;
- název souřadného rámce;
- polohu, rychlost a jejich kovarianci;
- stav lokalizačního zdroje a stáří poslední korekce;
- dynamické limity a režim autopilotu.

Možnosti společného rámce:

1. motion capture – nejlepší pro první důkaz algoritmu, protože oddělí chyby
   koordinace od SLAM;
2. UWB anchors – vhodné indoor, ale vyžaduje kalibraci a řešení NLOS;
3. GNSS/RTK – venku, ne pro byt;
4. společná mapa a multi-robot SLAM – největší výzkumná hodnota i složitost;
5. čistě relativní řízení – nepotřebuje globální polohu, ale potřebuje
   spolehlivě měřit sousedy a směr.

## 12. Komunikace a čas

### Přenášet stav, ne video jako řídicí signál

Rojová koordinace obvykle potřebuje desítky až stovky bajtů na agenta a update,
ne surový obraz každého člena. Vysílat se má kompaktní stav a zamýšlená
trajektorie; těžká senzorová data jen tam, kde je používá mapa nebo operátor.

### QoS podle významu

| Data | Vhodná politika |
| --- | --- |
| vysokofrekvenční stav/IMU | best effort, malá depth, zahazovat staré |
| trajektorie s verzí a platností | reliable, omezená fronta |
| emergency stop / mode change | reliable + potvrzení aplikačním stavem |
| statická konfigurace/TF | reliable + transient local |
| mapa | podle transportu, obvykle reliable a fragmentace mimo řídicí smyčku |

ROS 2 podporuje deadline, lifespan, liveliness a volbu reliability; nabídka a
požadavek ale musí být kompatibilní
([ROS 2 QoS](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html)).
QoS není watchdog: aplikace musí stále kontrolovat timestamp a stav agenta.

### Časová synchronizace

Pro relativní predikci je důležitější známá chyba hodin a stáří dat než
„zprávy chodí rychle“. Každý záznam má rozlišovat:

```text
t_measurement -> t_publish -> t_receive -> t_control -> t_actuation.
```

Při simulaci musí všechny instance používat stejný `/clock`. Na hardwaru je
potřeba měřit odchylku hodin a nepřepočítávat různé timestampy jako současný
stav bez kompenzace.

## 13. Poruchové chování

Každý agent má mít explicitní stavový automat, například:

```text
BOOT -> READY -> TAKEOFF -> ACTIVE -> HOLD -> LAND
                         \-> DEGRADED -> HOLD/LAND
                         \-> EMERGENCY
```

Minimální události:

- zastaralý swarm setpoint;
- ztráta společné lokalizace;
- nesouhlas lokální a externí polohy;
- rozpojení komunikačního grafu;
- nízká baterie jednoho člena;
- saturace nebo neschopnost sledovat trajektorii;
- ztráta senzoru překážek;
- restart koordinátoru nebo změna epochy mise.

Bezpečný výsledek závisí na prostoru. „Všichni okamžitě přistaň“ může v husté
formaci způsobit společný sestup do sebe. Lepší je předem rezervovat výškové
vrstvy, holding body nebo sekvenční přistání. Emergency stop je poslední
mechanický prostředek, ne univerzální manévr ve vzduchu.

## 14. Co zvolit pro jednotlivé úlohy

| Úloha | Rozumný první algoritmus | Další krok |
| --- | --- | --- |
| vzlet a přistání více strojů | sekvenční stavový automat | rezervace časoprostorových koridorů |
| držení tvaru | centralizovaná virtual structure | relativní distribuovaná formace |
| následování vedoucího | broadcast leader state + offset | volba nového leadera |
| volný společný pohyb | omezený Reynolds/Olfati-Saber | optimalizovaný flocking |
| vyhýbání členům | centrální párový safety filter | CBF-QP / ORCA s dynamickými limity |
| známé prostředí | časované trajektorie | centralizovaný MPC |
| neznámé prostředí | rozdělení frontier cílů | decentralizované trajektorie a sdílení map |
| pokrytí oblasti | Voronoi/Lloyd + geofence | informačně vážené pokrytí |

## 15. Hlavní poučení z výzkumných platforem

[Crazyswarm](https://doi.org/10.1109/ICRA.2017.7989376) a jeho ROS 2 následník
[Crazyswarm2](https://imrclab.github.io/crazyswarm2/) ukazují užitečný vzor:
malé drony si drží rychlou stabilizaci lokálně, zatímco vyšší příkazy a
experimentální orchestrace jsou oddělené. Platforma zároveň ukazuje, že
spolehlivost rádia a lokalizace jsou součást výsledku, ne instalační detail.

Pro tento repozitář není cílem kopírovat Crazyflie firmware. Přenositelná je
architektura, namespacing, skupinové API, simulace se stejným skriptem jako
hardware a systematické logování každého agenta.

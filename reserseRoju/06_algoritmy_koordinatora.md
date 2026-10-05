# Algoritmy koordinátoru průzkumu

Stav rešerše: **3. 10. 2026**

Kapitola [03](./03_teorie_a_algoritmy_roje.md) popisuje řízení roje obecně a
průzkumu věnuje jednu stránku. Tahle kapitola jde do hloubky u jediné části:
**pozemního koordinátoru, který z map několika dronů rozhoduje, kdo kam poletí
a kdo komu musí uhnout**. Je psaná proti tomu, co už v projektu běží
(`ros_ws/src/openipc_swarm`), a proti tomu, co ukázaly lety z 2. a 3. 10.

Co je doložené literaturou a co je doporučení této rešerše, je odděleno: každá
sekce končí odstavcem **Pro nás**.

## 0. Co koordinátor průzkumu dělá

V literatuře i u nás se rozpadá na pět úloh. Každá má vlastní rodinu
algoritmů a každá může selhat sama:

| Úloha | Otázka | U nás dnes |
| --- | --- | --- |
| 1. Společný rámec a slučování map | Jak z několika map udělat jednu? | offsety startu + slučování po buňkách (`frames`, `merge`) |
| 2. Detekce hranic | Kde končí známé a začíná neznámé? | průchod celé mřížky + BFS dosažitelnosti z každého dronu |
| 3. Přidělení cílů | Kdo poletí ke které hranici? | hladově 1 hranice = 1 dron (R5), zbytek „pryč od ostatních“ (R5a) |
| 4. Vzájemná bezpečnost a uváznutí | Jak se nesrazit a nezaseknout? | skalární limit rychlosti, stop / zpomalení / ustupování |
| 5. Vyhodnocení | Jak poznat, že je roj lepší? | pokrytí v pevném čase 130 s |

## 1. Společný rámec a slučování map

**Známé počáteční polohy** jsou nejjednodušší případ: mapy se převedou o
známou transformaci a slučují se buňka po buňce. Tak to dělá většina prací o
koordinaci průzkumu, které se slučováním nezabývají – Burgard et al. (2005) i
Yamauchi (1998) předpokládají společný rámec.

**Neznámé počáteční polohy** vyžadují registraci map. Hörner (2016) ji řeší
jako sešívání panoramat: hledá v mřížkách obsazenosti obrazové příznaky a
odhaduje mezi nimi transformaci. Výsledek je balíček
`multirobot_map_merge` v ROS, který umí obojí – se známými i neznámými
počátečními polohami. Přehled Wang et al. (2025) řadí slučování map pod
lokalizaci a ukazuje, že u reálných systémů (DARPA SubT) se rámec obvykle
sjednocuje dřív, než vznikne mapa: společným startovním bodem, kalibrační
značkou nebo sdílenou SLAM úlohou.

**Jak sloučit dvě buňky**, když se mapy liší: součtem log-odds (fúze měření,
předpokládá nezávislost), maximem obsazenosti (konzervativní – zeď vyhraje)
nebo pravidlem „kdo viděl naposledy“. Rozpor dvou map v téže buňce je
nejlevnější měřítko driftu lokalizace bez ground truth.

**Pro nás.** Jsme v nejjednodušším případě: známé starty, sdílený rámec
simulátoru. Slučování podle maxima je správně konzervativní. Na skutečném
dronu ale offsety startu z `START_POSES` znamenají, že **drony musí odstartovat
přesně tam, kde si to koordinátor myslí** – centimetrová chyba v položení na
stůl se přenese do každé buňky. Až se poletí naostro, je potřeba buď měřit
start (značka, UWB), nebo převzít registraci map (Hörner) jako kontrolu.

## 2. Detekce hranic

**Yamauchi (1998)** definoval hranici (frontier) jako volnou buňku sousedící s
neznámou a navrhl posílat robota k nejbližší z nich. Celý obor průzkumu
mřížek z toho vychází.

**Keidar a Kaminka (2014)** ukázali, že procházet kvůli hranicím celou mapu je
zbytečné. *Wavefront Frontier Detection* (WFD) pouští BFS od robota jen po
volném prostoru; *Fast Frontier Detection* (FFD) zpracuje jen buňky
z posledního skenu, protože nová hranice může vzniknout jen na jeho okraji.
Inkrementální varianty jsou o řády rychlejší než průchod celé mapy.

**Umari a Mukhopadhyay (2017)** hledají hranice rostoucími stromy RRT (lokální
a globální), což funguje i v mapách, kde je hranic mnoho a jsou roztříštěné.
**FUEL** (Zhou et al., 2021) udržuje hranice inkrementálně ve struktuře
*Frontier Information Structure* a ke každé hranici počítá **pozorovací
body** (viewpoints) – místa, odkud je hranice nejlépe vidět – místo
těžiště hranice. Na tom staví i jejich vícedronový RACER.

**Pro nás.** Průchod celé mřížky 200 × 200 a BFS od každého dronu stojí desítky
milisekund a při 5 Hz to stačí – rychlost detekce není náš problém. Problém je
**co je cíl**: posíláme těžiště shluku hranice, které u zalomené hranice padá
do zdi (dokumentováno v `cluster_centroid`). Pozorovací body z FUEL jsou
přesně odpověď na to – a zároveň dávají víc cílů než shluků (viz 3).

## 3. Přidělení cílů

Tady je v literatuře nejvíc práce a tady je i náš největší rozdíl:

| Metoda | Princip | Co řeší | Slabina |
| --- | --- | --- | --- |
| Yamauchi (1998) | každý robot k nejbližší hranici, nezávisle | jednoduchost, robustnost | víc robotů ke stejné hranici |
| Burgard et al. (2005) | postupně: robot dostane nejlepší cíl (užitek − cena), **užitek hranic v dosahu senzoru od tohoto cíle se sníží** | roboti se rozprostřou sami, i když je hranic málo | hladové pořadí |
| Zlot et al. (2002) | aukce / tržní ekonomika: roboti nabízejí cenu za cíle | decentralizace, výpadky | latence, nekonzistentní vítěz |
| Faigl et al. (2012) | srovnání: hladové, iterativní, **Hungarian**, MTSP | – | Hungarian a MTSP vycházejí nejlépe |
| MinPos (Bautin et al., 2012) | robot jde k hranici, kde má **nejnižší pořadí** mezi roboty podle vzdálenosti | rovnoměrné rozprostření, decentralizovatelné | ignoruje velikost hranice |
| Wurm et al. (2008) | mapa se **rozdělí na místnosti** (segmentace), přiděluje se po segmentech | roboti se neperou o jednu místnost | potřebuje rozumnou segmentaci |
| RACER (Zhou et al., 2023) | rozklad prostoru do mřížky *hgrid*, rozdělení práce jako **CVRP** (vehicle routing s kapacitou), párová domluva | vyvážená zátěž, decentralizace, UAV | složitost implementace |

Dva poznatky jsou pro nás zásadní:

1. **„Méně hranic než robotů“ je známá situace a klasická řešení ji neřeší
   odháněním.** Burgard ji řeší snížením užitku: první robot dostane hranici a
   okolí jeho cíle ztratí hodnotu, takže další robot jde jinam – klidně
   k menší, vzdálenější hranici nebo k jiné části téže hranice. MinPos ji řeší
   pořadím: robot, který není k žádné hranici první, jde tam, kde je druhý.
   Žádný z nich robota „neposílá pryč“ bez cíle.
2. **Optimální přiřazení se vyplácí.** Faigl et al. naměřili, že Hungarian
   (optimální přiřazení robot–cíl, O(n³)) a formulace jako MTSP dávají nejlepší
   časy průzkumu; hladový výběr je horší. Pro 3 drony a desítky cílů je
   Hungarian zanedbatelně levný.

**Pro nás.** Náš R5 je Yamauchi s pravidlem „jedna hranice jednomu“ a R5a je
vlastní záplata: agent bez hranice dostane místo co nejdál od ostatních.
Lety ukázaly, proč je to slabé – ve sloučené mapě bývá dosažitelný **jeden**
shluk hranice, takže dva ze tří dronů většinu letu nemají co objevovat a jen
se rozestupují. Literatura nabízí dvě přímočaré náhrady:

- **Burgardovo snižování užitku nad pozorovacími body.** Z každého shluku
  hranice udělat několik cílů (pozorovacích bodů, nebo prostě buněk hranice
  vzdálených od sebe aspoň dosah senzoru) a přidělovat postupně se snížením
  užitku v okolí už přiděleného cíle. Dlouhá hranice tak dá práci dvěma dronům
  a R5a se stane zbytečným.
- **Hungarian nad maticí dron × pozorovací bod** s cenou = délka trasy + otočka
  − informační zisk. Pro 3 × 30 je to pod milisekundu.

Segmentace na místnosti (Wurm) je zajímavá pro naši **ohradu**: je to
samostatná místnost s jedněmi dveřmi a ve slabších dnešních letech zůstala
zmapovaná ze 60–80 %, zatímco zbytek místnosti měl přes 85 %. Přidělit ji jednomu dronu jako celek by bylo přímočařejší než doufat,
že se k jejím dveřím někdo dostane přes frontu ostatních.

## 4. Vzájemná bezpečnost a uváznutí

**Bezpečnostní filtry** upravují nominální povel tak, aby nebyla porušena
podmínka odstupu. **Control barrier functions** (Wang, Ames, Egerstedt, 2017)
to formulují jako kvadratický program: najdi rychlost co nejbližší nominální,
pro kterou se odstup každé dvojice nezmenšuje rychleji, než dovoluje bariéra.
Rozhodující vlastnost: filtr **mění vektor rychlosti**, ne jen jeho velikost –
dron může bokem objet souseda. Decentralizace je přirozená: každý robot hlídá
jen blízké sousedy.

**Uváznutí je známá vlastnost reaktivních filtrů, ne chyba implementace.**
Grover, Liu a Sycara (2020, 2023) formálně ukázali, že CBF regulátory mají
rovnovážné stavy, kde roboti stojí před cílem, a odvodili jejich geometrii;
už Wang et al. (2017) přidávají kvůli uváznutí relaxované bariéry, brzdné
regulátory a **konzistentní perturbace**. **Buffered Voronoi Cells** (Zhou,
Wang, Bandyopadhyay, Schwager, 2017) dávají každému robotu jeho buňku
Voronoiho diagramu zmenšenou o bezpečnostní okraj; uváznutí předcházejí
**pravidlem pravé ruky** – každý robot objíždí souseda zprava, takže dva
proti sobě se míjejí místo aby stáli. **ORCA** (van den Berg et al.) řeší
totéž v prostoru rychlostí, s recipročním dělením odpovědnosti.

**Pro nás.** Náš filtr je záměrně slabší: kvůli R19 posílá koordinátor jen
**skalární limit rychlosti** a nikdy nemění směr. To je přesně konstrukce,
která uvázne – směr, kterým by se dvojice rozešla, nikdo nevolí. Dnes jsme
ho několikrát záplatovali (ustupující v každé zablokované skupině, ustupuje jen
ten, kdo míří pryč, rychlost měřená do kontaktu, pásmo zpomalení jen pro
sbližující se dvojice, otáčení na místě, hystereze); každá
záplata byla oprávněná, ale dohromady **znovu vynalézáme to, co CBF/BVC dávají
z principu**. Varianty, od nejmenšího zásahu:

- **Pravidlo pravé ruky v autonomii dronu** – když ho roj drží a cíl je za
  sousedem, objíždět zprava. Malá změna, žádné porušení R19.
- **Vektorový limit**: koordinátor posílá místo čísla zakázaný poloprostor
  (normála ke dvojici + maximální rychlost proti ní). Arbiter z povelu ořízne
  jen složku směrem k sousedovi – stále jen omezuje, nikdy neřídí, takže R19
  v duchu platí. To je CBF pro jednoduchý integrátor v uzavřeném tvaru.
- **Plný CBF-QP v arbiteru** – přesně formulace Wang et al.; vyžaduje stav
  sousedů na dronu.

## 5. Vyhodnocení

**Explore-Bench** (Xu et al., 2022) navrhuje sjednocené metriky:
**čas do 90 %** pokrytí (T_topo) a **čas do 99 %** (T_total) jako metriky
efektivity, a pro spolupráci **podíl překryvu** prozkoumané plochy mezi roboty
a **směrodatnou odchylku** ploch, které prozkoumali jednotlivě. Scénáře mají
standardizované typy: smyčka, úzká chodba, kout, více místností.

**Pro nás.** Měříme pokrytí po pevných 130 s – to ukáže, jestli roj stihne
totéž co jeden dron, ne jestli je **rychlejší**, což je jediný důvod mít roj.
Převzetí metrik z Explore-Bench je levné, protože trasa koordinátoru
(`trace.jsonl`) už obsahuje mapu po sekundách:

- **čas do 90 % podlahy** správně objevené (podle hodnocení v přehrávači);
- **překryv**: kolik buněk vidělo víc dronů (merge už počítá rozpory, stačí
  počítat i shody);
- **odchylka** příspěvků jednotlivých dronů – nízká = práce rozdělená.

K tomu známá vada naší metriky: buňka podlahy dotýkající se zdi se počítá
jako neprozkoumaná, ačkoli do ní mapa kreslí povrch zdi (~6 bodů z místnosti).

## 6. Co z toho plyne – návrh pořadí

Seřazeno podle poměru užitku a zásahu. Body 1–3 nemění žádné rozhodnutí ve
specifikaci; 4 a 5 ano.

1. **Měřit čas do 90 % a překryv** (Explore-Bench). Bez toho nelze říct, jestli
   cokoli dalšího pomohlo. Data už jsou v `trace.jsonl`.
2. **Více cílů z jedné hranice + Burgardovo snižování užitku**, přiřazení
   Hungarianem. Odstraní příčinu, kvůli které vzniklo R5a: dva ze tří dronů
   bez práce.
3. **Pozorovací body místo těžiště** (FUEL) – cíl, ze kterého je hranice
   vidět, ne bod uprostřed ní, který může ležet ve zdi.
4. **Vektorový limit místo skalárního** (CBF pro integrátor), nebo aspoň
   pravidlo pravé ruky. Nahradí většinu dnešních záplat jedním principem.
   Mění výklad R19 – rozhodnutí.
5. **Poziční cíle v režimu GUIDED** místo „leť rovně, zatoč u zdi“. Dnes cíl
   jen radí, kam se otočit; dokud tomu tak je, žádné přidělení cílů nemůže
   dron spolehlivě dostat do ohrady. Kapitola R19 to sama uvádí jako další
   krok.
6. **Segmentace na místnosti** (Wurm) – až bude místností víc než jedna
   ohrada.

## 7. Kontext: co ukázaly dnešní lety

Lety tří agentů ze společného startu (3. 10. 2026), po postupných opravách
filtru. Poslední verze (odstup cílů 0,2 m, hystereze), tři lety bez okna
Gazeba:

| Let | Místnost | Ohrada | Uletěno (v1/v2/v3) |
| --- | ---: | ---: | --- |
| D | 92 % | 95 % | 33 / 30 / 35 m |
| E | 90 % | 93 % | 38 / 16 / 11 m |
| F | 87 % | 73 % | 15 / 21 / 25 m |

Samostatný dron: 89–93 % místnosti, 92–94 % ohrady. Roj je nejlépe na úrovni
jednoho dronu, ne nad ní, a rozptyl mezi lety je velký. Lety s nízkým
výsledkem mají společné to, co popisují sekce 3 a 4: dva drony bez hranice a
dvojice, která se zablokuje na stopce. Detail je v `workflow/log.md` a
přehrávačích `logs/swarm_mapping/*/replay.html`.

## Zdroje

- B. Yamauchi, **Frontier-based exploration using multiple robots**, Autonomous
  Agents 1998. [Semantic Scholar](https://www.semanticscholar.org/paper/Frontier-based-exploration-using-multiple-robots-Yamauchi/ace4428762424373c0986c80c92be632ff9523e4)
- W. Burgard, M. Moors, C. Stachniss, F. Schneider, **Coordinated multi-robot
  exploration**, IEEE Transactions on Robotics 21(3), 2005.
- R. Zlot, A. Stentz, M. B. Dias, S. Thayer, **Multi-robot exploration
  controlled by a market economy**, ICRA 2002, s. 3016–3023.
- K. M. Wurm, C. Stachniss, W. Burgard, **Coordinated multi-robot exploration
  using a segmentation of the environment**, IROS 2008.
  [PDF](http://www2.informatik.uni-freiburg.de/~stachnis/pdf/wurm08iros.pdf)
- A. Bautin, O. Simonin, F. Charpillet, **MinPos: A novel frontier allocation
  algorithm for multi-robot exploration**, ICIRA 2012.
  [Springer](https://link.springer.com/chapter/10.1007/978-3-642-33515-0_49)
- J. Faigl, M. Kulich, L. Přeučil, **Goal assignment using distance cost in
  multi-robot exploration**, IROS 2012.
  [PDF](https://comrob.fel.cvut.cz/papers/iros12mre.pdf)
- M. Keidar, G. A. Kaminka, **Efficient frontier detection for robot
  exploration**, IJRR 33(2), 2014.
  [Semantic Scholar](https://www.semanticscholar.org/paper/Efficient-frontier-detection-for-robot-exploration-Keidar-Kaminka/422e642161a7005f3ad9519aba8cafa2aabc07b9)
- H. Umari, S. Mukhopadhyay, **Autonomous robotic exploration based on multiple
  rapidly-exploring randomized trees**, IROS 2017.
- B. Zhou, Y. Zhang, X. Chen, S. Shen, **FUEL: Fast UAV exploration using
  incremental frontier structure and hierarchical planning**, RA-L 2021.
  [arXiv:2010.11561](https://arxiv.org/abs/2010.11561)
- B. Zhou, H. Xu, S. Shen, **RACER: Rapid collaborative exploration with a
  decentralized multi-UAV system**, T-RO 39(3), 2023.
  [arXiv:2209.08533](https://arxiv.org/abs/2209.08533)
- J. Hörner, **Map-merging for multi-robot system**, bakalářská práce, MFF UK,
  2016; balíček [multirobot_map_merge](https://index.ros.org/p/multirobot_map_merge/),
  [m-explore](https://github.com/hrnr/m-explore).
- L. Wang, A. D. Ames, M. Egerstedt, **Safety barrier certificates for
  collisions-free multirobot systems**, T-RO 33(3), 2017, s. 661–674.
  [ACM DL](https://dl.acm.org/doi/10.1109/TRO.2017.2659727)
- D. Zhou, Z. Wang, S. Bandyopadhyay, M. Schwager, **Fast, on-line collision
  avoidance for dynamic vehicles using buffered Voronoi cells**, RA-L 2(2),
  2017, s. 1047–1054. [PDF](https://msl.stanford.edu/papers/zhou_fast_2017.pdf)
- J. Grover, C. Liu, K. Sycara, **Deadlock analysis and resolution for
  multi-robot systems**, WAFR 2020 ([arXiv:1911.09146](https://arxiv.org/abs/1911.09146));
  **The before, during, and after of multi-robot deadlock**, IJRR 2023
  ([arXiv:2206.01781](https://arxiv.org/abs/2206.01781)).
- Y. Xu et al., **Explore-Bench: Data sets, metrics and evaluations for
  frontier-based and deep-reinforcement-learning-based autonomous
  exploration**, ICRA 2022. [arXiv:2202.11931](https://arxiv.org/abs/2202.11931)
- C. Wang et al., **Multi-robot system for cooperative exploration in unknown
  environments: A survey**, 2025. [arXiv:2503.07278](https://arxiv.org/abs/2503.07278)

ORCA je v [05 – Zdroje](./05_zdroje.md) jako C1, EGO-Swarm jako C4.

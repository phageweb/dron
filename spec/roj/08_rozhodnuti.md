# 08 – Rozhodnutí

Odpovědi na otevřené otázky z dokumentů 01–06, na jednom místě. Každé
rozhodnutí má důvod a stav; co je označené **otevřené**, čeká na měření nebo na
volbu, kterou nemá smysl dělat od stolu.

Pořadí je podle dokumentů, ne podle důležitosti. Nejdůležitější je R19, které
žádná z otázek nepoložila — vyšlo najevo při jejich procházení.

## R19 — kde přesně je šev mezi vrstvami

**Rozhodnuto.** Koordinátor **neposílá `cmd_vel`**. Posílá dvě věci:

1. `explore/target` (`PointStamped`) — kam má agent zamířit,
2. `swarm/constraint` — omezení rychlosti nebo příkaz zastavit.

Mezi autonomii agenta a `/ap/cmd_vel` přibude malý uzel **arbiter**, který
nominální povel ořeže podle omezení a při mlčení koordinátoru ořezává
konzervativně.

Důvod je věcný nález v kódu. `simple_indoor_autonomy` už dnes odebírá
`explore/target` (`simple_indoor_autonomy.py:162, 235`) a `frontier_explorer`
ho publikuje — šev na správném místě tedy existuje. Kdyby koordinátor psal
`cmd_vel` přímo, obešel by ten uzel a s ním i G4 a G5 z
[02](./02_vrstva_drona.md): vyhýbání zdi, odmítání podlahy, přistání na
baterii. To jsou právě ty garance, kvůli kterým se vrstvy dělí.

**Co je na tom slabé, a je to potřeba říct dopředu:** cíl dnes neurčuje, kam se
letí. Ovlivňuje jen to, **kterým směrem se agent otočí**, až zastaví u zdi, a
jen když je `enable_exploring` zapnuté; `target_timeout_s` je 3 s. Autorita
koordinátoru je tedy zpočátku slabá — směr zatáčky a brzda. Jestli to na
rozdělení práce nestačí, dalším krokem je skutečná poziční reference v režimu
GUIDED, ne obcházení arbitru.

### R19a — omezení jako poloroviny (výchozí od 2026-10-05)

**Zavedeno 2026-10-03 jako volitelný režim, výchozí od 5. 10. 2026**
(`safety_filter`, `filter_mode` i `check_swarm_mapping.sh`; skalární R19
zůstává jako `scalar`). Skalární
limit umí jen brzdit, a dva agenti proti sobě proto oba stojí
([rešerše 06 §4](../../reserseRoju/06_algoritmy_koordinatora.md)). V režimu
`safety_filter:=vector` (koordinátor) a `filter_mode:=vector` (arbiter) posílá
koordinátor navíc `/v<i>/swarm/barrier` (`Float32MultiArray`, trojice
a_x, a_y, b na souseda, v rámci těla agenta): poloroviny povolených rychlostí
z recipročního CBF pro jednoduchý integrátor. Arbiter najde rychlost
nejbližší povelu autonomie, která v nich leží, s pravidlem pravé ruky
(`velocity_barrier.py`).

Duch R19 platí: směr dál určuje autonomie, arbiter **vpřed nikdy nezrychlí**
a přidat smí jen boční nebo zpětný pohyb do `lateral_max_mps` (odstoupení
zevnitř `d_safe` do 0,25 m/s). Ten směr autonomie nekontrolovala proti
zdem, a to byl důvod, proč režim nebyl výchozí. Od 5. 10. ho kontroluje
arbiter: z vlastního 360° scanu agenta udělá polorovinu z každé zdi do
1 m (`velocity_barrier.wall_half_planes`, 24 výsečí, odstup 0,30 m od
středu) a polorovinu, kterou by porušil už sám povel autonomie, povolí na
ten povel. Zeď tedy zastaví jen to, co přidal filtr, nikdy to, co zvolila
autonomie. S čerstvým scanem je `lateral_max_mps` 0,25 m/s, bez něj
0,15 m/s bez kontroly zdí jako dřív. Zastaralé poloroviny
(> `constraint_timeout_s`) se ignorují a platí skalární limit s fallbackem.

Proč výchozí (5. 10. 2026, 48 letů ve třech světech, varianty
`Gus/Guv/Gis/Giv` v `scripts/swarm_batch.py`): ve 21 párech „stejný svět,
stejný seed, jiný filtr“ byl vektor rychlejší k T90 ohrady v 10, pomalejší
v 8 a ve 3 stejně (medián −2 s), tedy **stejně rychlý**. Nejmenší odstup
dvojice ale držel na `d_safe` (0,77–0,78 m), skalár v každé dávce pod ním
(0,75–0,76 m). Dvě přiblížení ke zdi pod 0,25 m ve vektorových letech
(0,11 m u pilíře, 0,20 m na rohu ohrady) nastala se sousedy dál než 1,3 m,
kde filtr povel nemění; stejné přiblížení (0,10 m) měl i skalární let
z 4. 10. Jde o chybu autonomie, ne filtru (backlog).

Před letem na skutečném dronu zbývá ověřit boční pohyb na hardwaru: v SITL
je `linear.y` jen otočený (`to_ap_body_y`), skutečný regulátor a LD06
se mohou chovat jinak.

Při zavádění se našla chyba na hranici s ArduPilotem: `AP_DDS` čte
`linear.y` v `base_link` jako **doprava** (FRD), ne doleva, jak píše jeho
komentář (`AP_DDS_ExternalControl.cpp`). Arbiter proto y otáčí
(`arbiter.to_ap_body_y`). Bez toho se pravá ruka měnila v levou a odstoupení
mířilo k sousedovi: nejmenší odstup 0,20 m.

Agent pod bariérou nikdy nestojí, takže „držený 2 s“ z R5a se počítá jako
„pomalejší než `stalled_mps` vedle souseda“.

## Dokument 01 — zadání

### R1 — na kterém draku

**Rozhodnuto 19. 9. 2026: Pavo20 Pro 4S.** Zapsáno v
`workflow/decisions.md`, „The Swarm Experiment Flies the Pavo20".

Důvody: menší kolizní obálka (dosah špičky 0,06107 m proti 0,08335 m, tedy
geometrické minimum dvojice 0,1221 m proti 0,1667 m), a v místnosti 8 × 6 m se
ten rozdíl utratí třikrát; je to drak, který kusovník skutečně kupuje; a do
ohrady se dostal hlouběji.

Co z toho plyne pro zbytek složky: **všechna čísla závislá na draku jsou
Pavo20**. Baseline se měří jen pro něj (M0 se zkracuje ze šesti běhů na tři),
`d_safe` se počítá z 0,06107 m a rozhodnutí z 10. 9. o fyzické stavbě se tím
neotevírá.

### R2 — sekvenční vzlet

**Rozhodnuto: sekvenčně**, v pevném pořadí v1, v2, v3, a chyba kteréhokoli
vzletu ruší ty další. Současný vzlet tří strojů nic neměří a přidává jediný
okamžik, kdy jsou všichni tři nízko, blízko a v zemním efektu.

### R3 — rozpočet 130 s

**Rozhodnuto: 130 s zůstává**, protože srovnatelnost s baseline je celý smysl
úlohy. Vedle toho se **měří čas do dosažení baseline** — to je číslo, které roj
slibuje. Dvě metriky, jeden let.

**Oprava 2026-10-03:** `check_swarm_mapping.sh` čekal na vzlet pevných 90 s,
ačkoli agenti jsou ve vzduchu asi za 10 s, takže všechna čísla roje do
tohoto dne jsou po zhruba 220 s letu, ne po 130 s. Nově běží 130 s od chvíle,
kdy je ve vzduchu poslední agent. Baseline jednoho dronu měří 130 s od
spuštění autonomie, tedy i se svým vzletem (asi 10 s) – roj má tak o vzlet
víc, ne o 90 s. Časy T50/T80/T90 (`replay_swarm_run.py`) se počítají od
téhož okamžiku a co přesáhne 130 s, je „nedosaženo“.

## Dokument 02 — vrstva dronu

### R4 — kdo mapuje

**Rozhodnuto: varianta A** — mapuje každý agent, koordinátor slučuje. Dnešní
`occupancy_mapper` to umí bez úprav (témata jsou parametry), pásmo je zlomek a
agent při výpadku spojení mapuje dál. Podrobnosti v [06](./06_slozena_mapa.md).

### R5 — kde se vybírá cíl

**Rozhodnuto: v koordinátoru.** `frontier_explorer` se na agentovi **nespouští**;
jeho cenovou funkci (`lookahead_m 1.4`, `target_hold_m 1.0`,
`turn_cost_m_per_rad 1.25`) přebírá přidělovací část koordinátoru. Tři kopie
téhož uzlu nad toutéž mapou by vybraly týž cíl — to je přesně kolize, kterou má
roj řešit.

Uzel se nemaže. Je to baseline pro jeden dron a musí dál fungovat.

### R5a — agent, na kterého nezbyl otvor

**Rozhodnuto 2026-10-03: pošle se pryč od ostatních.** R5 dává jeden otvor
jednomu agentovi a ve sloučené mapě bývá dosažitelný otvor obvykle jeden, takže
dva ze tří agentů létali bez cíle podle reaktivního pravidla. Sletěli se do
jednoho rohu a navzájem se drželi na hranici stopu: za 130 s uletěli 4 až 14 m
a místnost vyšla na 85 %, proti 92 % v letech, kdy se náhodou rozptýlili.

Agent bez otvoru dostane dosažitelnou buňku volné podlahy co nejdál od ostatních
agentů a od už rozdaných cílů — ale jen do vzdálenosti, kde bezpečnostní filtr
dvojici přestane brzdit (`d_safe` + 2 × stopping room, při 0,5 m/s asi 2,0 m).
Dál už odstup nic nepřinese, jen delší let; z dost vzdálených buněk vyhrává ta
nejbližší po trase. Agenti bez otvoru se obsluhují postupně a každá volba se
pro dalšího počítá jako obsazená. Kód: `assignment.spread_targets`.

Zamítnuto: **sdílet otvor**, když je otvorů míň než agentů. Poslalo by to dva
stroje na totéž místo, což je kolize, kvůli které R5 vzniklo.

### R5b — jednotkou přidělení je pozorovací bod, ne otvor

**Rozhodnuto 2026-10-03**, podle rešerší
[06](../../reserseRoju/06_algoritmy_koordinatora.md) a
[07](../../reserseRoju/07_koordinator_revizni_reserse.md). Otvor se rozdělí na
pozorovací body aspoň `viewpoint_spacing_m` (1,0 m) od sebe; každý je
dosažitelná buňka otvoru mimo pás u zdi a nese odhad, co by z něj bylo vidět
(paprsky přes známou podlahu, nejvýš `unknown_depth_m` do neznáma, zeď je
zastaví). Body s menším odhadem než `min_gain_cells` se zahodí – to jsou
proužky, které v mapě nechává líc zdi. Dlouhý otvor tak dá práci dvěma
agentům; R5a zůstává pro agenta, na kterého ani tak nic nezbude.

Mění to R5a v jednom bodě: dva agenti **smí** dostat dva různé body téhož
otvoru. Stejný bod dvakrát dál ne. Že dva body neukazují totéž, hlídá
alokátor `utility`; ostatní to nevidí.

Cíl, který dron dostane, je **táž buňka, ke které se počítala cena** (dřív
těžiště otvoru, které u zalomeného otvoru padalo do zdi), cena otočení počítá
se skutečným yaw a odchod od minulého cíle stojí `switch_cost_m` (1,0 m).

Způsob přidělení je parametr `allocator`, aby šly metody z literatury
porovnat nad stejnými body:

| `allocator` | Princip | Zdroj |
| --- | --- | --- |
| `clusters` | jeden otvor jednomu agentovi, nejlevnější dvojice první (R5 tak, jak bylo) | — |
| `iterative` | totéž nad pozorovacími body | Faigl et al. 2012 |
| `hungarian` | nejmenší součet ceny − váha × zisk; agent může čekat | Faigl et al. 2012 |
| `minpos` | agent jde tam, kde je mezi agenty nejvýš v pořadí | Bautin et al. 2012 |
| `utility` (výchozí) | Burgardova sleva: co vidí jeden, má pro dalšího menší cenu | Burgard et al. 2005, 07 §4.2 |

Výchozí je `utility`, protože jako jediný řeší překryv pozorování. První lety
(dva na variantu) ho ukázaly mírně za `iterative`; **párové lety z 5. 10.
2026 to obrátily a výchozí zůstává `utility`**: ve 21 párech „stejný svět,
stejný seed, stejný filtr“ byl `utility` k T90 ohrady rychlejší ve 14,
pomalejší ve 4 a ve 3 stejně (medián −9 s, znaménkový test p ≈ 0,03).
`iterative` měl navíc nejpomalejší lety dávek (113 a 125 s ve světě
s úzkými dveřmi). Zamítnuto
zatím: aukce/CBBA (při centrálním uzlu nic nepřidá), CVRP/RACER a C²
(vyplatí se až s více místnostmi), FAME, Cross-rank, SIPP/CBS a vektorový
filtr – každý mění jinou vrstvu a měří se zvlášť (07 §11.2).

Rezervace průchodů (`passages.py`, jeden agent v místě, kde se dva
nemohou minout; 07 §4.3) je **od 5. 10. 2026 jako výchozí vypnutá**
(`reserve_passages`). Ve 47 letech nebyli dva agenti u jednoho úzkého
místa současně ani s ní, ani bez ní, a v jednom letu držitel, který
uvnitř přeskakoval mezi cíli, nechal ostatní dva většinu letu bez cíle.
Zapnout znovu až se ztrátou rezervace pro nepostupujícího držitele
a detektorem, který neslévá dveře s chodbou za nimi
([08 §7](../../reserseRoju/08_pruvodce_algoritmy.md)).

Měří se čas do 50/80/90 % podlahy (místnost a ohrada zvlášť,
`scripts/replay_swarm_run.py` → `time_to_coverage.json`), vedle pokrytí po
130 s (R3).

### R6 — `corridor_margin_m 0.25`

**Rozhodnuto: beze změny.** Je to parametr pro **zdi**, ne pro sousedy; odstup
mezi stroji řeší `d_safe` a arbiter. Kdyby se zvětšil kvůli roji, započítá se
tatáž rezerva dvakrát a koridor 0,667 m se zúží tam, kde to nikdo nechtěl.
Tentýž konstantní výraz je navíc v `check_room_coverage.sh:431` součástí
měřicího nástroje — změna by pohnula metrikou, se kterou se porovnává.

## Dokument 03 — vrstva roje

### R7 — hodiny

**Rozhodnuto: roj používá výhradně časové značky z `pose/filtered`.** Žádné
`use_sim_time`, žádné míchání s časem senzorů. Důvod je popsaný v
`sitl_gazebo.launch.py`: Gazebo tu `/clock` nepublikuje, AP_DDS ho odebírá a
nedostane, a obě osy se rozcházejí o desítky let. Dokud běží všichni tři agenti
na téže UTC z ArduPilotu, je porovnání stáří stavů platné.

Oprava `/clock` zůstává v backlogu; tohle rozhodnutí na ní nestojí.

### R8 — `d_safe` vodorovně, nebo ve 3D

**Rozhodnuto: měří se 3D vzdálenost, létá se v jedné výšce.** 3D je fyzikálně
správná veličina a stojí jednu odmocninu. Jedna výška je potřeba kvůli mapě —
2D lidar musí řezat tutéž rovinu, jinak se mřížky neslučují. Oddělené výšky by
sice byly bezpečnější, ale experiment by přestal dokazovat to, kvůli čemu je.

### R9 — kdy je mapování hotové

**Rozhodnuto: dvě podmínky, obě musí platit.** Žádný frontier shluk nad
`min_frontier_cells` (dnes 4) po dobu 10 s **a** uplynulý čas menší než rozpočet.
Samotné „nezbyly frontiery" je křehké — stačí šum na okraji mřížky, aby se
mapování nikdy neukončilo, nebo naopak jedna zaokrouhlená buňka, aby skončilo
předčasně.

## Dokument 04 — rozhraní

### R10 — vlastní zprávy

**Rozhodnuto: zatím `std_msgs/String` s JSONem** pro `/swarm/assignment` a
`/swarm/safety`. Obě jsou diagnostika, ne řízení; typovaný balíček znamená zásah
do buildu uprostřed milníku. Jakmile je bude číst druhý konzument nebo
regresní test, vznikne `openipc_swarm_msgs`.

`/v<i>/explore/target` a `/v<i>/swarm/constraint` typované jsou —
`PointStamped` (už existuje) a nejjednodušší možná zpráva pro omezení.

### R11 — QoS

**Rozhodnuto:** stavy a senzory `sensor_data` (best effort, keep last 1), jak to
dnes dělají demo uzly; povely a omezení reliable, keep last 1; mapy transient
local, aby pozdě spuštěný slučovač neměl prázdno. QoS AP_DDS témat se nemění —
není naše.

A pravidlo z rešerše, které platí nad tím: **QoS není watchdog.** Reliable
neznamená doručeno včas, proto stáří stavu a `GUID_TIMEOUT`.

### R12 — odebírá koordinátor scany

**Rozhodnuto: ne.** Plyne z R4. Koordinátor vidí mapy a polohy, nikoli syrové
lidary.

## Dokument 05 — infrastruktura

### R13 — generovat model, nebo přepsat plugin v `<include>`

**Rozhodnuto: generovat.** Ověřeno ve zdrojáku pluginu: `fdm_port_in` se čte
výhradně ze SDF (`external/ardupilot_gazebo/src/ArduPilotPlugin.cc:1272`), žádná
proměnná prostředí ani argument neexistují, a `<include>` neumí přepsat
parametr pluginu uvnitř vloženého modelu. Tři ručně udržované kopie by se
rozešly.

Generátor tedy vyrobí `openipc_cinewhoop_v1..v3` (různé jméno modelu, různý
`fdm_port_in`) do adresáře v `build/`, který se přidá do
`GZ_SIM_RESOURCE_PATH` — stejná mechanika, jakou už používá `OPENIPC_AIRFRAME`.

Rozsah práce je měřitelný: prefix tématu `/openipc_cinewhoop/` je v kódu a
skriptech na 77 místech, z toho 34 ve skriptech, a cesta ke gz modelu na 22.

### R14 — jedno Gazebo, nebo tři

**Rozhodnuto: jedno.** Je to jediné uspořádání, ve kterém existuje skutečná
vzdálenost dvojice, a ta je kritérium K1. Tři propojené simulace by ji musely
umět taky, a to je víc práce pro horší výsledek.

### R15 — startovní pozice

**Změněno 2026-10-03: jedno místo startu, agenti vedle sebe.** Roj má
vzlétat z jednoho místa, jako ze stolu ve skutečné místnosti, a rozptýlit se
sám. Původní rozestup 2 m mu odstup dal zadarmo, ještě než cokoli udělal.

| Agent | Pozice | Nejbližší stěna | Odstup od souseda |
| --- | --- | ---: | ---: |
| v1 | (0,5; −0,8; 0,035) | 1,11 m (roh ohrady) | 0,80 m |
| v2 | (0,5; 0,0; 0,035) | 1,05 m | 0,80 m |
| v3 | (0,5; +0,8; 0,035) | 1,05 m | 0,80 m |

0,8 m je těsně nad `d_safe` (0,78 m při 0,5 m/s) a pod hranicí stopu
(1,41 m): po vzletu stojí všichni ve stopce a ven je dostane jen ustupování
směrem od ostatních (R5a, `safety.escape_limit`). Blíž než `d_safe` startovat
nemají — tam se smí jen plazit k hranici kontaktu. Musí být celé buňky mapy
(0,10 m), jinak je `frames.offset_in_cells` odmítne.

`x = 0,5` a ne 0 drží všechny přes metr od stěny ohrady.

Původní rozhodnutí: tři pozice (0,5; −2 / 0 / +2) po 2 m, každá aspoň metr
od stěny.

Baseline jednoho dronu si ponechá svůj dnešní start (0, 0, 0,035).

## Dokument 06 — mapa

### R16 — velikost mřížky

**Rozhodnuto: 20 × 20 m při 0,10 m zůstává.** Místnost je 8 × 6 m, takže
prostor není problém.

Problém je jinde a otázka ho minula: mřížka je **vystředěná na počátek
frame** (`occupancy_mapper.py:94-98`), a tím počátkem je origin EKF daného
agenta. Mají-li tři agenti tři různé originy, jsou jejich mřížky vystředěné na
tři různá fyzická místa, přestože se všechny jmenují `map` — a slučování buňka
po buňce je pak nesmysl. Tohle je totéž, co [04 §3](./04_rozhrani.md) uvádí jako
nevyřešený předpoklad, jen s konkrétním důsledkem. **Změřit v M2, ne
předpokládat.**

### R17 — jak se pozná, že se mapy rozešly

**Rozhodnuto:** podíl konfliktních buněk (jeden agent volno, druhý obsazeno) se
počítá při každém sloučení a loguje. Práh se zapíše před prvním během M5. Je to
zadarmo — konflikty se stejně musí řešit — a je to jediná metrika kvality
lokalizace, kterou tenhle experiment dostane bez ground truth.

### R18 — posílat složenou mapu zpět agentům

**Rozhodnuto: ne.** Agenti dostávají hotové cíle (R5) a nic jiného s cizí mapou
nedělají. Méně kódu, méně pásma, a žádná zpětná vazba, ve které by se dala
schovat nestabilita.

## Co zůstalo otevřené

| # | Otázka | Čím se zavře |
| --- | --- | --- |
| — | `d_safe` jako číslo | měřením v M1 ([02 §3](./02_vrstva_drona.md)) |
| — | práh konfliktních buněk | zápisem před M5 |
| — | vejde se tři instance do reálného času | měřením RTF v M3 |

Nic z toho neblokuje M0.

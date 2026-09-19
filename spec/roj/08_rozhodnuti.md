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

**Rozhodnuto**, z geometrie světa (vnitřek x ∈ [−4, 4], y ∈ [−3, 3]; ohrada
x ∈ [−3,5, −0,55], y ∈ [−0,45, 2,45]; pilíř 0,4 × 0,4 v (2,0, −1,5)):

| Agent | Pozice | Nejbližší stěna | Odstup od souseda |
| --- | --- | ---: | ---: |
| v1 | (0,5; −2,0; 0,035) | 1,00 m | 2,00 m |
| v2 | (0,5; 0,0; 0,035) | 1,05 m | 2,00 m |
| v3 | (0,5; +2,0; 0,035) | 1,00 m | 2,00 m |

`x = 0,5` a ne 0, protože na ose y = 2 je vnější stěna ohrady ve vzdálenosti
0,55 m a agent by startoval uvnitř vlastního prahu zastavení (0,8 m).

Nesymetrie zůstává a je vědomá: k nejbližšímu rohu dveří ohrady je to
1,14 m z v2, 1,87 m z v1 a 2,67 m z v3.
Kdyby přidělení cílů fungovalo jen díky tomu, kdo stál blíž, pozná se to na
překryvu práce.

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
| R16 | shodují se originy EKF tří instancí? | měřením proti ground truth v M2 |
| — | `d_safe` jako číslo | měřením v M1 ([02 §3](./02_vrstva_drona.md)) |
| — | práh konfliktních buněk | zápisem před M5 |
| — | vejde se tři instance do reálného času | měřením RTF v M3 |

Nic z toho neblokuje M0.

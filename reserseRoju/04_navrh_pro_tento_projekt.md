# Návrh rojového řízení pro tento projekt

Tato kapitola je **technické doporučení odvozené z rešerše**, ne tvrzení, že
už je roj v repozitáři implementovaný. Vychází ze stavu projektu a lokálního
checkoutu ArduPilotu `8b9ea7004582` z 9. 9. 2026.

## 1. Cílový první scénář

První smysluplný cíl není „autonomní roj v neznámém bytě“. Je to:

> Dva a později tři shodné SITL cinewhoopy ve společném Gazebo světě vzlétnou
> sekvenčně, drží trojúhelníkovou nebo řádkovou formaci při pomalém pohybu,
> nepřekročí změřený bezpečnostní rozestup a při zastaralém stavu nebo povelu
> přejdou do předem otestovaného hold/land chování.

Tento scénář izoluje koordinaci od dosud nevyřešeného multi-robot SLAM. První
simulace může používat ground truth ve společném rámci. Další fáze postupně
přidá odhad ArduPilot EKF, drift, zpoždění, ztráty paketů a senzory.

## 2. Doporučená architektura

```text
                    +-----------------------+
                    | mission_manager       |
                    | režimy, role, cíle     |
                    +-----------+-----------+
                                |
                    +-----------v-----------+
                    | formation_generator   |
                    | nominální p/v cíle     |
                    +-----------+-----------+
                                |
          +---------------------v---------------------+
          | swarm_safety_filter                       |
          | čerstvost, geofence, párové rozestupy,    |
          | limity v/a, konflikt a proveditelnost     |
          +--------+------------------------+----------+
                   |                        |
          +--------v---------+     +--------v---------+
          | adapter v1       |     | adapter v2       |
          | map -> AP frame  |     | map -> AP frame  |
          +--------+---------+     +--------+---------+
                   |                        |
             /ap/v1/cmd_vel           /ap/v2/cmd_vel
                   |                        |
          +--------v---------+     +--------v---------+
          | ArduPilot v1     |     | ArduPilot v2     |
          | EKF + lokální    |     | EKF + lokální    |
          | kaskádní řízení  |     | kaskádní řízení  |
          +------------------+     +------------------+
```

`mission_manager` smí měnit režim pomalu. `formation_generator` dává nominální
záměr. `swarm_safety_filter` je jediný uzel, který smí z nominálního záměru
vyrobit letový příkaz. Adaptéry jsou tenké a neobsahují vlastní rozhodování.

### Proč zatím plánovač na zemi

Současný kusovník nemá na každém dronu companion computer schopný spouštět
ROS 2 plánovač. OpenIPC jednotka řeší video a zamýšlený přenos lidaru, ale není
v projektu ověřená jako výpočetní platforma pro rojový stack. Proto je první
verze nutně převážně centralizovaná.

To vytváří bezpečnostní hranici: výpadek pozemní linky nesmí znamenat pokračování
poslední rychlosti. ArduPilot Guided má parametr `GUID_TIMEOUT`; po vypršení bez
nového rychlostního/akceleračního povelu zpomalí do zastavení. Oficiální
dokumentace uvádí výchozí 3 s, ale pro malý indoor prostor se hodnota musí
odvodit z bezpečné ujeté vzdálenosti a experimentálně ověřit
([Guided Mode](https://ardupilot.org/copter/docs/ac2_guidedmode.html)). Vedle
toho se nastavuje a samostatně testuje GCS, RC, bateriový a EKF failsafe.

## 3. Identita a namespacing

Každá instance musí mít jednoznačnou identitu ve všech vrstvách:

| Vrstva | Příklad pro agenta 2 |
| --- | --- |
| logická identita | `v2` |
| ArduPilot `MAV_SYSID` | `2` |
| AP_DDS | `DDS_USE_NS=1` |
| AP topic | `/ap/v2/pose/filtered` |
| Gazebo model | `openipc_cinewhoop_v2` |
| TF prefix | `v2/` |
| swarm topic | `/swarm/agents/v2/state` |
| log / rosbag metadata | `agent_id=v2`, `mission_epoch=...` |

Lokální `external/ardupilot/libraries/AP_DDS/README.md` potvrzuje, že
`DDS_USE_NS=1` vloží do topiců a služeb segment `v<MAV_SYSID>`. `AP_DDS_Client`
také skládá unikátní XRCE client key z `MAV_SYSID`. Je to lepší základ než
ruční remap stejného `/ap` pro více instancí.

ArduPilot SITL oficiálně podporuje více vozidel pomocí `--count`,
`--auto-sysid` a `--swarm` nebo `--auto-offset-line`; viz
[Using SITL – Swarming with SITL](https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html).
Projekt ale používá vlastní Gazebo model a JSON backend, takže bude navíc nutné
parametrizovat jméno modelu, porty pluginu, počáteční pose a bridge pro každou
instanci. Samotný `--count` toto za repozitář neudělá.

## 4. Souřadné rámce

Navržený TF strom:

```text
map
├── v1/odom
│   └── v1/base_link
│       ├── v1/lidar_link
│       ├── v1/camera_link
│       └── v1/range_link
├── v2/odom
│   └── v2/base_link
└── v3/odom
    └── v3/base_link
```

- `map` je společný, pomalu korigovaný rámec roje.
- `vN/odom` je lokálně spojitý rámec daného odhadu.
- transformace `map -> vN/odom` vyjadřuje zarovnání a drift.
- každý frame senzoru má prefix agenta.
- pouze jeden proces smí být autoritou každé transformace.

Rojový koordinátor počítá jen ve `map`. Povel do AP_DDS `/cmd_vel` má
`header.frame_id="map"`, pokud jsou všechny odhady skutečně v témže ENU rámci.
Lokální zdrojový kód `AP_DDS_ExternalControl.cpp` převádí `map` z ENU na NED;
pro `base_link` provádí jinou transformaci. Prázdný nebo nesprávný frame vede k
odmítnutí povelu, proto má být součástí integračního testu.

## 5. Datové kontrakty

### Stav agenta

Jeden agregovaný stav je praktičtější než závislost koordinátoru na deseti
nízkoúrovňových topicích:

```text
AgentState
  header.stamp
  header.frame_id = "map"
  string agent_id
  uint64 mission_epoch
  pose + pose_covariance
  twist + twist_covariance
  float32 battery_remaining
  uint8 autopilot_mode
  bool armed
  bool pose_valid
  bool obstacle_sensor_valid
  duration pose_age
  duration command_age
  DynamicLimits limits
  HealthFlags health
```

Zpráva má nést čas měření a kvalitu. Koordinátor nesmí odvozovat zdraví pouze z
toho, že callback nedávno proběhl.

### Zamýšlená trajektorie

Pro první velocity verzi stačí `TwistStamped`, ale interní rozhraní se vyplatí
navrhnout pro krátký horizont:

```text
AgentIntent
  agent_id
  mission_epoch
  trajectory_version
  valid_from
  valid_until
  sequence of (time, position, velocity, acceleration, yaw)
  committed_prefix_duration
```

Verze a epocha zabrání tomu, aby restartovaný uzel přijal starou trajektorii.
`valid_until` je aplikační timeout nezávislý na DDS lifespan.

### Výstup safety filtru

Filtr má kromě povelu publikovat důvod změny:

```text
NOMINAL
LIMITED_SPEED
LIMITED_ACCELERATION
PAIRWISE_CONFLICT
STATIC_OBSTACLE
STALE_STATE
LOST_LOCALIZATION
NO_FEASIBLE_COMMAND
MISSION_EPOCH_MISMATCH
```

Bez této diagnostiky bude „dron stojí“ nerozlišitelné od závady regulace.

## 6. První algoritmus

### Nominální formace

Použít virtuální strukturu. Vedoucí virtuální pose `p_c, yaw_c` má pro každého
agenta pevný offset `r_i`:

```text
p_i,d = p_c + R_z(yaw_c) · r_i.
v_i,d = v_c + yaw_rate_c · e_z × R_z(yaw_c) · r_i.
```

Pozor na druhý člen: při otáčení formace nemají všichni členové stejnou
translační rychlost. Jeho vynechání vytvoří při yaw rotaci vlečnou chybu.

Nominální rychlost:

```text
v_i,nom = clamp(v_i,d + K_p·(p_i,d - p_i), limits_i).
```

Zrychlení mezi po sobě jdoucími povely se omezí. Skok formace se nesmí přenést
přímo do `cmd_vel`.

### Bezpečnostní filtr verze 1

Pro první implementaci doporučuji centrální predikční filtr nad body/kolizními
koulemi:

1. predikovat všechny agenty přes měřenou latenci a krátký horizont;
2. zkontrolovat statické překážky a každou dvojici;
3. omezit nominální rychlosti tak, aby neporušily `d_safe`;
4. pokud není přípustný povel, všem dotčeným agentům zadat řízené zabrzdění;
5. po přetrvávajícím konfliktu přejít do předem určených holding bodů, ne
   opakovat oscilující „uhni vlevo/uhni vpravo“.

Je jednodušší jej ověřit než okamžitě nasadit distribuovaný MPC. Po baseline
lze stejná testovací data použít k porovnání ORCA a CBF-QP.

### Rozestup jako konfigurační výsledek

`d_safe` nesmí být konstanta z literatury. Konfigurační nástroj jej sestaví z:

```text
geometrie
+ kvantil lokalizační chyby obou agentů
+ pohyb za end-to-end latenci
+ kvantil brzdné dráhy obou agentů
+ rezerva modelu a proudění.
```

Každá složka se uloží spolu s datem, firmwarem, hmotností a testovacím logem.
Při změně vrtule, hmotnosti, filtru nebo rychlostního limitu se hodnota
zneplatní.

## 7. Bezpečnostní vlastnosti na autopilotu

Rojová vrstva se nesmí stát jedinou ochranou. Každý ArduPilot musí mít před
letem samostatně ověřené:

- pre-arm check a konzistentní identitu;
- `GUID_TIMEOUT` a jeho skutečné chování pro `cmd_vel`;
- GCS failsafe a zvolenou akci;
- RC override/kill nebo bezpečný převzetí operátorem;
- battery failsafe;
- EKF failsafe při ztrátě indoor polohy;
- geofence přiměřenou místnosti;
- maximální rychlost, náklon, zrychlení a sestup;
- chování po restartu DDS agenta nebo koordinátoru.

ArduPilot podporuje BendyRuler v Guided režimu pro proximity překážky
([Object Avoidance with BendyRuler](https://ardupilot.org/copter/docs/common-oa-bendyruler.html)),
ale není to náhrada párové koordinace. Navíc současná plánovaná cesta plného
LD06 skenu vede přes OpenIPC na zem. Dokud není tentýž nebo samostatný proximity
zdroj dostupný lokálně autopilotu, nelze tvrdit, že statické vyhýbání přežije
výpadek linky.

## 8. ROS 2 a síť

### Doporučené procesy

```text
swarm_state_aggregator
mission_manager
formation_generator
swarm_safety_filter
ardupilot_agent_adapter (jedna instance na agenta)
swarm_visualizer
swarm_recorder
fault_injector (jen simulace/test)
```

Adaptér má normalizovat AP stav, hlídat čerstvost a publikovat nulový povel při
lokálně zjištěném problému. Pokud běží na témže pozemním počítači jako
koordinátor, nechrání proti smrti celého počítače; tu kryje `GUID_TIMEOUT` a
autopilot failsafe.

### QoS

- state: best effort, keep last 1–5, lifespan kratší než řídicí platnost;
- intent: reliable, keep last 1, explicitní verze a validity interval;
- mode/emergency request: reliable, ale úspěch potvrzuje až nový stav AP;
- diagnostics: reliable, větší fronta mimo kritickou smyčku;
- sensor streams: best effort; koordinátor nikdy nezpracovává starou frontu.

Pro malý počet agentů lze začít v jednom DDS domain. Už v simulaci se má měřit
discovery a provoz při 1, 2, 4 a více agentech. Pokud multicast na bezdrátové
síti selhává nebo discovery provoz roste, použít discovery server nebo router;
neměnit transport až během prvního fyzického roje.

## 9. Postup implementace a experimentů

### Fáze A – charakterizace jednoho agenta

- [ ] Zaznamenat hmotnost a geometrii konkrétní konfigurace.
- [ ] Změřit tracking error pro velocity step/ramp bez překážek.
- [ ] Změřit end-to-end latenci a její jitter.
- [ ] Změřit brzdnou dráhu pro sadu počátečních rychlostí a baterií.
- [ ] Ověřit `GUID_TIMEOUT`, GCS, battery a EKF failsafe v SITL.
- [ ] Opakovat relevantní testy na jednom reálném stroji v ochranném prostoru.

Výstup: verze `DynamicLimits` a výpočet počátečního `d_safe`.

### Fáze B – multi-instance infrastruktura bez letu

- [ ] Dvě SITL instance mají unikátní `MAV_SYSID`, porty a DDS namespace.
- [ ] Dva Gazebo modely mají unikátní entity, sensory a TF frames.
- [ ] Koordinátor nikdy nezamění stav a povel mezi agenty.
- [ ] Restart jedné instance nezmění identitu druhé.
- [ ] Rosbag obsahuje mission epoch, agent ID a synchronizovaný čas.

### Fáze C – oddělené vzlety a hold

- [ ] Sekvenční arm a vzlet; chyba jednoho zruší další vzlety.
- [ ] Každý stroj drží vlastní bod bez aktivní formace.
- [ ] Vstříknutá ztráta povelu vede k očekávanému zastavení/režimu.
- [ ] Vstříknutá ztráta pose vede k hold/land podle scénáře.

### Fáze D – formace v simulaci

- [ ] Pomalu se pohybující řada, potom trojúhelník.
- [ ] Rotace virtuální struktury se správnou tečnou rychlostí.
- [ ] Vstup jednoho agenta s horším trackingem.
- [ ] Latence, jitter, drop a out-of-order stavové zprávy.
- [ ] Dočasné rozpojení grafu a návrat bez automatického pokračování staré mise.
- [ ] Náhodné počáteční stavy v dávce opakování bez kolize.

### Fáze E – statické překážky a průchod

- [ ] Jedna široká překážka bez změny topologie.
- [ ] Průchod, kterým formace projde jen po změně tvaru.
- [ ] Deadlock detekce a návrat do holding bodů.
- [ ] Nakloněný 2D lidar a odmítání podlahy podle existující specifikace.

### Fáze F – dva fyzické stroje

- [ ] Nejprve motory bez vrtulí a kontrola směrování povelů.
- [ ] Samostatný let každého kusu se shodnými acceptance testy.
- [ ] Oddělené výšky/oblasti, jeden aktivní a druhý pouze sleduje.
- [ ] Dva současné hold body daleko nad `d_safe`.
- [ ] Pomalé přiblížení k bezpečnostní hranici, nikoli k fyzické kolizi.
- [ ] Až poté pohyb formace v síti/kleci s operátorem a okamžitým převzetím.

## 10. Metriky, bez kterých „funguje“ nic neznamená

| Oblast | Metrika |
| --- | --- |
| tracking | RMS a maximum chyby polohy/rychlosti na agenta |
| formace | RMS a maximum chyby každé aktivní hrany |
| bezpečnost | minimální skutečná vzdálenost a rezerva vůči `d_safe` |
| síť | latence p50/p95/p99, jitter, drop, out-of-order |
| koordinace | počet zásahů safety filtru a doba v omezeném režimu |
| robustnost | úspěšnost scénářů podle typu vstříknuté poruchy |
| energie | Wh/min nebo pokles baterie na agenta a misi |
| škálování | CPU, paměť a síť pro 1/2/4/N agentů |
| zotavení | čas od chyby do bezpečného stavu |

Přijímací meze se mají zapsat před testem. Pro bezpečnostní metriku je přijatelné
minimum „nikdy pod `d_safe`“, nikoli dobrý průměr s několika kolizemi.

## 11. Testovací matice

Každý algoritmus má projít alespoň těmito osami:

| Osa | Varianty |
| --- | --- |
| počet agentů | 1, 2, 3, potom 4+ |
| hmotnost | nominální, lehčí, těžší |
| baterie/tah | nominální, snížená autorita |
| stavová latence | nulová, konstantní, proměnná |
| ztráty | žádné, náhodné, burst |
| lokalizace | ground truth, šum, bias, drift, výpadek |
| okolí | volné, stěna, dveře, slepý roh |
| topologie | úplná, řetěz, dočasně rozpojená |
| porucha | agent stop, restart, stará epocha, chybný frame |

Scénáře musí používat deterministický seed a ukládat jej. Náhodný test bez
reprodukce je demonstrace, ne regresní test.

## 12. Co zatím neimplementovat

- přímé řízení motorů přes ROS 2/Wi-Fi;
- decentralizovaný multi-robot SLAM současně s prvním řízením formace;
- MARL bez bezpečnostního klasického baseline;
- dynamický leader election ve stejné fázi jako základní leader–follower;
- jeden společný emergency povel bez definice, co udělá ve vzduchu každý člen;
- automatický návrat do `ACTIVE` po odeznění závažného failsafe;
- předpoklad, že lidar vidí každý sousední dron za všech postojů a výšek.

## 13. Kritická otevřená rozhodnutí

Před fyzickým rojem musí být písemně uzavřeno:

1. Jaký zdroj poskytuje společnou indoor polohu a jaká je jeho změřená chyba?
2. Kudy jde řídicí linka každého agenta a co přesně se stane při jejím výpadku?
3. Má každý autopilot lokální obstacle data i bez pozemního počítače?
4. Jak operátor nezávisle převezme nebo ukončí let jednoho konkrétního agenta?
5. Jaké jsou fyzicky změřené rozměry ducts a výsledný kolizní poloměr?
6. Jak se oddělí rádiové kanály řízení, videa, lidaru a ROS/DDS provozu?
7. Je cílem homogenní roj, nebo těžký mapovací leader a lehcí followers?

Dokud nejsou zodpovězeny body 1–4, je správným cílem multi-agent SITL, ne
současný autonomní let více fyzických strojů.

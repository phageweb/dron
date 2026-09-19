# Teorie řízení jednoho malého kvadrokoptérového dronu

Rojový algoritmus předpokládá, že každý agent umí spolehlivě sledovat zadanou
rychlost nebo trajektorii. Pokud jeden dron osciluje, driftuje nebo nezná svou
polohu ve společném rámci, žádný „chytrý“ algoritmus roje to nevyřeší. Tato
kapitola proto začíná fyzikou jednoho stroje a končí rozhraním, které má dostat
rojová vrstva.

## 1. Stav, vstupy a souřadné soustavy

Zvolme světový rámec `W` se svislou osou `z` nahoru a tělový rámec `B` podle
REP 103: `x` dopředu, `y` doleva, `z` nahoru. Stav tuhého tělesa lze zapsat

```text
x = (p, v, R, omega)
```

kde:

- `p ∈ R³` je poloha těžiště ve světě;
- `v ∈ R³` je rychlost ve světě;
- `R ∈ SO(3)` otáčí vektor z tělového do světového rámce;
- `omega ∈ R³` je úhlová rychlost v tělovém rámci.

Čtyři fyzické vstupy jsou tahy rotorů `f₁ … f₄`, prakticky řízené otáčkami
motorů. V běžném pracovním rozsahu se používá aproximace

```text
f_i = k_f · Omega_i²
q_i = s_i · k_m · Omega_i²,
```

kde `Omega_i` je rychlost rotoru, `q_i` jeho reakční moment a `s_i ∈ {-1,+1}`
závisí na směru otáčení. Koeficienty nejsou univerzální konstanty vrtule; mění
se s napětím, prouděním, ductem a pracovním bodem.

## 2. Nelineární model tuhého tělesa

Při zanedbání pružnosti rámu a detailní aerodynamiky:

```text
p_dot       = v
m · v_dot   = (0, 0, -m·g) + R · (0, 0, f) + F_drag + F_dist
R_dot       = R · hat(omega)
J·omega_dot = tau - omega × (J·omega) + tau_dist
```

`f = Σf_i` je celkový tah, `J` momentová matice setrvačnosti a `hat(omega)` je
antisymetrická matice, pro kterou `hat(omega)·a = omega × a`.

Kvadrokoptéra má šest stupňů volnosti, ale jen čtyři nezávislé vstupy
`(f, tau_x, tau_y, tau_z)`. Je tedy **podaktuovaná**. Nemůže se libovolně
naklonit a současně zvolit nezávislý směr tahu; horizontální pohyb vytváří
nakloněním celého těla.

### Hoverová linearizace

V malém náklonu kolem visu je možné přibližně psát

```text
x_ddot ≈  g · theta
y_ddot ≈ -g · phi
z_ddot ≈ (f - m·g) / m,
```

kde `phi` je roll a `theta` pitch, znaménka závisejí na přesné konvenci rámce.
Tato linearizace vysvětluje kaskádu poloha → rychlost → požadované zrychlení →
náklon. Neplatí při velkých úhlech, saturaci tahu a agresivních manévrech.

## 3. Control allocation: z tahu a momentů na motory

Řídicí algoritmus obvykle nejdřív požaduje výsledný vektor

```text
u = (f, tau_x, tau_y, tau_z),
```

který mixer převede na čtyři `Omega_i²`:

```text
u = B · [Omega_1², Omega_2², Omega_3², Omega_4²]^T.
```

Matice `B` obsahuje `k_f`, `k_m`, ramena motorů a jejich skutečnou polohu a
směr otáčení. Pro quad X není bezpečné opsat anonymní matici z internetu:
číslování motorů a znaménka se mezi firmwarem, SDF pluginem a schématem rámu
liší. Tento repozitář už mapování ArduPilot ↔ Gazebo testuje; totéž musí platit
pro každý další model.

Mixer musí řešit saturaci. Pokud požadavek současně chce plný tah a velký roll,
neexistuje kombinace, která obojí splní. Řídicí systém proto prioritizuje osy,
omezuje integrátory a hlásí saturaci. Bez toho vzniká wind-up: integrátor během
nedosažitelného povelu roste a po uvolnění způsobí velký překmit.

## 4. Kaskádní regulace

Praktické autopiloty používají vnořené smyčky. Každá vnější smyčka předává
referenci rychlejší vnitřní smyčce:

```text
trajektorie p_d(t), v_d(t), a_d(t), yaw_d(t)
                    |
                    v
          regulace polohy / rychlosti
                    |
       požadovaný tah a orientace R_d
                    |
                    v
             regulace orientace
                    |
         požadované úhlové rychlosti
                    |
                    v
          regulace úhlové rychlosti
                    |
                    v
            mixer a ESC / motory
```

Vnitřní smyčka musí být rychlejší než vnější; jinak vnější regulátor předpokládá
okamžitou reakci, která ve skutečnosti nepřijde, a smyčky se mohou rozkmitat.
Konkrétní frekvence se nemá určit podle třídy 3", ale podle IMU, filtrů,
procesoru, motorové časové konstanty a změřených zpoždění.

### 4.1 Úhlová rychlost

Pro jednu osu je základ PID/FF zákon

```text
e_omega = omega_d - omega
tau_cmd = K_ff·omega_d + K_p·e_omega
          + K_i·integral(e_omega dt) + K_d·d(e_omega)/dt.
```

- `P` dává okamžitou tuhost;
- `I` odstraňuje stálou chybu od nesymetrie, těžiště nebo tahu;
- `D` tlumí rychlou změnu, ale zesiluje šum, a proto vyžaduje filtraci;
- feed-forward vytváří předvídaný moment dřív, než vznikne chyba.

U malého 3" rámu jsou vlastní frekvence, vibrace vrtulí a motorová odezva jiné
než u velkého výchozího modelu. Zisky se proto musí identifikovat a naladit pro
každou významně jinou hmotnost či vrtuli.

### 4.2 Orientace

Jednoduchá implementace reguluje Eulerovy úhly. Ty jsou srozumitelné, ale mají
singularitu a při velkých rotacích se osy vážou. Lepší reprezentace používá
kvaternion nebo přímo rotaci `R ∈ SO(3)`.

Geometrický regulátor definuje chybu orientace například

```text
e_R = 1/2 · vee(R_d^T·R - R^T·R_d)
e_omega = omega - R^T·R_d·omega_d
```

a moment tvoří ze zpětné vazby `-K_R e_R - K_omega e_omega` a dynamických
feed-forward členů. Výhoda je, že se nepracuje v lokálně problematických
Eulerových souřadnicích. Lee, Leok a McClamroch dokazují téměř globální
vlastnosti takového řízení v práci
[Control of Complex Maneuvers for a Quadrotor UAV using Geometric Methods on SE(3)](https://arxiv.org/abs/1003.2005).

Pro tento projekt není nutné nahrazovat vnitřní ArduPilot regulátor vlastním
geometrickým. Teorie je důležitá hlavně proto, aby vnější rojová vrstva
nepředpokládala, že `roll`, `pitch` a `yaw` jsou tři nezávislé lineární osy.

### 4.3 Poloha a rychlost

Vnější regulátor může vytvořit požadované zrychlení

```text
a_cmd = a_ff + K_p·(p_d - p) + K_v·(v_d - v).
```

Z vektoru `a_cmd - g_vector` se odvodí požadovaný směr tělové osy tahu a jeho
velikost. Požadovaný yaw doplní zbývající stupeň orientace. Povel se musí omezit
na dosažitelný tah, náklon, rychlost, akceleraci a jerk.

ArduCopter používá stejný princip v kaskádě: XY position P vytváří cílovou
rychlost, velocity PID cílové zrychlení a to se převádí na požadovaný náklon.
Svislá osa používá polohu, rychlost a akceleraci až k tahu. Viz oficiální
[Copter Position Control and Navigation](https://ardupilot.org/dev/docs/code-overview-copter-poscontrol-and-navigation.html)
a [Copter Attitude Control](https://ardupilot.org/dev/docs/apmcopter-programming-attitude-control-2.html).

## 5. Odhad stavu je součást řízení

Regulátor nezná pravý stav; pracuje s odhadem. Typická fúze:

| Veličina | Rychlý relativní zdroj | Pomalejší/absolutní korekce |
| --- | --- | --- |
| orientace a úhlová rychlost | gyroskop + akcelerometr | magnetometr, případně externí pose |
| výška | barometr, akcelerometr | dolní rangefinder |
| horizontální rychlost | IMU integrace | optical flow, VIO nebo GNSS |
| horizontální poloha | integrace rychlosti | motion capture, VIO/SLAM, GNSS, UWB |

EKF predikuje stav z dynamiky a IMU a koriguje ho měřeními s jejich nejistotou.
Kvalita řízení je tedy omezená observabilitou a kalibrací, ne jen zisky PID.

### Kritická indoor slabina projektu

Optical flow s rangefinderem dává horizontální rychlost vůči povrchu, ale bez
absolutní korekce poloha integrací driftuje. Pro jednoho drona při krátké misi
to může stačit. Pro formaci je ale rozdíl dvou driftujících odhadů přímo falešná
relativní vzdálenost. Roj potřebuje alespoň jednu z těchto cest:

- společný motion-capture systém pro první laboratorní validaci;
- UWB nebo jinou společnou poziční infrastrukturu;
- VIO/SLAM každého dronu a robustní slučování rámců;
- přímé relativní měření sousedů a řízení formace z něj.

ArduPilot umí použít optical flow a rangefinder v EKF, ale oficiální návod
výslovně pracuje s jejich konfigurací, limitem výšky rangefinderu a kontrolou
chování při driftu
([Optical Flow Sensor Testing and Setup](https://ardupilot.org/copter/docs/common-optical-flow-sensor-setup.html)).

## 6. Trajektorie, ne skoky v poloze

Skok cílové polohy implikuje v ideálním P regulátoru skok rychlosti a následně
akcelerace. Skutečný dron narazí do limitu, integrátor se nabije a chování se
špatně předpovídá. Plánovač má proto generovat časově parametrizovanou
trajektorii s omezenými derivacemi.

Kvadrokoptéra je za běžných podmínek diferenciálně plochá s plochými výstupy
`(x, y, z, yaw)`: z jejich dostatečných derivací lze odvodit orientaci, tah a
úhlové veličiny. To umožňuje skládat polynomické trajektorie mezi body.
Klasická práce
[Minimum Snap Trajectory Generation and Control for Quadrotors](https://doi.org/10.1109/ICRA.2011.5980409)
minimalizuje integrál čtvrté derivace polohy („snap“), aby vznikla hladká a
dynamicky sledovatelná trajektorie.

Pro pomalý první roj nemusí být minimum-snap implementace nutná. Nutné ale je:

- omezit rychlost, akceleraci, jerk, náklon a yaw rate;
- časově označit reference;
- odmítnout nebo bezpečně zastavit při zastaralém povelu;
- ověřit, že celá trajektorie, ne jen její koncový bod, leží v bezpečném
  prostoru.

## 7. Alternativy ke kaskádnímu PID

| Metoda | Silná stránka | Slabina | Vhodnost zde |
| --- | --- | --- | --- |
| PID + feed-forward | jednoduchý, levný, dobře podporovaný ArduPilotem | omezení se řeší nepřímo | nejlepší základ |
| LQR | systematický kompromis mezi chybou a úsilím kolem pracovního bodu | lineární model, závislost na vahách | výukové porovnání v simulaci |
| MPC | explicitní stavové a vstupní limity, predikce | výpočet a citlivost na model | vyšší lokální/rojový plánovač |
| geometrické řízení na SE(3) | konzistentní velké rotace a důkaz stability | složitější integrace a ladění | výzkumná alternativa, ne první krok |
| adaptivní/robustní řízení | nejistá hmotnost, tah a rušení | konzervativnost nebo více parametrů | užitečné při měnícím se nákladu |
| learned policy | může zachytit těžko modelovatelné jevy | obtížné garance a sim-to-real | až po měřitelném klasickém baseline |

MPC ani neuronová síť nenahrazují failsafe, měření latence a fyzické limity.

## 8. Specifika 3" cinewhoopu

### Vysoká autorita neznamená libovolnou akceleraci

Nízká setrvačnost umožní rychle měnit orientaci, ale maximální horizontální
zrychlení je pořád omezeno rezervou tahu. Při náklonu musí svislá složka tahu
současně nést hmotnost. Pokud celkový tah saturuje, stroj ztrácí výšku.

### Duct a blízkost stěny mění model

Proudění u stěny nebo podlahy, recirkulace v ductu a kontakt krytu nejsou v
jednoduchém modelu. Rojový plánovač proto nemá využívat celý geometricky volný
prostor bez rezervy. Identifikace se má dělat i v blízkosti stěny, ne jen ve
volném visu.

### Baterie mění zisk pohonu

S poklesem napětí se pro stejný normalizovaný povel mění dosažitelné otáčky a
tahová rezerva. Při roji nevzniká jen problém jednoho stroje: různě vybité
baterie znamenají různé dynamické limity. Plánovač má pracovat s konzervativním
společným limitem nebo s limity jednotlivých agentů.

### Vibrace a filtry přidávají fázi

Silnější low-pass/notch filtrace zmenší šum, ale přidá zpoždění. Příliš vysoký
gain pak může rozkmitat smyčku. Cílem není co nejhladší IMU graf, ale dostatečný
poměr šumu a fázové rezervy v uzavřené smyčce.

## 9. Co má rojová vrstva posílat

Od nejbezpečnějšího rozhraní k nejnáročnějšímu:

1. **cílová poloha / waypoint** – autopilot sám tvaruje pohyb; menší síťová
   frekvence, horší přímá kontrola časování formace;
2. **časovaná trajektorie** – nejlepší pro předvídatelný let, pokud ji autopilot
   nebo lokální companion umí sledovat a bufferovat;
3. **cílová rychlost + yaw rate** – vhodné pro reaktivní roj, ale vyžaduje
   pravidelné obnovování a timeout;
4. **attitude + thrust / body rates** – vysoká autorita a vysoké riziko;
5. **přímo motory** – přes bezdrátovou a obecnou ROS vrstvu pro tento projekt
   nevhodné.

Současné AP_DDS v repozitáři přijímá `TwistStamped` na `/ap/cmd_vel` a podle
`header.frame_id` rozlišuje `base_link` a `map`. To je použitelné rozhraní pro
první reaktivní koordinátor, ale musí mít explicitní watchdog a nulový/hold
fallback při výpadku povelů.

## 10. Co změřit před rojovým letem

Pro každou sestavu a relevantní hmotnost:

- maximální stabilní rychlost a akceleraci v indoor konfiguraci;
- brzdnou dráhu z několika rychlostí včetně rozptylu;
- dobu od vzniku povelu přes ROS/radio/autopilot k měřitelné reakci;
- chybu sledování trajektorie v přímce, zatáčce a u stěny;
- drift polohy po 10, 30 a 60 sekundách bez absolutní korekce;
- tahovou rezervu a pokles výkonu s napětím baterie;
- teplotu motorů/ESC při visu a opakovaných změnách směru;
- chování při ztrátě flow, rangefinderu, společné polohy a řídicí linky;
- rozdíl mezi kusy, ne pouze nejlepší kus.

Teprve horní kvantily těchto měření mají vstoupit do bezpečnostního rozestupu
roje.

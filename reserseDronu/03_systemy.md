# Systémy: z čeho se ten stroj skládá a co ho drží

## 1. Dekompozice a kde jsou skutečné vazby

```text
  rám + ducty ──────────────┐
  motory + vrtule ──────────┤
  ESC (AM32, 4x45 A) ───────┤
  FC (MicoAir H743 V2) ─────┼── ArduPilot ── AP_DDS ── XRCE-DDS ── ROS 2
  IMU + baro (na FC) ───────┤        │
  MTF-02P (tok + ToF) ──────┤        │
  LD06 (2D lidar) ──────────┘        │  ← tady vazba KONČÍ, viz §5
  ELRS RX ───────────────────────────┘
  OpenIPC video (Wyvern) ── wfb-ng ── pozemní přijímač
  baterie 4S LiHV ── napájí všechno výš
```

Osm subsystémů, ale rozhodnutí jsou svázaná do tří uzlů, a každý uzel je
jediné rozhodnutí, ze kterého vypadne polovina zbytku:

| Uzel | Rozhodnutí | Co z něj vyplynulo |
| --- | --- | --- |
| **ROS přes AP_DDS** | 1. 9. 2026 | nutnost H7 → 10g deska s 45A ESC na motory beroucí 10 A |
| **LD06 kvůli SLAM** | 9/2026 | +42 g, zdvojnásobení setrvačnosti v pitchi, přetečení hmotnostního rozpočtu → druhý drak |
| **OpenIPC video** | zadání | minimálně 2S, 13,8 g, až 15 W, a — nečekaně — jediná cesta skenu do ROS |

Žádné z těch tří rozhodnutí nebylo o aerodynamice. **Drak je důsledek datové
cesty, ne naopak.**

## 2. Volba firmwaru: co ArduPilot stojí na téhle třídě

| | ArduPilot | Betaflight | PX4 |
| --- | --- | --- | --- |
| cílová třída | 1–2 kg autonomní stroje | přesně tenhle rozměr | výzkumné a komerční VTOL |
| výchozí zisky | pro 9–12" vrtuli | pro 2–5" vrtuli | pro střední quady |
| filtrace malých strojů | umí, ale nastavuje se ručně | výchozí hodnoty vyladěné komunitou na whoopech | dobrá |
| autonomie, mise, failsafe | **nejlepší** | prakticky žádná | velmi dobrá |
| ROS 2 rozhraní | AP_DDS nativně (H7) | ne | uORB/µXRCE nativně |
| náročnost na MCU | vysoká (AP_DDS) | nízká (F4 stačí) | vysoká |

Volba ArduPilotu je správná a je odůvodněná: bez něj není AP_DDS, bez AP_DDS
není ROS bez dalšího hardwaru. **Ale má cenu, kterou je poctivé pojmenovat:**
projekt si vybral firmware, jehož výchozí ladění je pro pětkrát větší stroj, a
tím na sebe vzal ladicí práci, kterou by whoop-orientovaný firmware dal zadarmo.
Prvních pár set řádků poznámek v `ardupilot_params*.parm` je přesně splátka
téhle ceny.

Z toho plyne praktické doporučení, které nestojí nic: **rozdělit oživení na dvě
fáze.** Nejdřív ověřit mechaniku, směr motorů, rezervu tahu a vibrace na tom, co
jde měřit bez autonomie; teprve pak stavět ArduPilot ladění na už známém železe.
Kdo ladí neznámý rám a neznámý firmware současně, nerozezná, který z nich je
špatně.

## 3. FC a ESC: sedmkrát předimenzované a proč to nevadí

Čtyři LAVA 1104 berou ve špičce dohromady kolem 31 A; deska umí 45 A na každý ze
čtyř kanálů. Ta rezerva stojí gramy, které se na 229g stroji počítají, ale ESC
nebude nikdy limitem a jeho odpor při 8 A je zanedbatelný. Skutečné vlastnosti,
na kterých u téhle desky záleží, jsou jiné:

| Vlastnost | Proč rozhoduje |
| --- | --- |
| **AM32 firmware** | umí obousměrný DShot, tedy RPM zpět do ArduPilotu |
| RPM telemetrie | jediný spolehlivý vstup pro dynamický harmonický notch |
| H7 flash/RAM | podmínka AP_DDS, kvůli které deska vůbec je tak velká |
| volné UARTy | potřeba čtyři (ELRS, MTF-02P, LD06, telemetrie k videu); MicoAir má sedm, záložní Beast H7 pět |
| 36 × 36 mm obrys | neověřeno, že se vejde do 93,7mm rámu Pavo20 |

Poslední řádek je pořád otevřený a rozhodne ho maketa v ruce — ale **není to
blokující riziko**: [rozbor Pavo20](../spec/realna_stavba_dronu/10_pavo20.md#tři-otevřené-body-dořešené)
našel záložní desku iFlight Beast H7 55A AIO s obrysem 32,5 × 32,5 mm, stejnou
roztečí a o 1,5 g nižší hmotností. Pokud 36 mm nevyjde, zbývá 32,5 mm.

Ta záloha má pro §5 níž jeden důsledek, který stojí za zapsání: Beast H7 nese
BLHeli_S místo AM32. Doporučení postavit notch na RPM z ESC tím nepadá —
BLHeli_S vrací otáčky po signálové lince od verze 16.73 — ale je to jiná
kontrola na bench checklistu než u AM32.

## 4. Senzory a co z nich estimátor doopravdy dostane

| Senzor | Co měří | Co z toho EKF použije | Kde selže |
| --- | --- | --- | --- |
| IMU (na FC) | úhlová rychlost, zrychlení | základ všeho | vibrace vrtulí, teplotní drift |
| barometr | tlak | hrubá výška | průvan, zavřená místnost, prop wash |
| MTF-02P ToF | výška nad povrchem | přesná výška v dosahu | lesk, sklo, sklon, dosah |
| MTF-02P optický tok | rychlost vůči povrchu | horizontální rychlost | tma, koberec bez textury, neznámá výška |
| LD06 | 2D sken 360°, 4500 bodů/s | **nic** — viz §5 | sklo, tenké nohy nábytku, náklon |
| magnetometr | směr | yaw | rušení od vodičů a betonu |

Je poučné si všimnout, že **nejdražší a nejtěžší senzor na palubě nepřispívá
odhadu stavu ničím**. LD06 je tam kvůli mapování a vyhýbání, ne kvůli letu.
Z hlediska řízení je to 42 g nákladu, které zdvojnásobily setrvačnost.

## 5. Datová cesta je úzké hrdlo celého projektu

Tohle je nejdůležitější systémový nález v repozitáři a je ověřený ve zdrojovém
kódu, ne v dokumentaci: **AP_DDS nepublikuje žádný `LaserScan`, `Range` ani
proximity topic**, a `AP_Proximity` vrací osm vzdáleností po 45° s
`static_assert` na tom čísle. Autopilot LD06 nativně čte; problém je export.
Rozbor čtyř cest ven i s čísly je v
[Kudy se sken dostane do ROS 2](../spec/realna_stavba_dronu/09_kudy_do_ros.md).

Systémový důsledek, který stojí za zopakování na téhle úrovni:

- **sken jde do ROS jen přes video jednotku** (mavfwd/msposd přes wfb-ng),
  protože palubní počítač se do 294 g nevejde;
- **smyčka vyhýbání se tím překlápí na zem a přes rádio**, takže výpadek linky
  neznamená degradaci, ale slepotu;
- s tím se mění i požadavek na `GUID_TIMEOUT` a na hlídač zvětralého skenu —
  timeout musí být kratší než brzdná dráha při povolené rychlosti, ne 3 s;
- sken je **2 % kapacity linky**, tedy šířka pásma není problém. Problém je
  latence, jitter a to, co se stane, když paket nedorazí.

## 6. Tři rádia na jednom 229g stroji

| Linka | Pásmo | Co veze | Kritičnost |
| --- | --- | --- | --- |
| ExpressLRS | 2,4 GHz (nebo 868/915 MHz) | řízení, převzetí operátorem | **letová bezpečnost** |
| OpenIPC / wfb-ng | 5,8 GHz | video + nově i sken a MAVLink | mise a nově i vyhýbání |
| ROS 2 / DDS | přes tutéž linku nebo Wi-Fi | telemetrie a povely | autonomie |

Tři vysílače na jedné desce ve vzdálenosti deseti centimetrů vytvářejí problém,
který v žádném z dokumentů zatím není napsaný: **koexistence**. Prakticky to
znamená tři pravidla:

1. **ELRS na jiném pásmu než video, kde to jde.** Když musí být obojí na 2,4,
   je nutné mít kanálový plán a ověřit ho na zemi na dosah, ne na stole.
2. **Řídicí linka nesmí sdílet osud s datovou.** Pokud video jednotka veze
   MAVLink i sken, je to jeden bod selhání pro misi — ale nesmí se stát bodem
   selhání pro převzetí operátorem.
3. **Změřit dosah a chybovost s běžícím videem**, protože enkodér i vysílač
   jedou naplno teprve v letu a teplotní pokles výkonu je u těchhle jednotek
   doložený problém.

## 7. Napájení: jedna baterie pro let, výpočet i rádio

4S LiHV 750 mAh ≈ 11,4 Wh, z toho:

- let: ideálně 22–25 W, reálně násobek;
- video: **až 15 W** u srovnatelné jednotky;
- LD06, FC, přijímač: jednotky wattů.

Dvě věci z toho plynou a obě jsou systémové, ne komponentní:

- **Fixní odběr je srovnatelný s letovým.** Zkrátit misi o polovinu neznamená
  polovinu energie, protože video jede pořád. Kdo chce delší let, vypíná video
  nebo bere větší baterii — vrtule s tím nic neudělá.
- **5V větev je sdílená s tím, co drží stroj ve vzduchu.** Přetížený BEC při
  zapnutí vysílače je klasický způsob, jak restartovat FC ve visu. Patří to na
  bench checklist jako měření, ne jako úvaha.

## 8. Co se nesmí přenést ze simulace do letového kontroléru

Tohle je výstup, kvůli kterému tahle kapitola vznikla. Parametrové soubory jsou
pečlivě odvozené — **pro simulovaný rotor**. Tři hodnoty jsou identity modelu,
ne vlastnosti železa:

| Parametr | V simulaci | Proč tam | Co na železe |
| --- | ---: | --- | --- |
| `MOT_THST_EXPO` | 1,0 | model má tah ∝ ω² a ω lineární v povelu | **změřit na stolici**; pro malé vrtule spíš 0,5 a níž, u linearizujících ESC 0–0,2 |
| `MOT_BAT_VOLT_MIN/MAX` | 0 (vypnuto) | SITL nemodeluje propad napětí | **zapnout**; jinak se zisk smyčky mění o 35 % přes let |
| `SIM_BATT_VOLTAGE` | 16,4 | jen simulace | nepatří tam |
| `INS_GYRO_FILTER`, `ATC_RAT_*_FLT*` | nenastaveno | simulace nemá šum | **nastavit**; bez nich nemá měřená mez zisku platnost |
| `INS_HNTCH_*` | nenastaveno | simulace nemá vibrace | **nastavit z AM32 RPM** |
| `ATC_RAT_*_P` 0,040 | naměřený optimální kompromis | z mřížky bez šumu | **horní mez**, ne startovní hodnota |
| `MOT_PWM_MIN/MAX` 1100/1900 | shoda s rozsahem v SDF | vlastnost modelu | podle skutečné kalibrace ESC |
| `MOT_THST_HOVER` | 0,46 / 0,53 | z kalibrovaného rotoru | nechat se naučit (`MOT_HOVER_LEARN`) |

Naopak přenést se **má** metodika: pevný scénář, tři metriky, jeden parametr na
běh, a výsledek zapsaný i když vyjde nudně.

## 9. Co je dnes skutečně blokující

Seřazeno podle toho, kolik dalších věcí na tom visí:

1. **Žádné měření na železe.** Tahová křivka, spektrum vibrací, příkon ve visu.
   Blokuje ladění, výdrž, `d_safe` i jakoukoli diskusi o roji.
2. **Export skenu neověřený.** Stojí nula gramů a nula korun, ale dokud
   neproběhne, nemá projekt cestu k SLAM na skutečném stroji.
3. **Mechanika Pavo20.** Vejde se 36mm deska do 93,7mm rámu. Jedna papírová
   šablona; při neúspěchu se mění deska (Beast H7), ne drak.
4. **Koexistence tří rádií.** Zatím nikde nezapsaná.
5. **Teplota** — video jednotky i motorů. Obojí je u téhle třídy doložený
   problém a obojí se pozná až za letu.

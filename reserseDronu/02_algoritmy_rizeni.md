# Algoritmy řízení jednoho stroje

Tahle kapitola nezačíná u regulátoru, protože u něj nezačíná ani problém.
Kvadrokoptéra téhle třídy se ladí zdola: rozhoduje **alokace, zpoždění a
linearita pohonu**, a teprve pak zisky. Repozitář to jednou zaplatil odletem do
54 m s nulovým plynem v logu, což nebyla chyba regulátoru, ale saturace mixéru.

## 1. Co ArduPilot doopravdy běží

```text
cíl mise (ROS 2 / /ap/cmd_vel)
        |
        v
poziční smyčka  P: poloha  ->  cílová rychlost
        |
        v
rychlostní smyčka  PID: rychlost -> cílové zrychlení
        |
        v
převod na náklon a celkový tah  (a_cmd - g -> R_d, f)
        |
        v
smyčka orientace  P: úhel -> cílová úhlová rychlost
        |
        v
smyčka úhlové rychlosti  PID + FF   <-- tady se rozhoduje, jestli stroj letí
        |
        v
mixer / alokace  ->  4 x PWM  ->  ESC  ->  motor  ->  vrtule
```

Každá vnější smyčka smí být pomalejší než ta pod ní. Zajímavé je, že v
tomhle projektu je **jediná smyčka, kterou kdy někdo měřil, ta nejspodnější** —
`scripts/rate_step_response.py` řídí obdélníkový signál v rollu přes
`SET_ATTITUDE_TARGET` a měří překmit, RMS chybu a počet změn znaménka. Všechno
nad ní je zatím zděděné z výchozích hodnot ArduPilotu.

## 2. Alokace: kde to selže dřív než regulace

Regulátor si přeje vektor `u = (f, tau_x, tau_y, tau_z)`; mixer ho musí rozdělit
na čtyři nezáporné, shora omezené tahy. Když požadavek neexistuje ve splnitelné
množině, **někdo o něj musí přijít** a to rozhodnutí je návrhové, ne matematické.

ArduCopter prioritizuje moment před výškou. Zdejší log to ukazuje v nejčistší
podobě: při stock ziscích jeden rotor zůstal přisátý na podlaze `MOT_SPIN_MIN`
(597 rad/s), zatímco ostatní běžely 1500–2200, saturující rotor se přeléval mezi
osami, Copter dával plyn pryč, aby udržel autoritu, a log ukazoval `ThO 0.000`
a povel ke klesání −2,5 m/s, zatímco stroj stoupal do 54 m.

Z toho plynou pravidla, která mají větší váhu než jakékoli ladění:

- **Zisky musí odpovídat autoritě draku.** Výchozí hodnoty ArduPilotu cílí na
  9–12" vrtuli; tady jsou děleny zhruba 7,7.
- **Saturaci je nutné vidět v logu.** „Dron se choval divně" a „mixer byl
  nasycený 40 % času" jsou dvě různé diagnózy a jen druhá je akceschopná.
- **Rezerva tahu ve visu je rezerva na moment.** Pavo20 visí na 28,4 %, což je
  míň rezervy než CineLogových 21,5 %.

## 3. Rate loop: jediná naměřená věc

Zisky nebyly odvozeny ze škálování, ale změřeny mřížkou. Obě letadla dávají
stejnou mez:

| Drak | Autorita | Mez nestability | Zvolený zisk | Podíl meze |
| --- | ---: | ---: | ---: | ---: |
| CineLog30 V3 | 689 rad/s² | mezi 0,065 a 0,080 | 0,040 | 0,62 |
| Pavo20 Pro 4S | 583 rad/s² | mezi 0,065 a 0,080 | 0,040 | 0,62 |

Metoda je správná a stojí za převzetí i pro další parametry: **jeden parametr,
pevný scénář, tři metriky (překmit, RMS, zvonění), čerstvý SITL na každý bod.**
Jednotlivý běh „vypadal stabilně" není výsledek.

Stejně cenný je zapsaný **negativní nález**: očekávaný posun meze o 15 % se
neprojevil, protože krok mřížky je 23 %. Rešerše, která tohle zamlčí, vypadá
silněji a je horší.

### Co ta mez neumí vidět

Simulace nemá **šum gyroskopu, rezonanci rámu ani zpoždění ESC nad rámec
motorového modelu**. To jsou přesně tři věci, které na železe tlačí zisky dolů.
Proto je 0,040 horní mez, ke které se má na hardwaru přibližovat, ne hodnota k
prvnímu letu — a je to v parametrech napsané.

## 4. Rozpočet fáze: proč se filtry neplatí jen šumem

Rychlostní smyčka je integrátor (`J·dω/dt = tau`), tedy −90° fáze ze své
podstaty. Všechno ostatní jen ubírá, kolik zbývá:

| Frekvence | Motor, lag 12,5 ms | Gyro LPF 80 Hz | D-term LPF 40 Hz | Transport 2 ms | Součet |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 Hz | 21° | 4° | 7° | 4° | 36° |
| 10 Hz | 38° | 7° | 14° | 7° | 67° |
| 15 Hz | 50° | 11° | 21° | 11° | 92° |
| 20 Hz | 58° | 14° | 27° | 14° | 113° |
| 30 Hz | 67° | 21° | 37° | 22° | 146° |

S −90° z integrátoru je čistě proporcionální smyčka na hraně už kolem 10–15 Hz.
**Jediný zdroj předstihu v celém řetězci je D-člen** — a ten se filtruje, protože
jinak zesílí šum. Odtud plyne celé ladění malého quadu:

- `timeConstantUp` 12,5 ms v modelu je **největší jednotlivá položka** a je to
  modelový předpoklad, ne měření. Na železe závisí na ESC, protokolu a
  setrvačnosti vrtule; s bidirectional DShot a lehkou 2,2" vrtulí může být
  lepší, s pomalou regulací horší.
- Zpřísnění filtru vždy platí fází. Cílem není hladký graf gyroskopu, ale
  největší zisk, který ještě má rezervu fáze.
- **Notch filtr je výjimka**: úzké pásmo odstraní energii vrtule s mnohem menší
  fázovou daní než širokopásmový low-pass.

## 5. Filtry, které v parametrech nejsou

Ani jeden z obou souborů `ardupilot_params*.parm` nenastavuje `INS_GYRO_FILTER`,
`ATC_RAT_*_FLTD`, `ATC_RAT_*_FLTT` ani harmonický notch. V simulaci bez šumu je
to konzistentní rozhodnutí. **Pro železo je to prázdná polovina naladění**, a
je větší než ta, která je hotová.

Kotvy z oficiálního ladicího průvodce, které už jsou zapsané ve
[výzkumu rotorů](../workflow/research_rotor_simulation.md):

- `INS_GYRO_FILTER` 80 Hz pro 5" vrtuli, výš pro menší;
- `ATC_RAT_*_FLTD` a `FLTT` na `INS_GYRO_FILTER / 2` pro roll a pitch,
  `/ 4` pro yaw;
- výchozí zisky ArduPilotu cílí na 9–12" stroj.

Pro 2,2" a 3" vrtuli jsou vlastní frekvence výš, takže low-pass smí být volnější
— ale jen když notch odvede svou práci.

### Harmonický notch je pro tenhle stroj nejcennější funkce ESC

ArduPilot umí řídit frekvenci notche podle skutečných otáček z ESC. Novější
AM32, BLHeli32 (32.7+) a BLHeli_S (16.73+) vracejí RPM po signálové lince
(bidirectional DShot) a `INS_HNTCH_MODE = 3` je použije; bidirectional DShot
dodá aktualizaci až 400 Hz proti asi 100 Hz u sériové ESC telemetrie
([Managing Gyro Noise](https://ardupilot.org/copter/docs/common-imu-notch-filtering.html),
[ESC Telemetry Based Notch](https://ardupilot.org/copter/docs/common-esc-telem-based-notch.html)).

Pro stroj, který ve visu točí 28 400 RPM (473 Hz základní harmonická na
jednootáčkovém základu, 1420 Hz pro tři listy), je to rozdíl mezi filtrací a
hádáním. **Dobrá zpráva pro tenhle kusovník: kupovaná deska je varianta s AM32**
(`MicoAir H743 V2 45A AIO AM32`), a AM32 obousměrný DShot podporuje. Zbývá
ověřit verzi firmwaru a zapnout ji; není to nákupní riziko, je to položka na
bench checklist.

## 6. Linearizace tahu: `MOT_THST_EXPO 1.0` je artefakt simulace

V modelu platí `tah ~ omega²` a `omega` je lineární v povelu, takže expo 1.0
tu křivku **přesně invertuje**. Je to správně odvozené a v komentáři parametrů
i vysvětlené.

Na železe to platit nebude. ArduPilot popisuje `MOT_THST_EXPO` jako tvar tahové
křivky s výchozí hodnotou 0,65 a doporučuje ji měřit na tahové stolici;
u ESC s vlastní linearizací vycházejí hodnoty spíš kolem 0 až 0,2
([Motor Thrust Scaling](https://ardupilot.org/copter/docs/motor-thrust-scaling.html)),
zatímco pro 5" vrtule se v ladicím průvodci uvádí 0,55 a pro menší vrtule méně.

Co se stane při špatné hodnotě, je přesně ten druh chyby, který se hledá
špatně: **zisk smyčky se mění s plynem.** Stroj naladěný ve visu se rozkmitá při
stoupání nebo při agresivním brzdění a vypadá to jako chyba ladění zisků, i když
je chyba v linearizaci.

**Pravidlo pro přechod na hardware: `MOT_THST_EXPO` se do FC nepřenáší ze
simulace. Buď se změří, nebo se nechá na výchozí hodnotě a zisky se ladí až
potom.**

## 7. Propad napětí mění zisk smyčky o třetinu

4S LiHV jde od 17,4 V (plná) k 14,0 V (`BATT_LOW_VOLT`). Tah při stejném
povelu se řídí přibližně druhou mocninou napětí:

```text
(14,0 / 17,4)² = 0,65
```

Tedy **35% ztráta zisku smyčky mezi začátkem a koncem letu**. Stroj naladěný na
plné baterii je na konci letu měkký; stroj naladěný na vybité překmitává na
začátku.

ArduPilot na to má `MOT_BAT_VOLT_MIN/MAX`, které tuhle kompenzaci zapnou. Oba
parametrové soubory je mají **vypnuté (0,0) záměrně**, protože simulace propad
napětí nemodeluje a `copter.parm` by dosadil 3S hodnoty. Pro železo to platit
přestane — a je to druhá položka na seznam „co se nesmí zkopírovat do FC".

## 8. Odhad stavu: kde indoor stroj doopravdy stojí

| Veličina | Rychlý zdroj | Absolutní korekce | Co ji tady drží |
| --- | --- | --- | --- |
| úhlová rychlost | gyroskop | — | spolehlivá |
| orientace | gyro + akcelerometr | magnetometr | indoor rušený, ale roll/pitch drží |
| výška | barometr + akcelerometr | dolní ToF (MTF-02P) | dobrá do dosahu dálkoměru |
| horizontální rychlost | integrace IMU | optický tok | závisí na textuře, světle a známé výšce |
| horizontální poloha | integrace rychlosti | **nic** | **driftuje** |

Poslední řádek je celá pravda o indoor autonomii tohoto stroje. Optický tok dává
rychlost, ne polohu; poloha je její integrál a její chyba roste s časem
monotónně. To není chyba nastavení, je to vlastnost té sady senzorů.

Z toho plyne, co smí a nesmí stavět vyšší vrstva:

- **smí**: držet výšku, letět zadanou rychlostí, zastavit, reagovat na překážku
  v tělovém rámci, mapovat krátkou epizodu;
- **nesmí**: vracet se po dvou minutách na stejné místo bez korekce, spoléhat na
  absolutní polohu, nebo považovat dvě polohy dvou strojů za porovnatelné.

Poznámka z repozitáře, která ušetří půl dne: `AHRS_EKF_TYPE 10` (SITL ground
truth) odděluje dynamiku od estimace a odstraní celou třídu prearm chyb — ale
v tomhle modelu zatím dává náklon −90° a nearmuje. Kontrolní experiment s Iris
na téže JSON cestě armuje a stoupá správně, takže **to není omezení metody, ale
vlastní defekt modelu** — a je tedy opravitelný. Dokud opravený není, nese každý
test regulace i šum estimátoru.

## 9. Vnější rozhraní: co je bezpečné poslat

Od nejbezpečnějšího:

1. **waypoint / cílová poloha** — autopilot si tvaruje profil sám;
2. **časovaná trajektorie** — nejlepší předvídatelnost, nejvyšší nároky;
3. **rychlost + yaw rate** (`/ap/cmd_vel`, dnešní cesta) — vhodné pro reaktivní
   demo, ale **vyžaduje watchdog**; `GUID_TIMEOUT` (výchozí 3 s) zpomalí stroj
   do zastavení, což je pro pokoj dlouhá doba a má se zkrátit podle brzdné dráhy;
4. **náklon + tah** — vysoká autorita, vysoké riziko, používá to jen
   `rate_step_response.py`;
5. **přímo motory přes síť** — sem nepatří.

Ke každé úrovni patří tři věci, které nejsou volitelné: **timestamp měření,
platnost povelu a definované chování při jeho vypršení.**

## 10. Alternativy ke kaskádnímu PID

| Metoda | Co řeší lépe | Co stojí | Verdikt tady |
| --- | --- | --- | --- |
| **kaskádní PID + FF** | jednoduchost, podpora, laditelnost | omezení jen nepřímo | **zůstat**; je v ArduPilotu a je naměřený |
| **INDI** | nahradí model okamžitým měřením úhlového zrychlení; robustní k neznámému tahu, hmotnosti a nákladu | potřebuje čisté zrychlení (tedy dobrou filtraci) a model aktuátoru, včetně jeho zpoždění | nejzajímavější alternativa pro tuhle třídu; implementačně mimo ArduPilot |
| **LQR** | systematický kompromis chyba/úsilí | lineární model kolem pracovního bodu | dobré simulační srovnání, ne produkce |
| **NMPC** | limity a predikce explicitně | výpočet, citlivost na model | až na companion computeru, kterého tu není |
| **geometrické na SE(3)** | velké rotace bez singularit | složitost, ladění | výzkumné; kaskáda tady nesahá k velkým úhlům |
| **L1 / adaptivní** | měnící se hmotnost a tah | konzervativnost, další parametry | relevantní, až se bude měnit náklad |
| **naučená politika** | zachytí nemodelovatelné jevy | garance a sim-to-real | teprve po měřitelném klasickém baseline |

### INDI si zaslouží víc než řádek

INDI nahrazuje modelové členy přímým měřením: z rozdílu naměřeného a
požadovaného úhlového zrychlení spočítá **přírůstek** povelu, takže nepotřebuje
znát `J`, tah ani aerodynamiku přesně — jen jejich lokální citlivost. Pro stroj,
jehož `Ct` je zpětně dopočtený z jiného draku a jehož setrvačnost se mění s
každým přišroubovaným senzorem, je to přesně ten druh robustnosti, který chybí
([Cascaded INDI for MAV Disturbance Rejection](https://arxiv.org/abs/1701.07254);
novější [Learned INDI](https://arxiv.org/abs/2503.09441) přidává náklad na laně).

Cena je ale konkrétní a v tomhle projektu vysoká: INDI stojí a padá s kvalitou
úhlového zrychlení, tedy s derivací gyroskopu — a to je přesně signál, který je
na malém rámu s 28 000 RPM nejvíc zašuměný. INDI tedy **nešetří práci s
filtrací, přesouvá ji na první místo**. Pro repozitář je to smysluplný cíl až
poté, co bude na železe změřené spektrum vibrací.

### Naučené řízení: kam se za tři roky dostalo

- **Swift** (Nature 2023) porazil lidské mistry v dronových závodech s politikou
  trénovanou v simulaci a doladěnou reálnými daty — ale s vlastní vizuální
  lokalizací a v úloze, kde je trať známá
  ([10.1038/s41586-023-06419-4](https://doi.org/10.1038/s41586-023-06419-4)).
- **Learning to Fly in Seconds** ukazuje politiku až na úroveň otáček motorů,
  trénovanou 18 sekund na běžném notebooku a nasazenou na mikrokontrolér
  ([arXiv:2311.13081](https://arxiv.org/abs/2311.13081)).
- Systematická studie zero-shot sim-to-real pro kvadrokoptéry pojmenovává, co
  rozhoduje: vstupy politiky, regularizace hladkosti akcí, systémová
  identifikace a selektivní randomizace ([arXiv:2412.11764](https://arxiv.org/abs/2412.11764)).

Pro tenhle repozitář z toho plyne jedna věta: **naučená politika není náhrada za
neprovedené měření.** Randomizace v simulaci potřebuje rozsah, který se bere z
tahové stolice a z logu vibrací, tedy z těch samých dvou měření, která blokují i
klasické ladění.

## 11. Co změřit, v tomhle pořadí

1. **Spektrum gyroskopu na železe ve visu** — bez něj se nedá nastavit ani
   notch, ani low-pass, ani obhájit žádný zisk.
2. **Tahová křivka pro `MOT_THST_EXPO`** — jinak se zisk smyčky mění s plynem.
3. **Rate step na železe** stejnou metodou jako v simulaci, se stejnými třemi
   metrikami, aby se dala porovnat mez 0,065–0,080 se skutečnou.
4. **End-to-end latence** od odeslání `/ap/cmd_vel` po měřitelnou reakci,
   včetně rozptylu. Z ní teprve vyjde rozumný `GUID_TIMEOUT`.
5. **Drift polohy** po 10, 30 a 60 s bez korekce, s optickým tokem v provozním
   světle a nad reálnou podlahou.
6. **Totéž na druhém kusu.** Rozdíl mezi kusy je informace, kterou jeden kus
   nedá.

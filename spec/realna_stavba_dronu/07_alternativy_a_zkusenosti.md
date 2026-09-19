# Alternativy a zkušenosti uživatelů

Doplněk ke [kusovníku](./06_nakup.md) a [tabulce komponent](./03_komponenty.md).
Kusovník říká, co koupit a kde; tenhle dokument říká, **co si o tom myslí lidé,
kteří to už mají**, a **co koupit místo toho**, když se ukáže, že to nesedí.

Rešerše je z **12. 9. 2026**. U každého tvrzení je poznamenané, odkud je,
protože se míchají tři velmi různé váhy důkazu:

- **[repo]** — ověřeno přímo v tomhle projektu, dá se to znovu spustit
- **[dok]** — dokumentace výrobce nebo ArduPilotu
- **[fórum]** — jedna nebo pár zkušeností od uživatelů; užitečné jako varování,
  ne jako změřený fakt

---

## Nález, který mění nákupní seznam

**Sken z lidaru se do ROS 2 přes DDS nedostane. Ta cesta neexistuje.** [repo]

AP_DDS publikuje přesně tato témata: `time`, `navsat`, `tf_static`, `battery`,
`imu/experimental/data`, `pose/filtered`, `twist/filtered`, `airspeed`, `rc`,
`geopose/filtered`, `goal_lla`, `clock`, `gps_global_origin/filtered`, `status`,
`joy`, `tf`, `cmd_vel`, `cmd_gps_pose`. **Žádný `LaserScan`, žádná proximita.**
Ověřeno v tabulce témat ArduPilotu z 7. 9. 2026 a rešerše nenašla ani PR, který
by to přidával.

V simulaci se to neprojeví, protože tam jde sken z Gazeba přímo do ROS přes
`ros_gz_bridge`. Na skutečném stroji ta linka chybí — a celý demo stack
(`obstacle_monitor`, `occupancy_mapper`, `frontier_explorer`) stojí na
`LaserScan`.

ArduPilot umí LD06 přečíst sám (`SERIAL*_PROTOCOL 11` = Lidar360, baud 230400,
`PRX1_TYPE`, `AVOID_ENABLE 7`) [dok] — ale to je **jeho vlastní** vyhýbání se
překážkám, ne data pro nás.

### Čtyři cesty ven, a co která stojí

> **Aktualizováno 13. 9. 2026.** Tenhle seznam měl původně tři položky a dvě
> z nich se po ověření přímo ve zdrojáku ArduPilotu zavřely; přibyla naopak
> čtvrtá, se kterou backlog nepočítal. Důkazy — čísla řádků, `static_assert`
> i propočet linky — jsou v [Kudy se sken dostane do ROS 2](./09_kudy_do_ros.md).
> Tady zůstává jen shrnutí.

| Cesta | Hmotnost navíc | Dá SLAM? | Co ji drží zpátky |
| --- | ---: | :-: | --- |
| **LD06 → palubní počítač** (běžná praxe) | 10–30 g | ano | mimo hmotnostní rozpočet, viz níž |
| **LD06 → FC, sken přes video jednotku dolů** | **0 g** | ano | neověřeno na železe; smyčka vyhýbání jde přes rádio |
| **LD06 → FC + dopsat AP_DDS téma** | 0 g | **ne** | `AP_Proximity` vrací osm vzdáleností po 45° pod `static_assert`; fork by musel být druhý ovladač uvnitř autopilota |
| **LD06 → FC, ROS jen na zemi** | 0 g | **ne** | skrytý předpoklad: něco na palubě to musí poslat dolů, a autopilot umí poslat jen těch osm sektorů |

Návody ArduPilotu i cizí projekty na indoor autonomii shodně dělají **první
variantu**: lidar do palubního počítače, ne do FC. [dok][fórum] Druhá varianta
je ale to, co se má zkusit dřív — video jednotka je Linux, je v kusovníku tak
jako tak a stojí nula gramů.

### Proč „ROS na zemi" není zadarmo

wfb-ng, na kterém OpenIPC stojí, má IPv4 tunel — ale jeho vlastní dokumentace
říká, že se **nemá používat na nic jiného než málo datový provoz typu ssh**,
protože má vyšší režii a jiné kódování než video a MAVLink proudy. [dok]
OpenIPC navíc používá jen **podmnožinu** wfb-ng stacku.

Náš sken potřebuje **141 kbit/s** — ne 108, jak tu stálo dřív; skutečné číslo
vypadlo až z formátu paketu LD06 (12 bodů po 47 B, 375 paketů/s). To je řádově
víc než ssh a řádově míň než video: 2,0 % celé linky a 4,7 % toho, co po videu
zbývá. Nikdo to nezměřil.

Odpověď na ten tunel ale existuje a je to právě ta čtvrtá cesta: **nemá se jít
tunelem, ale syrovým UDP streamem.** `OpenIPC/mavfwd` posílá UDP, což je ta
správná strana téhle hranice. Otázka tedy není „projde to tunelem", ale jestli
má zvolená video jednotka volný UART a udrží 230400 baud vedle enkodéru.

### Co to znamená pro nákup

Kusovník **nemá palubní počítač** a bez rozhodnutí o něm se nedá dokončit.
Kandidáti:

| Deska | CPU / RAM | Hmotnost | Příkon | Poznámka |
| --- | --- | ---: | ---: | --- |
| Raspberry Pi Zero 2 W | 4× A53 1 GHz / 512 MB | ~11 g | 1,5–3 W | nejlehčí, nejmíň RAM; ekosystém největší |
| Radxa Zero 3W | 4× A55 1,6 GHz / až 8 GB | ~15 g | vyšší | výrazně silnější, [fórum] žere víc |
| Orange Pi Zero 2W | 4× A53 / 1–4 GB | ~14 g | střední | levnější, podpora slabší |

**Poběží na tom náš stack?** Změřeno tady [repo]: mapér potřebuje **4 ms na
sken** (rozpočet 100 ms při 10 Hz) a explorer **73 ms na mapu** (rozpočet
1000 ms při 1 Hz). Pi Zero 2 W je na tenhle typ práce v Pythonu řádově
8–15× pomalejší než tahle mašina, takže odhadem 30–60 ms na sken a 0,6–1,1 s na
mapu. **Mapér projde, explorer je na hraně.** V Rustu by obojí bylo pohodlné —
což je mimochodem nejsilnější praktický argument pro ten přepis.

---

## Rám: GEPRC CineLog30 V3

**Kupovat:** [Aerodrone CZ](https://aerodrone.cz/product/gep-cl30-v3-o4-ram/),
1 490 Kč.

**Zkušenosti:**

- V3 má **znatelně zesílené ochrany vrtulí** proti V2 a lépe snáší pády, ale
  pořád je to spíš subtilní konstrukce. [fórum]
- Po pádu se **uvolňuje držák kamery** a vracet silentbloky zpátky je otrava i s
  přiloženým nástrojem. [fórum]
- Varování, které se nás týká víc, než vypadá: uživatel s **původním** CineLogem
  30 ho nedostal výš než 1,5 m, „řval jako pominutý", a i po výměně za 1504
  3100KV a nové D75 třílisté vrtule se to nezlepšilo — odběr vysušil 550mAh
  baterii za minutu a ta se přehřívala. [fórum]

Ta poslední zkušenost je důvod brát **naši simulovanou statiku s rezervou**:
model počítá poměr tahu k váze 5,9, což je na ducted 3" hodně, a tah je
kalibrovaný z publikovaných dat motoru a učebnicových koeficientů, ne ze
zkušebního stavu. To je otevřená položka v backlogu a tohle je nezávislý důvod,
proč ji zavřít dřív než pozdě.

**Alternativy:** v téhle třídě prakticky nic, co by drželo 76mm ducty a mělo
místo na 30mm stack. Kdo chce robustnější, jde na 3,5" (těžší, do bytu horší).

---

## Motory: GEPRC SPEEDX2 1404 3850KV

**Kupovat:** [Rotorama CZ](https://www.rotorama.cz/product/geprc-speedx2-1404-3850kv),
379 Kč/ks, 4 ks.

**Alternativy** (stejná montážní rozteč, 1404/1408 třída):

| Motor | KV | Kdy zvolit |
| --- | ---: | --- |
| iFlight XING 1404 | 3800 | dostupnější v EU, podobný tah |
| RCinPower GTS V3 1404 | 3800 | oblíbený u cinewhoopů, [fórum] tišší |
| T-Motor F1404 | 3800 | dražší, lepší ložiska |

**Pozor na KV:** 3850KV na 4S je hodně, a v duktu to znamená vysoký odběr na
malý tah. Pokud se potvrdí problém s přehříváním nebo výdrží, cesta je **níž s
KV** (3000–3500), ne výš.

---

## Vrtule: HQProp DT76mmX3 V2

**Kupovat:** [Rotorama CZ](https://www.rotorama.cz/product/hqprop-dt76mmx3-v2),
79 Kč/sada, **3 sady**.

**Alternativy:** Gemfan D76 (levnější, [fórum] lehce hlučnější), HQProp T76.
Vrtule jsou spotřební materiál — kupovat víc, ne míň.

---

## Letový kontrolér: MicoAir H743 V2 45A AIO

**Kupovat:** [Rotorama CZ](https://www.rotorama.cz/product/micoair-h743-v2-45a-aio-am32),
2 090 Kč.

**Proč zrovna tenhle:** AP_DDS potřebuje H7 a tenhle je od 4.6.0 oficiálně
podporovaný ArduPilotem. [dok] To zužuje výběr drasticky.

**Zkušenosti:**

- **Mission Planner načítá parametry pomalu** — jeden uživatel hlásí 2,5 minuty
  přes USB-C na 115200. [fórum]
- Jiný strávil den tím, že se **sériové porty nezobrazovaly správně**. [fórum]
- Je hlášený **crashdump na Copter 4.6**. [fórum] Stojí za to sledovat, na jaké
  verzi to je.
- **VBAT je jediný vstup, který snese 3–6S.** Přivést napětí jinam desku zabije.
  [dok]
- Vestavěný kompas se kvůli rušení obvykle vypíná ve prospěch externího. [dok]
  Nás se to netýká — indoor bez GPS kompas stejně nepoužijeme.

**Alternativy:** cokoli z [seznamu podporovaných H7 desek](https://ardupilot.org/copter/docs/common-autopilots.html).
V AIO provedení a 30×30 to je hlavně **Holybro Kakute H7 V2** (bez ESC, potřeba
zvlášť) nebo **SpeedyBee F405** — ten ale **odpadá, je F4 a DDS na něm neběží**.

---

## Přijímač: SpeedyBee Nano 2.4G ELRS

**Kupovat:** [FPV24](https://www.fpv24.com/cs/speedy-bee/pijma-speedybee-nano-24ghz-elrs),
12,90 €.

**Zkušenosti a alternativy:**

| Přijímač | Hmotnost | Poznámka |
| --- | ---: | --- |
| SpeedyBee Nano | 0,7 g | SX1281+ESP8285, telemetrie ~170 mW [dok] |
| HappyModel EP1 | 0,4 g | doporučovaný pro whoopy, ale [fórum] **kolísavá kvalita**, kusy chodí mrtvé (výrobce mění) |
| RadioMaster RP1 | 0,6 g | [fórum] spolehlivý pro malé stroje |
| BetaFPV ELRS Nano | 1,2 g | větší a těžší, ale zvládá plných 500 Hz [fórum] |

Pro indoor let na pár metrů je dosah nepodstatný; rozhoduje spolehlivost a
hmotnost. SpeedyBee je rozumná volba, RadioMaster RP1 rovnocenná náhrada.

---

## Optický tok a výška: MicoAir MTF-02P

**Kupovat:** [Rotorama EU](https://www.rotorama.com/product/micoair-mtf-02p),
20,49 €.

**Tohle je nejrizikovější díl celé sestavy** a stojí za to vědět proč předem:

- **Potřebuje světlo, nejmíň 60 luxů.** V úplně tmavé místnosti se stroj
  rozbije. [fórum] Byt večer bez rozsvícení je na hraně.
- **Potřebuje nejmíň 8 cm nad zemí,** aby vůbec fungoval. [fórum]
- Dosah dálkoměru **6 m** při 90% odrazivosti, chyba pod 2 cm; zorné pole toku
  42°, max. rychlost 7 m/s. [dok]
- Před dvěma týdny hlásil uživatel 5" stroje s MTF-02P na ArduPilotu
  **oscilace výšky mezi 0,8 a 1,4 m** místo stabilního position holdu. [fórum]

Ta poslední věc je přesně náš letový profil (1 m) a přesně to, na čem stojí naše
odmítání podlahy — bere výšku z dálkoměru. Než se koupí zbytek, stálo by za to
najít, jak to ten člověk vyřešil.

**Alternativy:** Matek 3901-L0X (levnější, dálkoměr jen 2 m — **na náš 1m let
málo**), HereFlow (dražší, CAN). MTF-02P je v téhle hmotnosti (1,5 g) prakticky
bez konkurence.

---

## Lidar: LDRobot LD06

**Kupovat:** dovoz, [Sunhokey](https://sunhokey.cn/products/dtof-lidar-ld06),
75,50 USD. Kusovník správně říká **až po kontrole fotky štítku a konektoru**.

**Zkušenosti:**

- ArduPilot ho podporuje nativně jako Lidar360. [dok]
- **Venku nefunguje**; varianta LD06-**LD** má vyšší odolnost proti světlu a v
  testu dávala použitelná data i za jasu. [fórum] Nás se to netýká, letíme uvnitř.
- Oficiální ovladač měl chyby, kolem kterých vznikly komunitní forky. [fórum]
  Pokud pojede lidar na palubním počítači, počítej s tím, že si ovladač budeš
  vybírat.

**Alternativy:**

| Model | Dosah | Cena | Poznámka |
| --- | ---: | ---: | --- |
| **LD06** | 12 m | ~80 USD | náš výchozí, 4,5 kHz, 5–13 Hz |
| **LD19** | 12 m | ~70 USD | novější verze LD06, navíc spodní montážní deska; **levnější a novější** |
| **STL27L** | 25 m | ~160 USD | 21,6 kHz měření, přesnost ±20 mm do 8 m; dvojnásobná cena |
| RPLidar C1 | 12 m | ~90 USD | jiný výrobce, jiný protokol, ArduPilot ho zná |

**LD19 stojí za zvážení jako výchozí volba místo LD06** — je to jeho novější
verze, je levnější a ArduPilot ho vede pod stejnou podporou. Kusovník ho zatím
zakazuje kupovat „bez ověření hmotnosti, rozměrů a UART protokolu", což je
správná opatrnost; tohle je důvod to ověření udělat, ne důvod ho neudělat.

STL27L má **21,6 kHz proti 4,5 kHz** — pětkrát hustší data. Pro mapování bytu by
to bylo znatelně lepší, ale je to dvojnásobek ceny a víc dat po tom UARTu.

---

## Video: RunCam WiFiLink 2 vs. EMAX Wyvern Link Alpha

Kusovník správně říká **koupit právě jednu**.

| | RunCam WiFiLink 2 | EMAX Wyvern Link Alpha |
| --- | --- | --- |
| Cena | 3 349 Kč [Rotorama CZ](https://www.rotorama.cz/product/runcam-wifilink-2) | 82,39 € [Rotorama EU](https://www.rotorama.de/product/emax-openipc-wyvern-link-alpha-200mw-vtx) |
| Hmotnost | 25 g (30 s ventilátorem) | 13,76 g |
| Sestava | ~306 g | ~294 g |

**Zkušenosti s OpenIPC obecně:**

- Latence **kolem 25–30 ms** za dobrých podmínek, ale silně závisí na výkonu
  zařízení, na kterém se to dívá. [fórum]
- **Chlazení není detail.** Jednotka má ventilátor a bez něj se přehřívá; v
  dokumentaci OpenIPC je dokonce rada „zkontroluj, jestli je WiFi karta horká —
  když je studená, vysílání neběží". [dok] Na ducted whoopu je ta jednotka pod
  kabinkou, kde neproudí vzduch.
- **Není to plug-and-play.** Proti DJI nebo Walksnailu se musí nakonfigurovat
  několik nástrojů; vkládání SD karty je kvůli poloze desek otrava a celé to
  působí spíš jako rozdělaná práce než hotový produkt. [fórum]

**Doporučení:** pro tenhle projekt je Wyvern lepší volba — je o 11 g lehčí, což
je na 270g stroji přes 4 % hmotnosti, a video tu není hlavní funkce. Ale otevřená
kontrola spotřeby platí dál: **RunCam u srovnatelné jednotky uvádí až 15 W**, a
to je jediné číslo v celém energetickém rozpočtu, které chybí — a zároveň
největší spotřebič mimo motory.

---

## Baterie: Tattu R-Line 4S LiHV 750 mAh

**Kupovat:** [RCTech](https://www.rctech.de/tattu-lipo-akku-4s-750-mah-95c-hv-xt30-long),
19,90 €/ks, **long** provedení, 1–3 ks.

**Alternativy:** [fórum] shodně říká, že **GNB je za stejné peníze lepší hodnota
než Tattu**, a doporučuje se i Pulse. CNHL je levnější. Rozdíly mezi značkami
jsou v téhle třídě menší než rozdíly mezi kusy.

**Co je důležitější než značka:** kusovník trvá na **podlouhlém (long)
provedení** a na **LiHV**, protože s tím počítá CAD i vyvážení. Nabíječka musí
umět LiHV 4S s koncovým napětím 17,4 V — běžný LiPo režim baterii nedobije.

Kolik kusů: při naměřené výdrži **3,5–5 minut** (viz níž) je jedna baterie na
jeden pokus. Tři jsou minimum, aby se dalo v jednom odpoledni něco vyzkoušet.

---

## Co v kusovníku chybí

1. **Palubní počítač** a jeho napájení. Bez něj se sken nedostane do ROS.
2. **Redukce ZH1.5T-4P → JST-SH** pro LD06, nebo protikus s vodiči na
   přepájení. Kusovník to zmiňuje, ale nemá to jako položku k objednání.
3. **Nabíječka s LiHV 4S režimem**, smoke stopper, multimetr — jsou zmíněné jako
   „vybavení mimo letovou hmotnost", ale bez nich se nedá začít.
4. **Přijímací strana videa** (WiFi karta pro pozemní stanici) — u OpenIPC to
   není součást vysílací sady.

---

## Výdrž: kolik toho vlastně nalítá

Spočítáno z kusovníku [repo]: 269 g s lidarem, 4S LiHV 750 mAh = 11,4 Wh,
ideální indukovaný výkon 20 W, s reálnou účinností 3" vrtulí a duktů 95–130 W na
motory plus 5–20 W avioniky.

**3,6 až 5,5 minuty**, realisticky 4–5, s rezervou na přistání **3,5 minuty
užitečného letu**. Pětipokojový byt na jednu baterii nevyjde — vyjdou dva až tři
pokoje. Podrobněji i s tím, co je tam skutečná překážka (šířka dveří, ne
baterie), je to rozebrané v backlogu.

---

## Doporučené pořadí rozhodnutí

1. **Rozhodnout palubní počítač.** Mění hmotnost, spotřebu i to, kam vede kabel
   od lidaru. Všechno ostatní na tom závisí.
2. **Ověřit LD19 proti LD06.** Novější a levnější; když sedí, ušetří se a
   získá se lepší podpora.
3. **Zavřít otázku tahu na zkušebním stavu**, než se objedná víc než jedna sada
   motorů. Zkušenost s původním CineLogem je varování, které stálo někoho jinému
   za baterii.
4. **Najít, jak dopadly ty oscilace výšky s MTF-02P.** Je to náš letový profil.
5. Teprve pak objednávat video, které je nejdražší jedna položka.

---

## Zdroje

- [ArduPilot: LDRobot LD-06 Lidar](https://ardupilot.org/copter/docs/common-ld06.html)
- [ArduPilot: Simple Object Avoidance](https://ardupilot.org/copter/docs/common-simple-object-avoidance.html)
- [ArduPilot: MicoAir743v2](https://ardupilot.org/copter/docs/common-MicoAir743v2.html)
- [ArduPilot: ROS 2 Interfaces](https://ardupilot.org/dev/docs/ros2-interfaces.html)
- [ArduPilot: Cartographer SLAM with ROS 2](https://ardupilot.org/dev/docs/ros2-cartographer-slam.html)
- [AP_DDS README](https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/README.md)
- [MP very slow with MicoAir H743 V2](https://discuss.ardupilot.org/t/mp-very-slow-with-micoair-h743-v2/142709)
- [MicoAir H743 V2: serial ports weren't displaying correctly](https://discuss.ardupilot.org/t/micoair-h743-v2-serial-ports-werent-displaying-correctly/142753)
- [CrashDump MicoAir v2 H743 - Copter 4.6](https://discuss.ardupilot.org/t/crashdump-micoair-v2-h743/143262)
- [Optical flow and rangefinder indoor position hold - altitude oscillations](https://discuss.ardupilot.org/t/ardupilot-5-inch-drone-using-optical-flow-and-rangefinder-for-indoor-position-hold-altitude-oscillations/145352)
- [MicoAir MTF-02P product page](https://micoair.com/optical_range_sensor_mtf-02p/)
- [Oscar Liang: GEPRC Cinelog30 V3 review](https://oscarliang.com/geprc-cinelog30-v3/)
- [IntoFPV: Cinelog 30 murder](https://intofpv.com/t-cinelog-30-murder)
- [Oscar Liang: RunCam WiFiLink OpenIPC](https://oscarliang.com/runcam-wifilink-openipc/)
- [OpenIPC wiki: RunCam WiFiLink](https://github.com/OpenIPC/wiki/blob/master/en/fpv-runcam-wifilink-openipc.md)
- [wfb-ng README](https://github.com/svpcom/wfb-ng/blob/master/README.md)
- [Waveshare: DTOF LIDAR STL27L](https://www.waveshare.com/wiki/DTOF_LIDAR_STL27L)
- [awesome-2d-lidars](https://github.com/kaiaai/awesome-2d-lidars)
- [Oscar Liang: micro FPV batteries](https://oscarliang.com/whoop-toothpick-lipo-battery/)
- [Oscar Liang: BetaFPV ELRS Nano TX/RX](https://oscarliang.com/betafpv-elrs-nano-tx-rx/)
- [CNX: Pi Zero 2 W vs Radxa Zero](https://www.cnx-software.com/2021/11/01/raspberry-pi-zero-2-w-vs-radxa-zero-features-and-benchmarks-comparison/)
- [Autonomous indoor drone navigation (ArduPilot/PX4 + ROS2 + Pi)](https://github.com/ahmedeltaher/Autonomous-drone-navigation)

# Porovnání s rešerší roje

Obě rešerše vznikly **19. 9. 2026** nad stejným repozitářem a nezávisle na sobě.
Překrývají se v kapitole o jednom dronu — [reserseRoju/01](../reserseRoju/01_proc_3palcove_drony.md)
a [/02](../reserseRoju/02_teorie_rizeni_jednoho_dronu.md) proti
[reserseDronu/01](./01_velikost_a_vrtule.md) a [/02](./02_algoritmy_rizeni.md).
Tenhle dokument ten překryv rozebírá: co obě říkají stejně, kde se rozcházejí,
a co má každá navíc.

**Předem: rešerše roje je dobrá práce.** Má správnou vrstevnatou stavbu,
poctivou bibliografii s uvedenými limity přenositelnosti a na konci tabulku
„co je doložené a co je doporučení autora", což je přesně to, co většina
podobných dokumentů nedělá. Nic níž není argument pro její zahození.

## 1. Co dělá každá z nich

| | reserseRoju | reserseDronu |
| --- | --- | --- |
| předmět | skupina strojů | jeden stroj |
| těžiště | koordinace, grafy, bezpečné rozestupy | pohon, ladění, filtry, systémy |
| zdroje | akademická literatura roje | experimenty s vrtulemi, dokumentace ArduPilotu, čísla z repozitáře |
| vztah k repozitáři | návrh, co postavit dál | rozbor toho, co už je postavené a změřené |
| nejsilnější část | 03 a 04 (algoritmy roje, architektura) | 01 a 02 (teorie hybnosti proti vlastním datům, rozpočet fáze) |

Nejsou to konkurenční dokumenty. Jsou to dvě patra téhož a **rešerše roje své
spodní patro potřebuje**: její vlastní úvod říká, že rojový algoritmus
předpokládá spolehlivé sledování rychlosti u každého agenta.

## 2. V čem se shodujeme

| Tvrzení | Kde to je u obou |
| --- | --- |
| „3 palce" nic neurčuje kromě průměru vrtule | Roj 01 §2, Dron 01 §1 |
| větší disk je při stejném tahu účinnější | Roj 01 (teorie hybnosti), Dron 01 §3 |
| duct je ochrana, ne doložená účinnost | Roj 01, Dron 01 §5 |
| výchozí zisky ArduPilotu jsou pro mnohem větší stroj | Roj 02 §4.1, Dron 02 §2 |
| mixer musí řešit saturaci a wind-up | Roj 02 §3, Dron 02 §2 |
| poloha z optického toku driftuje a je to fyzika, ne nastavení | Roj 02 §5, Dron 02 §8 |
| rychlostní rozhraní vyžaduje watchdog a definovaný timeout | Roj 02 §9, Dron 02 §9 |
| naučené politiky až po měřitelném klasickém baseline | Roj 02 §7, Dron 02 §10 |
| bez měření na železe nemá žádné číslo platnost | obě, opakovaně |

Ta shoda vznikla nezávisle a je to užitečná informace sama o sobě: **obě cesty
končí u stejné překážky, kterou je chybějící měření na hardwaru.**

## 3. Kde se rozcházíme

### 3.1 Baseline drak je o jeden stroj pozadu

Rešerše roje počítá všude s 3" strojem o 0,306 kg a z něj odvozuje kolizní
obálku 0,1667 m i tabulku kinetické energie. Na větvi, na které leží, je ale
**druhý plně zkalibrovaný drak**: Pavo20 Pro 4S, 2,2", 0,22934 kg, s vlastním
parametrovým souborem, vlastním modelem a vlastním naměřeným sweepem. Dokument
ho zmiňuje jen jako odkaz ve zdrojích.

Důsledky nejsou kosmetické:

| Veličina | Roj uvádí (CineLog) | Pavo20 |
| --- | ---: | ---: |
| dosah špičky rotoru | 0,08335 m | 0,06107 m |
| geometrické minimum dvou strojů | 0,1667 m | **0,1221 m** |
| hmotnost pro tabulku energie | 0,306 kg | 0,229 kg |
| podíl 10 g navíc na hmotnosti | 3,27 % | **4,36 %** |

**Doporučení:** rozestup a energii psát jako funkci draku, ne jako konstantu.
Jedna tabulka se dvěma sloupci stojí stejně místa a nezastará při příštím
rozhodnutí o rámu.

### 3.2 „Menší je obratnější" má v tomhle projektu měřený protipříklad

Rešerše roje staví kapitolu 01 na škálovacím argumentu: `m ~ L³`, `J ~ L⁵`,
úhlové zrychlení roste zhruba jako `1/L` až `1/L²`, s odkazem na Kushleyeva a
kol. Fyzikálně to platí — **pro geometricky podobné zmenšení.**

Tenhle projekt geometricky nezmenšuje. Nechává stejný náklad a zmenšuje drak, a
výsledek jde proti očekávání:

```text
CineLog30 V3 (3")    689 rad/s²
Pavo20 Pro 4S (2,2") 583 rad/s²
```

Menší stroj má **o 15 % nižší** úhlovou autoritu, protože ztratil rameno a tah
rychleji než setrvačnost. A co víc — přidání jednoho 42g senzoru na stožár
zdvojnásobilo setrvačnost v pitchi a posunulo nejhorší náklon při vzletu z 6,5°
na 24,0° proti limitu 25°, tedy **desetkrát větší efekt než celá změna draku.**

To argument rešerše roje nevyvrací, ale otáčí jeho směr: pro tenhle projekt
není obratnost vlastností velikosti, ale **umístění nákladu**. Kapitola, která
má rozhodnout o volbě platformy, by to měla říct jako první, ne jako výhradu.

### 3.3 Seznam „co změřit" nerozlišuje, co už v repozitáři je

Rešerše roje má v 02 §10 seznam devíti věcí, které se mají změřit před rojovým
letem. Seznam je věcně dobrý a většina jeho položek skutečně chybí. Je ale psaný
jako čistý list, a repozitář čistý list není:

| Položka seznamu | Skutečný stav |
| --- | --- |
| chyba sledování trajektorie | na úrovni **orientace** změřená (RMS 0,74–0,86° přes mřížku zisků), na úrovni trajektorie ne |
| maximální stabilní dynamika | změřená **mez ladění** rate loopu (0,065–0,080), ne maximální rychlost a akcelerace |
| rozdíl mezi kusy | v simulaci existuje jako rozdíl mezi draky, i s nástrojem (`OPENIPC_AIRFRAME=pavo20 scripts/sweep_rate_gains.sh`) |
| chování při ztrátě senzoru a baterie | částečně hotové: `BATT_FS_*`, `check_sensor_dropout.sh`, `check_low_battery_landing.sh` |
| brzdná dráha, latence, drift, tahová rezerva, teploty | **skutečně nezměřeno**, ani v simulaci |

Rozdíl mezi „tohle se musí změřit" a „tohle je částečně změřené v simulaci a
chybí na železe" je celý rozdíl mezi seznamem přání a plánem. **Doporučení:**
psát ten seznam jako diff proti tomu, co v repozitáři je, a u každé položky
uvést, jestli chybí měření, nebo jen jeho hardwarová verze.

### 3.4 Chybí tři věci, které o letu malého quadu rozhodují

Kapitola 02 rešerše roje projde model, mixer, kaskádu, estimaci, trajektorie a
alternativy — a nikde nezmíní:

1. **Linearizaci tahu.** `MOT_THST_EXPO` mění zisk smyčky s plynem. V simulaci
   je 1,0, což je identita modelovaného rotoru; kdo tu hodnotu přenese do FC,
   dostane stroj, který je ve visu naladěný a při stoupání kmitá.
2. **Kompenzaci propadu napětí.** Mezi plnou a vybitou 4S LiHV se zisk smyčky
   mění faktorem `(14,0/17,4)² = 0,65`. To je větší změna než celý rozdíl mezi
   oběma draky.
3. **Rozpočet fáze a filtry.** Dokument má jeden odstavec („Vibrace a filtry
   přidávají fázi"), který je správný, ale nedojde k číslu ani k parametru.
   Přitom ani jeden parametrový soubor v repozitáři nenastavuje
   `INS_GYRO_FILTER`, `ATC_RAT_*_FLTD/FLTT` ani harmonický notch — a bez nich
   naměřená mez 0,065–0,080 na železe neplatí.

Tohle není akademický spor. Je to rozdíl mezi rešerší, podle které se dá naladit
stroj, a rešerší, podle které se dá o ladění mluvit.

### 3.5 V přehledu alternativ chybí INDI

Tabulka v 02 §7 má PID, LQR, MPC, geometrické řízení, adaptivní a naučené.
Chybí v ní **INDI** — metoda, která nahrazuje modelové členy měřeným úhlovým
zrychlením a je proto robustní vůči neznámé setrvačnosti, tahu a nákladu.
Pro stroj, jehož `Ct` je zpětně dopočtený z jiného draku a jehož setrvačnost se
mění s každým senzorem, je to nejrelevantnější alternativa v celé tabulce.

Chybí i její praktický předstupeň: **řízení s RPM zpětnou vazbou** z ESC, které
je na kupované desce (AM32) k dispozici a které je současně podmínkou
dynamického notche.

### 3.6 Teorie hybnosti se zastaví o krok dřív

Rešerše roje spočítá plochu disku 0,01824 m² a plošné zatížení 164 N/m² — obojí
správně. Chybí tři kroky, které z toho dělají rozhodovací nástroj:

- **křivka při konstantní hmotnosti** (33,5 W na 2,2" proti 24,6 W na 3" a
  14,8 W na 5" pro tentýž náklad), ze které je vidět, že tam žádné optimum není
  a že velikost vrtule je vždycky kompromis s tím, co se vejde;
- **Reynoldsova výhrada** — obě vrtule projektu pracují kolem `Re ≈ 25 000`,
  tedy pod rozsahem 50 000–100 000, ve kterém existují systematická měření;
- **poznámka, že to simulace nemůže ukázat**, protože model Pavo20 přebírá `Ct`
  z CineLogu, takže rozdíl v účinnosti mezi 3" a 2,2" v ní z definice není.

### 3.7 Drobnosti

- **Tabulka ductů** je věrohodná, ale nemá jediný zdroj, zatímco na přesně téhle
  třídě vrtulí existují měření vlivu vůle špičky.
- **Tabulka kinetické energie** končí u translační energie. Rotační energie
  jedné vrtule ve visu je řádově jednotky joulů, tedy víc než celý stroj letící
  2 m/s — a pro indoor bezpečnost je to relevantnější číslo.
- **`GUID_TIMEOUT`** je zmíněný s výchozími 3 s a výzvou hodnotu odvodit; z
  tabulky brzdné dráhy plyne, že při 1 m/s to jsou nejméně 3 metry doletu, což
  je v bytě celá místnost.

## 4. Co má rešerše roje navíc a co z ní převzít

Bez výhrad a bez ekvivalentu v téhle rešerši:

- **vrstvení L0–L5** a pravidlo, že se mezi vrstvami nesmí přeskakovat;
- **grafový formalismus** (Laplacián, `lambda_2`) a seznam předpokladů, které
  školní důkaz konsenzu porušují v reálném provozu;
- **přehled rodin formací** (leader–follower, virtuální struktura, relativní
  offsety, vzdálenostní) včetně otázky rigidity;
- **rozklad bezpečného rozestupu** na geometrii, lokalizační chybu, latenci,
  brzdnou dráhu a rezervu — to je dobře postavená rovnice a má se použít;
- **stavový automat poruch** a poznámka, že „všichni přistaňte" je v husté
  formaci nebezpečný povel;
- **tabulka QoS podle významu dat** a upozornění, že QoS není watchdog;
- **ověřený AP_DDS namespacing** (`DDS_USE_NS=1` → `v<MAV_SYSID>`) ze zdrojového
  kódu v repozitáři, ne z dokumentace;
- **fázovaný plán experimentů A–F** a testovací matice s deterministickým seedem;
- **tabulka „co je doložené a co je doporučení"** — nejlepší jednotlivý nápad v
  celém dokumentu; převzal jsem ho sem.

## 5. Co má tahle rešerše navíc

- srovnání obou draků projektu v jedné tabulce, včetně naměřených sweepů;
- křivka ideálního výkonu proti průměru vrtule při konstantní hmotnosti;
- Reynoldsův rozbor a důsledek pro katalogová čísla i pro kalibraci modelu;
- rozpočet fáze v číslech a z něj plynoucí role D-členu a notche;
- linearizace tahu a kompenzace napětí jako dva konkrétní zdroje změny zisku;
- tabulka parametrů, které se nesmí přenést ze simulace do letového kontroléru;
- INDI, RPM zpětná vazba a současný stav naučeného nízkoúrovňového řízení;
- koexistence tří rádií na jedné palubě;
- brzdná dráha jako funkce povoleného náklonu.

## 6. Co s tím překryvem udělat

Návrh, seřazený podle poměru užitku k práci:

1. **Nechat obě složky.** Dělí se čistě: `reserseRoju` je koordinace, `reserseDronu`
   je stroj. Sloučení by vyrobilo dokument, který nikdo nedočte.
2. **Prokřížit odkazy.** V `reserseRoju/01` a `/02` odkázat na
   `reserseDronu/01` a `/02` pro pohon, ladění a filtry; odsud zpět na roj pro
   vrstvení a rozestupy. Dvě věty na každý dokument.
3. **Jedna sdílená tabulka „co je změřeno".** Obě rešerše si dnes vedou vlastní
   seznam chybějících měření a ty seznamy se rozejdou. Patří do `workflow/`,
   vedle backlogu, a obě rešerše na ni mají odkazovat.
4. **Parametrizovat drak.** Všechna čísla odvozená z hmotnosti a geometrie psát
   pro oba draky, nebo je odvozovat z jednoho místa. Dnes jsou v `reserseRoju`
   napevno pro CineLog.
5. **Doplnit do `reserseRoju/02 §7` řádek INDI** a do §10 rozlišení
   změřeno/nezměřeno. To jsou dvě nejmenší změny s největším dopadem.

## 7. Tvrzení, stav, důkaz

| Tvrzení | reserseRoju | tato rešerše | Stav |
| --- | --- | --- | --- |
| menší kvadrokoptéra je obratnější | ano, z literatury | **ne pro tenhle případ** | v projektu měřeno: 583 proti 689 rad/s² |
| větší disk je účinnější | ano | ano, s křivkou | doloženo teorií hybnosti |
| duct zvyšuje účinnost | „nezaručeně" | „neznámé, neměřeno" | shoda; nikdo to tady neměřil |
| zisky se musí měřit, ne počítat | ano | ano | **hotovo v simulaci**, chybí na železe |
| mez zisku je 0,065–0,080 | neuvádí | ano | měřeno na obou dracích |
| `MOT_THST_EXPO 1.0` platí i na železe | neřeší | **ne** | odvozeno z modelu, ne z vrtule |
| poloha driftuje bez absolutní korekce | ano | ano | vlastnost senzorové sady |
| sken se dostane do ROS | „neplatí v současné cestě" | „jen přes video jednotku" | shoda, ověřeno ve zdrojáku |
| 3" je vhodná volba pro tenhle projekt | „výzkumný člen roje, ne lehký agent" | „konzervativní volba; 2,2" je ta pod 250 g" | obojí platí, jiná kritéria |
| projekt je připravený na fyzický roj | ne | ne | shoda |

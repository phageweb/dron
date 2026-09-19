# Velikost, vrtule a co za to

## 1. Co „3 palce" určuje a co ne

Označení fixuje jediný rozměr:

```text
3" = 76,2 mm průměru, poloměr 38,1 mm
```

Neurčuje hmotnost, rozvor, rezervu tahu, dobu letu, hlučnost ani kolizní
obálku. Tenhle projekt je toho vlastním důkazem: pod stejným nákladem — LD06,
OpenIPC video, optický tok, H7 deska — má dva plně zkalibrované draky, které se
v průměru vrtule liší o 27 % a v hmotnosti o 25 %.

| Veličina | CineLog30 V3 | Pavo20 Pro 4S | zdroj |
| --- | ---: | ---: | --- |
| průměr vrtule | 76,2 mm | 55,88 mm | model |
| rameno motoru | 45,25 mm | 33,13 mm | model |
| hmotnost | 0,306 kg | 0,22934 kg | kusovník |
| max. tah na rotor | 3,485 N | 1,980 N | kalibrace rotoru |
| tah / hmotnost | 4,65 | 3,52 | výpočet |
| podíl tahu ve visu | 0,215 | 0,284 | výpočet |
| `MOT_THST_HOVER` | 0,46 | 0,53 | parametry |
| otáčky ve visu | ≈ 17 600 RPM | ≈ 28 400 RPM | výpočet |
| rychlost špičky ve visu | 70 m/s | 83 m/s | výpočet |

Poslední tři řádky jsou pointa celé kapitoly. Menší vrtule musí ten samý tah
vyrobit **rychleji otáčeným menším diskem**, a všechno nepříjemné, co dál
následuje — příkon, hluk, vibrace, opotřebení ložisek, Reynoldsovo číslo —
vychází z nich.

## 2. Škálovací zákony a proč se tady nesmí použít přímo

Klasický argument pro malé drony zní: při geometricky podobném zmenšení s
charakteristickou délkou `L` platí `m ~ L³`, `J ~ L⁵`, a při konstantní rychlosti
špičky `T ~ L²`, takže moment `~ L³` a úhlové zrychlení `~ L³/L⁵ = 1/L²`. Malý
stroj je tedy v úhlové ose dramaticky rychlejší.

Platí to, a [rešerše roje](../reserseRoju/01_proc_3palcove_drony.md) to cituje
správně. **Jenže tenhle projekt nikdy geometricky nezmenšuje.** Zmenšuje drak a
nechává na něm stejný náklad:

- LD06 váží 42 g na obou strojích, tedy 13,7 % CineLogu a 18,3 % Pavo20;
- video jednotka, deska i přijímač jsou identické;
- baterie je v cílové variantě tatáž 4S LiHV.

Proto reálná čísla škálovací zákon nepotvrzují ani nevyvracejí — měří něco
jiného:

```text
CineLog30 V3   2 · 3,485 N · 0,04525 m = 0,3154 N·m / 0,000458 = 689 rad/s²
Pavo20 Pro 4S  2 · 1,980 N · 0,03313 m = 0,1312 N·m / 0,000225 = 583 rad/s²
```

Menší stroj má **nižší** úhlovou autoritu, ne vyšší, protože ztratil rameno a
tah rychleji, než ztratil setrvačnost. Škálovací zákon předpokládá, že s draky
se zmenšuje i to, co vezou; tady se nezmenšuje nic.

## 3. Teorie hybnosti proti vlastním číslům projektu

Ideální indukovaný výkon ve visu:

```text
P_i = T^(3/2) / sqrt(2 · rho · A),   A = 4 · pi · r²
```

Tabulka pro **konstantní hmotnost 0,306 kg**, tedy otázka „co stojí zmenšení
vrtule, když náklad zůstane":

| Vrtule | Plocha disku | `P_i` ideál | Nosnost na ideální watt |
| ---: | ---: | ---: | ---: |
| 1,6" | 51,9 cm² | 46,1 W | 6,6 g/W |
| 2,2" | 98,1 cm² | 33,5 W | 9,1 g/W |
| 2,5" | 126,7 cm² | 29,5 W | 10,4 g/W |
| **3,0"** | **182,4 cm²** | **24,6 W** | **12,4 g/W** |
| 3,5" | 248,3 cm² | 21,1 W | 14,5 g/W |
| 4,0" | 324,3 cm² | 18,4 W | 16,6 g/W |
| 5,0" | 506,7 cm² | 14,8 W | 20,7 g/W |

Vztah je hladký a jednosměrný: `P_i ~ 1/D`. **Žádné optimum tam není** — pokud
jde jen o vis, větší vrtule vyhrává vždycky. Optimum vzniká teprve tím, že
větší vrtule potřebuje větší rám, delší ramena, těžší motory a přestane se
vejít do místnosti.

Skutečné dvě konfigurace projektu, každá se svou hmotností:

| Drak | Hmotnost | Disk | `P_i` | g/W | Plošné zatížení |
| --- | ---: | ---: | ---: | ---: | ---: |
| CineLog30 V3, 3" | 0,306 kg | 182,4 cm² | 24,6 W | 12,4 | 165 N/m² |
| Pavo20 Pro, 2,2" | 0,229 kg | 98,1 cm² | 21,8 W | 10,5 | 229 N/m² |

Tohle je nejdůležitější číslo celé rešerše: **zmenšení draku o 25 % hmotnosti
koupilo 12 % ideálního výkonu**, protože polovina disku vzala skoro všechno, co
ušetřená hmota dala. Dokument [Pavo20](../spec/realna_stavba_dronu/10_pavo20.md)
dochází ke stejnému závěru z jiné strany (na 3S je výdrž 2,4 min proti 3,5) a
formuluje ho správně: **rozhoduje baterie, ne rám.**

Plošné zatížení stoupá z 165 na 229 N/m² a to není kosmetika. Vyšší plošné
zatížení znamená rychlejší indukované proudění, hlasitější stroj, silnější
recirkulaci u podlahy a menší toleranci k poryvu — a při visu nad kobercem i
víc zvířeného prachu do ductů.

## 4. Reynoldsovo číslo: obě vrtule jsou pod publikovanými daty

Při visu vychází rychlost v 75 % poloměru 52 m/s (CineLog) a 62 m/s (Pavo20).
S odhadnutou tětivou listu 8 a 6 mm to dává

```text
Re ≈ 28 000   (3",  chord 8 mm)
Re ≈ 25 000   (2,2", chord 6 mm)
```

Systematická měření malých vrtulí z UIUC pracují s rozsahem přibližně
**50 000 až 100 000** a i uvnitř něj hlásí účinnosti o **7,5 až 15 % nižší** než
u větších průměrů; se zdvojnásobením Reynoldsova čísla není neobvyklé získat
přes 10 % účinnosti ([Brandt & Selig 2011](https://m-selig.ae.illinois.edu/pubs/BrandtSelig-2011-AIAA-2011-1255-LRN-Propellers.pdf),
[Deters et al. 2014](https://m-selig.ae.illinois.edu/pubs/DetersAnandaSelig-2014-AIAA-2014-2151.pdf)).

Praktické důsledky pro tenhle projekt jsou tři a všechny nepříjemné:

1. **Obě vrtule leží pod rozsahem, ve kterém existují publikovaná data.**
   Extrapolace shora je optimistická: klesá vztlak, roste odpor a předpověď
   přestává být spolehlivá.
2. **Katalogový statický tah není účinnost.** BetaFPV publikuje pro LAVA 1104 +
   D2.2-3 přes 230 g tahu, ale ne příkon v pracovním bodě. Z jednoho bodu
   maximálního tahu nelze spočítat ani výdrž, ani `MOT_THST_EXPO`.
3. **Simulace to netuší.** Model Pavo20 přebírá `Ct = 0,2103` zpětně dopočtený
   z CineLogu, aby se draky lišily geometrií a ne předpokladem. Je to čistý
   postup, ale znamená, že **rozdíl v účinnosti mezi 3" a 2,2" v simulaci
   neexistuje** — nemůže z ní tedy vypadnout.

## 5. Ducty: ochrana, kterou nelze počítat jako účinnost

Teorie ductu slibuje hodně: zrušení koncového víru, difuzor, který zvětší
efektivní plochu disku, a část tahu nesenou samotným pláštěm. Experimentální
práce na přesně téhle třídě — shrouded 5" Gemfan vrtule, NACA 7312 plášť,
vůle špičky 0,6 %, 1,11 % a 3,6 % — ukazuje, že velikost přínosu je funkcí
expanzního poměru a vůle špičky, ne přítomnosti krytu
([Rapid Design Process of Shrouded Rotors](http://eprints.gla.ac.uk/227960/2/227960.pdf)).

Cinewhoopový duct ale není difuzor. Je to vstřikovaný kryt, jehož primární
funkce je mechanická a jehož vůle je dána výrobní tolerancí, ne aerodynamickým
návrhem. Proto:

| Vlastnost | Co duct doopravdy dělá tady |
| --- | --- |
| kontakt se stěnou | zásadní přínos; lehký dotyk nekončí zastavenou vrtulí |
| ochrana okolí | zásadní přínos; jediné, co dělá indoor let v bytě obhajitelným |
| účinnost | **neznámá**; může být kladná i záporná, nikdo ji tady nezměřil |
| hmotnost a setrvačnost | jistá ztráta; hmota je daleko od osy |
| chování u stěny a podlahy | mění se; recirkulace v ductu není v žádném modelu |
| akustika | horší; vyšší otáčky a užší kanál |

**Pravidlo:** duct se v celém projektu smí započítat jako ochrana a jako hmota.
Jako účinnost se smí započítat teprve po tahové stolici, a to zvlášť pro každou
kombinaci vrtule a ductu.

## 6. Obratnost: rozhoduje náklad, ne vrtule

Repozitář má na tohle tvrdý důkaz. Přidání LD06 (42 g na stožáru 46 mm dopředu
a 50 mm nahoru) **zhruba zdvojnásobilo setrvačnost v pitchi** a stávající
naladění přestalo platit: při `ATC_RAT_*_P 0.027` vzrostl nejhorší náklon při
guided vzletu z 6,5 na 24,0 stupně, proti limitu kontroly 25 stupňů.

Naproti tomu přechod na o 15 % nižší autoritu (689 → 583 rad/s²) **naměřenou
mez ladění neposunul**:

| Rate gain | Překmit | RMS chyba | Zvonění |
| ---: | ---: | ---: | ---: |
| 0,040 | 4,5 % | 0,86° | 5 |
| 0,065 | 4,3 % | 0,74° | 4 |
| 0,080 | 49,6 % | 5,33° | 162 |
| 0,095 | 71,6 % | 7,50° | 55 |
| 0,110 | 82,5 % | 7,81° | 39 |

(Pavo20, `OPENIPC_AIRFRAME=pavo20 scripts/sweep_rate_gains.sh`. Na CineLogu
vychází mez do stejné dvojice 0,065–0,080.)

Ten výsledek je poctivě zapsaný i se svou slabinou: krok mřížky z 0,065 na
0,080 je 23 %, zatímco hledaný posun byl 18 %, takže **mřížka ten rozdíl vidět
nemůže**. Není to důkaz, že autorita nerozhoduje; je to důkaz, že v téhle
otázce je 15 % změny draku menší efekt než 100 % změny setrvačnosti od jednoho
senzoru.

**Závěr pro stavbu: umístění nákladu je řídicí parametr, ne kosmetika.** Gram
blízko těžiště stojí nic; gram na konci stožáru stojí naladění.

## 7. Energie, výdrž a proč malý dron neletí déle

Výdrž je energie děleno příkonem, a v obou členech je průměr vrtule až druhý
hráč:

- **Energie** je vlastnost baterie. 4S LiHV 750 mAh ≈ 11,4 Wh; 3S 550 mAh ≈
  6,1 Wh. To je faktor 1,9 a žádná vrtule ho nedožene.
- **Fixní odběr** nesouvisí s letem vůbec. RunCam u srovnatelné jednotky uvádí
  až 15 W; LD06 a deska přidají další. Na 6,1Wh baterii je to dvojnásobný podíl
  než na 11,4Wh.
- **Letový příkon** je ideálních 22–25 W dělených celkovou účinností vrtule,
  motoru a ESC. U 3" ducted vrtule na nízkém Reynoldsovi je to násobek, ne
  přirážka.

Proto tabulka z [Pavo20](../spec/realna_stavba_dronu/10_pavo20.md) vychází, jak
vychází: 205g Pavo na 3S letí **kratčeji** než 294g CineLog na 4S. Menší dron s
menší baterií neletí déle.

### Rezerva tahu je druhá strana téhož

CineLog visí na 21,5 % maximálního tahu, Pavo20 na 28,4 %. Obě čísla jsou
zdravá, ale nejsou stejná:

- vyšší rezerva znamená víc dosažitelného náklonu, tedy kratší brzdnou dráhu;
- nižší rezerva znamená dřívější saturaci mixéru při současném požadavku na
  výšku a moment — přesně ten stav, který v tomhle repozitáři jednou skončil
  odletem do 54 m;
- rezerva klesá s vybíjením baterie, takže konec letu je jiný stroj než začátek.

## 8. Bezpečnost: nejvíc energie nese vrtule, ne let

Translační kinetická energie při indoor rychlostech je malá:

| Rychlost | 0,306 kg | 0,229 kg |
| ---: | ---: | ---: |
| 0,5 m/s | 0,038 J | 0,029 J |
| 1,0 m/s | 0,153 J | 0,115 J |
| 2,0 m/s | 0,612 J | 0,459 J |

Rotační energie **jedné** vrtule ve visu je ale podle setrvačností z modelu
řádově 1,4 J (CineLog) a 3,5 J (Pavo20) — tedy víc než celý stroj letící 2 m/s.
Je to řádový odhad a jedna jeho slabina stojí za zapsání: **oba modely mají
rotoru `izz` 8·10⁻⁷ kg·m²**, přestože vrtule Pavo20 je o 27 % menší v průměru a
v modelu má 2,6× menší hmotnost (0,58 g proti 1,5 g). Setrvačnost menší vrtule
tedy nebyla přepočítaná, jen zkopírovaná, a číslo výš je proto pro Pavo20 spíš
horní mez. Na letovou dynamiku to vliv nemá (rotory jsou v `MulticopterMotorModel`
kinematické), na tuhle úvahu o energii ano.

Směr závěru to ale nemění a odpovídá tomu, co se o malých dronech ví z měření
nárazů: samotná hmotnost ani jednoduchý energetický práh nevystihují
mechanismus poranění
([Heliyon 2022](https://doi.org/10.1016/j.heliyon.2022.e11677)).

Praktický důsledek: **duct a disciplína při armování dělají pro bezpečnost víc
než rychlostní limit**, i když rychlostní limit je pořád nutný — energie roste
s druhou mocninou rychlosti a brzdná dráha s ní taky.

### Brzdná dráha je limitovaná náklonem, ne vrtulí

Kvadrokoptéra brzdí složkou tahu, takže dosažitelné zpomalení je `g·tan(θ)` a
navíc přijde až po přetočení do náklonu:

| Max. náklon | Zpomalení | Z 1 m/s | Z 2 m/s | Z 3 m/s |
| ---: | ---: | ---: | ---: | ---: |
| 10° | 1,73 m/s² | 0,29 m | 1,16 m | 2,60 m |
| 15° | 2,63 m/s² | 0,19 m | 0,76 m | 1,71 m |
| 20° | 3,57 m/s² | 0,14 m | 0,56 m | 1,26 m |
| 25° | 4,57 m/s² | 0,11 m | 0,44 m | 0,98 m |

K tomu se přičítá doba na natočení a latence celé cesty povelu. Kontrola
guided vzletu v repozitáři má limit náklonu 25°, což tuhle tabulku uzavírá
shora. Pro indoor let v bytě je z ní vidět, proč je 2 m/s jiná disciplína než
1 m/s: brzdná dráha roste čtyřnásobně.

## 9. Hranice 250 g

Rozhodnutí projektu z 10. 9. 2026 říká výslovně, že **hmotnost je cíl, ne
limit**, a žádná komponenta se podle 250 g nevybírá. Přesto je to číslo, které
stojí za sledování: 0,306 kg je nad ním, stavěná 4S varianta Pavo20 kolem
0,229–0,239 kg pod ním. Rozdíl mezi „musím dodržet" a „chci vědět, jestli tam
jsem" je celý rozdíl mezi omezením a informací.

Pod 250 g nevzniká povolení k čemukoli — provoz v otevřené kategorii má dál
podmínky včetně VLOS a kamera může vyvolat registraci provozovatele. Pro
konkrétní let je nutné ověřit aktuální pravidla; tenhle dokument není právní
stanovisko.

## 10. Kdy 3" vyhrává a kdy prohrává

| Situace | Volba | Proč |
| --- | --- | --- |
| indoor průlet, náklad 40–60 g, rezerva na ladění | **3"** | největší disk, který se ještě vejde do dveří; nejvyšší rezerva tahu |
| tvrdý cíl pod 250 g se stejným nákladem | **2,2"** | jediná cesta, jak se pod čáru dostat bez ztráty doletu; platí se 36 % indukovaného výkonu |
| delší let, těžší senzor, venek, vítr | **4" a víc** | 18,4 W proti 24,6 W při stejné hmotnosti; disk je jediná páka, která funguje |
| první stavba a učení se ladění | **3"** | nejvyšší tahová rezerva odpouští chyby v nastavení |
| roj pěti kusů v jedné místnosti | **2,2"** | rozhoduje geometrická obálka a cena za kus, ne účinnost |
| náklad nad 100 g (GPU, 3D lidar) | **žádná z nich** | plošné zatížení a rezerva tahu už nevyjdou |

## 11. Co změřit, aby tahle kapitola přestala být teorie

Pořadí je podle poměru informace ku ceně:

1. **Tahová stolice na obě kombinace** (LAVA 1104 + D2.2-3, A1204 + 2218) na 4S
   při 25/50/75/100 % plynu: tah, proud, napětí, teplota po 30 s. Z toho teprve
   vypadne `motorConstant`, `maxRotVelocity`, `MOT_THST_EXPO` a reálná účinnost.
   V repozitáři na to je `scripts/check_thrust_stand.sh` jako simulační protějšek.
2. **Totéž s duktem a bez ductu.** Je to jediné měření, které v celém projektu
   odpoví, jestli duct něco stojí, nebo něco dává.
3. **Příkon ve visu na celém stroji**, ne jen na jednom motoru — z něj a z
   kapacity baterie vyjde výdrž, kterou dnes všechny dokumenty jen počítají.
4. **Doběh po povelu k zastavení** z 0,5, 1,0 a 1,5 m/s, několikrát, s rozptylem.
   Tabulka náklonu výš je horní mez, ne měření.
5. **Teplota motorů po dvou minutách visu.** Pavo20 jede vrtuli mimo doporučenou
   vzletovou hmotnost; teplota je první místo, kde se to projeví.

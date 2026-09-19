# Proč mohou být 3" drony výhodné pro roj

## Stručný verdikt

3" kvadrokoptéra je zajímavý kompromis pro **indoor průzkum, výuku,
experimenty s formací a lety v omezeném prostoru**. Proti většímu stroji může
být kompaktnější, obratnější, levnější na kus a při stejné rychlosti mít nižší
kinetickou energii. Díky menší obálce lze do stejného prostoru umístit více
členů roje.

Cena za to je zásadní: malá vrtule má horší energetickou účinnost, náklad tvoří
velkou část celkové hmotnosti, krátká ramena a rychlé motory vyžadují rychlou a
dobře naladěnou regulaci a menší baterie dávají málo času na chyby. Ducts chrání
vrtule a okolí, ale přidávají hmotnost a moment setrvačnosti. Pro venkovní
dlouhý let, těžký lidar nebo palubní GPU je obvykle výhodnější větší platforma.

## Co označení 3" říká a neříká

Říká pouze přibližný průměr vrtule:

```text
3 in = 76,2 mm, poloměr jedné vrtule = 38,1 mm
```

Neurčuje hmotnost, rozvor, motor, počet článků baterie, tah, ochranný kryt ani
dobu letu. Dva „3" drony“ mohou být lehký open-prop racer a výrazně těžší
cinewhoop s ducts, kamerou a lidarem. Pro řízení a bezpečnost je potřeba
pracovat s měřenou konfigurací, ne se štítkem velikosti.

Projektový cinewhoop má v současné implementační specifikaci:

| Veličina | Projektová hodnota |
| --- | ---: |
| průměr vrtule | 0,0762 m |
| rozvor | 0,128 m |
| dosah špičky rotoru od středu | 0,08335 m |
| průměr minimální rotorové obálky | 0,1667 m |
| simulační hmotnost s nákladem | 0,306 kg |

Poslední dvě hodnoty jsou pro roj důležitější než slovo „3 palce“: určují
geometrickou kolizní obálku a spolu s rychlostí i energii nárazu.

## Fyzikální důvody pro malou platformu

### 1. Menší rotační setrvačnost a vyšší obratnost

Při geometricky podobném zmenšení s charakteristickou délkou `L` roste hmotnost
přibližně jako `L³` a moment setrvačnosti jako `L⁵`. Tah rotoru se v jednoduchém
modelu škáluje s plochou a druhou mocninou rychlosti špičky. Výsledkem je, že
úhlová akcelerace malého dronu roste při běžných škálovacích předpokladech
přibližně jako `1/L` až `1/L²`.

Praktický význam: kvadrokoptéra nejdřív natočí vektor tahu a teprve tím zrychlí
do strany. Rychlejší změna orientace proto zlepšuje změnu směru, odmítnutí
poryvu a sledování těsnější trajektorie. Tento argument i experiment s 20
mikrokvadrokoptérami uvádějí Kushleyev, Mellinger a Kumar v práci
[Towards a Swarm of Agile Micro Quadrotors](https://www.roboticsproceedings.org/rss08/p28.pdf).

Není to ale záruka, že každý malý postavený stroj je dobře ovladatelný. Ducts,
těžký lidar daleko od těžiště, měkký rám, pomalá telemetrie nebo špatné filtry
mohou fyzikální výhodu spotřebovat.

### 2. Těsnější prostory a hustší formace

Menší fyzická obálka přináší dvě různé výhody:

- dron projede užším koridorem a může mapovat prostory nedostupné velkému stroji;
- při stejném bezpečnostním násobku rozměru může být vzdálenost mezi středy
  sousedů menší, takže se do místnosti vejde více agentů.

Výzkum mikrokvadrokoptér přímo uvádí provoz ve stísněném prostředí a v těsných
formacích jako hlavní důvod zmenšování. Je však nutné započítat lokalizační
chybu, latenci a brzdnou dráhu; minimální rozestup není jen dvojnásobek
poloměru dronu.

### 3. Menší energie při stejné rychlosti

Translační kinetická energie je

```text
E_k = 1/2 · m · v²
```

Při stejné rychlosti tedy klesá přímo s hmotností. Pro projektovou hmotnost
0,306 kg:

| Rychlost | Kinetická energie |
| ---: | ---: |
| 0,5 m/s | 0,038 J |
| 1,0 m/s | 0,153 J |
| 2,0 m/s | 0,612 J |
| 5,0 m/s | 3,825 J |

Tabulka není hodnocení poranění: rotující vrtule, tvrdé výstupky, baterie a
deformace mění důsledek nárazu. Ukazuje ale, proč je **omezení rychlosti stejně
důležité jako nízká hmotnost**; energie roste s druhou mocninou rychlosti.
Experimentální literatura k nárazům malých UAS zároveň upozorňuje, že samotná
hmotnost nebo jednoduchý energetický práh nevystihují celý mechanismus
poranění ([Evaluation of the drone-human collision consequences](https://doi.org/10.1016/j.heliyon.2022.e11677)).

### 4. Nižší cena a menší následek ztráty jednoho kusu

Roj získává hodnotu redundancí pouze tehdy, když ztráta jednoho člena není
katastrofa pro celou misi ani rozpočet. Menší stroj zpravidla potřebuje méně
materiálu a menší pohon. To umožňuje:

- koupit několik shodných kusů a držet náhradní díly;
- rozdělit senzory mezi členy;
- experimentovat s poruchou jednoho agenta;
- zvýšit počet pozorovacích míst místo zvětšování jednoho drahého nosiče.

Tato výhoda platí jen při standardizaci. Pět unikátních ručně stavěných dronů s
odlišným firmwarem může být provozně dražších než dva větší shodné stroje.

## Proč malá platforma není energetické perpetuum mobile

V ideální teorii hybnosti je indukovaný výkon ve visu přibližně

```text
P_i = T^(3/2) / sqrt(2 · rho · A)
```

kde `T` je celkový tah, `rho` hustota vzduchu a `A` součet ploch rotorových
disků. Pro stejný požadovaný tah tedy větší celková plocha rotorů snižuje
potřebný indukovaný výkon. Přehled
[Design and Control of Drones](https://hiperlab.berkeley.edu/wp-content/uploads/2021/09/2021_DesignAndControlOfDrones.pdf)
shrnuje tentýž kompromis: větší vrtule pomáhají výdrži, kompaktní uspořádání
pomáhá obratnosti.

Pro čtyři 3" vrtule je ideální celková plocha disků bez započtení překryvu

```text
A = 4 · pi · (0,0381 m)² = 0,01824 m².
```

Při hmotnosti 0,306 kg je statické plošné zatížení přibližně

```text
DL = mg/A = 164 N/m².
```

Je to užitečný srovnávací ukazatel, nikoli přesný příkon: ducts, vzájemné
ovlivnění rotorů, profil listu, nízké Reynoldsovo číslo, účinnost motoru a ESC
a proudové omezení baterie ideální model porušují. Skutečný tah a příkon se
musí změřit na konkrétní kombinaci motor–vrtule–duct–baterie.

### Důsledky pro roj

- Více malých dronů obvykle spotřebuje na nesení stejné celkové hmotnosti více
  energie než jeden správně navržený větší stroj.
- Roj dává smysl kvůli paralelismu, prostorovému pokrytí, redundanci nebo
  přístupu do úzkých míst, ne jako automatický způsob prodloužení výdrže.
- Přidaný gram senzoru se na malém dronu projeví výrazněji. U projektové
  hmotnosti je 10 g navíc 3,27 % celku.
- Větší baterie nemusí prodloužit let: energii přidává lineárně, ale zároveň
  roste potřebný tah a výkon. Existuje optimum, které se má hledat měřením.

## Ducted cinewhoop versus otevřené vrtule

| Vlastnost | Cinewhoop s ducts | Open-prop rám |
| --- | --- | --- |
| kontakt se stěnou | větší šance přežít lehký dotyk | vrtule se může okamžitě zastavit nebo poškodit |
| ochrana okolí | lepší bariéra proti přímému bočnímu kontaktu | horší |
| hmotnost | vyšší | nižší |
| moment setrvačnosti | často vyšší; hmota je daleko od těžiště | obvykle nižší |
| aerodynamika | silně závisí na vůli a geometrii ductu | jednodušší a obvykle předvídatelnější |
| účinnost | dobrý duct může pomoci v jednom pracovním bodě, špatný škodí | bez hmotnosti ductu často lepší celek |
| chování po dotyku | může sklouznout po povrchu, ale také se zachytit | častěji pád po zásahu vrtule |

Duct tedy není „účinnost zdarma“. Pro indoor roj je hlavní hodnota mechanická
ochrana a opakovatelnost lehkého kontaktu. Jeho dopad na tah, vibrace a regulaci
se má identifikovat jako součást hotového stroje.

## Vliv malé velikosti na senzory a komunikaci

### Co je snazší

- menší prostor mezi členy umožní více překrývajících se pohledů kamer;
- krátké indoor vzdálenosti mohou snížit požadovaný vysílací výkon;
- více členů může měřit prostředí paralelně a sdílet jen mapové přírůstky nebo
  trajektorie místo surových dat.

### Co je těžší

- malý nosič má málo energie, chlazení, RAM a mechanického prostoru;
- vrtule a ducts zabírají velkou část zorného pole a vytvářejí vibrace;
- optical flow potřebuje texturu, světlo a známou vzdálenost od povrchu;
- malá základna omezuje přesnost některých stereosystémů;
- každý další vysílač zvyšuje sdílené rádiové zatížení;
- ROS 2/DDS discovery provoz může při růstu počtu procesů a na Wi-Fi tvořit
  nezanedbatelný režijní provoz. Oficiální ROS 2 dokumentace upozorňuje, že
  standardní distribuované discovery neškáluje efektivně a multicast nemusí
  být na Wi-Fi spolehlivý
  ([Fast DDS Discovery Server](https://docs.ros.org/en/rolling/Tutorials/Advanced/Discovery-Server/Discovery-Server.html)).

## Regulační výhoda pod 250 g má podmínky

Podle aktuálního přehledu EASA lze soukromě postavený dron s MTOM pod 250 g a
maximální rychlostí pod 19 m/s provozovat v otevřené podkategorii A1; pořád
platí další podmínky, například zákaz letu nad shromážděním osob a v otevřené
kategorii zásadně VLOS. Kamera může vyvolat povinnost registrace provozovatele.
Viz [EASA – Open category](https://www.easa.europa.eu/en/the-agency/faqs/open-category)
a [FPV/VLOS FAQ](https://www.easa.europa.eu/en/faq/140037).

Pro tento projekt z toho plynou dvě výhrady:

1. označení 3" samo o sobě neznamená méně než 250 g; současný model 0,306 kg
   je nad hranicí;
2. rojové lety mohou snadno přestat splňovat VLOS nebo další podmínky otevřené
   kategorie. Pod 250 g není univerzální povolení k autonomnímu roji.

## Kdy je 3" výhodná volba

- indoor laboratoř nebo hala se stísněnými průlety;
- krátká, opakovaná mise s možností rychlé výměny baterie;
- formace a distribuované pokrytí, kde je cennější počet pohledů než těžký
  senzor na jednom stroji;
- výukový a sim-to-real vývoj, kde má být následek jednotlivé havárie omezený;
- rychlé reakce a nízká letová rychlost v blízkosti překážek.

## Kdy zvolit větší nebo jiný dron

- dlouhá doba ve visu nebo velký dolet;
- vítr a venkovní počasí;
- těžký 3D lidar, výkonný companion computer nebo velká kamera;
- požadavek na dlouhou rádiovou linku a redundantní navigační senzory;
- úloha, kde jeden velký stroj zvládne práci bez potřeby paralelního pokrytí;
- přeprava společného nákladu, pokud koordinace více nosičů nepřináší jinou
  hodnotu.

## Co to znamená pro tento projekt

3" cinewhoop je dobrý **výzkumný člen malého indoor roje**, ale současná
konfigurace s 0,306 kg je spíše senzorový demonstrátor než lehký spotřební
agent. Doporučení:

1. zachovat ducts pro první fyzické pokusy, ale používat je jako ochranný
   prvek, ne jako důkaz vyšší účinnosti;
2. držet nízkou rychlost a odvozovat bezpečnostní rozestup z naměřené brzdné
   dráhy, ne jen z geometrie;
3. před stavbou více kusů změřit tahovou rezervu, čas letu, teploty motorů,
   latenci řízení a rozptyl zastavení;
4. zvážit dvě role: těžší mapovací dron s lidarem a lehčí členové bez něj;
5. v simulaci parametrizovat alespoň dvě hmotnosti a zpoždění, aby algoritmus
   nefungoval jen pro dokonale shodné agenty.

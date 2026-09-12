# Implementační specifikace

Tenhle dokument je **zadání, ne popis kódu**. Je psaný tak, aby podle něj šlo
celé chování postavit znovu v jiném jazyce, aniž by se člověk musel podívat na
stávající Python — obsahuje každé pravidlo, každou konstantu i každý hraniční
případ, na kterém záleží. Kde je číslo, je u něj i to, odkud se vzalo, protože
skoro každá konstanta tady je buď rozměr z modelu dronu, nebo něco naměřeného, a
opsat ji bez toho druhého znamená opsat ji špatně.

Co tu **není**: jak se to pouští, jak se to staví a čím se to ověřuje. To je v
[Ověřovacím checklistu](./07_overovaci_checklist.md) a ve `workflow/`.

Vztah k ostatním dokumentům ve `spec/`: [ROS rozhraní](./04_ros_rozhrani.md) a
[Demo nody](./05_demo_nody.md) jsou **původní návrh** a jsou v detailech
zastaralé. Kde se rozcházejí s tímhle dokumentem, platí tenhle — je odvozený z
toho, co je postavené a naměřené.

Struktura: nejdřív konvence a geometrie, pak čistá logika (skeny, mapa,
průzkum, baterie), nakonec kontrakty jednotlivých procesů.

## Konvence

Všude platí REP 103, tedy pravotočivá soustava svázaná s tělem stroje:

- **x** dopředu, **y** doleva, **z** nahoru
- **roll** kolem x, kladný naklání **pravé** křídlo dolů
- **pitch** kolem y, kladný sklání **nos dolů**
- **yaw** kolem z, kladný **proti směru hodinových ručiček** při pohledu shora

Tyhle znaménka jsou v celém projektu nejčastější zdroj chyb, protože špatné
znaménko u rollu zahodí strop místo podlahy a všechno ostatní vypadá dál v
pořádku. Každé pravidlo níž, kde na znaménku záleží, to má napsané slovy.

Úhly jsou v radiánech, vzdálenosti v metrech, časy v sekundách. Skenové úhly
(`bearing`) jsou měřené od nosu, kladné doleva, a **musí se skládat do
⟨−π, π⟩**, jinak se kužel namířený za stroj rozpadne na dva kusy kolem přechodu.

## Geometrie stroje

Čísla pocházejí z modelu dronu (URDF i SDF popisují týž stroj a hlídá to
konzistenční kontrola). Uzly si je nesou jako výchozí hodnoty parametrů,
protože žádný z nich neposlouchá TF.

| Veličina | Hodnota | Odkud |
| --- | ---: | --- |
| rameno motoru od středu (x i y) | 0,04525 m | rozvor 128 mm / 2 / √2 |
| poloměr vrtule | 0,0381 m | 3" vrtule |
| dosah špičky rotoru od středu | **0,08335 m** | rameno + poloměr |
| lidar před `base_link` | 0,046 m | model |
| lidar nad `base_link` | 0,050 m | model |
| lidar před dálkoměrem | 0,026 m | model |
| lidar nad dálkoměrem | 0,066 m | model |
| hmotnost | 0,306 kg | model |

Přední lidar je **jednorovinný**: 360 vzorků po jednom stupni, dosah 0,02 až
12 m, 10 Hz. Ta rovina se naklápí s tělem stroje, což je důvod skoro celé
kapitoly o zemi níž.

## Základní transformace

### Skládání úhlu

```
wrap(a) = ((a + π) mod 2π) − π
```

Použít **všude**, kde se odčítají dva úhly. Rozdíl 350°, který je ve
skutečnosti −10°, je klasický způsob, jak poslat stroj otáčet se dokola.

### Roll a pitch z kvaternionu

```
roll  = atan2(2(wx + yz), 1 − 2(x² + y²))
pitch = asin(clamp(2(wy − zx), −1, 1))
yaw   = atan2(2(wz + xy), 1 − 2(y² + z²))
```

Clamp u `asin` je nutný: kvaternion, který se odchýlí od jednotkové délky, jinak
spadne mimo definiční obor.

### Bod pevně spojený s tělem, ve světě

Rotace `Rz(yaw) · Ry(pitch) · Rx(roll)` aplikovaná na bod v tělových
souřadnicích. Rozepsáno (`s` = sin, `c` = cos):

```
X = cy·cp·x + (cy·sp·sr − sy·cr)·y + (cy·sp·cr + sy·sr)·z
Y = sy·cp·x + (sy·sp·sr + cy·cr)·y + (sy·sp·cr − cy·sr)·z
Z =   −sp·x +            cp·sr·y  +            cp·cr·z
```

Tuhle rotaci je potřeba napsat **jednou**. Znaménka v ní jsou celá obtížnost a
druhá kopie je druhá příležitost splést se.

**Výška** bodu je třetí řádek a yaw z něj vypadává — otočení kolem svislé osy
nemůže změnit výšku. Proto rozpoznávání podlahy funguje, aniž by kdy vědělo,
kam je stroj natočený.

## Odmítání podlahy

Lidar je přišroubovaný k rámu, takže při náklonu jeho přední paprsky najdou
podlahu. Bez korekce se stroj zastaví před vlastní zemí.

### Jak hluboko návrat leží

Pro návrat na azimutu `b` ve vzdálenosti `r`:

```
drop = Z-složka rotace bodu (r·cos b, r·sin b, 0)
     = −sin(pitch)·r·cos b + cos(pitch)·sin(roll)·r·sin b
```

Záporná hodnota znamená pod senzorem. Sklopený nos dává zápornou hodnotu pro
návrat před strojem; náklon doleva (záporný roll) sníží to, co je vlevo.

### Je to podlaha?

```
výška návratu = výška senzoru nad podlahou + drop
je to podlaha ⟺ výška návratu ≤ mez(r)
mez(r) = ground_margin_m + r · attitude_margin_rad
```

s výchozími hodnotami **0,10 m** a **0,035 rad (2°)**.

Ta mez je **chybová úsečka, ne odstup** — a to je podstatné. Otázka nezní „je
ten návrat nízko", ale „leží ten návrat *na podlaze*". Ty dvě věci se rozejdou
všude tam, kde paprsek trefí něco vysokého u paty, což dělají přední paprsky
nakloněného stroje: se sklopeným nosem o 5,7° ve výšce 0,55 m je zeď 3 m daleko
trefená 0,25 m nad zemí, a ten návrat je jediné varování před dvěma metry zdi
nad ním.

Úsečka roste se vzdáleností, protože chyba náklonu se vzdáleností roste: špatný
odhad o úhel posune návrat ve vzdálenosti `r` o `r`-krát ten úhel. První člen
kryje to, co je špatně na místě (dálkoměr, nerovná podlaha), druhý náklon. Ve
3 m to dělá 0,21 m, v 8 m 0,38 m — a tam se návrat z podlahy od nízkého opravdu
rozeznat nedá.

**Neznámá výška nezahazuje nic.** Bez výšky se nesmí začít zahazovat skutečné
překážky.

Dvě stupně jsou v simulaci nepodložené (SITL má bezšumovou IMU) a jsou to
zároveň skoro celá úsečka na dálku. Na železe se musí změřit.

### Výška senzoru

Dálkoměr je taky přišroubovaný k rámu, takže při náklonu měří **šikmou**
vzdálenost:

```
výška dálkoměru = slant · cos(roll) · cos(pitch)
```

Při náklonu 30° je to 16 % rozdíl. Když je `cos(roll)·cos(pitch) ≤ 0`, stroj je
přes 90° a údaj neznamená nic → není výška.

Rozpoznávání se ale netýká dálkoměru, nýbrž **lidaru**, který sedí jinde:

```
výška lidaru = výška dálkoměru + Z-složka rotace bodu (0,026, 0, 0,066)
```

Naplocho je to 66 mm, které se jinak zahodí; v náklonu méně, protože offset se
otáčí s rámem.

Výška je k dispozici jen tehdy, když jsou **čerstvé obě** vstupy — poloha
(kvůli náklonu) i dálkoměr. Ani jedno nechodí spolu se skenem, takže obojí může
zestárnout, zatímco lidar dál funguje. Zastaralý náklon je horší než žádný:
zahodí zeď, na kterou stroj právě letí. Důvody, proč výška není, se rozlišují a
logují: *žádný náklon zatím*, *náklon zastaralý*, *žádný dálkoměr zatím*,
*dálkoměr zastaralý*, *dálkoměr nevidí povrch*, *stroj je přes 90°*.

## Co je v cestě

### Platný návrat

Návrat je platný, pokud je konečný (ne NaN, ne nekonečno) a leží v
⟨`range_min`, `range_max`⟩ senzoru. Cokoli jiného se přeskakuje, **nikdy**
nenahrazuje nulou ani maximem. Nejbližší platný návrat z celého skenu je
minimum přes tyhle hodnoty, nebo „žádný".

### Nejbližší návrat v kuželu

Minimum přes návraty, jejichž azimut leží do `sector/2` od zadaného středu.
Používá se na **boky** — „kde je víc místa" — a při odpovědi se zahazuje
podlaha stejně jako vpředu, protože v náklonu je země i vedle stroje.

Neplatné hodnoty (nekonečno, NaN, mimo rozsah senzoru) se přeskakují. Celý
kruh se skládá do ⟨−π, π⟩, aby kužel namířený dozadu nebyl rozseknutý.

### Nejbližší překážka v koridoru

Na otázku „smím letět rovně" se **kužel nehodí**. Kužel míchá dohromady, jak je
něco daleko, a jak je to stranou, takže nerozliší zeď od veřeje, kterou stroj
čistě mine. Konkrétně: při požadovaných 1,7 m volna je kužel 60° široký 1,7 m,
takže **otvor užší než to nemůže nikdy vyjít jako volný** — u stroje širokého
0,167 m. Naměřeno: osm náletů na dveře 1,6 m, osm odvrácení na 1,35–1,40 m.

Místo toho se ptáme na pruh, kterým stroj skutečně letí:

```
pro každý platný návrat (b, r):
    dopředu   = r · cos b
    stranou   = r · sin b
    přeskoč, pokud dopředu ≤ nose_ahead_m
    přeskoč, pokud |stranou| > half_width_m
    přeskoč, pokud je to podlaha
    kandidát = dopředu
výsledek = minimum kandidátů, jinak "nic v cestě"
```

Dvě věci, na kterých záleží:

- Vrací se **vzdálenost podél dráhy**, ne šikmá. Šikmá nadhodnocuje volno až o
  půlšířku koridoru na jeho okraji.
- Koridor **začíná u nosu**. Návrat po boku má vzdálenost podél dráhy skoro
  nulovou, přitom není překážka; zastavit kvůli němu znamená zastavit tam, kde
  zastavení nepomůže, protože stroj je už vedle něj.

Šířka: `half_width = rotor_tip_half_width_m + corridor_margin_m`, tedy
0,08335 + 0,25 = **0,333 m** na stranu, koridor 0,667 m široký. Rezerva 0,25 m
je stejného řádu jako naměřený odstup špičky rotoru od zdi (0,16–0,23 m) při
zastavení a pokrývá odchylku od dráhy a natočení za letu.

Práh začátku koridoru je `nose_ahead_m = rotor_tip_half_width_m`.

### Volno, prázdno a slepota

Tři různé odpovědi, které se **nesmí** slít do jedné:

| Stav | Význam | Co dělat |
| --- | --- | --- |
| v koridoru je něco blíž než práh | překážka | stát |
| v koridoru **není nic**, ale sken návraty má | volná cesta | letět |
| sken **nemá žádný** platný návrat | stroj nevidí | stát |

Dokud byla cesta kužel, druhý a třetí případ splývaly — 360° lidar v místnosti
má skoro vždycky něco v ±30°, takže „nic v kuželu" znamenalo rozbitý senzor. U
koridoru je prázdno běžný stav volné cesty, a kdyby kvůli němu stroj stál,
nemohl by se hnout z místa.

### Prahy

```
rychlost = forward_speed_mps, pokud sken něco vidí
                              a (koridor je prázdný
                                 nebo nejbližší ≥ stop_distance + braking)
           jinak 0
```

`stop_distance_m` = 0,80 m je odstup, který se má udržet.
`braking_distance_m` = 0,60 m je **naměřená** dojezdová dráha z 0,5 m/s pod
tvarováním pohybu, které ArduPilot dělá schválně (jerk 5 m/s³, akcelerace
2,5 m/s²). Rozhodnutí se proto posouvá dřív, místo aby se brzdilo tvrději.

Rozjet se zpátky ale smí až o kus dál:

```
volno ⟺ nic v koridoru, nebo nejbližší ≥ stop + braking + turn_clear_margin
```

s `turn_clear_margin_m` = 0,30 m. Není to negace zastavovacího pravidla
schválně: bez té mezery se obě rozhodnutí perou o centimetr a stroj cuká.

### Důvod stání

Latchuje se **důvod**, ne fakt, že stroj stojí, a ne vzdálenost:

1. sken je zastaralý → *„no recent scan"*
2. sken nemá žádný návrat → *„no valid range in the scan"*
3. jinak → *„obstacle"* + vzdálenost jako detail

Detail se **nelatchuje**, aby překážka klesající z 1,17 na 1,16 m nelogovala
desetkrát za sekundu. Když se latchoval jen fakt stání, stroj, který zastavil
kvůli mrtvému lidaru a pak zůstal stát kvůli zdi, hlásil mrtvý lidar donekonečna.

### Dálkoměr z vějíře paprsků

Simulovaný dálkoměr je malý vějíř, protože skutečný time-of-flight senzor hlásí
nejbližší povrch ve svém kuželu. Převod na jedno číslo:

```
odečet = nejbližší platný návrat, nebo +∞
```

`+∞` je to, co `sensor_msgs/Range` znamená pod „mimo rozsah", tedy **žádná
detekce** — a je to i to, co Gazebo už tak posílá. Nula by znamenala povrch
přímo na senzoru.

## Otáčení

### Na kterou stranu

Bez cíle: k té straně, kde je víc místa. `None` (nic v dosahu) znamená všechno
místo, jaké je. Shoda padá doleva — stroj se musí rozhodnout a držet se toho,
protože pravidlo, které si to rozmyslí v půlce, nechá stroj kývat na místě.

### S cílem

Azimut cíle vůči nosu:

```
bearing = wrap(atan2(cíl_y − y, cíl_x − x) − yaw)
```

Kladný je doleva, stejně jako yaw v příkazu, takže znaménko jde předat přímo.

Pravidla otáčky jsou tři a drží pohromadě:

**Vzdát se cíle** (`going_round`): jakmile je cíl na nose a cesta je pořád
zavřená, znamená to, že cíl je za zdí. Od té chvíle je otáčka ta stará
reaktivní — točit dál, dokud se něco neuvolní. **Je to lepivé** a v tom je celý
smysl: pravidlo bez paměti („miř na cíl, pokud není na nose") pošle stroj hned
zpátky, jakmile se o chlup přetočí. Naměřeno bez toho: stroj s cílem před nosem
se za 20 sekund otočil o 9,2° a 195krát ze 200 tiků změnil názor. Ruší se na
**začátku** každé otáčky, aby se otázka pokládala znovu proti aktuální mapě.

**Kterým směrem točit**: dokud je cíl stranou, k němu kratší cestou. Jakmile
otáčka „jde okolo", nese ji zapamatované znaménko a cíl už nemá hlas.

**Kdy otáčku ukončit**: cesta je volná **a** stroj míří na cíl (do
`align_tolerance_deg` = 10°, což jsou při 4 m asi 0,7 m). Obě půlky jsou
potřeba a selhávají jinak: samotné „volno" nechá stroj kroužit otevřeným
středem, samotné „zamířeno" ho pošle do zdi, za kterou cíl je. Výjimka je právě
`going_round`, kde by trvání na obojím byl deadlock — tam končí otáčka na starém
pravidle, které skončit umí. Bez cíle platí staré pravidlo taky.

## Mapa

Mapa je **2D řez** ve výšce letu. Buňka neříká, že sloupec je zablokovaný od
podlahy ke stropu, jen že tam něco bylo ve výšce, ve které byl lidar. Na
poznání místnosti to stačí, na plánování přelezu ne.

### Mřížka

- Rozměr: `ceil(rozměr / rozlišení)`, rozlišení musí být kladné.
- Buňka bodu: `col = floor((x − origin_x) / res)`, stejně pro řádek. Mimo mapu
  se vrací **záporný index**, ne `None` — paprsek, který mapu opouští, se pořád
  musí dokreslit k okraji a k tomu je potřeba vědět, kudy odešel.
- Střed buňky: `origin + (index + 0,5) · res`.
- Uvnitř mapy: `0 ≤ col < cols` a `0 ≤ row < rows`.
- Uvnitř obdélníku `(x_min, x_max, y_min, y_max)`: včetně hranic.

### Kam návrat patří

Návrat je měřený **od lidaru**, ale poloha je `base_link`. Posun ve světě:

```
offset = rotace bodu (lidar_ahead + r·cos b, lidar_left + r·sin b, lidar_above)
```

s yaw zahrnutým. Mapa stavěná bez toho vrhá každý paprsek z místa, kde žádný
senzor není.

### Log-odds

Ne příznak a ne počítadlo. Příznak se nedá odargumentovat, takže jediný falešný
návrat nechá zeď v mapě navždy a stroj, který kolem téhož prázdna proletí
padesátkrát, nemá jak to říct. Log-odds se sčítají, což je přesně to, co má
opakovaný důkaz dělat.

```
obsazeno:  +0,85
volno:     −0,40
ořez:      ±5,0
```

Ořez určuje, jak rychle mapa umí změnit názor: ±5 je asi šest souhlasných
měření na každou stranu.

Do zprávy:

```
buňka, které se nikdy nic nedotklo  → −1 (neznámo)
jinak → round(100 · (1 − 1/(1 + e^log_odds)))
```

Neznámo a padesát na padesát jsou **různé odpovědi** a zpráva má pro obojí
hodnotu. Slít je dohromady znamená zahodit jedinou informaci o tom, kde stroj
vlastně byl.

### Paprsek

Bresenham (celočíselný, nemůže ujet), **bez koncového bodu**: čím paprsek
prošel, je volné, a obsazené je jen tam, kde skončil. Vracet obojí v jednom
seznamu znamená, že to volající musí zase rozdělit — a ten, kdo zapomene,
vybarví každou nalezenou zeď jako volnou.

Smyčka je omezená `dx + dy + 1` kroky, aby nesmyslný vstup (endpoint z NaN)
nezavěsil uzel.

### Podlaha se do mapy nekreslí vůbec

Návrat rozpoznaný jako podlaha se zahodí **celý**, ne že by se dokreslil volný
paprsek až k němu. Ten paprsek sice doletěl bez překážky, ale letěl přitom dolů,
takže dokazuje jen to, že vzduch mezi strojem a podlahou je volný — což není,
co znamená buňka ve vodorovném řezu.

## Průzkum

### Hranice

**Hraniční buňka** je volná podlaha, která sousedí s neznámem. Je tedy zároveň
dosažitelná a stojí za to k ní letět; když žádná nezbyde, místnost je hotová.

- Sousedství se počítá **po hranách, ne po rozích**. Dotyk rohem není otvor: v
  kvantované mřížce má každá skutečná hranice hran dost, a rohy přidají buňky,
  jejichž jediné spojení s neznámem je bod.
- **Za okrajem mapy není neznámo**, i když v nejprostším smyslu je. Tam se nikdy
  nic zmapovat nedá, takže buňka na okraji je na hranici toho, co mapa umí
  zobrazit, ne u průchodu — a mířit tam znamená mířit na mapu místo do místnosti.

**Shlukování** hraničních buněk do otvorů je naopak **po osmi směrech**, a ten
rozdíl není nedůslednost: jsou to dvě různé otázky. Jestli buňka leží na
hranici, je o tom, čeho se dotýká, a roh není dotyk. Jestli dvě hraniční buňky
patří téže hranici, je o tom, jestli jedna vede k druhé — a podél zdi pod jiným
než pravým úhlem běží hranice diagonálně. Rozsekat to na jednotlivé buňky by
nechalo samé třísky, a třísky zahodí filtr velikosti.

**Filtr velikosti**: shluk pod `min_frontier_cells` = 4 (tedy 0,4 m při
rozlišení 0,10 m) se ignoruje. Nefiltruje se tím, co se kam vejde — jednou nebo
dvěma buňkami je skoro vždycky roztřepený konec zdi, a pravidlo „nejbližší
první" by je vybíralo pořád dokola, protože po pravdě nejbližší jsou.

**Těžiště otvoru** je průměr středů jeho buněk, v metrech v rámci mapy. Je to
**směr, kterým vyrazit, ne místo, kam dorazit**: u hranice ohnuté za roh může
těžiště padnout dovnitř zdi, kolem které se ohýbá.

### Kudy

Říct **kam** nestačí. Přímka k těžišti hranice vede skrz zeď vedle dveří skoro
pokaždé; naměřeno: stroj se dostal dovnitř v jednom letu ze dvou, a i ten jeden
byl náhoda polohy. Proto se počítá cesta.

**Nafouknutí stěn** (`blocked_cells`): každá obsazená buňka zabere kolem sebe
kotouč o poloměru `clearance_cells`. **Kruhový, ne čtvercový** — odstup je
vzdálenost a čtvercový roh by si diagonálně nárokoval 1,41násobek, což ve
dveřích zavře průchod, kterým se stroj vejde.

**Rezerva plánování** je o buňku větší než půlšířka koridoru:

```
clearance_cells = ceil((rotor_tip + corridor_margin + rozlišení) / rozlišení)
```

Při 0,10 m to je 5 buněk, tedy 0,50 m na stranu. Kdyby se plánovalo přesně na
půlšířku koridoru, cesta smí vést těsně podél nafouknuté zdi, a ve dveřích
1,6 m to nechá stroj až 0,5 m od osy s veřejí 0,3 m stranou — **uvnitř
koridoru**, takže stroj hlásí zavřeno přesně u dveří, ke kterým byl poslán.
Stojí to otvory mezi 0,67 m a 1,0 m, kterými by se koridor protáhl: cesta, po
které stroj spolehlivě neproletí, není cesta.

**Prohledávání** (`reachability`): jedna vlna do šířky po známé volné podlaze,
čtyřsměrně, z buňky stroje. Vrací vzdálenost v krocích ke každé dosažitelné
buňce a rodiče pro rekonstrukci trasy. Neznámem se **neletí** — a právě to dělá
z hranice cíl místo průjezdu: stroj doletí na okraj toho, co zná, podívá se, a
příští vlna může dál.

Dvě výjimky, obě nutné:

- **Buňka stroje je vždy místo, kde stroj být může.** Už tam je. Start, který
  by se vyloučil, nechá stroj, co se přiblížil ke zdi, bez jediného kroku.
- **Ven z nafouknuté zóny se smí**, protože stroj blíž ke zdi než odstup má
  všechny sousedy zarostlé a vlna by nenašla nic — a hlásila by hotovou
  místnost půl metru od zdi, za kterou se nepodívala. Únik je **omezený** na
  tloušťku odstupu (dál by se vlna protáhla pruhem podél zdi a proklouzla
  dveřmi, které odstup má vyloučit) a **jednosměrný**: povolení se spotřebuje
  dosažením volné podlahy a z volné podlahy se do zóny vstoupit nedá.

### Který otvor

Ne nejbližší, nýbrž **nejlevnější**, a rozdíl je otáčka.

```
cena = délka cesty [m] + |azimut na první krok cesty| · turn_cost_m_per_rad
```

`turn_cost_m_per_rad` = **1,25 m/rad** = `forward_speed / turn_yaw_rate` =
0,5 / 0,4. Obrat čelem vzad tedy stojí, co stojí uletět čtyři metry.

Bez toho pravidlo osciluje z principu: doletíš k otvoru, ten se prozkoumá a
přestane být otvorem, a nejbližší ze zbylých je za tebou. Naměřeno: jeden let
strávil celou druhou půlku otáčkami o 133, 143, 146, 171 a 172 stupňů za sebou.

Je to **cena, ne zákaz** — otáčka, která se vyplatí, se pořád udělá.

Otvor, ke kterému vlna nedošla, se nevybírá vůbec. Tím odpadlo hádání: dřív se
nedosažitelnost odvozovala z toho, jak dlouho se stroj marně snaží dorazit, a
timeout neuměl odlišit zeď v cestě od otvoru, který je prostě daleko.

### Kam mířit

Publikuje se **bod krok napřed po cestě**, ne konec cesty:

```
carrot = střed buňky, jejíž index · rozlišení ≥ lookahead_m (jinak konec cesty)
```

`lookahead_m` = 1,4 m, tedy vlastní zastavovací vzdálenost dema. Blíž a stroj
míří na buňku, ve které stojí; dál a bod v první zatáčce z cesty uteče, což je
právě ta chyba, kvůli které tohle vzniklo.

Vzdálenost se počítá jako `index · rozlišení`, **ne** postupným přičítáním:
devětkrát přičtená desetina je o kousek míň než devět desetin, a carrot, který
kvůli tomu občas přeskočí o buňku dál, je chyba, která se projeví jen jako
lehce divný kurz.

**Držení cíle**: jednou vybraný otvor se drží, dokud je pořád otvorem — dokud
je nějaký kvalifikovaný shluk do `target_hold_m` = 1,0 m od jeho těžiště a je
dosažitelný. Přepočítávat od nuly při každé aktualizaci mapy je správně a
zbytečně: nejbližší otvor se mění, jak mapa přibývá a stroj se hýbe, a stroj,
který se rozhoduje desetkrát za sekundu, se nikam nedostane.

## Baterie

```
je vybitá ⟺ napětí / počet_článků ≤ land_below_volts_per_cell
```

Výchozí: 4 články, **3,5 V/článek**. Na článek, ne na balík, protože tam je
chemie: lithiový článek drží kolem 3,7 V po většinu kapacity a pak spadne z
útesu.

**Rozhodnutí drží** (latch) a to je celé jádro. Baterie pod zátěží klesne a
vrátí se, jakmile zátěž povolí, takže stroj, který se rozhodl přistát, zpomalil,
uviděl vrácené napětí a letěl dál, by to dělal pořád dokola, zatímco náboj,
který měří, mizí.

**Neznámé napětí není vybitá baterie** (ani nabitá) — co s neznámem, je
samostatná otázka:

| Stav tématu | Reakce |
| --- | --- |
| napětí pod prahem | přistát, důvod je napětí |
| téma mlčí déle než `battery_timeout_s` = 5 s | přistát, důvod je mlčení |
| téma **nikdy** nic neposlalo | jen jednou varovat, letět dál |

Poslední řádek je proto, že v části kontrol běží uzel úplně bez ArduPilotu.
Rozlišují se, aby log řekl, co se stalo, i když vedou na totéž přistání.

Přistání samo: přestat publikovat rychlost **úplně** a požádat o režim LAND.
Rychlostní příkaz v polohově řízeném režimu už jednou nahradil takeoff a tady
by bojoval se sestupem. Stroj je předaný ArduPilotu a brát mu ho v půlce sestupu
na vybité baterii není, co dělat.

Pod tím vším je failsafe samotného ArduPilotu (`BATT_LOW_VOLT`, `BATT_CRT_VOLT`,
obojí s akcí přistát, s desetisekundovou prodlevou kvůli propadům při plynu).
Ten funguje, i když ROS vrstva umře — což je jediný důvod, proč tam je.

## Vzlet

Služba takeoff odpoví úspěchem, jakmile GUIDED požadavek přijme, ale stoupání
začne až s polohovým řešením EKF. Do té doby stroj sedí ozbrojený na volnoběh a
po deseti sekundách se sám odzbrojí. Jediné důvěryhodné potvrzení je výška:

```
opakovat ⟺ uplynulo ≥ takeoff_retry_s
           a (výška není známa, nebo výška − výška_při_žádosti < climb_margin_m)
```

Do dosažení výšky se **nesmí** publikovat žádná dopředná rychlost — rychlostní
příkaz v GUIDED nahradí takeoff a stroj zůstane na zemi, zatímco všechny služby
hlásí úspěch.

## Čerstvost

Jednotné pravidlo pro všechno, co nechodí spolu se skenem:

```
čerstvé ⟺ stáří ≠ neznámo a stáří ≤ timeout
```

Zastaralé čtení je nebezpečnější než žádné: poslední sken může ukazovat volný
vzduch, zatímco stroj mezitím doletěl ke zdi, a poslední náklon může ukazovat
sklon, který stroj přestal držet před vteřinami.

## Míry pro kontroly

Tyhle funkce nelétají, ale kontroly by se bez nich nedaly napsat.

- **Pokrytí oblasti**: podíl volných buněk ku všem buňkám uvnitř obdélníku, s
  vyloučením zadaných obdélníků (půdorysů překážek). Vyloučení vypadává z
  **obou** stran zlomku: buňka uvnitř sloupu není podlaha, kterou stroj
  nedokázal vidět, a počítat ji jako neviděnou dělá mapu tím horší, čím víc
  nábytku našla.
- **Rozsah mapy**: ohraničující obdélník obsazených buněk v metrech. Na
  obdélníkovou místnost se ptáme, jak velká vyšla, a to není počet buněk.
- **Vzdálenost od nejbližší zdi**: vzdálenost k nejbližší ze čtyř přímek, ne k
  obdélníku — bod uvnitř i vně dostává tutéž otázku, totiž jak daleko od zdi
  přistál.

## Procesy

Sedm samostatných procesů. Rozdělené jsou proto, že každý odpovídá na jednu
otázku a čitelné zůstanou jen tak dlouho, dokud jich neodpovídají víc. Kterýkoli
jde spustit bez ostatních.

Společné pro všechny: senzorová témata se odebírají **BEST_EFFORT**
(`qos_profile_sensor_data`), protože tak je publikuje AP_DDS a RELIABLE
odběratel se s ním tiše nikdy nespáruje. Ukončení přes Ctrl-C nebo TERM není
chyba a nemá vypisovat traceback.

### `range_adapter`

Přemostění, které existuje jen v simulaci: Gazebo umí vyrobit `LaserScan`, ale
skutečný ovladač dálkoměru publikuje `sensor_msgs/Range`. Bez něj nemá nic
výšku a odmítání podlahy se nikdy nezapne.

| | |
| --- | --- |
| odebírá | `/openipc_cinewhoop/range/down_raw` (`LaserScan`) |
| publikuje | `/openipc_cinewhoop/range/down` (`Range`) |
| parametry | `min_range_m`, `max_range_m`, `field_of_view_rad` = 0,035 |

Převod je „dálkoměr z vějíře paprsků" výše. Hlavička a rámec se přebírají ze
vstupu.

### `pose_tf_broadcaster`

Vysílá transformaci `map` → `base_link` z pozice, kterou hlásí řídicí jednotka,
aby měla mapa kam se zavěsit.

| | |
| --- | --- |
| odebírá | `/ap/pose/filtered` (`PoseStamped`) |
| vysílá | TF `map` → `base_link` |
| parametry | `pose_topic`, `frame_id` = `map`, `child_frame_id` = `base_link` |

**Pozor na past**: `header.frame_id` té zprávy říká `base_link` a **je to
špatně**. AP_DDS ji plní z pozice vůči domovu převedené do ENU, takže obsah je
„kde je base_link vůči domovu", což se v base_link vyjádřit nedá. Je to týž
rámec, ve kterém se staví mapa — a jen proto jde cíl z mapy vůbec porovnat s
polohou stroje.

### `trajectory_publisher`

Kudy stroj letěl, jako `nav_msgs/Path`, pro zobrazení.

| | |
| --- | --- |
| odebírá | `/ap/pose/filtered` |
| publikuje | `/openipc_cinewhoop/path` (`Path`) |
| parametry | `max_points` = 2000 (nejstarší se zahazují) |

### `obstacle_monitor`

Hlásí, co je nablízku. Je to **varování pro člověka**, ne rozhodnutí.

| | |
| --- | --- |
| odebírá | přední sken, poloha, dálkoměr |
| publikuje | nic, jen loguje |
| parametry | `warn_distance_m` = 0,8, `log_period_s` = 0,5, `scan_timeout_s` = 1,0, `forward_sector_deg` = 60, plus celá sada pro odmítání podlahy |

Ptá se **kuželem**, ne koridorem, a je to schválně: otázka „co je nablízku" je
jiná než „smím se pohnout". Znamená to, že log může hlásit překážku 0,9 m
daleko, zatímco stroj kolem ní správně proletí.

Mlčící lidar se hlásí jednou, ne opakovaně.

### `occupancy_mapper`

Staví vodorovný řez místnosti z návratů a polohy.

| | |
| --- | --- |
| odebírá | přední sken, poloha, dálkoměr |
| publikuje | `/openipc_cinewhoop/map` (`OccupancyGrid`), **TRANSIENT_LOCAL** |
| parametry | `resolution_m` = 0,10, `map_width_m`/`map_height_m` = 20, `publish_period_s` = 1,0, `frame_id` = `map`, offsety senzorů, sada pro odmítání podlahy |

Trvanlivost je podstatná: odběratel, který se připojí později, dostane mapu tak,
jak už stojí, místo aby čekal na další.

Postup na každý sken:

1. Není-li výška pro odmítání podlahy, **nemapovat vůbec** a říct proč. Bez ní
   by se podlaha zakreslila jako zeď.
2. Střed paprsků je **lidar**, ne `base_link` — posun se otočí náklonem i yaw.
3. Pro každý paprsek: platný návrat → koncový bod obsazený, buňky po cestě
   volné. Nekonečno → volné až po `range_max`. NaN nebo pod `range_min` →
   **nic**, paprsek selhal a nedá se z něj nic vyvodit.
4. Návrat rozpoznaný jako podlaha se zahodí **celý**, ani se nekreslí volný
   paprsek.
5. Buňky se aktualizují log-odds a periodicky se publikují.

### `frontier_explorer`

Odpovídá na otázku **kam letět** a vrací **kudy**. Nic neřídí.

| | |
| --- | --- |
| odebírá | `/openipc_cinewhoop/map` (TRANSIENT_LOCAL), `/ap/pose/filtered` |
| publikuje | `/openipc_cinewhoop/explore/target` (`PointStamped`) |
| parametry | `min_frontier_cells` = 4, `rotor_tip_half_width_m`, `corridor_margin_m`, `lookahead_m` = 1,4, `target_hold_m` = 1,0, `turn_cost_m_per_rad` = 1,25 |

Na každou mapu: buňka stroje → vlna dosažitelnosti → hraniční buňky → shluky →
filtr velikosti → držený cíl, jinak nejlevnější → trasa → carrot → publikovat.
Když nezbyde žádný dosažitelný otvor, **říct to jednou** a přestat publikovat.

Nese si vlastní kopii šířky stroje místo aby ji četl z druhého uzlu, protože
proces, který nejde spustit samostatně, se nedá ladit. Konzistenční kontrola
drží obě kopie u modelu.

### `simple_indoor_autonomy`

Bezpečnostní vrstva a jediný proces, který velí strojem.

| | |
| --- | --- |
| odebírá | přední sken, `/ap/status`, poloha, dálkoměr, cíl průzkumu, `/ap/battery` |
| publikuje | `/ap/cmd_vel` (`TwistStamped`) |
| služby | `/ap/prearm_check`, `/ap/mode_switch`, `/ap/arm_motors`, `/ap/experimental/takeoff` |

Stavy:

```
WAIT_SCAN      → čeká na první sken
WAIT_SERVICES  → čeká, až všechny čtyři služby odpovídají
PREARM         → opakuje prearm, dokud neprojde
MODE           → přepnout na GUIDED (režim 4)
ARM            → ozbrojit
WAIT_ARMED     → čekat, až motory opravdu běží
TAKEOFF        → požádat o vzlet
CLIMB          → stoupat, případně vzlet zopakovat
CRUISE         → letět dopředu
TURN           → stát a otáčet se
LAND           → přistát na vybité baterii (režim 9), konečný stav
```

S `auto_takeoff = false` se přeskakuje rovnou na `CRUISE` a nevolá se žádná
služba; tak uzel jezdí ve většině kontrol.

Vždy platí:

- **Jedno volání služby naráz.** Další se nepošle, dokud předchozí nedoběhne.
- Ozbrojení potvrzuje **stav**, ne odpověď služby. Žádost o vzlet před
  skutečným ozbrojením se přijme a tiše zahodí a stroj se za pár sekund
  odzbrojí.
- **Během stoupání se nesmí publikovat dopředná rychlost.** Rychlostní příkaz
  v GUIDED nahradí vzlet.
- Zastaralý sken se rovná žádnému skenu: stroj stojí.
- Odbočka se rozhoduje jednou a znaménko se drží.
- Do stavu `LAND` se vstupuje jen z `CLIMB`, `CRUISE` nebo `TURN` a **nevede z
  něj cesta zpět**.

Klíčové parametry jsou v tabulce na konci; každý je běhový, takže se dají měnit
za letu (čehož využívá kontrola baterie).

## Čísla na jednom místě

| Parametr | Výchozí | Odkud |
| --- | ---: | --- |
| `forward_speed_mps` | 0,5 | pomalý indoor let, zadání |
| `stop_distance_m` | 0,80 | odstup, který se má udržet |
| `braking_distance_m` | 0,60 | **naměřeno** z ground truth při 0,5 m/s |
| `turn_clear_margin_m` | 0,30 | hystereze proti cukání |
| `turn_yaw_rate_rps` | 0,4 | pomalá otáčka |
| `forward_sector_deg` | 60 | kužel pro boky |
| `side_sector_deg` | 60 | totéž |
| `rotor_tip_half_width_m` | 0,08335 | **model**, hlídá konzistenční kontrola |
| `corridor_margin_m` | 0,25 | řádově naměřený odstup špičky od zdi |
| `align_tolerance_deg` | 10 | při 4 m je to 0,7 m |
| `ground_margin_m` | 0,10 | dálkoměr a nerovnost podlahy |
| `ground_attitude_margin_deg` | 2,0 | **nepodložené**, čeká na železo |
| `scan_timeout_s` | 0,5 | lidar jede 10 Hz |
| `min_frontier_cells` | 4 | 0,4 m při rozlišení 0,10 m |
| `lookahead_m` | 1,4 | zastavovací vzdálenost dema |
| `target_hold_m` | 1,0 | vodítko na posun těžiště hranice |
| `turn_cost_m_per_rad` | 1,25 | rychlost / rychlost otáčení |
| `battery_cells` | 4 | 4S LiHV pack |
| `land_below_volts_per_cell` | 3,5 | konec plató lithiového článku |
| `battery_timeout_s` | 5,0 | delší než výpadek zprávy |
| rozlišení mapy | 0,10 m | |
| log-odds obsazeno / volno / ořez | +0,85 / −0,40 / ±5,0 | |

Rozdělení podle původu, protože se s nimi zachází jinak:

- **Z modelu**: dosah špičky rotoru, offsety senzorů. Změna modelu je musí
  rozbít, a konzistenční kontrola to zařídí.
- **Naměřené**: brzdná dráha, řádově rezerva koridoru. Změnou stroje se mění.
- **Politika**: rychlost, odstupy, prahy hranic. Volba, ne měření.
- **Nepodložené**: dva stupně chyby náklonu. Simulace na ně odpověď nemá.

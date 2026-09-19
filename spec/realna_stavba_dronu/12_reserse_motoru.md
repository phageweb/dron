# Rešerše motorů pro Pavo20 Pro 4S

Stav nabídek a parametrů ověřen **16. 9. 2026**. Cílem není najít
nejrychlejší motor pro běžné Pavo20, ale pohon pro tento konkrétní stroj:
Pavo20 Pro s 4S baterií, 2,2" ducty a vzletovou hmotností kolem 229 g kvůli
LD06 a OpenIPC. Rám vyžaduje montáž **4× M2 na kružnici 9 mm** a vrtuli s
hřídelí 1,5 mm.

## Závěr

**První volba je BetaFPV LAVA 1104 5500KV, ale jako ověřený komplet s
vrtulí Gemfan D2.2-3, ne s dnešní 2218.** Je to jediný nalezený motor, pro
který výrobce současně potvrzuje:

- 4S, 2,2" vrtuli a mechaniku Pavo20 Pro;
- rozteč 9 mm, čtyři M2 a hřídel 1,5 mm;
- hmotnost 5,3 g, maximální proud 7,7 A a výkon 123,5 W;
- přes 230 g statického tahu s vrtulí Gemfan D2.2-3.

Zdroj je přímo [karta motoru BetaFPV](https://betafpv.com/products/lava-series-1104-brushless-motors).
Stejný motor je nyní i v [nabídce Allegro CZ](https://allegro.cz/produkt/betafpv-lava-1104-5500kv-24mm-motor-pro-fpv-dron-pavo20-pro-1-ks-f5749340-73f0-4290-87af-aa4725312259):
446 Kč za kus, zobrazeno 6 kusů, doprava od 55 Kč. Tím padá důvod,
proč ho původní kusovník nahradil Flashhobby A1204: motor už lze koupit
z českého rozhraní bez samostatného dovozu z Francie. Před objednáním je
nutné znovu zkontrolovat skutečný počet kusů u prodejce.

## Srovnání kandidátů

| Motor | 4S | Montáž | Hmotnost | Publikovaný proud / tah | Verdikt |
| --- | --- | --- | ---: | --- | --- |
| **BetaFPV LAVA 1104 5500KV** | ano | 9 mm, 4× M2 | **5,3 g** | 7,7 A; **>230 g s D2.2-3** | **vybrat**; přímo určený pro 4S Pavo20 a jako jediný má relevantní tahovou tabulku |
| Flashhobby A1204 5200KV | uváděno 2–4S | 9 mm, M2 | 6,2 g | relevantní tah s 2,2" vrtulí nezveřejněn | rozumná levná záloha z Rotoramy, ale 202 g v modelu je pouze výpočet |
| GEPRC GR1204 5000KV | ano, 3–4S | výrobce ji na kartě neuvádí | **3,8 g** | tah ani proud neuveden | papírově lehký, ale bez mechanického a tahového důkazu se koupit nedá |
| GEPRC SPEEDX2 1303.5 5500KV | ano, 2–4S | 9 mm, M2 | 6,5 g | 8,7 A; tah neuveden | elektricky vhodný, ale zvon Ø17,35 mm je proti LAVA větší a pro starší duct neověřený |
| HGLRC SPECTER 1303.5 5500KV | ano, 2–4S | 9 mm, M2 | 7,15 g | relevantní tah neuveden | těžší alternativa bez doloženého přínosu |
| BetaFPV 1105 5000KV | ano | 9 mm, M2 | 5,2 g | katalog bez relevantního tahu | starší záloha pro 2–3"; LAVA má pro tento rám lepší data |

Podklady: [Flashhobby A1204 u Rotoramy](https://www.rotorama.com/product/flashhobby-a1204-5200kv),
[GEPRC GR1204](https://geprc.com/product/geprc-gr1204-5000kv-motors/),
[GEPRC SPEEDX2 1303.5](https://geprc.com/product/geprc-speedx2-1303-5-3800kv-5500kv-motor/),
[HGLRC SPECTER 1303.5](https://www.hglrc.com/products/hglrc-specter-1303-5-5500kv-brushless-motor)
a [BetaFPV 1105](https://betafpv.com/products/1105-6000kv-motors-4-pcs).

### Vyřazené varianty

- LAVA 1104 **7200KV** je 3S varianta; na 4S sem nepatří.
- T-Motor F1204 5000KV je výrobcem/prodejcem veden pro 2–3S, ne pro 4S.
- DarwinFPV Bling 1104 5000KV má 8,5 mm a M1,6, takže nepasuje do 9mm M2
  otvorů rámu.
- Motory 1303.5 a 1404 nejsou automaticky lepší jen větším statorem.
  Bez zkoušky v ductu není znám jejich tah ani chlazení a větší zvon může
  narazit na plastovou geometrii, která byla navržena pro 1104.

## Co se změní proti dnešnímu kusovníku

Dnešní sestava má čtyři A1204 po 6,2 g a jednu sadu 2218 o 2,32 g.
Komplet LAVA + D2.2 vychází podle publikovaných hmotností na:

| | Flashhobby + 2218 | LAVA + D2.2 |
| --- | ---: | ---: |
| 4 motory | 24,80 g | 21,20 g |
| 4 vrtule | 2,32 g | 3,80 g podle BetaFPV |
| Celý pohon | 27,12 g | **25,00 g** |
| Odhad vzletové hmotnosti | 229,34 g | **227,22 g** |
| Statický tah | 808 g, jen odvozeno | **>920 g, publikováno** |
| Tah / hmotnost | 3,52 | **>4,05** |

Jde tedy asi o **15 % lepší poměr tahu k hmotnosti**, ne o zázračnou
úsporu hmotnosti. Cena čtyř motorů na Allegro je 1 784 Kč proti dnešním
1 076 Kč za Flashhobby, tedy +708 Kč před dopravou. Evropskou alternativou
je [Drone-FPV-Racer](https://www.drone-fpv-racer.com/en/betafpv-lava-1104-5500kv-24mm-fpv-motor-16354.html)
za 14,90 €/kus; stejný obchod má [osm vrtulí D2.2-3](https://www.drone-fpv-racer.com/en/d22-3-pc-15mm-propellers-8pcs-by-gemfan-15604-84386.html)
za 3,90 €.

**Pozor na vrtuli:** 230 g je měření pro Gemfan **D2.2-3 s pitch 1,5"**.
Kusovník dnes kupuje Gemfan **2218 s pitch 1,8"**. Mají stejný průměr a
hřídel, ale nejsou to stejné vrtule. Nelze tedy vzít 230 g z katalogu LAVA a
současně v modelu ponechat 2218 jako by šlo o změřenou kombinaci.

## Elektrika a mechanické riziko

Čtyři LAVA motory mají katalogové maximum 30,8 A dohromady. MicoAir H743
V2 uvádí [45 A trvale na každém ze čtyř ESC](https://micoair.com/flightcontroller_micoair743v2_aio_45a/),
takže deska není limitem. Při 227,22 g je tah ve visu 56,8 g na motor, zhruba
25 % publikovaného statického maxima. To je pro regulaci zdravá rezerva, ale
stroj je pořád výrazně těžší než 140g vzletová hmotnost doporučená u
vrtule D2.2; teplotu motorů a skutečnou výdrž nelze převzít ze stock Pava.

LAVA 5500KV se nyní prodává jen s **24mm vodičem a konektorem**. MicoAir má
pájecí plošky, ne odpovídající motorové konektory. Před objednáním se musí
na skutečném rámu ověřit, zda po odstřižení konektoru vodiče dosáhnou k
rohovým ploškám. Pokud ne, prodloužení vodičů ubere část hmotnostní výhody
a přidá čtyři místa, která se mohou mechanicky unavit.

## Co ověřit před změnou modelu

1. Koupit nejprve **jeden** LAVA 1104 5500KV a jednu sadu D2.2-3.
2. Ověřit 9mm montáž, vůli zvonu, délku vodičů a vůli vrtule v ductu
   skutečného Pavo20 Pro.
3. Na tahové stolici změřit LAVA + D2.2 na 4S při 25, 50, 75 a 100 % plynu:
   tah, proud, napětí a teplotu po 30 s. Stejně změřit A1204 + 2218.
4. Teprve podle křivky přepsat `maxRotVelocity`, `motorConstant`,
   `momentConstant` a `MOT_THST_HOVER`. Samotné KV ani jeden bod maximálního
   tahu nestačí pro kalibraci simulace.

Do té doby je bezpečné ponechat Flashhobby v existujícím modelu označený
jako **odhad**. Pro fyzický nákup ale dává LAVA + D2.2 lepší smysl: pasuje,
je dostupný, je lehčí a jeho výkon je doložen na konkrétní vrtuli.

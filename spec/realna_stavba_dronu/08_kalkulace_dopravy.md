# Kalkulace: kde nakoupit, když se doprava zdražila

Doplněk k [nákupnímu seznamu](./06_nakup.md). Odpovídá na jednu otázku: **při
dnešních sazbách dopravy se u které položky vyplatí dovoz z Číny a u které ne.**
Allegro se tu počítá jako tuzemský kanál (EU, bez cla, běžná doprava), ne jako
dovoz.

Kurzy ČNB 11. 9. 2026: **1 € = 24,26 Kč**, **1 $ = 20,93 Kč**, **1 zł = 5,61 Kč**.
Ceny e-shopů ověřené **13. 9. 2026**. Přepočítat jde skriptem
[`scripts/nakup_calc.py`](../../scripts/nakup_calc.py) — sazby dopravy jsou v
něm nahoře v `SHIP`.

## Nález, který mění rozdělení objednávek

Kusovník posílá kupovat MTF-02P a Wyvern na **rotorama.com / rotorama.de**.
Obojí je přitom na **rotorama.cz**, za prakticky stejné peníze:

| Díl | Kusovník (Rotorama EU) | Rotorama CZ | Rozdíl |
| --- | ---: | ---: | ---: |
| MicoAir MTF-02P | 20,49 € = 497 Kč | **499 Kč**, skladem | +2 Kč |
| EMAX Wyvern Link Alpha | 82,39 € = 1 999 Kč | **2 019 Kč**, skladem | +20 Kč |

Zboží je o 22 Kč dražší, ale **odpadá celá jedna zahraniční zásilka**. Při
odhadovaných 240 Kč za dopravu z Rotoramy EU je to čistá úspora ~218 Kč a
o jednu zásilku méně, na kterou se čeká. Bod 4 v „Doporučeném rozdělení
objednávek" v kusovníku je tím pádem zbytečný.

Rám na Rotoramě samostatně není (jen kompletní drony a náhradní chrániče),
takže Aerodrone jako samostatná objednávka zůstává.

## Doprava, se kterou se počítá

| Obchod | Kč / zásilka | Zdroj |
| --- | ---: | --- |
| Rotorama CZ | **89** na adresu, **59** Zásilkovna | ověřeno na webu, **žádný limit dopravy zdarma** |
| Aerodrone CZ | 99 | odhad, sazba není zveřejněná |
| FPV24 (DE) | 240 (9,90 €) | odhad podle jejich rakouského tarifu do 100 € |
| RCTech (DE) | 291 (12 €) | odhad; LiPo jen pozemní přepravou, tedy dráž a pomaleji |
| Dovoz LD06 (Sunhokey) | 419 (20 $) | odhad |
| AliExpress | 73 (3 €) na prodejce | odhad; často „zdarma", ale pomalu |
| Allegro (PL → CZ) | 112 (20 zł) | odhad, prodejce od prodejce se liší |

Ověřená je jen sazba Rotoramy. Ostatní jsou odhady — proto je ten skript
parametrický: přepiš sazbu a spusť znovu.

## Srovnání variant celé objednávky

Bez videa se počítá Wyvern (lehčí varianta, kterou používá model v `cad_codex`).

| Varianta | Zboží | Doprava | Zásilek | Celkem | Proti B |
| --- | ---: | ---: | ---: | ---: | ---: |
| **A** kusovník tak, jak je napsaný | 11 170 | 1 378 | 6 | **12 548 Kč** | +218 |
| **B** konsolidovaně, MTF-02P a Wyvern z rotorama.cz | 11 192 | 1 138 | 5 | **12 330 Kč** | — |
| **C** B + motory, AIO, vrtule a RX z AliExpressu | 10 247 | 970 | 5 | **11 218 Kč** | −1 112 |
| **D** B + z AliExpressu jen AIO | 10 672 | 1 211 | 6 | **11 882 Kč** | −448 |

Zboží u varianty A je o 22 Kč **levnější** než u B, protože rotorama.com prodává
MTF-02P i Wyvern o ty korunky níž než rotorama.cz. Celé to ale sežere jedna
zahraniční zásilka navíc, takže konsolidace stojí +218 Kč — přesně tolik, kolik
říká nález nahoře.

Varianta C vychází nejlíp, ale za cenu toho, že **AIO, motory i přijímač
přijdou za tři až šest týdnů a bez evropské reklamace.** Varianta D bere
z toho jen ten jeden kus, kde je rozdíl skutečně velký.

## Co se vyplatí dovážet a co ne

Test je marginální: ušetřeno na zboží mínus jedna zásilka z AliExpressu navíc
(73 Kč). Položky, které stejně kupuješ z Rotoramy, mají mezní dopravu **nula** —
89 Kč zaplatíš tak jako tak.

| Díl | CZ/EU | Čína | Úspora zboží | Po dopravě | Verdikt |
| --- | ---: | ---: | ---: | ---: | --- |
| MicoAir H743 V2 AIO | 2 090 | 1 569 (74,99 $) | +521 | **+448** | **vyplatí se** |
| SPEEDX2 1404 3850KV ×4 | 1 516 | 1 255 (14,99 $/ks) | +261 | +188 | hraniční |
| SpeedyBee Nano ELRS RX | 313 (12,90 €) | 230 (10,99 $) | +83 | +10 | nevyplatí |
| HQProp DT76 ×3 sady | 237 | 157 | +80 | +7 | nevyplatí |
| LDRobot LD06 | 1 580 (75,50 $) | 1 580 | 0 | −73 | už to **je** dovoz |
| MicoAir MTF-02P | 499 | — | — | — | **ber v CZ**, je levný |
| Tattu 4S LiHV 750 long | 1 448 (3 ks) | — | — | — | **z Číny to nejde** |
| GEPRC CineLog30 V3 rám | 1 490 | neověřeno | ? | ? | ber v CZ, viz níž |

**Jediná položka, kde má dovoz jasný smysl, je AIO.** 448 Kč po dopravě je
skoro čtvrtina jeho ceny. Motory jsou hraniční — 188 Kč za čtyři kusy je
nejistota kurzu a jedné zásilky; pokud stejně objednáváš AIO z AliExpressu,
přidej je do stejného košíku u stejného prodejce a je to zadarmo, jinak to
nemá cenu.

U přijímače a vrtulí je rozdíl **v řádu desetikorun** a zmizí na první zásilce.
Ty kupuj v Evropě bez přemýšlení.

## Tři věci, které se z Číny nevyplatí z jiného důvodu než z ceny

**Baterie.** Tattu 4S LiHV 750 mAh „long" se z Číny letecky neposílá — LiPo
podléhá omezení letecké přepravy a AliExpress ji do EU prakticky nedodá.
RCTech jako zdroj zůstává, a to i s tou drahou pozemní dopravou. Navíc jde
o **konkrétní podlouhlou 15,2V variantu**, se kterou počítá CAD; „podobná"
baterie z marketplace je právě ta záměna, před kterou kusovník varuje.

**LD06.** Dovoz to už je, takže tady se nerozhoduje mezi CZ a Čínou, ale mezi
Čínou a **Allegrem**: tam se LD06/LD19 prodává kolem **395 zł = 2 216 Kč**, což
je proti 1 580 Kč ze Sunhokey o **636 Kč dráž**. I po připočtení dopravy je
přímý dovoz levnější. Allegro dává smysl jen tehdy, když chceš díl do týdne
a s evropskou reklamací — u dílu, u kterého kusovník požaduje kontrolu
fotografie štítku a konektoru, to za úvahu stojí.

**Rám.** Cenu samotného rámu GEP-CL30 **V3** se na AliExpressu nepodařilo
ověřit — nabídky, které vyhledávač našel, jsou buď starší CL30, nebo celý
dron. Za 1 490 Kč u Aerodrone to nemá smysl dál honit; rozdíl by musel být
přes 400 Kč, aby zaplatil zásilku a riziko, že přijde jiná verze rámu.

## Co z toho plyne pro objednávku

1. **Aerodrone CZ** — rám. 1 490 Kč + 99.
2. **Rotorama CZ** — motory, vrtule, MTF-02P, Wyvern *(a AIO, pokud nejdeš
   do dovozu)*. 89 Kč dopravy, Zásilkovna 59.
3. **FPV24** — přijímač. Zůstává, protože na Rotoramě skladem nebyl; jinak by
   patřil do bodu 2 a ušetřil 240 Kč.
4. **RCTech** — baterie. Neobejitelné.
5. **Dovoz** — LD06, a případně AIO ve stejném období.

Kusovník uvádí **5 333 Kč** za českou část košíku — to je rám, motory, vrtule
a AIO, bez videa a bez dopravy. Po přesunu MTF-02P a Wyvernu na rotorama.cz
je česká část **7 851 Kč za zboží**, tedy **8 039 Kč včetně obou zásilek**;
je v ní ale o dvě položky víc, než kolik jich kusovník do těch 5 333 Kč
počítal, a celé video.

## Co v tomhle výpočtu ověřené není

- Sazby dopravy u Aerodrone, FPV24, RCTech a Sunhokey jsou odhady. Skutečné
  číslo se ukáže až v košíku; u FPV24 a RCTech to může být i dvojnásobek.
- Ceny „Čína" jsou ceníky výrobců a Banggoodu (MicoAir store, GEPRC, Banggood),
  ne živé ceny konkrétní nabídky na AliExpressu — ty se nepodařilo načíst.
  Ber je jako řádovou hladinu, ne jako cenu, za kterou to koupíš.
- Cena rámu GEP-CL30 V3 na AliExpressu a Allegru je neznámá.
- Kusovníku pořád chybí **palubní počítač** — viz nález v
  [Alternativy a zkušenosti](./07_alternativy_a_zkusenosti.md). Ať tahle
  kalkulace vyjde jakkoliv, není to cena hotového stroje.

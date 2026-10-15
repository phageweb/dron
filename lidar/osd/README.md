# Sken lidaru přes OSD

Letový počítač zapíše každou otáčku lidaru jako znaky do spodních řádků OSD.
Walksnail je přenese spolu s videem a pozemní stanice je přečte zpátky.
Proč tahle cesta a jak se změří linka: [Test linky pro sken](../../spec/realna_stavba_dronu/15_test_linky_skenu.md).

| Soubor | Kde běží | Co dělá |
| --- | --- | --- |
| `scan_osd.lua` | H743, ArduPilot Lua | čte LD06/D500, skládá otáčky, píše rámce do OSD, plní proximity backend |
| `osdscan.py` | zem | z MSP DisplayPort složí plátno, dekóduje rámce a skládá otáčky |
| `osdvideo.py` | zem | totéž z obrazu VRX: živě ve `vrx.py`, nebo ze záznamu `.mkv` |
| `glyphs_vrx_btfl.npz` | zem | šablony znaků Betaflight fontu, jak ho kreslí VRX (výchozí, `MSP_OPTIONS 4`) |
| `glyphs_vrx_ardu.npz` | zem | šablony ArduPilot fontu, pro záznamy do 14. 10. 2026 |
| `upload.py` | notebook | nahraje skript na SD kartu FC přes USB a restartuje skripty |
| `test_osdscan.py` | notebook | Lua kodér proti Python dekodéru na reálných datech z D500 |
| `test_osdvideo.py` | notebook | čtení z obrazu na třech skutečných snímcích z VRX (`vrx_frames.npz`) |
| `sitl_check.sh` | notebook | celý řetězec v SITL, bez VTX |

```sh
PATH=$(nix build --no-link --print-out-paths nixpkgs#lua5_4)/bin:$PATH python3 lidar/osd/test_osdscan.py
lidar/osd/sitl_check.sh 30          # v dev shellu projektu
python3 lidar/osd/test_osdvideo.py  # potřebuje numpy
```

## Čtení z obrazu VRX

```sh
nix run .#vrx                       # radar vpravo v okně, klávesa L ho skryje
nix run .#osdvideo -- ~/Videos/vrx/vrx_….mkv --session lidar/sessions
nix run .#lidar                     # záznam je pak v seznamu „záznamy…“ i s videem
```

`--session` udělá ze záznamu VRX stejný záznam, jaký dělá telefon
(`video.mp4`, `lidar.jsonl`, `meta.json`), takže ho webová stránka lidaru
přehraje synchronně s videem. Bez `--session` program jen vypíše, kolik
otáček v záznamu našel. Záznamy z doby před změnou abecedy
(do 15. 10. 2026) potřebují `--old-alphabet`, `vrx.py` totéž.

Jak to čte: buňka OSD má v obraze 1080p rozměr 36 × 54 px, řádky 16 a 17
mají střed na y = 900 a 954 a sloupec *c* na x = 27,3 + 36 *c*. Z buňky
se vezme bílá maska a porovná se se šablonami znaků. U buněk, kde si
porovnání není jisté, se zkusí i druhý nejbližší znak. Který z nich platí,
rozhodne CRC: je lineární nad GF(2), takže stačí vyřešit soustavu
16 rovnic, ne zkoušet všechny kombinace. Ze správně přečtených rámců se
šablony průběžně doučují. `vrx.py` si naučené šablony ukládá do
`~/Videos/vrx/glyphs_vrx.npz`, `osdvideo.py --learn` je přepočítá ze záznamu.

### Font ve VRX

VRX kreslí OSD fontem podle toho, za jaký FC se ArduPilot vydává. 15. 10.
2026 po restartu VRX začal kreslit **Betaflight font**, i když FC hlásil
ArduPilot: šipky na jiných písmenech, `p` budík, `z` teploměr, místo
desetinných čísel žluté čárky. Pořadí zapnutí FC a VTX to nespravilo.
`MSP_OPTIONS 4` (EnableBTFLFonts) to vyřešilo: ArduPilot se pak VTX hlásí
jako `BTFL` a ikony posílá na místa Betaflight fontu, takže OSD je čisté
a font je pokaždé stejný.

V Betaflight fontu jsou některé znaky abecedy barevné ikony nebo skoro
prázdné (dvě čárky v rozích). Dekodér proto bere nejjasnější barevný
kanál, ne jas, a snímek zahodí jako nedokreslený až při víc než 8 prázdných
buňkách.

**Kalibrace fontu.** Když se nepřečte většina snímků, `osdvideo.py` font
nejdřív zkalibruje z celého záznamu: buňky seskupí podle tvaru a který tvar
je který znak, spočítá z CRC jako soustavu rovnic nad GF(2), každý snímek
dá 16 rovnic. Nic o fontu předem vědět nemusí. Na Betaflight fontu z ~250
různých snímků vychází jednoznačně skoro všech 72 tvarů a přečte se 100 %
čistých snímků. `vrx.py` totéž dělá živě po 20 nečitelných snímcích za sebou.

Na záznamu z 15. 10. 2026 01:51 (51 s chůze bytem) se přečetlo 871 snímků
a 96 otáček (1,9/s). Nečitelné zůstávají snímky, kde je za písmem jasné
pozadí: kamera mířící na obrazovku notebooku nebo na osvětlený strop.

Na záznamu z 14. 10. 2026 (92 s, stará abeceda, dron na stole) se přečetlo
1 313 snímků s řádky a 3 ne. Vyšlo z nich 542 různých rámců a 130 celých
otáček za 68 s. Jeden snímek trvá v `vrx.py` asi 10 ms.

S novou abecedou (`scan_osd.lua` nahraný přes MAVFTP 15. 10. 2026, 25 s
z VRX, ještě ArduPilot font): přečteno 479 snímků s řádky ze 479, druhý
odhad potřebovalo jen 11 z nich a po doučení šablon žádný. Vyšlo 197 rámců
a 47 otáček (1,9/s).

## Formát

Otáčka se rozdělí na **144 výsečí po 2,5°**. Pro každou se pošle nejbližší
vzdálenost jako **9bitový kód**: 0 znamená bez odrazu, 1–511 je logaritmická
stupnice od 50 mm do 12 m s krokem asi 1,1 %. To je zhruba 1 cm na 1 m a 9 cm
na 8 m. Úhel je v rámci lidaru, tedy od předku po směru hodinových ručiček;
výseč *i* má střed v (*i* + 0,5) · 2,5°.

Jedna otáčka se pošle jako **tři rámce** po 48 výsečích. Rámec má 77 znaků
z abecedy 64 znaků, 6 bitů na znak:

```text
0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqr<>[]%@/z-+
```

Malá písmena kreslí font Walksnailu pro ArduPilot jako šipky a ikony
a `s t u v w x y` vypadají přesně jako `b d f h j l n`. Proto jsou na jejich
místech `< > [ ] % @ /`. Hodnoty znaků zůstaly stejné. `osd:write` z Lua
posílá text tak, jak je, `%` tedy nic neformátuje. Ověřeno v SITL
15. 10. 2026: 189 rámců, 0 vadných, 3,1 otáčky/s.

| znaky | obsah |
| --- | --- |
| 1 | číslo otáčky 0–63 |
| 1 | číslo rámce 0–2 |
| 72 | 48 × 9 bitů, od nejvyšších bitů |
| 3 | CRC-16/CCITT-FALSE přes hodnoty předchozích 74 znaků (4 + 6 + 6 bitů) |

Na obrazovce zabírá rámec **řádky 16 a 17** plátna 50 × 18 (`OSD1_TXT_RES 1`).
Řádek 16 je celý, na řádku 17 jsou znaky 51–77 od levého okraje. Zápis je po
nejvýš 25 znacích, protože MSP DisplayPort jich vezme nanejvýš 30.

Skript posílá jeden rámec za 100 ms, protože tak často ArduPilot překresluje
OSD. Rozpracovanou otáčku dopošle celou a pak vezme nejnovější; otáčky mezi
tím zahodí.

## Na desce

```text
SCR_ENABLE 1
SERIAL5_PROTOCOL 28   SERIAL5_BAUD 230    lidar
SERIAL2_PROTOCOL 42   SERIAL2_BAUD 115    HD VTX
OSD_TYPE 5            OSD1_TXT_RES 1
MSP_OPTIONS 4                             VRX pak kreslí vždy Betaflight font
PRX1_TYPE 15                              vyhýbání ze stejných dat
```

`scan_osd.lua` patří do `APM/scripts/` na SD kartě. Nahraje ho tam přes
USB, bez vyndávání karty, `nix run .#fc-upload` (`upload.py`, MAVFTP):
odmítne nahrávat do zajištěného dronu, soubor přečte zpátky a porovná,
restartuje skripty a vypíše, co FC hlásí.

**Na ArduPilotu 4.7.1 skript nepoběží**, protože `osd:write` je až v masteru.
Deska proto potřebuje master: `nix run ./firmware#flash-master`, viz
[Master na desce](../../firmware/README.md#master-na-desce).

## Ověřeno 8. 10. 2026

- **Kodek na skutečných datech.** Surové bajty z D500 (`d500_sample.bin`)
  projdou Lua parserem a kodérem a výsledné rámce jsou znak po znaku stejné
  jako z Python kodéru. Záznamy z telefonu, 176 000 bodů, tedy 50 600
  výsečí: chyba vzdálenosti po přenosu má medián 1,8 mm, u 95 % výsečí je
  do 10 mm a nejvýš 38 mm. Změna jednoho libovolného znaku CRC vždy odhalí.
- **Celý řetězec v SITL** (master `8b9ea70`): za 28 s 89 celých otáček,
  **3,17 otáčky/s**, z 3,33 možných při 10 rámcích/s. 0 vadných rámců,
  1 neúplná otáčka na startu. Simulovaný LD06 se točí 6×/s a v prázdném světě
  nic nevidí, takže SITL ověřuje přenos, ne obsah. Obsah ověřil předchozí test.
- **Limit Lua:** nejhorší volání je asi 7 500 instrukcí z 10 000
  (`SCR_VM_I_COUNT`). Načtení skriptu stojí 1 100, protože CRC tabulky jsou
  vepsané jako čísla; kdyby se počítaly při startu, stálo by to 28 700 a
  skript by neběžel.

## Co zbývá

- **Polovina překreslení je bez našich řádků, potvrzeno.** Na záznamu
  z VRX 14. 10. 2026 je ve 33 % snímků obrazovka bez řádků a v 17 % jsou
  řádky napůl vykreslené. VRX ukáže asi 5,7 různých rámců za sekundu místo 10.
  Proto přišlo jen 1,9 otáčky/s, protože ztracený rámec shodí celou otáčku.
  Pomohlo by posílat řádky i v prvním DRAW, nebo skládat otáčku z částí
  různých otáček.
- **Rychlejší přenos:** se čtyřmi řádky by šly dva rámce na jedno překreslení,
  tedy ~6,6 otáčky/s.
- **Náklon dronu v hlavičce**, aby šly skládat nakloněné řezy do 3D.

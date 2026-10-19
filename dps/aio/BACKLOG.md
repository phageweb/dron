# Backlog: dotrasování desky AIO

**Změna zadání 19.–20. 10. 2026:** znovu projít vznik DPS, co nejvíc automaticky,
primární vzor **MicoAir743v2-AIO-45A**. Uživatel připouští promyšlené změny
rozmístění i ostatních částí. Původní omezení níže o nedotknutelné mědi ESC už
není absolutní; případná změna musí mít technické zdůvodnění a ověření.
Nový postup, referenční profil, příkazy a meze automatizace jsou v
[AUTOMATIZACE.md](./AUTOMATIZACE.md). Starý seznam 22 spojů níže platí pro
nezměněnou hlavní desku, nikoliv pro vygenerovanou variantu V2.

Předávka 19. 10. 2026 večer. Podrobná historie je v [NAVRH.md](./NAVRH.md), kap. 7 (Deska)
a kap. 8 (Otevřené otázky). Tady je jen to, co zbývá udělat, a jak.

## Stav

- `aio.kicad_pcb`: **22 nespojených spojů** (všechno signály), DRC **0 chyb**, schéma a deska
  sedí (14 `net_conflict` jsou známé piny bez padu v ESC a USB-C). ERC 18 chyb, všechny vysvětlené.
- Natrasováno 134 ze 156 párů routerem `gen/trasuj.py`, únik z BGA hotový (kromě kuliček D2
  +3.3V, J8 IMU2_SCK a J6 IMU2_INT, ty čekají na trasování z kuličky).
- Rozmístění je podle MicoAir743-AIO zrcadlově, protože obvod desky (motory, baterie, tranzistory
  ESC z OpenAIO) je zrcadlo MicoAiru. Piny GPS (UART8), přijímače (UART5), LD06 (USART3), Bluetooth
  padů (UART7) a obou IMU (BMI270 na SPI1, ICM-42688 SCK/CS/DRDY na PB13/PB12/PE12) jsou kvůli tomu
  přeřazené; hwdef `hwdef/Pavo20AIO` je upravený a firmware se sestaví (`hwdef/sestav.sh`).
- Commit `73ac7fd` obsahuje přeskládání a router, deska je natrasovaná touto verzí `trasuj.py`.
- Rozpracovaný rip-up a reroute v `trasuj.py` z jiné session (`TRASUJ_RIP`: neprošlý pár smí
  přes trasy téhož běhu, ty se vytrhnou a zařadí znovu) je v `git stash` („trasuj.py: rip-up…“,
  `git stash show -p`). Jeho běh skončil stejně jako bez něj (134 / 22) a poslední úprava není
  vyzkoušená. Použít jen, pokud se vyplatí ho dodělat.

## Úkol

Dotáhnout všech 22 spojů tak, aby DRC hlásilo 0 nespojených a 0 chyb. Pak prošít ostrovy GND
(`--prosij`), přegenerovat tabulky a zapsat výsledek do `NAVRH.md` kap. 7 a 8.

## Proč to router sám nedá

Router trasuje spoje jeden po druhém a položený vodič už neposune. Okolí BGA je přitom těsné:
- trasovat se smí jen po L1, L3, L6, L8 (L2/L7 rovina GND, L4 +BATT, L5 napájení);
- na L3, L6 a L8 kolem BGA a pod ním leží pevná měď ESC z OpenAIO (budiče, fáze, AT32), se
  kterou se nehýbe;
- změna vrstvy znamená microvia L1–L2 + buried via L2–L7 (+ microvia L7–L8), buried via musí
  být volná na všech vnitřních vrstvách najednou;
- na L1 je mezi BGA a díly jen pás pár milimetrů, kudy vychází přes 60 signálů.

`--pretrasuj` (průchody, kde neprošlé sítě jdou příště první) i rip-up skončily na 22 až 24.
Příklad, SWCLK (kulička A9 → pad TP304, 3,4 mm): přes cestu vedou na L1 vodorovně SD_CMD
(y 68,71) a SD_D0 (y 70,11) ke slotu, vedle je R301 s prokovem +3.3V a pod TP304 na L3/L8 fáze 2C
a budič ESC2, takže se nevejde ani prokov. Router položil sběrnici SD dřív a nejkratší cestou.

Spoje je tedy potřeba řešit po jednom, jako člověk: uvolnit konkrétní místo (posunout drobný díl,
vytrhnout a jinudy vést blokující vodič), daný spoj natrasovat jako první a vrácené pak znovu.

## Zbývající spoje

Souřadnice v mm (KiCad, y roste dolů). Střed BGA U301 je 75,9; 64,1, kuličky ±3,6 mm, rozteč 0,8,
řada K nahoře, A dole, sloupec 10 vlevo, 1 vpravo.

| Síť | Od | Do | Poznámka |
| --- | --- | --- | --- |
| SWCLK | A9 (73,10; 67,70) | TP304 (72,50; 71,00) | přes cestu SD_CMD a SD_D0 na L1, R301 vedle; viz výš |
| PDR_ON | R301.2 (73,32; 69,61) | microvia u F7 (74,70; 63,70) | R301 sedí v pásu úniků pod BGA, přesunout ho |
| SD_D2 | únik B9 (72,70; 67,30) | J302.1 (65,56; 62,21) | sběrnice SD |
| SD_D2 | únik B9 (72,70; 67,30) | R312.2 zespodu (75,92; 74,91) | pull-up |
| UART1_TX | únik C9 (73,10; 66,10) | J305.3 zespodu (81,50; 71,50) | z JZ rohu BGA podél jihu na spodek |
| RC_TX | únik B5 (75,90; 67,30) | J305.5 zespodu (79,50; 71,50) | |
| GPS_RX | únik D4 po L2 (79,75; 65,30) | J303.4 (80,50; 71,50) | únik vylezl na východ, konektor je dole |
| EXT_SDA | A4 (77,10; 67,70) | R315 / vodič (81,20; 69,61) | I2C1 ke GPS |
| LED_R | B3 (77,90; 66,90) | D301.1 (84,30; 69,39) | LED by mohly jít jinam (třeba k J303) |
| VBAT_SENSE | F1 (79,50; 63,70) | C314.1 (84,50; 62,73) | vpravo od BGA krystal Y301 |
| ESC_CURRENT | F2 (78,70; 63,70) | buried via (71,16; 65,38) | přes celé BGA; zvážit cestu po L3/L6 pod BGA |
| IMU_SPI.MISO | J3 (77,90; 61,30) | U8.1 (78,95; 52,84) | BMI270 nad BGA |
| IMU_SPI.MOSI | K3 (77,90; 60,50) | U8.14 (79,12; 53,51) | |
| IMU_INT | únik G4 po L2 (77,10; 62,90) | U8.4 (77,45; 52,84) | |
| IMU2_MISO | únik E2 (79,10; 63,55) | vodič u U303 (77,25; 58,73) | ICM-42688 nad BGA |
| IMU2_SCK | J8 (73,90; 61,30) | U303.13 (76,00; 58,53) | únik z kuličky chybí |
| IMU2_CS | K8 (73,90; 60,50) | U303.12 (75,50; 58,53) | blokuje ho UART7 z J5 k TP314 |
| UART7_RX | únik H5 (76,30; 62,10) | TP314 (72,60; 52,11) | pady Bluetooth, dají se posunout |
| LIDAR_TX | únik J9 (72,70; 60,90) | TP201 (74,90; 54,71) | pad LD06 |
| PWM11 | únik po L2 (73,90; 62,10) | TP319 (67,70; 51,61) | pad, dá se posunout |
| MOTOR2 | K6 (75,50; 60,50) | vodič zespodu (72,40; 61,20) | k R58 v ESC2 |
| +10V_VTX | C203.1 (81,53; 56,01) | vodič na L6 (82,15; 59,36) | spínač VTX U201, třída Power 0,3 mm |

## Nástroje

Všechno v `nix develop ./dps` (KiCad 10, pcbnew v Pythonu přes wrapper):

```sh
A=dps/aio/gen/aktualizuj_desku.sh
$A --trasuj [deska] [regex sítí]     # natrasuje jen spoje sítí podle regexu, do skupiny "trasuj"
$A --trasuj [deska] --smaz           # smaže všechno ze skupiny "trasuj"
$A --pretrasuj [deska] [průchodů]    # smaže "trasuj" a trasuje vše znovu v několika průchodech
$A --rucne [deska]                   # gen/rucne.py: ručně zadaná měď, skupina "rucne" (router ji nemaže)
$A --prosij [deska]                  # prošije ostrovy rozlití GND
$A --okoli deska L1.Top x y r        # co za měď je kolem bodu (síť, mezera, skupina)
$A --rozmisti                        # rozmístí díly, které leží mimo desku (x > 95)
$A --vycisti                         # smaže měď, na které přistály nové díly
kicad-cli pcb drc --schematic-parity --format json -o drc.json dps/aio/aio.kicad_pcb
python3 dps/aio/tabulky.py           # tabulky v NAVRH.md ze schématu
```

Proměnné routeru: `TRASUJ_OKNO` (mm kolem páru, 8 stačí), `TRASUJ_UZLY` (limit A*, 2,5 M),
`TRASUJ_PRVNI` (soubor se sítěmi, které jdou první). Celé `--pretrasuj` se 4 průchody trvá asi
30 min. Pravidla sítí (pořadí, vrstvy, cena prokovu) jsou v `RULES` v `trasuj.py`.

## Doporučený postup

1. Pracovat na kopii desky, `aio.kicad_pcb` přepsat až výsledkem s DRC bez chyb a s méně
   nespojenými. Kopie potřebuje vedle sebe `aio.kicad_pro`, `aio.kicad_dru`, `fp-lib-table`
   a odkaz `lib.pretty`, jinak DRC hlásí nesmysly.
2. Uvolnit pás pod BGA: přesunout R301 (PDR_ON) a případně SWD pady TP303/TP304, LED D301–D303
   s R316–R318 a I2C pull-upy, které v něm sedí. Pevné pozice se zadávají v `ANCHORS`
   v `gen/rozmisti.py`; díl se přesune tak, že se vyndá z desky (x > 95) a pustí se `--rozmisti`,
   pak `--vycisti`.
3. Pro každý spoj: `--okoli` na místech, kudy má vést, rozhodnout, co uhne. Vytrhnout jen sítě,
   které překážejí (smazat jejich vodiče ze skupiny "trasuj"), natrasovat napřed dotyčný spoj
   (`--trasuj kopie '^/MCU H743/SWCLK$'`) a pak vytržené (`--trasuj kopie 'SD_CMD|SD_D0'`).
4. Co router nenajde ani tak, zadat geometrií do `gen/rucne.py` (jako propojky USB-C tam).
   Prokovy: microvia 0,25/0,10 mm L1–L2 nebo L7–L8, buried via 0,33/0,15 mm L2–L7.
   Šířka a izolace podle třídy sítě v `aio.kicad_pro` (signály 0,09/0,09, Power 0,3/0,1,
   Analog 0,12/0,12).
5. Na konci `--prosij`, DRC, `tabulky.py`, zápis do NAVRH.md (kap. 7 výsledek, kap. 8 řádek
   „Trasování“) a commit.

## Co nedělat

- Neměnit měď ESC z OpenAIO (L3, L6, L8 kolem BGA, fáze, budiče) ani roviny L2/L7 mimo krátké
  propojky, jaké už jsou pod BGA a pod USB-C.
- Nepřepisovat schéma v KiCadu: generuje se z `gen/gen_aio.py` a pak `aktualizuj_desku.sh`.
- Nespouštět `--zbytky` naslepo: maže měď z OpenAIO podle stavu v gitu.
- Desku neotevírat v KiCadu současně se skripty (uložil by přes ni svou kopii).

## Další otevřené body (po dotrasování)

- Potisk: popisky padů z OpenAIO (cam, LED, gnd…) přepsat.
- Rotace IMU v hwdefu (`ROTATION_NONE`) doplnit podle toho, jak U8 a U303 sedí.
- LCSC čísla dílů s „—“, sklad TPS22810DRVR a ICM-42688-P (NAVRH.md kap. 8).
- Pin 1 konektorů J303–J305 ověřit multimetrem proti kabelu z MicoAiru před prvním zapnutím.

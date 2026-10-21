# Automatický postup a reference MicoAir V2

**Aktuální směr 21. 10. 2026:** rešerše a návrh přesunů jsou v
[RESERSE_LAYOUTU_V2.md](./RESERSE_LAYOUTU_V2.md), provedení v
[PREDAVKA_LAYOUTU_V2.md](./PREDAVKA_LAYOUTU_V2.md). Níže popsané nástroje zůstávají
k dispozici, ale před dalším trasováním je nutné řešit rozmístění a uvedené
limity kontrol, zejména chybějící courtyard a zúžení silových spojů routerem.

Rozhodnutí uživatele z 19.–20. 10. 2026: znovu projít vznik DPS, co nejvíc kroků
automatizovat a co nejvíc se řídit **MicoAir743v2-AIO-45A**. Rozmístění ani měď ESC
nejsou nedotknutelné; změna má mít technický důvod a ověřený výsledek. Starý cíl
„za každou cenu dokončit zbývajících 22 spojů na stávajícím layoutu“ tomu ustupuje.

## Co je skutečná reference

Zdroje: [výrobce, přesně V2 AIO 45A](https://micoair.com/flightcontroller_micoair743v2_aio_45a/),
[hwdef ArduPilotu](https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_HAL_ChibiOS/hwdef/MicoAir743v2/hwdef.dat)
(pro běhy používáme místní checkout `external/ardupilot`),
[repozitář výrobce](https://github.com/micoair/MicoAir743v2).
V nalezeném repozitáři jsou firmware a README, nikoliv schéma a PCB zdroj.
Pinout a vnější uspořádání tedy mohou být vzorem; skryté vrstvy a napájecí obvody
nelze z fotografie prohlásit za převzaté či ověřené.

Pozor na varianty: místní obrázek
`external/ardupilot/libraries/AP_HAL_ChibiOS/hwdef/MicoAir743-AIO/MicoAir743-AIO_Ports_Connection.jpg`
patří **starší 35A AIO**, nikoliv V2. Starší AIO má odlišný pinout IMU, LED i I2C.
Fotografie spodku navíc není ve stejné projekci jako horní pohled PCB.
Před převodem poloh z fotografie sjednotit revizi, stranu desky, orientaci a měřítko.
Odkaz na fotografii na hlavním webu výrobce vrací HTTP 404 i 21. 10. 2026.
Funkční fotografie V2 a diagram zapojení byly nyní nalezeny na jeho e-shopu:
[reference/README.md](./reference/README.md). Dokládají vnější uspořádání;
přesné souřadnice pouzder a vnitřní měď z nich stále nejsou ověřené.

## Dvě porovnatelné varianty

`current` reprodukuje nynější vlastní zapojení. `micoair-v2` vrací následující
funkce na referenční piny. Generátor současně vytvoří příslušný hwdef v kandidátovi.

| Funkce | Dosavadní AIO | Referenční varianta |
| --- | --- | --- |
| GPS, SERIAL3 | UART8, PE1/PE0 | USART3, PD8/PD9 |
| Přijímač, SERIAL6 | UART5, PB6/PB5 | USART6, PC6/PC7 |
| LD06, SERIAL5 | USART3 RX, PD9 | UART5 RX, PB5 |
| Bluetooth, SERIAL8 | UART7, PE8/PE7 | UART8, PE1/PE0 |
| BMI270 | SPI1 PA5/PA6/PA7, CS PA4, DRDY PC4 | SPI3 PB3/PB4/PD6, CS PA15, DRDY PB7 |
| Druhá IMU | SPI2 SCK PB13, CS PB12, DRDY PE12 | SPI2 SCK PD3, CS PD4, DRDY PC14 |

Poslední řádek je **naše adaptace**: stále ICM-42688-P, využívá CS/DRDY
akcelerometru BMI088 z reference. Není to kopie osazené BMI088. Nezapojený UART5 TX
a pady UART8 dostaly i odpovídající názvy sítí, aby značení nelhalo o periférii.

Zůstávají naše elektrické hodnoty: 10 V za spínačem TPS22810, proudový senzor
INA186A3/0,2 mΩ (`HAL_BATT_CURR_SCALE 50.0`), dělič 100k/10k
(`HAL_BATT_VOLT_SCALE 11.0`), vlastní board ID 25026 a současný obrys/stackup.
Převzetí kalibrací či firmware binárky MicoAiru by těmto obvodům neodpovídalo.
Rotace IMU se musí určit podle výsledného osazení; `ROTATION_NONE` je stále otevřený bod.

## Jeden příkaz pro opakovatelný běh

Spouštět z kořene repozitáře. Výstupní adresář musí být nový; bez `--output` se
vytvoří časově označený pod `build/aio/`.

```sh
# Stav současného projektu, bez generování a trasování:
nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --auto --check

# Referenční varianta: generování, synchronizace, rozmístění, únik BGA,
# trasování, prošití, kontroly a tabulky:
nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --auto \
  --profile micoair-v2 --passes 2 --output build/aio/micoair-test

# Jen připravit a změřit referenční variantu, bez routeru:
nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --auto \
  --profile micoair-v2 --prepare-only --output build/aio/micoair-prepare

# Pokračovat v trasování již vygenerované varianty, bez přepsání schématu:
nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --auto \
  --source build/aio/micoair-prepare/project --profile micoair-v2 \
  --route-only --passes 2 --output build/aio/micoair-route

# Sestavit firmware přesně pro tuto variantu:
nix develop ./dps#firmware -c dps/aio/hwdef/sestav.sh \
  build/aio/micoair-firmware build/aio/micoair-test/project/hwdef/Pavo20AIO
```

Běh pracuje na úplné kopii projektu včetně pravidel, knihoven, schémat a hwdefu.
Zdroj nepřepisuje. Výstup obsahuje `REPORT.md`, `result.json`, `logs/`, `reports/`
a `project/aio.kicad_pcb`. JSON obsahuje příkazy, časy, verzi KiCadu a SHA256 vstupní
desky. `--timeout` omezuje čas jednoho podprocesu (výchozí 1800 s).

Návratové kódy: **0** bez nespojených a bez neočekávaných ERC/parity či DRC chyb,
**2** kontrolovaný, ale nedokončený layout, **1** chyba nástroje nebo neplatný návrh.
Nula není automatické uvolnění do výroby. Varování jsou v reportu, zůstává kontrola
napájecích proudů, USB/SD signálů, návratových cest, orientací a výrobních parametrů.

## Co se automaticky hlídá

1. Skutečná netlist ze schématu proti hwdefu: UARTy podle `SERIAL_ORDER`, SPI podle
   `SPIDEV`, CS/DRDY, I2C, SDMMC, SWD, ADC, USB, LED a PWM. Nový profil se navíc
   porovnává s mapou `gen/micoair.py`.
2. ERC toleruje jen 18 konkrétních známých hlášení a parity 14 konkrétních pinů
   bez padů. `gen/vyjimky.json` páruje typ, popis, UUID pinů a cestu listu;
   stejný počet jiných chyb neprojde. Zdůvodnění původních ERC výjimek je v README.
3. Při změně přiřazení pinů se na kopii odstraní vodiče/prokovy dotčených
   signálových sítí. Převod napájecí sítě se tímto mechanismem odmítne; vyžaduje
   samostatně navrženou migraci. Nezměněné sítě zůstávají. Změna signálu může
   odstranit i jeho původní propojení z OpenAIO, nikoliv jen výstup routeru.
4. Rozmístění přesouvá jen díly mimo desku. Již osazené kotvy a konektory se při
   opakovaném běhu nevracejí na historické souřadnice. Neumístěný díl ukončí krok
   chybou. Volby při umísťování jsou deterministické.
5. Router běží jen nad návrhem bez DRC/parity/ERC chyby. Chybějící únik BGA se
   vyzkouší s kontrolním bodem. První průchod dotrasuje, další přetrasují skupinu
   `trasuj` s prioritou neprošlých sítí. Rozhoduje **počet nespojených ze skutečného
   DRC a nula DRC chyb**, nikoliv počet úspěchů v textu routeru. Horší výsledek či
   pád nástroje obnoví nejlepší desku. Stejnou kontrolou prochází prošití GND.
6. Tabulky v kopii `NAVRH.md` se generují z výsledného schématu a zvoleného profilu.

Tento postup zatím **sám nepřeskládává bloky ESC ani neoptimalizuje všechny polohy**.
Nový pinout rovněž není nový layout: na začátku se zachovají současné pozice.
Tyto limity jsou záměrně viditelné, aby se automatický běh nezaměňoval za hotovou DPS.

## Zjištění a další návrhový krok

**21. 10. 2026:** nový audit potvrdil hlavní desku 22 / 0. Dokončený běh V2
`build/aio/micoair-route-20261021` snížil 30 nespojených na 23 po trasování
a na **21 po prošití GND**, bez DRC error a neočekávaných ERC/parity hlášení.
Výsledný hwdef odpovídá netlistu. Varování včetně nevhodného prokovu MOTOR3
zůstávají; podrobnosti a příkaz pro pokračování jsou v
[STAV-2026-10-21.md](./STAV-2026-10-21.md). Hlavní projekt se tímto během neměnil.

Kontrola původního projektu potvrdila 22 nespojených a 0 DRC chyb. Referenční mapa
má oproti němu 16 odchylek (včetně změn názvů UART sítí). Převod na V2 odstranil
175 vodičů/prokovů dotčených signálů; výsledkem před novým trasováním je
**30 nespojených, 0 DRC chyb, 0 neočekávaných ERC/parity hlášení a soulad s hwdefem**.
Pouhé přečíslování pinů bez odpojení staré mědi mělo 16 DRC chyb a je odmítnuté.

Pro další rozmístění má prioritu topologie FC podle V2: blízkost H743–IMU,
H743–SD a H743–USB, dostupné konektory a prostor pro únik z BGA. Zachování každého
vodiče OpenAIO už není cílem. Případný přesun ESC navrhnout po funkčních blocích
a zvlášť ověřit silové smyčky, buzení hradel, napájení a teplo; pouhé lepší číslo
DRC takovou změnu nezdůvodňuje. Přesné kotvy podle V2 stanovit až ze správných
podkladů, nikoliv z dřívější fotografie 35A AIO.

Regresní testy kontroly a migrace:

```sh
python3 -m unittest discover -s dps/aio/gen -p test_automat.py -v
```

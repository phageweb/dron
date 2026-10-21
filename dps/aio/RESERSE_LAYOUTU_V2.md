# Rešerše a návrh rozmístění AIO podle MicoAir V2

21. 10. 2026. Zadání: přiblížit vlastní AIO referenci MicoAir743v2-AIO-45A,
problémy řešit rozmístěním součástek a bloků. Tento dokument je návrhový podklad;
provedení je rozdělené na kontrolovatelné kroky v [předávce](./PREDAVKA_LAYOUTU_V2.md).

## Doporučení

**Nepokračovat dalšími plošnými průchody routeru. Nejdřív opravit podklady pro
rozmístění, zkusit otočení microSD a uvolnit prostor u skutečných vývodů IMU.**
Změna pinoutu na V2 proběhla, fyzické rozmístění a významná část mědi jsou stále
z OpenAIO. Proto se obtížné spoje vracejí i po přetrasování.

Výchozí varianta V2 má 21 nespojených spojů, hlavní projekt 22. Malý ověřovací
přesun R301, TP304 a TP319 dovolil připojit SWCLK, ale zůstal otevřený SD_CMD;
celkem opět 21. To dokládá lokální konflikt o prostor, nikoliv dokončené řešení.
Pokus s dodatečným vedením SWCLK po L2 dosáhl 20, ale odporuje zadanému směru
a **není doporučeným základem**. Podrobnosti a otisky souborů jsou v předávce.

První návrhový krok má zachovat U301 na místě a zlepšit jeho okolí. Pokud tím
nelze vytvořit souvislý prostor pro sběrnice, doporučuji společné nové rozmístění
FC, konektorů a dotčených bloků ESC. Uživatel přesuny povolil; zachování každého
původního vodiče nemá přednost před rozumnou topologií.

## Co skutečně přebíráme z MicoAiru

Referencí je **V2 AIO 45A**, nikoliv starší 35A AIO. Výrobce uvádí H743VIH6,
BMI088 + BMI270, SPL06, microSD, 36 × 36 mm, otvory 25,5 mm, 5V/2A a 12V/2A
výstupy. Jeho údaj 45 A na ESC není ověřenou vlastností našeho návrhu.
[Specifikace a pinout výrobce](https://micoair.com/flightcontroller_micoair743v2_aio_45a/).

Fotografie správné revize a zapojení portů jsou v [reference/](./reference/README.md).
Při orientaci bateriovými pady dolů je USB vlevo dole, karta nad MCU, GPS nahoře
a VTX vpravo nahoře. Je to podklad pro dostupnost portů a rozmístění bloků.
Z fotografie nelze zjistit vnitřní vrstvy, přesné pouzdrové souřadnice ani
orientaci všech BGA vývodů. Spodní pohled je nutné převést do stejné projekce.
[Fotografie a diagram výrobce](https://store.micoair.com/product/micoair743v2-aio-45a/).

Ve veřejném repozitáři výrobce nebyl nalezen zdroj schématu/PCB, pouze firmware
a doprovodné informace: [MicoAir743v2](https://github.com/micoair/MicoAir743v2).
Proto je cílem podobná funkce a uspořádání, nikoliv deklarovaná kopie jeho mědi.

| Oblast | Vlastní návrh, který má další agent zachovat |
| --- | --- |
| Mechanika | 35,4 × 35,4 mm; rozteč otvorů 25,5 mm, průměr 3 mm; ověřit osazení do rámu s M2. Starší požadavek na 26 mm byl později upraven. |
| Baterie / ESC | 4S LiHV, maximum 17,4 V; návrhový požadavek alespoň 10 A špičkově na kanál. Proudové a tepelné ověření stále chybí. |
| MCU / firmware | H743VIH6, vlastní board ID 25026, profil pinů `micoair-v2`. |
| Senzory | BMI270 + **ICM-42688-P**, nikoliv BMI088. ICM je vědomá adaptace zapojení. |
| VTX | 10 V za TPS22810; stálá větev +10V současně napájí budiče ESC. Přesun nesmí zaměnit obě větve. Cíl VTX 2 A vyžaduje posouzení celé cesty. |
| Měření | INA186A3 + 0,2 mΩ: 50 A/V; dělič 100k/10k: 11,0. Nekopírovat kalibrace výrobce. |
| Stackup | Dosavadní 8vrstvý HDI 1+6+1, přibližně 0,997 mm, měď 1 oz; výrobní proveditelnost přesné skladby ještě potvrdit. |

Podklady vlastního návrhu: [požadavky](../docs/04_pozadavky.md),
[návrh](./NAVRH.md), [rozdíly profilu V2](./AUTOMATIZACE.md).
Naše ESC mají 24 samostatných MOSFETů, polovinu na každé straně desky.
Počet pouzder viditelných na jedné fotografii MicoAiru není důkazem jiné topologie.

## Naměřené příčiny obtížného trasování

Měření je z V2 kandidáta s 21 nespojenými, nikoliv ze starého hlavního projektu.
Strojový podklad: [geometry.json](./research-v2/geometry.json).
Souřadnice jsou v mm, pohled shora, osa y v KiCadu roste dolů.

### 1. MicroSD má kontakty na vzdálenější straně

U301 leží v (75,90; 64,10), natočení 180°. J302 leží v (66,81; 65,99),
natočení 90°. Všech osm kontaktů karty leží na x = 65,56, tedy západně od
středu slotu a **odvráceně od MCU**. Po otočení J302 na 270° při stejném středu
budou na x = 68,06, směrem k MCU; jejich pořadí v ose y se obrátí.

To je konkrétní první kandidát, nikoliv hotové umístění. Otočí se také tělo,
vstup karty a mechanické pady. Nejdřív ověřit výkres TF-021B-H265, prostor pro
zasunutí/vytažení karty a sousedy. Současný footprint nemá courtyard, takže
prázdný výsledek automatického hledání kolizí **neprokazuje volné místo**.
Bez této kontroly nepřesouvat slot podle pouhých kontaktů.

### 2. BMI270 je na opačné straně než jeho vývody MCU

U8 leží v (78,20; 54,01), nad MCU. Při aktuálním natočení U301 jsou BMI270
MISO/SCK/CS/INT na jižní řadě A a MOSI na C6. Všech pět spojů této skupiny
zůstává otevřených; jejich přímé vzdálenosti jsou přibližně 11–15 mm.
Podobně GPS používá severozápadní K9/J9, zatímco J303 leží na jižní hraně.

První návrh: **BMI270 i jeho lokální napájení a pasivy přesunout k jižnímu okraji
MCU**, kde jsou piny SPI3. Potřebný prostor získat přeuspořádáním SD, drobných
testovacích padů a případně konektorů. Senzor nesmí skončit u spínacího uzlu
ESC jen proto, že je tam krátká vzdušná čára. Toto je cílová oblast k ověření,
ne garantované volné souřadnice. ICM posuzovat společně: jeho vývody nejsou
na jedné straně BGA, samotné přiblížení SCK nemusí zlepšit celou sběrnici.

Pro případ nového rozmístění FC byly virtuálně změřeny čtyři rotace U301.
Tabulka uvádí průměrný posun skupiny padů od středu MCU (dx; dy), nikoliv
umístění periferií. Nezohledňuje překážky a není skórem routovatelnosti.

| Rotace U301 | USB | SDMMC | BMI270 SPI + CS/INT | GPS |
| ---: | --- | --- | --- | --- |
| 0° | +3,60; −2,40 | +2,27; −1,73 | +0,72; −3,28 | +2,80; +3,20 |
| 90° | −2,40; −3,60 | −1,73; −2,27 | −3,28; −0,72 | +3,20; −2,80 |
| **180° nyní** | −3,60; +2,40 | −2,27; +1,73 | −0,72; +3,28 | −2,80; −3,20 |
| 270° | +2,40; +3,60 | +1,73; +2,27 | +3,28; +0,72 | −3,20; +2,80 |

Závěr měření: otočení MCU samo nemá jednoznačného vítěze. Například 0° pomůže
severní IMU, ale USB vývody přemístí na východ. Rotaci vybírat se slotem,
USB, IMU, krystalem a konektory, ne podle jediné sítě.

### 3. Mechanické kontroly jsou neúplné

U8, U303, J301 a J302 nemají v desce courtyard. V projektu jsou navíc globálně
ignorované `missing_courtyard`, `courtyards_overlap`, `malformed_courtyard`
a `copper_edge_clearance`. Nula DRC error tedy nevypovídá o těchto kolizích.
Obrysy doplnit podle skutečných pouzder a konektorů, včetně manipulačního
prostoru. Po opravě knihoven aktualizovat jejich instance v kandidátovi.
U spodních součástek kontrolovat také výšku vůči rámu a součástkám na druhé
straně; samotná 2D kontrola každé strany na to nestačí.

Pro doplnění obrysů byly dohledány konkrétní výrobky z místních knihoven:

- **J302: SOFNG TF-021B-H265, C498185.** [Výrobní dokument SOFNG poskytovaný
  distributorem](https://datasheet.lcsc.com/datasheet/pdf/649033837db010158dd715a72dbc0940.pdf?productCode=C498185)
  uvádí krátké push-pull pouzdro TF-021B 11,35 × 5,50 × 2,5 mm a na druhé
  straně footprint/pinout. Označení výkresu je obecnější než přípona H265
  v kusovníku; před opravou knihovny potvrdit konkrétní variantu a výšku.
  Krátké tělo konektoru nezahrnuje celou zasunutou kartu.
- **J301: SHOU HAN TYPE-C 16P QTWT, C5187472.** [Výrobní dokument SHOUHAN
  poskytovaný distributorem](https://datasheet.lcsc.com/datasheet/pdf/d3846d73123f7a78a150a5dc80fdd645.pdf?productCode=C5187472)
  obsahuje výkres a specifikaci tohoto modelu. Při doplnění obrysu zkontrolovat
  i všechny mechanické kotvy, nikoliv pouze signálové pady.

Tyto odkazy řeší dohledání zdroje. Úplná vizuální rozměrová shoda výkresů
s importovanými footprinty v rámci této rešerše ověřena nebyla.

### 4. Název vrstvy není důkaz souvislé země

Na `L2.GND` již jsou například VCAP 5,69 mm, USB_CC1 4,85 mm a několik signálů
kolem 2–3 mm; to je součet segmentů příslušné sítě, nikoliv délka jedné cesty.
Na `L7.GND` také není výhradně zem. Toto měření nezahrnuje polygony ani oblouky.
Zděděné fáze a napájení proto zmapovat po všech vrstvách. BGA prokov musí mít
průchod přes celý použitý rozsah vrstev, nikoliv pouze volné místo nahoře.

Signálové koridory mají vzniknout přesunem bloků nebo jejich mědi na určených
signálových vrstvách L1/L3/L6/L8. Nepřidávat obchvaty po GND jen pro lepší
počet spojů. Dosavadní lokální úniky nejdřív inventarizovat; neprohlašovat
celou desku za návrh s nepřerušenými rovinami.

## Elektrické zásady opřené o výrobce součástek

| Blok | Dopad na náš návrh | Primární podklad |
| --- | --- | --- |
| H743 | MCU přesouvat s blokováním, VCAP a krystalem. VCAP1/2 mají mít odpovídající lokální 2,2µF kondenzátory s nízkým ESR a propojení podle zapojení ST; neoddělit je při uvolňování prostoru. Krystalové cesty držet krátké. | [ST AN4938 Rev. 7](https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-mcu-hardware-development-stmicroelectronics.pdf), §2.2 a §7. |
| BMI270 | Zachovat oddělené VDD a VDDIO dle vlastního schématu a lokální blokování; osy senzoru určovat z datasheetu a skutečné orientace footprintu. Přesun celého bloku je naše návrhové doporučení. | [Bosch BMI270, Rev. 1.6](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi270-ds000.pdf), SPI zapojení §7.4, pouzdro a osy §8. |
| ICM-42688-P | Zkontrolovat SPI zapojení, VDD blokování 0,1 µF + 2,2 µF a VDDIO 10 nF podle doporučené aplikace. Přesun/rotaci promítnout do hwdefu po určení os. | [TDK DS-000347 Rev. 1.6](https://product.tdk.com/system/files/dam/doc/product/sensor/mortion-inertial/imu/data_sheet/ds-000347-icm-42688-p-v1.6.pdf), §4.2–4.3. |
| Buck LMR51430 | Zachovat krátkou vstupní spínací smyčku a lokální CIN, zpětnou vazbu mimo SW. Případný přesun provést s okolními součástkami; krátká sběrnice FC neospravedlňuje zhoršení bucku. | [TI LMR51430](https://www.ti.com/lit/ds/symlink/lmr51430.pdf), §9.4. |
| TPS22810 / VTX | VIN a VOUT vést krátce a dostatečně široce, vstupní a výstupní kondenzátory u spínače. Posoudit úbytek a ztráty při cílovém proudu. U201 a C201–C203 řešit společně. | [TI TPS22810](https://www.ti.com/lit/ds/symlink/tps22810.pdf), §12. |
| USB | Jde o OTG FS s interním PHY. Ověřit VBUS a ochranu u konektoru; nepřebírat bez rozlišení požadavky externího HS/ULPI rozhraní. Při změně cesty kontrolovat referenční zem a skutečný stackup. | [ST AN4879 Rev. 12](https://www.st.com/resource/en/application_note/an4879-introduction-to-usb-hardware-and-pcb-guidelines-using-stm32-mcus-stmicroelectronics.pdf). |
| SDMMC | Nejdřív ověřit všech šest signálů včetně odboček pull-upů, pak délky celé sběrnice a skutečný provozní režim. Z aplikační poznámky nelze odvodit univerzální toleranci délky 0,1 mm. | [ST AN5200 Rev. 3](https://www.st.com/resource/en/application_note/an5200-getting-started-with-stm32h7-mcus-sdmmc-host-controller-stmicroelectronics.pdf) popisuje řadič a konfiguraci, není podrobným předpisem layoutu naší desky. |

Oddálení MEMS od výkonových spínacích uzlů, tepla a mechanicky namáhaných míst
je zde návrhové doporučení k prověření celého uspořádání. Rešerše neurčila
jednu výrobcem garantovanou minimální vzdálenost v mm pro tuto AIO.

## Výroba a skutečné podmínky dokončení

Současná pravidla počítají s microvia L1–L2 a L7–L8, přibližně 0,25/0,10 mm,
a buried via L2–L7, nejméně 0,33/0,15 mm. Průchozí prokovy jsou možné dle
stávajícího návrhu. Mechanický blind via MOTOR3 L6–L8 je ale stále přítomen
a zákaz má pouze závažnost warning. Před výrobou musí být nahrazen
proveditelným propojením, nikoliv skryt výjimkou.

NextPCB veřejně nabízí HDI 1+n+1, laserové otvory a via-in-pad. Tyto obecné
schopnosti nejsou potvrzením naší přesné kombinace osmi vrstev, 1 oz, tloušťky,
průměrů, stohování a plnění prokovů. Vyžádat posouzení konkrétního stackupu
a výrobních dat. [Oficiální HDI možnosti](https://www.nextpcb.com/pcb-type/hdi-pcb).

Zbývá 41 DRC varování: 1 nevhodný prokov, 9 zúžení spojů, 1 solder-mask bridge,
20 visících tras, 1 izolovaná měď, 5 rozdílů footprintů proti knihovně a 4 měděné
třísky. Maska mezi C44.2 a R83.1 na spodku si zaslouží konkrétní opravu.
Nulová konektivita a nula chyb při dnešním nastavení ještě nejsou výrobní kontrola.

Za dokončení návrhu považovat až soulad schéma–PCB–hwdef, všechny spoje,
ověřené obrysy/osazení, proveditelné prokovy, proudové cesty, návratové cesty,
orientace senzorů a mechaniku. Proudové schopnosti a chování IMU/SD/USB/ESC
se následně ověřují na prototypu. Měřením zatím není doložena proudová
zatížitelnost ani shoda vlastností s komerčním MicoAirem.

## Co tato rešerše nerozhodla

Přesné finální souřadnice všech bloků nejsou stanovené: scházejí spolehlivé
mechanické obrysy a zkouška routovatelnosti společného rozmístění. Otočení
J302 na 270° je geometricky změřený návrh, nikoliv hotový DRC ověřený layout.
Vhodnost jižní polohy BMI270 závisí na skutečné mědi a osazení ESC.
To jsou první úkoly v předávce, nikoliv důvody pokračovat náhodným trasováním.

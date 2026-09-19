# Tabulka komponent

Výstup fáze 1 [plánu stavby](./01_plan_stavby.md) pro cílový airframe: GEPRC
CineLog30 V3 s MicoAir H743 V2 45A AIO. Je to zároveň dron, na který je
nakalibrovaná simulace.

Alternativní airframy se zvažovaly a vypadly, viz [rozhodnutí o H7](../../workflow/decisions.md).
Ve zkratce: AP_DDS potřebuje H7, a žádná OpenIPC video jednotka neumí 1S.

## Jak číst čísla

Hmotnosti jsou **publikované výrobcem nebo prodejcem, ne zvážené**. Sloupec
"jistota" říká, jak moc se na číslo dá spoléhat; předchozí zkušenost s motorovými
tabulkami v [research](../../workflow/research_rotor_simulation.md) ukázala, že
vendor čísla se musí brát s rezervou. Vážení skutečných dílů zůstává otevřené.
Tahle tabulka je vstup pro objednávku, ne náhrada váhy.

Co v tabulce **není** a v realitě váží: kabeláž, cín, smršťovačky, šrouby, TPU
držáky, antény a kondenzátor. Odhad je v křížové kontrole níž.

## Komponenty

| Komponenta | Konkrétní díl | Hmotnost | Napájení | Konektor | Datové rozhraní | Jistota |
| --- | --- | ---: | --- | --- | --- | --- |
| Rám | GEP-CL30 V3, 2.5 mm karbon, wheelbase 128 mm | 78 g | - | - | - | prodejce, není jasné, zda včetně ductů |
| Motory 4x | GEPRC SPEEDX2 1404 3850KV | 4x 10.5 g = 42 g | 4S | pájení na AIO pady | - | vendor, včetně kabelu |
| Vrtule 4x | HQProp DT76mmX3 V2, polykarbonát | 4x 1.65 g = 6.6 g | - | 1.5 mm hřídel | - | vendor |
| FC/ESC | MicoAir H743 V2 45A AIO | 10 g | 2-6S vstup | XT30 na desku | USB, 7x UART | vendor |
| RX | SpeedyBee ELRS Nano 2.4G | 0.7 g + 0.6 g anténa | 5 V | IPEX1 anténa | UART, CRSF | vendor |
| Video | RunCam WiFiLink 2 (OpenIPC, IMX415) | 25 g bez ventilátoru, 30 g s ním | 9-22 V | - | WiFi, IP stream | prodejce |
| Video, lehčí alternativa | EMAX Wyvern Link Alpha 200 mW (OpenIPC, IMX415) | 13.76 g | 2-6S | 25.5x25.5 mm | WiFi, IP stream | prodejce; není jisté, zda zahrnuje kamerový modul |
| Optical flow + range | MicoAir MTF-02P | 1.5 g | 5 V, 40 mA | - | UART 115200 LVTTL, MAVLink | vendor |
| Baterie | Tattu R-Line 4S LiHV 750 mAh 95C | 69-74 g | 15.2 V nominál | XT30 | - | prodejci se liší, uvedená tolerance +/-20 g |
| Přední obstacle senzor | neurčeno | ? | ? | ? | ? | **otevřené, viz níž** |

Součet bez předního senzoru a bez montážního materiálu, s WiFiLink 2:
**164.4 g nasucho**, **238.4 g s baterií**. S Wyvern Link Alpha místo něj
**153.2 g nasucho**, **227.2 g s baterií**.

## Křížová kontrola proti simulaci

> **Aktualizováno.** Tahle sekce se jmenovala „Křížová kontrola proti 240 g
> v simulaci" a těch 240 g už neplatí ani pro jeden drak. Simulace dnes jede na
> **0,306 kg** pro CineLog30 V3 s LD06 a na **0,229 kg** pro
> [variantu Pavo20](./10_pavo20.md). Těch 0,240 kg byl CineLog ještě bez lidaru
> — a hlavně to bylo zadané číslo, ne měřené. Úvaha pod tím platí dál a vlastně
> je to přesně ta úvaha, která ke 306 g vedla.

Původních 0.240 kg bylo zadané číslo, ne měřené. Součet výše na něj seděl skoro
přesně, ale byla to falešná shoda, protože v tabulce chybí montážní materiál.

Reálnější odhad dá stock CineLog30 V3: prodejci ho uvádějí 187-192 g **bez**
baterie, a to s DJI O4 air unitem a TAKER F722 AIO místo našich dílů, které váží
zhruba stejně. Rozdíl proti našim 164.4 g nasucho, tedy asi 23-28 g, je právě
kabeláž, šrouby, TPU a antény.

| Stav | Hmotnost | Poměr tah/váha při 4x 350 g |
| --- | ---: | ---: |
| Simulace dnes | 240 g | 5.9 |
| Odhad s WiFiLink 2, bez předního senzoru | ~264 g | ~5.3 |
| Totéž s Wyvern Link Alpha místo WiFiLink 2 | ~252 g | ~5.6 |
| S VL53L5CX třídou senzoru | ~266 g / ~254 g | ~5.3 / ~5.5 |
| S LD06 | ~306 g / ~294 g | ~4.6 / ~4.8 |

**Přední obstacle senzor rozhoduje, jestli 240 g v simulaci dál platí.** Volba
video jednotky je druhá největší páka: Wyvern Link Alpha je o 11 až 16 g lehčí a
je to rozdíl mezi "těsně nad 250 g" a "jasně nad". Co se za to platí, není z
publikovaných údajů vidět, EMAX neuvádí spotřebu ani dosah.

## Přední obstacle senzor: nevyřešená volba

| Kandidát | Hmotnost | Dosah | FOV | Rozhraní | Dostupnost v ČR | Poznámka |
| --- | ---: | --- | --- | --- | --- | --- |
| LDRobot LD06 | **42 g** bez kabelu, potvrzeno datasheetem | **0.02 - 12 m** při 70% odrazivosti | 360 stupňů, rozlišení 1°, 10 Hz (5-13), vzorkování 4500 Hz | UART 230400; **4.5-5.5 V**, rozběh 300 mA, provoz 180 mA; konektor ZH1.5T-4P | **není** - TME ho stáhlo z nabídky, jinak dovoz | **vybráno**, viz [rozhodnutí](../../workflow/decisions.md); jediný lehký, co dá skutečný `LaserScan`, a ArduPilot ho umí jako proximity |
| Slamtec RPLidar C1 | **110 g**, 55.6x55.6x41.3 mm | 12 m | 360 stupňů | UART | rpishop.cz, 2279 Kč | 360 stupňů skladem v ČR, ale je to 40 % hmotnosti dronu |
| DFRobot TF-Luna | ~5 g | 8 m | jeden bod | UART/I2C | rpishop.cz, 799 Kč | skladem a lehký, ale jeden paprsek místo skenu |
| Benewake TFmini-S | ~5 g | 12 m | jeden bod | UART/I2C | rpishop.cz, 1245 Kč | totéž, delší dosah |
| ST VL53L5CX (breakout) | ~2 g, nepotvrzeno | 4 m | 63 stupňů, 8x8 zón, 60 Hz | I2C | neověřeno; LaskaKit vede jen jednozónový VL53L1X | nejblíž tomu, co simulace modeluje, ale poloviční dosah |

**Dostupnost v ČR tu volbu zužuje víc než hmotnost.** České obchody vedou 360stupňové
lidary jen v třídě RPLidar, která začíná na 110 g - to je 40 % hmotnosti celého
dronu a 55 mm široký rotující válec na rámu se 128 mm rozvorem. Lehké senzory
skladem jsou jednobodové. **Skutečný 2D sken v hmotnostní třídě dronu se v ČR
nekoupí**; LD06 by byl dovoz.

Simulace dnes modeluje přední lidar jako 61 vzorků přes 60 stupňů, 0.10 až 8.0 m.
Tomu neodpovídá **žádný** z kandidátů přesně: LD06 má dosah i pokrytí, ale váhu,
VL53L5CX má úhel a váhu, ale poloviční dosah. Až bude senzor vybraný, musí se
`front_lidar` v modelu upravit na jeho skutečné parametry, protože demo se
rozhoduje 0.8 m + 0.6 m brzdné dráhy před překážkou, a to je uvnitř dosahu obou.

### Jedna vlastnost LD06, která se bude počítat

Datasheet uvádí **pitching angle 0 až 2 stupně, typicky 0.5** - rovina skenu není
dokonale vodorovná. Přesně to v simulaci způsobilo, že zaparkovaný lidar měří
podlahu (viz [troubleshooting](../../workflow/troubleshooting.md)), a na reálném
kuse to bude platit taky: při 0.5 stupně a výšce 35 mm nad zemí odraz od podlahy
vyjde na 4 m, při 2 stupních na 1 m. **Za letu je to jedno** - z metru výšky by
podlaha vyšla přes 100 m, tedy daleko za dosahem - ale na stole to bude vidět a
není to závada.

## Elektrické propojení: sedí to k sobě?

Kontrola proti tomu, co MicoAir H743 V2 45A AIO nabízí: vstup 2-6S, BEC **5 V/2 A**
a 12 V/2 A, **7 UARTů** a 45A ESC.

| Spotřebič | Napájení | Odběr | Sběrnice |
| --- | --- | ---: | --- |
| Motory 4× 1404 3850KV | z ESC, 4S | špička 10 A na motor | ESC pady |
| SpeedyBee ELRS Nano | 5 V | jednotky mA | UART, CRSF |
| MicoAir MTF-02P | 5 V | 40 mA | UART 115200, MAVLink |
| LDRobot LD06 | 4.5-5.5 V | **300 mA rozběh, 180 mA provoz** | UART 230400, jednosměrný |
| EMAX Wyvern Link Alpha | **2-6S přímo z baterie** | neuvádí se | WiFi, telemetrie po UART |

**Napěťově i kapacitně to vychází s rezervou:**

- 5 V větev: 300 mA (LD06 při rozběhu) + 40 mA (flow) + jednotky mA (RX) je
  zhruba **360 mA proti 2 A**, tedy pod pětinou.
- UARTy: RX, flow, lidar a telemetrie k videu jsou **4 ze 7**.
- ESC 45 A proti špičce 10 A na motor je předimenzované, což nevadí.
- 4S LiHV má 17.4 V naplno, Wyvern bere 2-6S, takže sedí.

**Tři věci, které z toho ale plynou a nejsou zadarmo:**

1. **LD06 má konektor ZH1.5T-4P**, rozteč 1.5 mm. UARTy na AIO deskách bývají
   JST-SH 1.0 mm. **Bude potřeba redukce**, nebo přepájet konektor. Objednat
   rovnou s lidarem.
2. **LD06 má na sdílené 5 V větvi motor.** Podle datasheetu je **bezkartáčový**,
   ne kartáčový, jak jsem psal dřív - rušení tím pádem menší, ale rozběhových
   300 mA na stejném BEC jako optical flow a přijímač pořád stojí za kondenzátor
   a za proměření.
3. **Spotřebu videa nikdo neuvádí.** EMAX ji nepublikuje; RunCam u srovnatelného
   WiFiLinku 2 udává až 15 W. To je jediné číslo v celém rozpočtu, které chybí,
   a je to zároveň největší spotřebič mimo motory.

## Poznámky, které vyplynuly z rešerše

- **Chlazení není detail.** Na ArduPilot fóru je u OpenIPC hlavní varování přes
  100 °C na stole. Mario AIO má v příslušenství 7.36 g chladič a 5.37 g
  ventilátor, RunCam u WiFiLink 2 uvádí až 15 W, a na ducted whoopu je ta
  jednotka pod kabinkou.
- **OpenIPC do volby FC nemluví.** Wiki OpenIPC nejmenuje žádný flight
  controller; od FC chce jen UART s MAVLink telemetrií. Volba H743 stojí na
  ArduPilot podpoře, ne na videu.
- **MicoAir743 je oficiálně podporovaný ArduPilotem od 4.6.0** a od stejného
  výrobce je i MTF-02P, takže flow senzor a FC jsou z jedné dílny.
- **Wheelbase nesedí:** spec počítá 126 mm, GEPRC uvádí 128 mm, což posouvá
  souřadnice motorů v modelu o 1.6 %.

## Otevřené položky

- zvážit skutečné díly, až budou fyzicky na stole
- vybrat přední obstacle senzor a podle něj upravit `front_lidar` v modelu
- vybrat video jednotku mezi WiFiLink 2 a Wyvern Link Alpha
- potvrdit hmotnost baterie, prodejci se liší o 5 g
- srovnat hmotnost v modelu s reálným odhadem
- ~~rozhodnout, co znamená, že dron bude nad 250 g~~ - žádná váhová třída se
  nedrží, hmotnost je cíl a rozhodčí mezi rovnocennými variantami, ne limit,
  viz [rozhodnutí](../../workflow/decisions.md)
- zavřít fázi 8, OpenIPC stream do `sensor_msgs/msg/Image`, s kamerou na stole

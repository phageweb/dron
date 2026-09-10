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

## Křížová kontrola proti 240 g v simulaci

Simulace jede na 0.240 kg jako celkovou hmotnost včetně baterie, což bylo zadané
číslo, ne měřené. Součet výše na něj sedí skoro přesně, ale je to falešná shoda,
protože v tabulce chybí montážní materiál.

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

| Kandidát | Hmotnost | Dosah | FOV | Rozhraní | Poznámka |
| --- | ---: | --- | --- | --- | --- |
| LDRobot LD06 | ~42 g, nepotvrzeno | 12 m | 360 stupňů | UART 230400, 5 V napájení, 3.3 V TTL | jediný, co dá skutečný `LaserScan`; ArduPilot ho podporuje jako proximity |
| ST VL53L5CX (breakout) | ~2 g, nepotvrzeno | 4 m | 63 stupňů diagonálně, 8x8 zón, 60 Hz | I2C | nejblíž tomu, co simulace modeluje, ale poloviční dosah |
| Benewake TF-Luna třída | ~5 g | 8 m | jeden bod | UART/I2C | jen jeden paprsek, ne scan |

Simulace dnes modeluje přední lidar jako 61 vzorků přes 60 stupňů, 0.10 až 8.0 m.
Tomu neodpovídá **žádný** z kandidátů přesně: LD06 má dosah i pokrytí, ale váhu,
VL53L5CX má úhel a váhu, ale poloviční dosah. Až bude senzor vybraný, musí se
`front_lidar` v modelu upravit na jeho skutečné parametry, protože demo se
rozhoduje 0.8 m + 0.6 m brzdné dráhy před překážkou, a to je uvnitř dosahu obou.

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
- rozhodnout, co znamená, že dron bude nad 250 g
- zavřít fázi 8, OpenIPC stream do `sensor_msgs/msg/Image`, s kamerou na stole

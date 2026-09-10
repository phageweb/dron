# Kde se co koupí

Nákupní seznam k [tabulce komponent](./03_komponenty.md). Ta řeší, co díly umí;
tenhle soubor, odkud je vzít.

**Ceny ověřené 11. 9. 2026** a mění se, takže je ber jako řádovou orientaci, ne
jako nabídku. Rotorama je český obchod, ale ceny ukazuje v eurech.

## Rotorama - skoro celý dron

[rotorama.com](https://www.rotorama.com) vede většinu kusovníku, což je hlavní
zjištění téhle rešerše: nemusíš to skládat z pěti obchodů.

| Díl | Kusů | Cena/ks | Skladem | Odkaz |
| --- | ---: | ---: | --- | --- |
| GEPRC CineLog30 V3 **rám** | 1 | 57.79 € | **na cestě** | [odkaz](https://www.rotorama.com/product/geprc-cinelog30-v3) |
| MicoAir H743 V2 45A AIO | 1 | 85.99 € | **ano** | [odkaz](https://www.rotorama.com/product/micoair-h743-v2-45a-aio-am32) |
| GEPRC SPEEDX2 1404 3850KV | **4** | 15.59 € | **ne** | [odkaz](https://www.rotorama.com/product/geprc-speedx2-1404-3850kv) |
| MicoAir MTF-02P | 1 | 20.49 € | **ano** | [odkaz](https://www.rotorama.com/product/micoair-mtf-02p) |
| HQProp DT76MMX3 V2 | 1-2 sady | neověřeno | ? | [odkaz](https://www.rotorama.com/product/hqprop-dt76mmx3-v2) |
| SpeedyBee ELRS Nano 2.4G | 1 | neověřeno | ? | [odkaz](https://www.rotorama.com/product/speedy-bee-nano-2-4g) |
| RunCam WiFiLink 2 | 1 | neověřeno | ? | [odkaz](https://www.rotorama.com/product/runcam-wifilink-2) |

Ověřené položky dají **226.63 €** za rám, FC, čtyři motory a flow senzor. Zbytek
je potřeba doplnit.

**Pozor: rám je „na cestě" a motory nejsou skladem.** Jsou to dvě položky, bez
kterých se nedá začít, takže je má smysl hlídat jako první.

## LD06 - jediná položka, která se v ČR nekoupí

Přední lidar musí být z dovozu. TME ho vede jako **stažený z nabídky** a české
obchody vedou 360stupňové lidary jen ve třídě RPLidar, která začíná na 110 g -
to je 40 % hmotnosti tohohle dronu, viz [tabulka komponent](./03_komponenty.md).

Zdroj: AliExpress nebo Amazon, prodejci LDRobot a Inno-Maker. Existuje i varianta
**LD19**, což je novější sourozenec s montážní deskou navíc; rozměry a rozhraní
jsou stejné.

**Objednej k němu redukci.** LD06 má konektor ZH1.5T-4P s roztečí 1.5 mm, UARTy
na AIO deskách bývají JST-SH 1.0 mm. Bez ní budeš přepájet.

## Baterie a spotřební materiál

| Díl | Kde | Poznámka |
| --- | --- | --- |
| Tattu R-Line 4S LiHV 750 mAh, XT30 | české FPV obchody | vezmi aspoň dvě, jedna nálet nezachrání |
| Redukce ZH1.5T-4P na JST-SH | s lidarem, nebo elektro obchod | jinak přepájení |
| Kondenzátor na 5 V větev | GME, Laskakit | kvůli rozběhovým 300 mA lidaru |
| Hliníkové šrouby | dle rámu | pár gramů, viz [rozhodnutí o hmotnosti](../../workflow/decisions.md) |
| Smrštovačky, cín, pásky | běžné | - |

## Co ještě není rozhodnuté

**Video jednotku neobjednávej, dokud se nerozhodne.** Volba stojí mezi
RunCam WiFiLink 2 (25-30 g, na Rotoramě) a EMAX Wyvern Link Alpha 200 mW
(13.76 g, v českých obchodech jsem ho nenašel, nejspíš taky dovoz). Wyvern je
o 11 až 16 g lehčí, ale EMAX neuvádí spotřebu ani dosah, kdežto RunCam u své
jednotky udává až 15 W. **Chybí právě ta dvě čísla**, a je to zároveň největší
spotřebič mimo motory.

Model dnes létá na hmotnosti s WiFiLinkem, tedy 306 g. S Wyvernem by to bylo
zhruba 294 g a rate gainy by chtěly proměřit znovu.

## Než objednáš

- **rám a motory nejsou skladem** - hlídat dostupnost
- **redukce ke konektoru lidaru** patří do stejné objednávky jako lidar
- **video jednotka čeká na rozhodnutí**
- companion computer pro ROS 2 v kusovníku není; dnešní demo jede z notebooku

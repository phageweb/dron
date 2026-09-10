# Nákupní seznam

Praktický kusovník k [tabulce komponent](./03_komponenty.md). Ceny a sklad byly
ověřené **11. 9. 2026**; před zaplacením je zkontroluj znovu. Doprava, případné
clo a DPH u dovozu v součtech nejsou.

## Co objednat

| Díl | Minimum | Doporučeno | Kde | Cena při kontrole | Stav při kontrole |
| --- | ---: | ---: | --- | ---: | --- |
| GEPRC CineLog30 V3 rám | 1 | 1 | [Aerodrone CZ](https://aerodrone.cz/product/gep-cl30-v3-o4-ram/) | 1 490 Kč | 1 ks skladem |
| GEPRC SPEEDX2 1404 3850KV | 4 | 4 | [Rotorama CZ](https://www.rotorama.cz/product/geprc-speedx2-1404-3850kv) | 379 Kč/ks | skladem |
| HQProp DT76mmX3 V2 | 1 sada | 3 sady | [Rotorama CZ](https://www.rotorama.cz/product/hqprop-dt76mmx3-v2) | 79 Kč/sada | skladem |
| MicoAir H743 V2 45A AIO AM32 | 1 | 1 | [Rotorama CZ](https://www.rotorama.cz/product/micoair-h743-v2-45a-aio-am32) | 2 090 Kč | skladem |
| SpeedyBee Nano 2.4GHz ELRS RX | 1 | 1 | [FPV24, Německo](https://www.fpv24.com/cs/speedy-bee/pijma-speedybee-nano-24ghz-elrs) | 12,90 € | více než 10 ks |
| MicoAir MTF-02P | 1 | 1 | [Rotorama](https://www.rotorama.com/product/micoair-mtf-02p) | 20,49 € | skladem |
| Tattu 4S LiHV 750 mAh 95C, **long**, XT30 | 1 | 3 | [RCTech, Německo](https://www.rctech.de/tattu-lipo-akku-4s-750-mah-95c-hv-xt30-long) | 19,90 €/ks | skladem |
| LDRobot **LD06** | 1 | 1 | [Sunhokey, Čína](https://sunhokey.cn/products/dtof-lidar-ld06) | 75,50 USD | dovoz |

Jedna sada vrtulí obsahuje 2 CW a 2 CCW vrtule, tedy právě jednu letovou sadu.
Tři sady jsou rozumné minimum pro stavbu a první lety.

Česká část košíku bez videa vychází s doporučenými třemi sadami vrtulí na
**5 333 Kč**. K tomu se přičte přijímač, MTF-02P, baterie, LD06 a právě jedna
z následujících video variant.

## Video: koupit právě jednu variantu

| Varianta | Kde | Cena při kontrole | Co znamená pro model |
| --- | --- | ---: | --- |
| **RunCam WiFiLink 2** | [Rotorama CZ](https://www.rotorama.cz/product/runcam-wifilink-2) | 3 349 Kč, skladem | výchozí sestava o hmotnosti přibližně **306 g**; kamera je součástí jednotky |
| **EMAX Wyvern Link Alpha 200 mW** | [Rotorama EU](https://www.rotorama.de/product/emax-openipc-wyvern-link-alpha-200mw-vtx) | 82,39 €, skladem | lehčí sestava přibližně **294 g**; kamera, dvě antény a USB/Ethernet adaptér jsou v sadě |

Model v `cad_codex` používá lehčí Wyvern. Hmotnost 306 g naopak záměrně patří
variantě RunCam. **Nekupovat obě jednotky.** Před objednáním Wyvernu ještě platí
otevřená kontrola spotřeby, dosahu a skutečné hloubky elektroniky v držáku.

## Co se musí vyrobit nebo přepojit

Tyto položky nejsou hotové katalogové díly kusovníku:

- zvýšený držák LD06 nad vrtulemi;
- přední držák/adaptér zvolené kamery;
- spodní držák MTF-02P;
- kabel LD06 z konektoru **ZH1.5T-4P, rozteč 1,5 mm** na JST-SH 1,0 mm nebo
  přímo na pájecí plošky AIO;
- případná pravoúhlá USB-C prodlužka až po změření přístupu v sestaveném rámu.

Pro kabel LD06 je lepší koupit protikus s vodiči a zakončení upravit. Hotový
USB adaptér LD06-PI je do letadla zbytečně velký a těžký.

## Co nekupovat samostatně

Následující věci už jsou přibalené, nebo zatím nejsou rozhodnuté:

- další XT30 přívod, hlavní kondenzátor, microSD, soft-mounty a kabelovou sadu:
  jsou u MicoAir H743 V2 AIO;
- zvláštní kameru k RunCam ani Wyvernu: oba video sety ji obsahují;
- první ELRS anténu a kabel: jsou v balení SpeedyBee RX;
- kabelovou sadu MTF-02P: je v balení senzoru;
- druhou video jednotku, samostatné Wyvern antény nebo jeho USB/Ethernet
  adaptér: jsou duplicitní;
- běžnou kompaktní **14,8V LiPo** Tattu R-Line 750 mAh: cílový CAD počítá s
  podlouhlou **15,2V LiHV** variantou;
- LD06-LD, LD19 nebo jiný údajný ekvivalent bez ověření hmotnosti, rozměrů a
  UART protokolu proti původnímu LD06;
- companion computer, dokud nebude rozhodnuto, zda ROS 2 poběží na palubě,
  nebo na pozemním notebooku.

Samostatný 5V kondenzátor pro lidar se nekupuje preventivně. AIO má na 5V větvi
rezervu; filtraci doplň až tehdy, pokud měření při rozběhu LD06 ukáže propad nebo
rušení.

## Vybavení mimo letovou hmotnost

Pokud už není v dílně, je ještě potřeba:

- balanční nabíječka s režimem **LiHV 4S** (koncové napětí 17,4 V);
- smoke stopper a multimetr;
- páječka, tavidlo, cín, smršťovací bužírky a tenké signálové vodiče;
- notebook/pozemní stanice;
- ELRS 2.4GHz vysílač a přijímací část pro zvolený OpenIPC video systém.

Konkrétní rádio, nabíječka a pozemní přijímač zatím v projektu vybrané nejsou,
proto nejsou započítané do ceny dronu.

## Doporučené rozdělení objednávek

1. **Aerodrone CZ:** rám.
2. **Rotorama CZ:** čtyři motory, tři sady vrtulí, AIO a případně RunCam.
3. **FPV24:** ELRS přijímač, protože na Rotoramě při kontrole nebyl skladem.
4. **Rotorama EU:** MTF-02P a případně Wyvern.
5. **RCTech:** jedna až tři přesné podlouhlé LiHV baterie.
6. **Dovoz:** původní LD06 až po kontrole fotografie štítku, konektoru a
   datasheetu konkrétní nabídky.

Nejdřív lze objednat rám, pohon a AIO. Drahé/importované LD06 a video je
rozumné zaplatit až po zkušebním osazení jejich maket do vytištěných držáků.

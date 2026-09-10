# Díly pro CAD model

Tohle není kusovník - ten je v [tabulce komponent](./03_komponenty.md) a řeší
hmotnosti, napětí a rozhraní. Tady jde o **geometrii**: co je jak velké, kde má
díry a kam to na rámu patří, aby z toho šel postavit model.

## Souřadnice

Stejné jako v ROS modelu, aby se ty dva nerozešly:

- počátek v `base_link`, tedy geometrický střed rámu v rovině horní desky
- **X dopředu**, **Y doleva**, **Z nahoru**
- motory v quad X na `±45.25 mm` v X i Y, což je půl rozvoru 128 mm děleno
  odmocninou ze dvou

## Jistota

Sloupec říká, odkud číslo je. **Rozměry označené `sim`** jsou z dnešního Gazebo
modelu, kde jsem je odhadl, aby model vypadal jako cinewhoop - **nejsou měřené a
do CADu se nemají opisovat jako fakt**. Sloužily jen k tomu, aby fyzika měla
rozumné bloky.

## Ověřené rozměry

| Díl | Rozměry | Uchycení | Zdroj |
| --- | --- | --- | --- |
| Rozvor | 128 mm mezi protilehlými motory | - | GEPRC |
| Karbonová deska | tloušťka 2.5 mm | - | prodejce |
| Motor GEPRC SPEEDX2 1404 | ⌀18.2 × 13.8 mm, hřídel ⌀1.5 mm, vývody 160 mm | dle 1404 standardu, neověřeno | vendor |
| Vrtule HQ DT76MMX3 V2 | ⌀76 mm, 3 listy | náboj na ⌀1.5 mm hřídel | vendor |
| FC MicoAir H743 V2 45A AIO | 36 × 36 × 8 mm | **25.5 × 25.5 mm** | vendor |
| RX SpeedyBee ELRS Nano | 10.4 × 18.4 mm | lepený/stahovací | vendor |
| Anténa RX | T-anténa 54 × 78 mm | IPEX1 | vendor |
| MicoAir MTF-02P | 21.6 × 16 × 6.5 mm | neověřeno | prodejce |
| Baterie Tattu 4S LiHV 750 | dvě provedení: 60 × 31 × 27 mm, nebo „long" 76 × 17 × 28 mm | pásek | prodejci |

## Rozměry, které chybí

Tyhle se z webu vytáhnout nedaly a **do modelu je potřeba je doplnit z
datasheetu nebo změřit**, až díly dorazí:

| Díl | Co chybí | Kde to vzít |
| --- | --- | --- |
| **LDRobot LD06** | půdorys, výška, rozteč a průměr montážních děr, výška optického okna nad základnou, konektor | [datasheet PDF](https://www.yahboom.net/xiazai/LiDar-LD06/LDROBOT_LD06_Datasheet.pdf) - obsahuje montážní výkres |
| **EMAX Wyvern Link Alpha** | rozměr desky (uchycení 25.5 × 25.5 je známé), rozměr kamerového modulu, vyložení objektivu | manuál EMAX; objektiv je 19 mm |
| Rám GEP-CL30 V3 | vnitřní a vnější průměr ductu, výška ductu, obrys spodní desky, rozmístění stojin, prostor pod kanopou | výkres GEPRC, nebo změřit |
| Motor 1404 | rozteč montážních děr (obvykle 9 × 9 mm u 1404, neověřeno) | datasheet |
| MTF-02P | poloha a průměr montážních děr | MicoAir |

Bez rámu je model stejně jen sestava komponent ve vzduchu, takže **duct a spodní
deska jsou to nejdůležitější, co dohledat**.

## Co model musí zodpovědět

Kvůli tomu se staví, ne kvůli obrázku:

1. **Kam LD06.** Musí vidět dopředu mimo ducty a nesmí zasahovat do roviny
   vrtulí. To je otevřená otázka, která může celou volbu senzoru zabít, viz
   [rozhodnutí](../../workflow/decisions.md).
2. **Těžiště.** Baterie nahoře nebo dole, a jak daleko dozadu, aby vyvážila LD06
   vpředu.
3. **Výhled MTF-02P dolů** bez stínění spodní deskou nebo baterií.
4. **Kam kamera Wyvernu**, aby nekoukala do ductu.
5. **Přístup k USB** na FC, když je všechno smontované.

## Poznámka k rozměrům v simulaci

Bloky v `model.sdf` jsou přibližné: tělo 105 × 105 × 18 mm, kamera 26 × 22 × 20
na x = 68, lidar 18 × 30 × 14 na x = 73, rangefinder na x = 20, z = -16. Vznikly
proto, aby model vypadal a choval se jako cinewhoop, ne z výkresu.

Až bude CAD stát na skutečných rozměrech, mají se **hodnoty přenést do simulace**,
ne naopak. Hlídat to umí `scripts/check_model_consistency.py`, který dnes drží
shodu URDF a SDF - CAD by byl třetí místo, kde se geometrie může rozejít.

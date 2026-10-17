# hwdef pro ArduPilot — Pavo20AIO

Popis desky `dps/aio` pro ArduPilot. Vychází z `MicoAir743v2`, což je cíl,
na kterém běží dnešní MicoAir H743 V2 45A AIO (board ID 1179, viz
[firmware](../../../firmware/README.md)). Piny jsou stejné jako tam, takže
mapa pinů ve schématu ([NAVRH.md](../NAVRH.md#mapa-pinů-h743)) a hwdef říkají totéž.

| Soubor | Co |
| --- | --- |
| `Pavo20AIO/hwdef.dat` | firmware |
| `Pavo20AIO/hwdef-bl.dat` | bootloader |
| `Pavo20AIO/defaults.parm` | výchozí parametry, které plynou ze zapojení: relé VTX, INA226 |

## Rozdíly proti MicoAir743v2

| Co | MicoAir743v2 | Pavo20AIO | Proč |
| --- | --- | --- | --- |
| `APJ_BOARD_ID` | AP_HW_MicoAir743v2 (1179) | **25026**, soukromé | uploader nesmí nahrát cizí firmware. Rozsah 1000–19999 přiděluje ArduPilot jen přes PR, 25026 není v `board_types.txt` použité. Před zveřejněním desky požádat o jméno `AP_HW_…` |
| Dělič baterie | 21.12 | **11.0** | R303 100k / R304 10k |
| Proud | 40.2 | **50.0** A/V | INA186A3 100 V/V × 0,2 mΩ = 20 mV/A |
| Kompas | QMC5883L na desce | **jen externí** v GPS, `HAL_I2C_INTERNAL_MASK 1` | na desce kompas není. I2C2 (bus 0) je vnitřní, I2C1 (bus 1) vede ke GPS |
| Baro | SPL06 0x77 | SPL06 0x77 **a** DPS310 0x76, oba se zkusí | baro ještě není vybrané |
| OSD | AT7456E na SPI1, `OSD_TYPE 1` | **bez SPI1**, `HAL_OSD_TYPE_DEFAULT 5` (MSP DisplayPort) | VTX je digitální |
| BMI088 | ano | piny rezervované, když není osazený, ArduPilot ho nenajde a jede dál | druhá IMU je otevřená otázka |
| Rotace IMU | ROLL_180… | `ROTATION_NONE` | **doplnit po layoutu** podle toho, jak čipy sedí |
| SERIAL7 | telemetrie ESC | bez výchozího protokolu | ESC z OpenESC nemají vodič telemetrie, otáčky jdou přes bidirectional DShot |
| SERIAL3 | — | GPS | WS-M181 na USART3 |
| PD13 (PWM8) | výstup | relé VTX: `RELAY1_PIN 57`, `RELAY1_DEFAULT 1`, `SERVO8_FUNCTION -1` | spíná EN bucku U201 |
| INA226 | — | `BATT2_MONITOR 21`, bus 0, 0x40, 0,02 Ω, 3 A | proud VTX |

## Sestavení

```sh
nix develop ./dps#firmware -c dps/aio/hwdef/sestav.sh     # → build/pavo20aio/
```

Skript sestaví v kopii `external/ardupilot` z hardlinků (aby SITL build v
originále zůstal na své desce) bootloader a ArduCopter a zkopíruje
`arducopter.apj`, `arducopter_with_bl.hex` a `Pavo20AIO_bl.bin` do `build/pavo20aio/`.

Stav **17. 10. 2026**, ArduPilot `8b9ea70` (s projektovým patchem pro DDS),
GCC arm-none-eabi 15.3.1:

| Cíl | Výsledek | Flash |
| --- | --- | --- |
| bootloader (`--Werror`) | sestaven | 20 360 B, 110 kB volno |
| ArduCopter | sestaven | 1 435 912 B, **268 kB volno** z 1 920 kB |

Varování jsou obecná, ne od desky: 6× `-Woverloaded-virtual` v `AP_HAL/RCOutput.h`
z novějšího GCC a jedno varování linkeru o segmentu RWX. Firmware **nikdo
nenahrál do desky**, deska ještě neexistuje. Sestavení ověřuje, že hwdef je
úplný a konzistentní, ne že deska poletí.

## Co se ještě změní

Až se rozhodne v [otevřených otázkách](../NAVRH.md#8-otevřené-otázky): baro (jedna
řádka `BARO`), logování (SDMMC, nebo `HAL_LOGGING_DATAFLASH` se SPI flash),
BMI088 (smazat, když nebude), rotace IMU podle layoutu.

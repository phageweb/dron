# Zdroje

Stav k **7. 10. 2026**.

## OpenDrone (Incutec), KiCad 10, CERN-OHL-S-2.0

- [OpenDrone-hw](https://github.com/OpenDrone-hw) — přehled repozitářů a stavů
- [OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20) — 4in1 AM32, `AGENTS.md` s díly, LCSC a revizemi
- [OpenESC-30x30](https://github.com/OpenDrone-hw/OpenESC-30x30) — 2–8S sourozenec
- [OpenFC-Lite-Mini](https://github.com/OpenDrone-hw/OpenFC-Lite-Mini) — RP2354A FC, Rev2 létala; zdroj napájení a víceznačné IMU plošky
- [OpenRX-Lite](https://github.com/OpenDrone-hw/OpenRX-Lite) — ESP32-C3 + SX1281, 10 × 11,5 mm
- [OpenRX](https://github.com/OpenDrone-hw/OpenRX) — rodina přijímačů
- [OpenAIO](https://github.com/OpenDrone-hw/OpenAIO) — AIO skládaný z listů, nevyrobený
- [OpenAIO-Whoop](https://github.com/OpenDrone-hw/OpenAIO-Whoop) — plánovaný 1S whoop
- [nicoflojo/OpenAIO](https://github.com/nicoflojo/OpenAIO) — fork OpenAIO
- [OpenDrone-hw/KiCad-Library](https://github.com/OpenDrone-hw/KiCad-Library) — sdílená knihovna s `PARTS-USED.md`

## Ostatní ESC

- [Just4Stan/Open-4in1-AM32-ESC](https://github.com/Just4Stan/Open-4in1-AM32-ESC) — předchůdce OpenESC-20x20
- [IOkFly-Race-AM32-4in1-ESC](https://github.com/IOkFly-BLENDERIS/IOkFly-Race-AM32-4in1-ESC)
- [AM32 firmware](https://github.com/am32-firmware/AM32)

## Letové kontroléry H743

- [HeyPCB/kestrel-fc](https://github.com/HeyPCB/kestrel-fc) — Kestrel H7, KiCad 10, nevyrobený
- [Jun-copter/FlightComputer](https://github.com/Jun-copter/FlightComputer) — H743 + ELRS, ve vývoji
- [salehali22/SAL-FC](https://github.com/salehali22/SAL-FC) — H743, HW soubory soukromé
- [CBUnmanned H743 Stamp, ArduPilot wiki](https://ardupilot.org/copter/docs/common-StampH743.html)
- [CBUnmanned: footprinty a 3D model](https://wiki.cbunmanned.com/wiki/products/cbunmanned-stamp-eco-system/h743-stamp-flight-controller-and-low-cost/pcb-footprints-and-3d-model)
- [ArduPilot discourse: Fully open source design of H743 FC](https://discuss.ardupilot.org/t/fully-open-source-design-of-h743-flight-controller-for-fixed-wing-aircraft/126482)
- [ArduPilot: Porting to a new flight controller board](https://ardupilot.org/dev/docs/porting.html)
- `external/ardupilot/libraries/AP_HAL_ChibiOS/hwdef/MicoAir743v2/hwdef.dat` a `CBU-H7-LC-Stamp/` — lokálně, `8b9ea70`

## ArduPilot na RP2350

- [PR #32995 RP2350 Port](https://github.com/ArduPilot/ardupilot/pull/32995) — otevřený, změny vyžádané
- [Issue #28266 Support for RP2350](https://github.com/ArduPilot/ardupilot/issues/28266)

## Ostatní

ESP32 odkazy zůstávají jen jako záznam rešerše — ESP32 na desce nebude.

- [DroneBridge for ESP32](https://github.com/DroneBridge/ESP32) — UART ↔ Wi-Fi/ESP-NOW, Apache-2.0
- [espressif/kicad-libraries](https://github.com/espressif/kicad-libraries) — symboly a footprinty ESP32
- [NicheElectronics/2.4GHz-ELRS-ESP32C3-SX1281-RX](https://github.com/NicheElectronics/2.4GHz-ELRS-ESP32C3-SX1281-RX) — další otevřený ESP32-C3 RX v KiCadu
- [bitcraze/crazyflie-electronics](https://github.com/bitcraze/crazyflie-electronics) — archivované KiCad soubory Crazyflie
- [Pixhawk Hardware](https://github.com/pixhawk/Hardware) — referenční návrhy Pixhawk, CC BY-SA 3.0, ne KiCad
- [RadioMaster XR1 Nano, GetFPV](https://www.getfpv.com/radiomaster-xr1-nano-multi-frequency-elrs-2-4ghz-sub-g-900mhz-dual-band-receiver.html) — LR1121, 2,4 GHz + 900 MHz

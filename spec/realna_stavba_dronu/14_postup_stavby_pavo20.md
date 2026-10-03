# Postup stavby Pavo20 Pro

Celý postup od krabic na stole po první let, pro díly, které jsou opravdu
koupené — viz [Nakoupeno](./13_nakoupeno.md). Obecná pravidla a stop podmínky
jsou v [bench checklistu](./04_bench_checklist.md); tenhle soubor je jeho
konkrétní pořadí pro tuhle sestavu, s piny a parametry.

Pravidlo platí i tady: **když krok neprojde, další se nezačíná.** A vrtule se
nasazují až v kroku 9.

Parametry jsou ověřené z dokumentace ArduPilotu a karty MicoAir k 2. 10. 2026,
ne na kusu. Kde to tak není, je to napsané.

## 0. Příprava

- [ ] Každý díl zvážit (váha s rozlišením 0,01 g) a hmotnost zapsat do
      [Nakoupeno](./13_nakoupeno.md). Žádná hmotnost v projektu ještě zvážená
      není — teď je jediná chvíle, kdy jde vážit díly jednotlivě.
- [ ] Baterie: změřit napětí článků, nabít na storage (LiHV kolem 3,85 V na
      článek), uložit v lipo bagu.
- [ ] Laboratorní zdroj: kabel zakončený XT30 samicí, polarita ověřená
      multimetrem.

## 1. Firmware — jen přes USB

Deska se napájí z USB, baterie ani zdroj nejsou potřeba.

- [ ] Target **`MicoAir743v2`** (MicoAir pro desku *MicoAir743v2-AIO-45A*;
      ArduPilot ho podporuje od 4.6.0). Firmware:
      `firmware.ardupilot.org/Copter/stable-4.7.1/MicoAir743v2/`.
- [ ] Nahrát ArduCopter 4.7.1 podle [`firmware/`](../../firmware/README.md) —
      flake s připnutým firmwarem a nástroji:

      ```sh
      nix run ./firmware#flash      # na desce už je ArduPilot
      nix run ./firmware#flash-dfu  # Betaflight z výroby: držet BOOT, připojit USB
      ```
- [ ] `FRAME_CLASS 1`, `FRAME_TYPE 1` (quad X), restart.
- [ ] Parametry uložit do souboru **před** jakoukoli další změnou.
- [ ] Gyro v klidu kolem nuly, barometr reaguje na zvednutí ze stolu.
      Akcelerometr až v kroku 6, v sestaveném dronu — holá deska na USB se
      do bočních poloh nedá postavit, konektor ji podpírá a vypadává.

## 2. Mechanika nasucho

- [ ] Rám složit bez pájení. **Ověřit, že je to Pavo20 Pro, ne Pro II**
      ([rozdíl](./10_pavo20.md#pro-versus-pro-ii)).
- [ ] Motory A1204 na ramena (díry 9 mm, M2). **Protočit rukou a změřit
      mezeru zvonu proti ductu** — A1204 je o 1,2 mm širší než 1104, na který
      je rám dělaný. Drhne-li, dál se nejde.
- [ ] Délka šroubů motoru: šroub nesmí sáhnout do vinutí. Změřit, ne odhadnout.
- [ ] AIO na rozteč 25,5 × 25,5 se soft-mounty, šipka dopředu. USB-C musí být
      v sestaveném rámu dostupný.
- [ ] Zkusmo umístit: XR1, GPS, MTF-02P (dolů, **mimo půdorys baterie**),
      kameru Lite+ a VTX. Kde co bude, rozhoduje o délkách vodičů v kroku 3.
- [ ] Baterii 750 mAh zasunout do slotu a zkontrolovat, že sedí a nic netlačí.

## 3. Pájení napájení a motorů

- [ ] XT30 přívod a kondenzátor (oboje přibalené k AIO) na hlavní pady.
      Polarita podle desky, ne podle barvy kabelu.
- [ ] Motorové vodiče zkrátit na délku a připájet na pady M1–M4. Pořadí
      vodičů jednoho motoru je jedno — směr se nastaví softwarově v kroku 5.
- [ ] Vizuálně: žádný cínový můstek, nic se nedotýká karbonu.
- [ ] **Multimetrem mezi + a − XT30: žádný zkrat** (pod ~10 Ω = stop).
- [ ] První napájení z **laboratorního zdroje: 16 V, limit 0,3–0,5 A**. Proud
      v klidu jsou desetiny ampéru; skočí-li hned na limit a napětí spadne,
      je zkrat — odpojit a hledat.
- [ ] Změřit **5V BEC** (5,0 V ± 0,2) a **12V BEC**. Hodnotu 12V BEC zapsat —
      podle ní se v kroku 7 rozhodne, jestli na něj smí Lite+ (strop 12,6 V).

## 4. Přijímač XR1 Nano

| XR1 | AIO |
| --- | --- |
| 5V | 5V |
| GND | GND |
| TX | RX6 |
| RX | TX6 |

- [ ] Parametry: `SERIAL6_PROTOCOL 23` (RCIN), `RSSI_TYPE 3`.
- [ ] Stejná hlavní verze ELRS v TX15 a v XR1. Binding phrase nastavit v obou
      (XR1 přes WiFi: ~60 s bez spojení, pak `10.0.0.1`).
- [ ] Kalibrace RC. Roll, pitch, throttle, yaw jdou správným směrem.
- [ ] Kanál na arm/disarm (`RCx_OPTION 153`) a na letové režimy
      (`FLTMODE_CH`): Stabilize, AltHold, Loiter.
- [ ] `FS_THR_ENABLE 1`. **Vypnout TX15 → FC musí hlásit failsafe.** Bez toho
      dál ne.

## 5. Motory bez vrtulí

Teď už z baterie (nebo ze zdroje s limitem zvýšeným na 2–3 A). Dron přidržet.

- [ ] `MOT_PWM_TYPE 6` (DShot600). Bidirectional DShot (`SERVO_BLH_BDMASK 15`,
      `SERVO_BLH_POLES 14`) jen pokud ho target na výstupech 1–4 umí —
      **neověřeno**; počet pólů ověřit spočítáním magnetů ve zvonu.
- [ ] Motor test v QGC/Mission Planneru, 5–10 % plynu: test A musí roztočit
      **přední pravý**, B zadní pravý, C zadní levý, D přední levý (ArduPilot
      testuje po obvodu). Nesedí-li to, přeházet `SERVO1..4_FUNCTION`
      (33–36), ne pájet znovu.
- [ ] Směry: přední pravý a zadní levý **CCW**, přední levý a zadní pravý
      **CW** (pohled shora). Špatný směr otočit `SERVO_BLH_RVMASK` nebo v AM32
      konfigurátoru přes passthrough.
- [ ] `MOT_SPIN_ARM` a `MOT_SPIN_MIN` z motor testu: nejnižší hodnota, kdy se
      všechny čtyři točí spolehlivě, + rezerva.
- [ ] Nic se nepřehřívá, nedrhne, nehrká.

## 6. Senzory

**Akcelerometr** (dron složený, AIO na soft-mountech, bez baterie, jen USB):

- [ ] Kalibrace v 6 polohách na hranách rámu, pak level na rovném stole.
      Bez ní ArduPilot neodjistí (`3D Accel calibration needed`).
- [ ] Šipka na AIO míří dopředu: při nose-down musí X ukazovat −1 g.

**MTF-02P** (optical flow + dolní rangefinder):

- [ ] Nejdřív v MicoAssistant změnit `mav_id` na 200 — od ArduPilotu 4.5
      ho jinak nemusí poznat.
- [ ] Zapojit na UART4: 5V, GND, TX → RX4, RX → TX4.
- [ ] `SERIAL4_PROTOCOL 1`, `SERIAL4_BAUD 115`, `FLOW_TYPE 5`,
      `RNGFND1_TYPE 10`, `RNGFND1_MIN 0.01`, `RNGFND1_MAX 6`,
      `RNGFND1_ORIENT 25`. Od 4.7 `MAV4_OPTIONS 2`, dřív `SERIAL4_OPTIONS 1024`.
- [ ] Výška nad stolem sedí s pravítkem ve dvou výškách; flow reaguje na ruční
      posun; při točících se motorech (bez vrtulí) nevypadává.

**GPS M181 s kompasem:**

- [ ] UART3: 5V, GND, TX → RX3, RX → TX3; kompas na SDA/SCL.
- [ ] `SERIAL3_PROTOCOL 5`. Kompas nakalibrovat **v sestaveném dronu**.
- [ ] Rozhodnout, co s kompasem uvnitř: checklist říká vypnout, jenže EKF bez
      kompasu nemá yaw pro Loiter na flow. Pro první lety (Stabilize,
      AltHold) to jedno je — **otevřená otázka**, zapsat výsledek.

## 7. Video Walksnail Lite+

- [ ] **Napájení: nikdy z baterie.** 12V BEC jen pokud v kroku 3 naměřil
      nejvýš ~12,3 V. Jinak řešit (dioda, samostatný BEC) dřív, než se pájí.
- [ ] Zapojit na UART2: 12V, GND, TX → RX2, RX → TX2 (OSD).
- [ ] `SERIAL2_PROTOCOL 42` (DisplayPort), `SERIAL2_BAUD 115`, `OSD_TYPE 5`,
      `MSP_OPTIONS 4` (Betaflight fonty).
- [ ] Spárovat s **VRX Pro**, obraz přes HDMI na monitor/brýle. **Anténu
      připojit vždy dřív, než se VTX zapne.**
- [ ] Kameru a VTX upevnit — dočasně, dokud není [TPU věž](./11_kusovnik_pavo20.md#co-se-musí-vyrobit).

## 8. Baterie a failsafe

Hodnoty ze simulace (`ardupilot_params_pavo20.parm`):

- [ ] `BATT_MONITOR 4`; napětí na desce porovnat s multimetrem, případně
      opravit `BATT_VOLT_MULT`. Proud ověřit až za letu.
- [ ] `BATT_LOW_VOLT 14.0`, `BATT_CRT_VOLT 13.2`, `BATT_FS_LOW_ACT 1`,
      `BATT_FS_CRT_ACT 1`, `BATT_LOW_TIMER 10` — přistát, ne vracet se.
- [ ] Rate gainy ze simulace (`ATC_RAT_RLL/PIT_P 0.060` atd.) brát jako
      **strop**, ne startovní hodnotu: simulace nemá šum gyra ani rezonance
      rámu. **Nepřebírat** `MOT_PWM_MIN/MAX`, `MOT_THST_EXPO 1.0` a `SIM_*` —
      to jsou hodnoty modelu, ne dronu.

## 9. Vrtule a první let

- [ ] **42g maketa LD06** na místě lidaru — ladí se jednou, s ní.
- [ ] Vrtule Gemfan 2218 podle směrů z kroku 5.
- [ ] Venku nebo ve velké místnosti, nikdo v dosahu. Arm ve Stabilize, krátký
      visení nízko. Kmitá-li, přistát a snížit `ATC_RAT_*_P`.
- [ ] Failsafe znovu za letu: vypnout TX15 v metru nad zemí.
- [ ] Teprve pak AltHold, pak AutoTune, pak Loiter na flow.
- [ ] Po letu: log, harmonic notch (`INS_HNTCH_*`) podle spektra, výdrž proti
      odhadu 4,0 min.

## 10. Etapa B — LD06

- [ ] Kabel ZH1.5T-4P → AIO, jen TX lidaru → RX5 (nebo RX8), 5V, GND.
- [ ] `SERIAL5_PROTOCOL 11` (Lidar360), `SERIAL5_BAUD 230`, `PRX1_TYPE 16`,
      `PRX1_ORIENT 0`.
- [ ] Přeměřit 5V větev při rozběhu lidaru (300 mA).
- [ ] Maketu vyměnit za lidar; hmotnost a těžiště se nemění, gainy zůstávají.

## Rozvržení UARTů

| UART | Výchozí v ArduPilotu | Tady |
| --- | --- | --- |
| 1 | MAVLink2 | volný (telemetrie, palubní počítač) |
| 2 | DisplayPort | Walksnail Lite+ OSD |
| 3 | GPS | M181 |
| 4 | MAVLink2 | MTF-02P |
| 5 | — | LD06 (etapa B) |
| 6 | RCIN | XR1 Nano |
| 8 | — | volný |

Mapování UARTů je z karty MicoAir; **které pady na desce jsou který UART,
ověřit na potisku a pinoutu desky** dřív, než se pájí.

# Reálná stavba dronu - plán stavby

## Fáze 1: Potvrzení komponent

Cíl:

- potvrdit přesné verze všech komponent
- ověřit mechanickou kompatibilitu rámu, AIO desky, kamery a senzorů
- zapsat hmotnosti skutečných dílů

Checklist:

- [ ] GEPRC CineLog30 V3 frame kit
- [ ] MicoAir H743 V2 45A AIO
- [ ] 4x GEPRC SPEEDX2 1404 3850 KV
- [ ] sada 3" cinewhoop vrtulí
- [ ] Tattu 4S LiHV 750 mAh
- [ ] SpeedyBee ELRS Nano RX
- [ ] RunCam WiFiLink 2 / OpenIPC
- [ ] MicoAir MTF-02P
- [ ] přední obstacle lidar/depth/range sensor
- [ ] vhodný companion computer pro ROS 2, pokud nemá běžet mimo dron

Výstup:

- tabulka komponent, hmotností, konektorů, napájecích napětí a datových rozhraní

## Fáze 2: Mechanická montáž nasucho

Cíl:

- poskládat rám bez pájení
- ověřit prostor pro FC, kameru, RX, MTF-02P a kabeláž
- najít umístění předního obstacle senzoru

Kritéria:

- těžiště co nejblíž středu
- kamera vpředu bez kontaktu s ducty
- optical flow a rangefinder mají čistý výhled dolů
- přední lidar má čistý výhled dopředu
- USB/servisní konektory jsou dostupné

## Fáze 3: Napájení a pájení

Cíl:

- připravit napájecí rozvod
- připájet motory k AIO
- připravit RX, kameru a senzory

Bezpečnost:

- baterii připojovat poprvé přes smoke stopper
- vrtule nenasazovat
- kontrolovat polaritu před každým prvním zapojením

Checklist:

- [ ] XT30/napájecí vstup
- [ ] motor 1 až 4 na správných ESC padech
- [ ] ELRS RX UART
- [ ] MTF-02P UART/I2C/CAN podle reálné varianty
- [ ] kamera/OpenIPC napájení podle specifikace
- [ ] přední obstacle sensor napájení a data

## Fáze 4: ArduPilot firmware na MicoAir H743

Cíl:

- nahrát ArduPilot firmware pro správný board target
- ověřit komunikaci přes USB
- nastavit základní parametry frame typu

Checklist:

- [ ] správný ArduPilot target pro MicoAir H743 V2
- [ ] spojení s GCS nebo MAVProxy
- [ ] akcelerometr/gyra kalibrace
- [ ] compass jen pokud bude potřeba venkovní varianta
- [ ] barometr čte reálná data
- [ ] frame class/type pro quad X

Poznámka:

- GPS pro první indoor variantu není potřeba.
- Kompas/GPS nepoužívat jako podmínku indoor demo letu.

## Fáze 5: RC a failsafe

Cíl:

- spárovat ExpressLRS RX
- ověřit kanály
- nastavit failsafe a arm switch

Checklist:

- [ ] ELRS bind
- [ ] správné mapování roll/pitch/throttle/yaw
- [ ] arm/disarm switch
- [ ] flight mode switch
- [ ] radio failsafe
- [ ] throttle failsafe

## Fáze 6: Motor test bez vrtulí

Cíl:

- ověřit pořadí motorů a směry rotace
- sladit ArduPilot motor mapping s fyzickým quad X rozložením

Checklist:

- [ ] motor 1 fyzicky odpovídá ArduPilot motoru 1
- [ ] motor 2 odpovídá
- [ ] motor 3 odpovídá
- [ ] motor 4 odpovídá
- [ ] směry rotace odpovídají zvolenému prop směru
- [ ] žádný motor se nepřehřívá

## Fáze 7: Senzory

Cíl:

- oživit optical flow a dolní rangefinder
- oživit přední obstacle sensor
- rozhodnout, které senzory čte ArduPilot a které ROS companion

Checklist:

- [ ] MTF-02P publikuje/posílá optical flow
- [ ] dolní vzdálenost odpovídá realitě
- [ ] přední obstacle sensor měří vzdálenost před dronem
- [ ] časování senzorů je stabilní
- [ ] data lze převést na ROS messages

## Fáze 8: OpenIPC video

Cíl:

- oživit RunCam WiFiLink 2 s OpenIPC
- ověřit IP video stream
- připravit cestu do ROS image topicu

Checklist:

- [ ] kamera bootuje
- [ ] síťové připojení funguje
- [ ] video stream je dostupný na notebooku/companion computeru
- [ ] latence je přijatelná pro experimenty
- [ ] existuje plán převodu na `sensor_msgs/msg/Image`

## Fáze 9: ROS 2 companion vrstva

Cíl:

- zprovoznit ROS 2 na companion computeru nebo pozemním počítači
- připojit se k ArduPilotu přes DDS/MAVLink/adaptér
- zachovat topic názvy kompatibilní se simulací

Ověření:

```bash
ros2 topic list
ros2 service list
ros2 topic echo /openipc_cinewhoop/range/down --once
ros2 topic echo /openipc_cinewhoop/scan/front --once
```

## Fáze 10: První letové testy

Pořadí:

1. bez vrtulí: arm/disarm, motor test, failsafe
2. s vrtulemi: krátký ruční hover v bezpečném prostoru
3. optical flow hold / altitude hold
4. pomalý indoor let
5. ROS pouze monitoruje data
6. ROS posílá jednoduché příkazy až po stabilním ručním letu

Kritéria:

- dron je mechanicky stabilní
- drží hover
- failsafe funguje
- senzory dávají smysluplná data
- ROS autonomie se zapíná jen kontrolovaně a pomalu

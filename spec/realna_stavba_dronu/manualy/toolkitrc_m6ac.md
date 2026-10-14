# ToolkitRC M6AC — manuál V1.1 (2025.03)

Přepis oficiálního PDF do Markdownu:
<https://download.toolkitrc.com/wp-content/uploads/2024/12/M6AC-Manual-V1.1.pdf>
(staženo 2026-10-11). Text je anglický originál, jen opravené zalomení a
překlepy. Snímky obrazovek z PDF tu nejsou; kde text odkazuje „as shown
below“, je obrázek jen v PDF.

**Poznámka pro tenhle projekt:** manuál neříká výslovně, na kterém konektoru je
režim zdroje (kap. *Power*). Na přední straně je ze silových výstupů jen
*Output port* (XT60, nabíjecí) a USB-A 5 V/1 A, takže zdroj 1–28 V / 0,5–15 A
jde přes XT60. Před prvním připojením dronu ověřit napětí a polaritu
multimetrem. Redukce na dron: XT60 samice → XT30 samec (viz
[13_nakoupeno.md](../13_nakoupeno.md)).

---

## Introduction

Thank you for purchasing the M6AC balance charger, please read this manual
carefully before use.

### Further information

To ensure you have the best experience with this product, please follow us on
Facebook @ToolkitRC to stay up to date with news, information and firmware
updates for your charger; this information could be found at
www.toolkitrc.com.

## Safety

1. Allows input voltage of DC 7–28 V or AC 100–240 V. Ensure the charger is
   only connected to a suitable power source and correct polarity.
2. Do not use this product in hot, humid, flammable or explosive environments.
3. Please do not use this charger without supervision. Never leave charging
   batteries unattended.
4. When not using this product, please unplug the input power.
5. When using the charging function, please set a current that matches the
   battery. Do not set an excessive current for charging to avoid damage to
   the battery. Check the guidelines of your battery's manufacturer for
   correct charging instructions.

## Product description

The M6AC is a multifunctional tool that integrates functions such as a balance
charger and discharger, a signal measuring device, and a signal source.

- Supports AC or DC dual input.
- Charges, discharges and balances (where applicable) LiPo, LiHV, LiFe,
  LiIon, LTO 1–6S, NiMH 1–16S, PB 1–10S batteries.
- Charge current: max 15 A @ max 300 W.
- Discharge current: recycle max 15 A @ 300 W; internal mode max 3 A @ 20 W.
- Lithium battery cut-off voltage can be adjusted at will (TVC function).
- Measures battery voltage, battery internal resistance, and balances lithium
  packs automatically.
- Measures / outputs PWM/PPM/SBUS standard signals with an accuracy of 1 µs.
- Constant current and constant voltage source output, customizable 1–28 V
  constant voltage, 0.5–15 A constant current.
- Can be adapted for charging consumer-grade drone batteries.
- Multi-language user interface.
- Easily upgradable via USB.

## M6AC layout

| Strana | Prvky |
| --- | --- |
| Front | display, USB output, balance port, signal port, output port, buttons |
| Back | DC input, cooling fan, AC input |

## Quick start

1. Connect a 7–28 V or AC 100–240 V power supply or battery/power bank to the
   input port on the back of the M6AC.
2. The display shows the boot logo and stays for 2 seconds.
3. A welcome sound (voice pack dependent) is played simultaneously.
4. After booting up, the screen enters the main interface.
5. Press and hold [■ button] to enter the multi-function interface.
6. Press [▲▼ button] to switch between pages.
7. When the charger is idle, short press [● button] to set the charging
   parameters. Press [● button] during the charging process to adjust the
   amperage or stop the charge process.
8. When the charger is idle, press and hold [● button] to enter the system
   setting interface.
9. Short press [■ button] to return to the previous interface.

## Charge and discharge settings

In the main interface, select and short press [● button] to enter the
charging function. If the battery selection option is enabled on the setup
page, the battery selection interface will be displayed (not enabled by
default).

### 1. Battery type setting

Press [▲▼ button] and select one of the presets, or create a new battery. Up
to 32 battery files can be created. Press [● button] to enter a specific
battery setting.

Move the cursor to [Battery Type] and press [● button] to modify the battery
type.

The charger supports charging and discharging of these battery types: LiPo,
LiHV, LiFe, LiIon, LTO, NiMH and PB. There is also a smart battery mode to
choose from. Battery destruction is supported for LiPo, LiHV, LiFe, LiIon,
LTO.

After selecting the battery type that matches the battery on charge, short
press [● button] and [■ button] to save and return to the previous interface.

> **Warning:**
> 1. Ensure the correct battery type has been selected prior to charging. An
>    incorrect choice may damage the battery and/or become a fire hazard.
>    Please use caution.
> 2. Do not use this product to charge non-compatible battery chemistries.

**Glossary of battery terms:**

| Typ | Nominal | Full |
| --- | ---: | ---: |
| LiPo (lithium polymer) | 3.70 V | 4.20 V |
| LiHV (high-voltage lithium) | 3.85 V | 4.35 V |
| LiFe (iron-lithium) | 3.30 V | 3.60 V |
| LiIon (lithium-ion) | 3.60 V | 4.10 V |
| LTO (lithium titanate) | 2.40 V | 2.70 V |
| NiMH | 1.20 V | — |
| PB (lead-acid) | 2.00 V | — |

### 2. Cell setting

Move the cursor to [Battery Section], then press [● button] to modify the
number of cells. Press [▲▼ button] to adjust the value. When set to [Auto],
the charger will automatically identify the number of cells by checking the
total voltage against the balance port data. Short press [● button] and
[■ button] to take effect and return to the previous interface.

> **Tips:**
> 1. If the connected battery is over-discharged or over-charged, this may
>    cause an incorrect cell count, in which case the cell number needs to be
>    adjusted manually.
> 2. If the cell count is set incorrectly, it may lead to overcharging, which
>    can present itself as a fire risk.
> 3. The cell count can be more accurately determined if the balance port is
>    connected.

### 3. Work mode

Move the cursor to [Mode] and press [● button] to modify the work mode.

LiPo, LiHV, LiFe, LiIon, LTO batteries can be charged, discharged, stored and
destroyed. NiMH battery can be charged, discharged, or cycled. PB battery can
be charged and discharged. Short press [● button] and [■ button] to take
effect and return to the previous interface.

### 4. Discharge mode

Under discharge, storage, and cycle modes, the option of discharging the
battery will appear. Move the cursor to [Discharge Mode] and press
[● button] to modify the discharge mode.

The charger supports 2 discharge modes:

1. **Normal mode:** discharge using internal heat dissipation, maximum
   3.0 A @ 15 W discharge.
2. **Recycle mode:** when a battery is used as the input, the power is
   recovered to the input-side battery through this function, max
   15.0 A @ 300 W discharge.

### 5. Max input voltage

When the discharge mode is set to recycle (first set "Power type" to Battery
under input settings), the Max input voltage option will appear. Move the
cursor to [Max Input Vol.] and press [● button] to adjust. If the input
voltage reaches this value during discharge, the discharge will stop.

> **Tips:** Please set the max input voltage to the highest protection voltage
> of the power supply. After the voltage is reached, the charger will
> automatically stop recycling discharge. Setting a high overvoltage may
> damage the input power source.

### 6. End voltage setting (TVC)

Move the cursor to [End Voltage] and press [● button] to modify the end
voltage for the individual cells. When charging, it is the charge cut-off
voltage, and the range is ±50 mV of the full voltage. When discharging, it is
the discharge cut-off voltage. Press [▲▼ button] to adjust the value, step
0.01 V.

> 1. Only LiPo, LiHV, LiFe batteries can set the cut-off voltage.
> 2. Do not modify the cut-off voltage if you are not familiar with the
>    battery characteristics.
> 3. The charging cut-off voltage can be set to a range of ±50 mV of full
>    voltage.
> 4. TVC: terminal voltage control.

### 7. Current setting

Move the cursor to [Charge Current] or [DisCHG Current] and press [● button]
to modify the current. Press [▲▼ button] to adjust the value, step 0.1 A.
Press [▲▼ button] quickly to increase or decrease faster. The charger
supports up to 15.0 A.

> **Tips:**
> 1. Please set a charging rate of 1–2C according to the battery capacity.
>    For example, if the battery capacity is 2000 mAh, set the charge current
>    to 2.0–4.0 A.
> 2. The charge/discharge current is only valid in the corresponding work
>    mode.
> 3. For the discharge mode setting, please refer to the *System settings*
>    chapter of this manual.

### 8. NiMH setting (PeakV)

When the battery type is NiMH, the peak voltage value when the battery is
fully charged can be set, range 5–15 mV.

> **Tips:** This function is only available on NiMH cells. PeakV: the maximum
> voltage drop per cell when the NiMH battery is fully charged.

### 9. Cycle setting

When the battery type is NiMH and in cycle mode, the options Cycle times and
Rest time will appear.

Move the cursor to [Cycle times] and press [● button] to set the cycle count,
range 2–12. The charger follows the pattern discharge → charge → discharge →
charge…; "discharge → charge" counts as 2 times.

Move the cursor to [Rest time] and press [● button] to set the rest time of
the cycle charge, range 2–10 minutes.

### 10. Smart battery setting

When UAV battery is selected as the battery type, there are only two options:
drone type and max current.

Move the cursor to [Drone model] and press [● button] to select between
different drone models. Move the cursor to [Max Current] and press
[● button] to set the charge current, range 0.5–15 A.

## Charge and discharge work

When charging or discharging starts, the charger enters the working
interface. Press [▲▼ button] to toggle between 3 displays.

**Page 1:**

| Údaj | Význam |
| --- | --- |
| P1 | power selection in system settings |
| 24.01V | input voltage |
| 10.0Wh | accumulated energy |
| 45.0℃ | internal temperature of the charger |
| 24.01V | main port voltage |
| 2.00A | main port current |
| 010:00 | working time |
| 338mAh | charged capacity |
| 1 4.000V | voltage of cell 1 (… for each cell) |
| -.---V | no battery connected |

Status flags: V constant voltage, C constant current; current limit flags:
P power limit, I input limit, C maximum current; A charging active; F main
port voltage or a single cell voltage is full.

Short press [● button] to dynamically set the charge current or stop
charging. To end the process, short press [● button], move the cursor to
[Stop], short press [● button]; charging stops and the charger returns to
the main interface. When charging is complete or an error occurs, a popup
appears along with an audible tone.

**Page 2 — internal resistance:** `1 5.2mΩ` internal resistance of cell 1
(… per cell); `T:32mΩ` total internal resistance.

**Page 3 — general information:** `Charging` current status;
`4.20V/2.00A` end voltage / charge current; `48.2W` current charging power.

> **Tips:**
> 1. When charging and discharging, never leave the cells unattended.
> 2. When charging and discharging lithium batteries, balancing only occurs
>    if the balance plug is connected. The charger automatically balances each
>    cell if a balance plug is detected.
> 3. Charging will automatically start for the next battery if the first
>    battery is disconnected after being fully charged. If a fixed cell count
>    is set, ensure the next battery has the same cell count. If set to
>    automatic, make sure the cell count matches what is detected.

## Accessibility (auxiliary functions)

In the main interface, press and hold [■ button] to enter the auxiliary
function interface.

### 1. Measure resistance

Short press [● button] to test the internal resistance of the connected
battery and return to the main interface display.

### 2. Measure signal

Move the cursor to Measure signal, short press [● button] to enter the signal
test interface. Press [▲▼ button] to select the signal type: PWM, PPM or SBUS.
For SBUS, [▲▼ button] shows channels 1–8, channels 9–16, and overall status.

### 3. Signal output

Move the cursor to Signal output, short press [● button] to enter. Press
[▲▼ button] to select the signal type.

- **PWM:** move the cursor to [Manual], press [● button] to set the output
  mode: manual, auto 1, auto 2, auto 3. In manual mode you change pulse width
  and cycle with the cursor. In auto 1/2/3 the pulse width changes
  automatically at 3 different speeds. Width 800–2200 µs; cycle 2.5 ms
  (400 Hz) to 50.0 ms (20 Hz).
- **PPM / SBUS:** press [▲▼ button] to move the cursor to the channel value to
  modify, press [● button] to modify the output pulse width of that channel.

### 4. ESC test

Select ESC test, press [● button] to enter. Press [▲▼ button] to move the
cursor to pulse width / cycle, press [● button] to change the value.

### 5. Power

Select the adjustable power supply with the cursor and short press
[● button] to enter. The voltage and current of the output power supply can
be set at will. Move the cursor to Start and short press [● button] to start
power output and return to the main interface.

## System settings

Long press [● button] in the main interface to enter the system settings
page. Short press to expand each group.

**Input settings** (input power related):

- *Power selection:* preset power 1, power 2, power 3.
- *Power type:* battery pack or adapter. For battery packs recycle mode is
  enabled, for adapters it is disabled.
- *Max power:* maximum wattage allowed via the input port during charging.
- *Max current:* maximum current allowed via the input port during charging.
- *Voltage range:* input voltage range.

**Security settings:**

- *Safe Inter. Temp.:* charging stops when the device temperature exceeds
  this value.
- *Safe Exter. Temp.:* charging stops when the ambient temperature exceeds
  this value.
- *Safe time:* maximum time for continuous charging/discharging.
- *Safe capacity:* maximum accumulated capacity for one charge/discharge
  session.

**Personalization:**

- *Backlight:* display brightness 1–10.
- *Operation volume:* button volume off / low / medium / high.
- *Language:* English, Chinese, etc.
- *Theme style:* light or dark.
- *Battery selection:* show/hide frequently used parameters (default off).
- *Continuous work:* enable/disable continuing after battery replacement.
- *Work completed:* stop or trickle charge after charge complete (default
  no trickle).
- *Balance start Vol:* balance cells before the full-current charge.
- *Default:* restore factory settings.
- *ID:* unique ID of the device.

## Other functions

1. **Firmware upgrade.** Connect the M6AC to a computer with the USB cable
   from the box; the computer recognizes a USB drive named *Toolkit*.
   Download the upgrade file `app.upg` from the ToolkitRC website and
   overwrite the file on the drive.
2. **USB output.** Type-A USB supplies 5.0 V 1.0 A to charge mobile devices.
3. **Automatic continue.** When a battery is fully charged, connect the next
   one; the device continues charging/discharging automatically. Can be
   turned on/off in settings.
4. **Fan level.** The fan starts at 40 °C internal temperature and speeds up
   linearly with temperature. On AC input above 55 W input power the fan runs
   at full speed.
5. **Manual voltage calibration.** With the M6AC off, press and hold
   [● button] and connect power; the system enters manual voltage
   calibration. Measure each cell with a voltmeter, move the cursor to the
   corresponding value and change it to match. Move the cursor to Save and
   short press once; a single beep confirms. Exit or power off afterwards.
6. **Full charge mode.** When a lithium battery is full, "Fast charge
   complete" is shown. If the battery is not removed, the charger trickle
   charges until it is disconnected.

## Specifications

| Skupina | Položka | Hodnota |
| --- | --- | --- |
| Input | AC | 100–240 V @ max 120 W |
| Input | DC | 7–35 V @ max 30 A |
| Battery type | Lithium | LiPo, LiHV, LiFe, LiIon, LTO @ 1–6S |
| Battery type | Other | NiMH @ 1–16S, PB @ 1–10S |
| Balance | | 1000 mA @ 4.2 V |
| Accuracy | | < 0.005 V |
| Charge | Power | 0.1–15 A @ 300 W |
| Discharge | Recycle mode | 0.1–15 A @ 300 W |
| Discharge | Internal mode | 0.1–3 A @ 20 W |
| USB A | | 5.0 V / 1.0 A @ 10 W, or upgrade |
| Measure | Voltage | 1.0–5.0 V @ 1–6S |
| Measure | Internal resistance | 0.1–99 mΩ @ 1–6S |
| Measure | PWM | 880–2200 µs @ 20–400 Hz |
| Measure | PPM | 880–2200 µs × 8 CH @ 20–50 Hz |
| Measure | SBUS | 880–2200 µs × 16 CH @ 20–100 Hz |
| Output | PWM | 500–2500 µs @ 20–1000 Hz |
| Output | PPM | 880–2200 µs × 8 CH @ 50 Hz |
| Output | SBUS | 880–2200 µs × 16 CH @ 74 Hz |
| Output | Power | 0.5–15 A @ 1–28 V, CC+CV |
| Display | LCD | IPS 2.0", 320 × 240 px |
| Product | Size / weight | 108 × 106 × 60 mm, 350 g |
| Packing | Size / weight | 144 × 158 × 63 mm, 510 g |

Nesrovnalosti v originálu: DC vstup je v *Safety* a *Quick start* uveden jako
7–28 V, ve specifikacích 7–35 V. Vybíjení v interním režimu je v kap. 4
3 A @ 15 W, jinde 3 A @ 20 W.

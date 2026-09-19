# 05 – Infrastruktura simulace

Dnes v repozitáři nepoletí dva drony, natož tři, a není to jedna překážka. Je
jich šest a všechny mají společnou příčinu: **název modelu `openipc_cinewhoop`
je použitý jako identita.** Je v cestě každého tématu mostu, v předplatných
můstku aktuátorů, v URI ve světě a nepřímo i v TF.

Tenhle dokument je jejich seznam s odkazy na soubory, aby se o nich dalo
rozhodovat jednotlivě.

## 1. Překážky

### P1 — jméno modelu je jedno pro všechny

`worlds/cluttered_room.sdf:212` vkládá `model://openipc_cinewhoop` bez
`<name>`, takže v Gazebu je entita jedna. Tři instance potřebují tři jména;
`<include><name>v1</name></include>` to umí, ale rozbije P2 a P3.

### P2 — `fdm_port_in` je napevno 9002

`models/openipc_cinewhoop/model.sdf:337-338` má `fdm_addr 127.0.0.1` a
`fdm_port_in 9002`. Tři modely ve stejném světě by poslouchaly na témž portu.
`<include>` neumí přepsat parametr pluginu uvnitř vloženého modelu, takže tohle
je hlavní rozhodnutí: **generovat model na agenta** (xacro/šablona), nebo držet
tři adresáře, jak se to dnes dělá pro draky (`models_pavo20`).

Doporučení: generovat. Tři ručně udržované kopie modelu se rozejdou a
`check_model_consistency.py` dnes hlídá shodu s URDF, ne mezi kopiemi.

### P3 — most Gazebo→ROS má cesty s názvem modelu

`config/gz_bridge.yaml` má v každé položce
`/world/@world@/model/openipc_cinewhoop/link/.../sensor/...`. Šablona dnes
nahrazuje jen `@world@` (`launch/gazebo.launch.py:19-40`). Přibude `@model@`
a generování tří konfigurací, nebo jedné se všemi devíti tématy.

### P4 — můstek aktuátorů je jeden proces na model

`tools/ap_actuator_bridge/main.cc:36-91` bere `--model` (výchozí
`openipc_cinewhoop`) a odebírá `/model/<name>/joint/rotor_N_joint/cmd`.
Parametrizovaný už je; potřebuje jen tři instance s různým `--model`.
`sitl_gazebo.launch.py` ho ale spouští bez argumentů.

### P5 — SITL, DDS a porty — **ověřeno 20. 9. 2026**

Launch dnes spouští jednu instanci s `-I0`, `--sim-port-out=9002`,
`--serial0=udpclient:127.0.0.1:14550` a `--defaults` na jeden parametrový
soubor. Pro tři je potřeba `-I0/-I1/-I2`, z toho plynoucí posun portů a
`MAV_SYSID` 1/2/3 s `DDS_USE_NS 1` (viz [04 §1](./04_rozhrani.md)).

`scripts/check_multi_instance_dds.sh` to zkouší bez Gazeba a bez letu, na
vnitřním modelu `quad`, a odpovídá na otázku, která tu byla otevřená:
**jeden agent na portu 20199 obslouží oba klienty.** Naměřeno: 18 témat pod
`/ap/v1/` a 18 pod `/ap/v2/`, žádné nenamespacované `/ap/time` vedle nich, obě
skutečně publikují, a zabití v2 nechá v1 běžet — v2 se vrátí jako v2 a žádná
třetí identita nevznikne.

Zbývá z P5 jen jedno a je to důsledek `--wipe`: každá instance potřebuje
**vlastní pracovní adresář**, protože `eeprom.bin` se zapisuje do aktuálního a
dva autopiloti nad jedním úložištěm nejsou dva autopiloti.

### P6 — hodiny

`sitl_gazebo.launch.py` má u `use_sim_time: false` dlouhý komentář: Gazebo zde
nepublikuje `/clock`, AP_DDS ho odebírá a nedostane, a `/ap/pose/filtered` nese
ArduPilotí UTC, zatímco senzory z mostu počítají od startu simulace — naměřeno
22,3 s proti 1789156172 ve stejném okamžiku. S jedním dronem to řeší obcházka.

S třemi to je horší: koordinátor porovnává stáří stavů tří agentů. Dokud běží
všichni na téže UTC, projde to; jakmile se do rozhodování zapojí čas ze senzorů
nebo z Gazeba, míchají se dvě časové osy. **Buď se `/clock` opraví, nebo se
napíše, že roj používá výhradně stampy z `pose/filtered`.** Nerozhodnout je
nejhorší varianta.

## 2. Co už parametrizované je

Dobrá zpráva, ať to není jen seznam překážek:

| Věc | Stav |
| --- | --- |
| témata všech demo uzlů | parametry, ne konstanty (`declare_parameter` v každém uzlu) |
| TF frames v `pose_tf_broadcaster` | parametry `frame_id`, `child_frame_id` |
| `--model` v můstku aktuátorů | argument |
| výběr draku | `OPENIPC_AIRFRAME`, adresář modelu i parametrový soubor |
| šablonování konfigurace mostu | už existuje, zatím jen pro `@world@` |
| kontrola konzistence modelu | `check_model_consistency.py` bere drak jako argument |

Změny jsou tedy převážně v launch souborech a v generování modelu, ne v uzlech.

## 3. Rozpočet CPU

Tři SITL instance, tři modely s 360bodovým lidarem na 10 Hz, tři kamery, tři
mappery na mřížce 20 × 20 m při 0,10 m a koordinátor. **Není změřeno, jestli se
to vejde do reálného času**, a Gazebo, které nestíhá, se nepozná jako chyba —
pozná se jako drony, které se chovají divně.

- [ ] Před M3 změřit RTF (real time factor) pro 1, 2 a 3 instance.
- [ ] Rozhodnout, co se vypne jako první. Kamera je nejdražší a mapování ji
      nepoužívá.
- [ ] Zapsat, na jakém stroji čísla platí.

## 4. Pořadí prací

Nejmenší krok, který něco odemkne, je nahoře:

1. P5 bez Gazeba — tři SITL instance a tři jmenné prostory v ROS (nic nelétá).
2. P1 + P2 + P3 — generovaný model a most na agenta; dva drony v jednom světě.
3. P4 — tři můstky aktuátorů; dva drony, které se dají ovládat.
4. P6 — rozhodnout hodiny dřív, než na nich začne stát koordinátor.
5. Rozpočet CPU s třemi instancemi.

## 5. Rozhodnutí

Odůvodnění a čísla jsou v [08](./08_rozhodnuti.md).

- **R13 — model se generuje.** Ověřeno ve zdrojáku: `fdm_port_in` se čte
  výhradně ze SDF (`external/ardupilot_gazebo/src/ArduPilotPlugin.cc:1272`),
  žádná proměnná prostředí neexistuje a `<include>` parametr pluginu nepřepíše.
  Generátor vyrobí `openipc_cinewhoop_v1..v3` do `build/` a přidá je do
  `GZ_SIM_RESOURCE_PATH`, stejnou mechanikou jako `OPENIPC_AIRFRAME`.
- **R14 — jedno Gazebo se třemi modely.** Je to jediné uspořádání, ve kterém
  existuje skutečná vzdálenost dvojice, a ta je kritérium K1.
- **R15 — startovní pozice** (0,5; −2,0), (0,5; 0,0) a (0,5; +2,0) ve výšce
  0,035 m. Svět se nemění. `x = 0,5` proto, že na ose `x = 0` by v3 startoval
  0,55 m od stěny ohrady, tedy uvnitř vlastního prahu zastavení 0,8 m.

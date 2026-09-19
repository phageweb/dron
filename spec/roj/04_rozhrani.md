# 04 – Rozhraní mezi vrstvami

Tenhle dokument je ta hranice. Když se něco pokazí, první otázka zní „která
strana kontraktu ho porušila" — a odpověď musí být tady, ne v kódu.

## 1. Identita agenta

Jeden agent = jedno `MAV_SYSID` ∈ {1, 2, 3}. Z něj se odvozuje **všechno**
ostatní: jmenný prostor ROS, název modelu v Gazebu, TF frames, porty i adresář
logu. Nikde se nesmí objevit druhý, nezávislý identifikátor.

ArduPilot to umí sám. Ověřeno ve zdrojáku v tomhle repozitáři, ne v dokumentaci:
`DDS_USE_NS` je parametr v `external/ardupilot/libraries/AP_DDS/AP_DDS_Client.cpp:245`
a při nenulové hodnotě se jméno skládá v `dds_format_name`
(`AP_DDS_Client.cpp:1498`) jako `rt/ap/v<sysid>/<topic>`, tedy ROS téma
`/ap/v1/pose/filtered`. Účastník DDS se přejmenuje na `ap_v1` (`:1521`).

## 2. Témata

Směr je z pohledu agenta.

| Téma | Typ | Směr | Kdo vlastní | Poznámka |
| --- | --- | --- | --- | --- |
| `/ap/v<i>/pose/filtered` | `PoseStamped` | ven | AP_DDS | jediný zdroj polohy pro roj |
| `/ap/v<i>/cmd_vel` | `TwistStamped` | dovnitř | AP_DDS | píše **jen arbiter agenta**, nikdy roj |
| `/v<i>/cmd_vel_nominal` | `TwistStamped` | uvnitř agenta | `simple_indoor_autonomy` | vstup arbitru |
| `/v<i>/explore/target` | `PointStamped` | dovnitř | koordinátor | kam mířit; téma už dnes existuje |
| `/v<i>/swarm/constraint` | omezení rychlosti nebo stop | dovnitř | koordinátor | vstup arbitru |
| `/v<i>/scan/front` | `LaserScan` | ven | most Gazebo→ROS | dnes `/openipc_cinewhoop/scan/front` |
| `/v<i>/range/down` | `Range` | ven | `range_adapter` | logické jméno, viz `gz_bridge.yaml` |
| `/v<i>/map` | `OccupancyGrid` | ven | `occupancy_mapper` agenta | vstup do složené mapy |
| `/swarm/map` | `OccupancyGrid` | — | koordinátor | výstup, viz [06](./06_slozena_mapa.md) |
| `/swarm/assignment` | vlastní | — | koordinátor | kdo má který cíl, pro log a ladění |
| `/swarm/safety` | vlastní | — | koordinátor | každý zásah filtru, pro metriku |

Co na seznamu **není** a nesmí přibýt: jakékoli téma, kterým by roj sahal na
motory, režimy letu nebo zisky.

### Kde přesně je šev

```text
koordinátor --> /v1/explore/target ------+
            --> /v1/swarm/constraint --+ |
                                       v v
   simple_indoor_autonomy --> /v1/cmd_vel_nominal --> arbiter --> /ap/v1/cmd_vel
```

Arbiter patří **agentovi**, ne roji: ořezává, nevymýšlí, a když omezení
nedorazí, ořezává konzervativně. Tím zůstávají G4 (nevletět do zdi) a G5
(odmítnout podlahu) tam, kde byly, i když koordinátor mlčí nebo se plete.

Cena tohoto řešení je zapsaná v [08 R19](./08_rozhodnuti.md) a je reálná: cíl
dnes neurčuje trajektorii, jen směr zatáčky u zdi, a jen při zapnutém
`enable_exploring` (`target_timeout_s` 3 s). Autorita koordinátoru je zatím
směr a brzda. Poziční reference v GUIDED je další krok, ne obcházka arbitru.

## 3. Frames

Jeden sdílený `map`, pod ním tři stroje:

```text
map
 +-- v1/base_link --> v1/front_lidar_link, ...
 +-- v2/base_link
 +-- v3/base_link
```

`pose_tf_broadcaster` už dnes má `frame_id` i `child_frame_id` jako parametry
(`pose_tf_broadcaster.py:38-40`), takže tři instance s prefixem jsou změna
konfigurace, ne kódu. URDF prefix je práce navíc a je v [05](./05_infrastruktura_simulace.md).

**Nevyřešený předpoklad:** že ten `map` je pro všechny tři týž. Každá SITL
instance má vlastní EKF a vlastní origin, zatímco v Gazebu má každý model svou
`<pose>` ve světě. Pokud se home pozice instance a spawn pozice modelu
neshodnou, agent si myslí, že je jinde, než je — a složená mapa bude mít stěny
dvakrát. Tohle je první věc, kterou má M2 změřit proti ground truth, ne
předpokládat.

## 4. Meze povelů

Koordinátor nesmí poslat povel mimo tyhle meze; agent ho stejně nesplní, ale
tady se to pozná.

| Veličina | Mez | Odkud |
| --- | --- | --- |
| vodorovná rychlost | ≤ 0,5 m/s | `forward_speed_mps` v `simple_indoor_autonomy` |
| svislá rychlost | zapsat před testem | dnes neurčeno |
| perioda povelu | 5–10 Hz | volba; musí být výrazně častěji než `GUID_TIMEOUT` |
| stáří stavu, které roj přijme | ≤ 200 ms | volba; nad ní agent přestane dostávat cíle |

Poslední dvě jsou volby, ne měření, a proto musí být v konfiguračním souboru.

## 5. Timeouty a epochy

| Mechanismus | Kde žije | Co dělá |
| --- | --- | --- |
| `GUID_TIMEOUT` | agent | ztichne-li `cmd_vel`, agent zastaví sám |
| stáří stavu | koordinátor | starý stav se nepoužije k plánování |
| epocha mise | oba | celé číslo v každé zprávě roje; agent nepokračuje ve staré epoše po návratu spojení |

Epocha je jediná obrana proti scénáři „koordinátor se restartoval a agenti
dojíždějí povely z minulého života". Bez ní se to pozná až podle mapy.

## 6. Jak se kontrakt testuje

Kontrakt, který se netestuje, není kontrakt:

- [ ] **Záměna identit.** Poslat každému agentovi cíl v jiném rohu a ověřit z
      ground truth, že tam letěl ten správný. To je K5 z [01](./01_zadani_mapovani.md).
- [ ] **Ztichnutí.** Zastavit koordinátor za letu a změřit, za jak dlouho a o
      kolik metrů dál se každý agent zastaví.
- [ ] **Zastaralý stav.** Uměle zpozdit stav jednoho agenta a ověřit, že mu roj
      přestane přidělovat cíle a rozšíří kolem něj odstup.
- [ ] **Stará epocha.** Restartovat koordinátor a ověřit, že se nikdo nerozjede
      po starém cíli.
- [ ] **Restart instance.** Restartovat jednu SITL instanci a ověřit, že se
      identita druhých dvou nezměnila.

## 7. Rozhodnutí

Odůvodnění je v [08](./08_rozhodnuti.md).

- **R10 — zprávy:** `/swarm/assignment` a `/swarm/safety` zatím jako
  `std_msgs/String` s JSONem, protože jsou to diagnostiky. Typovaný balíček
  vznikne, až je bude číst druhý konzument nebo regresní test. Cíl a omezení
  typované jsou.
- **R11 — QoS:** stavy a senzory `sensor_data`, povely a omezení reliable
  keep-last-1, mapy transient local. QoS témat AP_DDS se nemění. A platí, že
  QoS není watchdog — proto stáří stavu a `GUID_TIMEOUT`.
- **R12 — koordinátor neodebírá scany.** Plyne z R4.

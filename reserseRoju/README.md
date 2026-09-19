# Rešerše řízení rojů malých dronů

Stav rešerše: **19. 9. 2026**

Tato složka shrnuje tři související otázky:

1. proč může být malý kvadrokoptérový dron s přibližně 3" vrtulemi vhodný
   jako člen roje;
2. jak se řídí jeden takový dron od motorů až po sledování trajektorie;
3. jak se nad stabilizovanými jednotlivci staví řízení celé skupiny.

Rešerše je psaná pro tento repozitář: 3" cinewhoop, ArduPilot, ROS 2 Jazzy,
Gazebo Harmonic, optical flow, rangefinder a 2D lidar. Nejde tedy jen o přehled
literatury, ale i o návrh realistické cesty od současného jednoho modelu k
několika strojům v simulaci a později na stole a ve vzduchu.

## Nejdůležitější závěr

Roj se nemá stavět tak, že ROS 2 po síti přímo řídí motory všech dronů. Každý
dron si musí lokálně a rychle hlídat odhad stavu, úhlovou rychlost, orientaci,
výšku a základní failsafe. Rojová vrstva pracuje výše: přiděluje role a cíle,
plánuje trajektorie, hlídá vzájemné rozestupy a posílá jednotlivým autopilotům
omezené poziční nebo rychlostní reference.

Pro první funkční verzi tohoto projektu dává největší smysl **hierarchické
centralizované řízení**:

```text
mise / operátor
        |
        v
pozemní swarm coordinator (ROS 2)
  - společná mapa a světový rámec
  - formace / přidělení cílů
  - plánování a bezpečnostní filtr
        |
        +------------+------------+
        v            v            v
   /ap/v1/...    /ap/v2/...    /ap/v3/...
   ArduPilot     ArduPilot     ArduPilot
   lokální EKF   lokální EKF   lokální EKF
   a regulace    a regulace    a regulace
```

Je to snáze měřitelné a laditelné než plně decentralizovaný roj. Decentralizace
má přijít až poté, co jsou ověřeny dynamické limity jednotlivého dronu,
lokalizace, stáří zpráv, nouzové chování a dva až tři stroje bez kolizí.

## Co přesně znamená „roj“

Ne každá skupina současně letících dronů je roj:

| Uspořádání | Co dělá | Odolnost | Typický příklad |
| --- | --- | --- | --- |
| Předem nahrané trajektorie | Každý přehrává svůj časový plán | malá; chyba času nebo polohy se nevyjedná | světelná show |
| Centrální multi-agent systém | Jeden plánovač zná všechny stavy a dává cíle | závisí na lince a centrálním uzlu | laboratorní formace |
| Hierarchický systém | Mise je centrální, stabilizace a část bezpečnosti lokální | dobrý praktický kompromis | doporučení pro tento projekt |
| Decentralizovaný roj | Každý komunikuje jen se sousedy a rozhoduje lokálně | bez jediného bodu selhání, ale těžší ověřování | flocking, distribuovaný průzkum |

V technickém smyslu má roj lokální interakce, škáluje bez ručního programu pro
každého člena a při ztrátě jednoho člena se zbytek bezpečně přeskupí. Pouhé
rozeslání stejného povelu všem strojům tyto vlastnosti nedává.

## Obsah

- [01 – Proč malé 3" drony](./01_proc_3palcove_drony.md): fyzikální výhody,
  limity, energie, bezpečnost a proč 3" není automaticky optimum.
- [02 – Teorie řízení jednoho dronu](./02_teorie_rizeni_jednoho_dronu.md):
  model, směšování motorů, kaskádní regulace, odhad stavu, trajektorie a
  specifika malého cinewhoopu.
- [03 – Teorie a algoritmy řízení roje](./03_teorie_a_algoritmy_roje.md): grafy,
  konsenzus, formace, flocking, pokrytí, plánování, komunikace a bezpečnost.
- [04 – Návrh pro tento projekt](./04_navrh_pro_tento_projekt.md): konkrétní
  architektura ArduPilot + ROS 2, datové kontrakty, postup experimentů a
  přijímací kritéria.
- [05 – Zdroje](./05_zdroje.md): komentovaná bibliografie a oddělení toho, co
  je doložené, od doporučení autora rešerše.

## Doporučené pořadí čtení

Pro rychlé rozhodnutí stačí tento soubor a kapitoly „Verdikt“ a „Co to znamená
pro tento projekt“ v dokumentu 01. Pro implementaci pokračovat dokumentem 04.
Dokumenty 02 a 03 vysvětlují, proč je navržené rozdělení vrstev stabilní a kde
jsou jeho hranice.

## Rozsah a omezení

- „3 palce“ zde znamenají **průměr vrtule 76,2 mm**, ne rozvor ani průměr
  celého dronu. Skutečný vnější rozměr, hmotnost a nosnost závisejí na rámu,
  ducts, baterii a nákladu.
- Konkrétní projektový model má podle
  [implementační specifikace](../spec/10_implementation_spec.md) hmotnost
  0,306 kg a dosah špičky rotoru 0,08335 m od středu. Není tedy rozumné převzít
  výsledky pro 30–70g nanoquadrotory bez přeměření.
- Čísla jako maximální rychlost, brzdná dráha, doba letu a minimální odstup
  nejsou vlastností označení 3". Musí se identifikovat z konkrétního stroje.
- Rešerše řeší kooperativní civilní robotiku: formace, mapování, pokrytí a
  bezpečný průlet. Neřeší bojové použití ani potlačování cizích systémů.
- Právní poznámka je orientační, nikoli právní rada. Pro venkovní experiment je
  nutné před letem ověřit aktuální pravidla a zeměpisné zóny.

## Slovník použitých pojmů

| Pojem | Význam v těchto dokumentech |
| --- | --- |
| agent | jeden dron v multi-agent systému |
| soused | agent, jehož stav používá lokální řídicí zákon |
| common frame | společná souřadná soustava, ve které lze porovnat polohy |
| setpoint / reference | požadovaná poloha, rychlost, orientace nebo tah |
| consensus | sbližování vybrané veličiny mezi sousedy |
| formation control | držení předepsaných relativních poloh |
| flocking | soudržný, bezkolizní a rychlostně sladěný pohyb |
| safety filter | vrstva, která smí změnit nominální povel, aby neporušil omezení |
| CBF | control barrier function, matematická podmínka udržující bezpečnou množinu |
| MPC | model predictive control, optimalizace řízení v posuvném časovém horizontu |
| ORCA | reciproční vyhýbání kolizi ve stavovém prostoru rychlostí |
| SITL | autopilot jako proces v simulaci, software-in-the-loop |

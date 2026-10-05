# Vstup do kumbálu: oprava a ověření (2026-10-04)

## Výchozí měření

Audit `logs/swarm_batches/rand100/results.csv` a jednotlivých
`coordinator_log.json` potvrdil 30 platných běhů bez vstupu do kumbálu:

| Stav v záznamu koordinátoru | Běhy |
| --- | ---: |
| Cíl uvnitř byl přidělen | 21 |
| Kandidát uvnitř existoval, ale nebyl přidělen | 7 |
| Kandidát uvnitř nevznikl | 2 |

Při prvním auditu dávka obsahovala 98 platných výsledků; po doběhnutí
posledního případu 99 platných výsledků ze 100. Počet 30 neúspěšných vstupů
se nezměnil. Přítomnost kandidáta sama o sobě neprokazuje jeho dosažitelnost.
Varianty E a F už používaly `visible_carrot`; samotné zapnutí této funkce
tedy není oprava. Pro určení vstupu se používá poloha uvnitř geometrie
kumbálu, nikoliv procento podlahy viditelné lidarem zvenku.

## Změny

- `grid_helpers.py`: kontrola celého úseku ze skutečné polohy proti plným
  čtvercům buněk, stěnám, neznámu a okraji mapy. Neexistuje neověřený
  náhradní bod. Ústup z již překročené bezpečnostní rezervy nesmí zmenšit
  vzdálenost k žádné překážce, překročit rozměry těla ani skončit v rezervě.
  Pokud plánovaná cesta nevede bezpečně ven, hledá se samostatný blízký
  ústupový bod; jinak dron drží polohu.
- `allocation.py`: pozorovací cíle mohou ležet před hranicí neznámého prostoru.
  Zpětné hledání z hranice probíhá pouze po známé volné podlaze. Průletnost
  celé trasy zahrnuje šířku koridoru a neznámý prostor. Malé hranice se
  neposuzují pouze podle počtu buněk; stále musí nabídnout dostatečný
  očekávaný výhled. Rezervované dveře vstupují přímo do hledání cesty,
  takže lze najít obchvat.
- `exploration.py`: paměť prostorově odpovídajících cílů. Dosažitelné oblasti
  stárnou, po 30 s má nejstarší odkládaná oblast přednost. Pouhé přidělení
  stáří neresetuje. Po 15 s bez zkrácení zbývající trasy alespoň o 0,3 m
  dostane konkrétní dvojice dron/oblast přestávku 25 s; jiný dron může oblast
  převzít. Navštívený nezměněný výhled se po 2 s zpracování mapy přestane
  nabízet. Nově odhalené neznámé buňky ho mohou znovu otevřít.
- `passages.py`, `coordinator.py`, `assignment.py`: nové rezervace platí už
  pro publikaci tras ve stejném kroku. Čekací cíle se volí mimo přístup ke
  dveřím. Časovač neuvolní obsazený průchod ani průchod s neznámou polohou
  držitele. Cesta k čekacímu bodu respektuje cizí rezervace.
- `simple_indoor_autonomy.py`: koordinovaný režim při chybějícím, starém
  nebo dosaženém cíli drží polohu. Neopouští trasu reaktivním kroužením.
  Před koncem úseku zpomaluje; spouštěč vyžaduje přesnější natočení před
  dopředným letem.
- `check_swarm_mapping.sh`: stejná skutečná pološířka dronu a stejná rezerva
  pro koordinátor i lokální řízení. Výchozí režim používá ověřované úseky,
  řízení podle trasy a rezervace. `swarm_batch.py` přidává variantu G,
  výběr prvního simulačního slotu a otisky zdrojových souborů pro každý pokus.
  Písmena B–F nyní rozlišují nastavení řízení nad společným opraveným kódem;
  původní výsledky se porovnávají s archivovanou dávkou, nikoliv pouze podle
  shodného písmene.

Výpočet bezpečné mapy používá bitové řádky. Na uloženém snímku světa 2
celé přidělení cílů po této optimalizaci trvalo přibližně 35–39 ms.
Ekvivalenci se samostatnou kontrolou každé kruhové masky ověřuje test.

## Ověření

```sh
nix develop -c python3 -m pytest \
  ros_ws/src/openipc_cinewhoop_demo/test ros_ws/src/openipc_swarm/test -q
bash -n scripts/check_swarm_mapping.sh
git diff --check
```

Regrese zahrnují roh, překážku hned u začátku úseku, mezeru v neznámém
prostoru, bezpečný ústup, pozorování z odstupu, přidělení odkládané oblasti,
restart po uváznutí, opakovaný nezměněný výhled, současný zájem o dveře,
obchvat rezervace a skutečnou publikaci cíle z koordinátoru do rámce dronu.

První dvě vývojové verze (`enclosure_fix_seed2`, `enclosure_fix2_seed2`)
do kumbálu ve světě 2 nevstoupily. První odhalila příliš hrubou kontrolu
u začátku úseku, druhá potřebu samostatného ústupu. Nejde o výsledky konečné
verze. Souběžné pokusy `enclosure_fix3_seed2` a `enclosure_fix3_seed10`
byly narušeny nevzletem nebo přistáním při výpadku telemetrie baterie;
simulace běžela přibližně 0,3–0,5násobkem reálného času. Tyto pokusy
neprokazují účinnost opravy. Další lety probíhají jednotlivě.

## Kritéria přijetí

1. Vstup do kumbálu do 240 s od vzletu všech dronů, zvlášť pro každý svět.
2. Čas prvního přidělení dosažitelného cíle uvnitř a doba skutečného postupu.
3. Žádné zhoršení nejmenší vzdálenosti dronů a žádný průnik těla do stěn.
4. Měřit skutečně navštívenou podlahu i mapové pokrytí; tyto metriky se liší.
5. Odděleně evidovat nevzlet, výpadky telemetrie a rychlost simulace.
6. Po cílených světech 2, 10, 6 a 19 zopakovat všech 20 původních světů
   a více letů na každém. Jediný úspěšný let neprokazuje spolehlivost.

# Zdroje a jak s nimi bylo naloženo

Stav ověření: **19. 9. 2026**.

Pravidla, která jsem si pro tuhle rešerši nastavil:

- pro čísla o vrtulích mají přednost **měřicí práce**, ne katalogy prodejců;
- pro chování ArduPilotu má přednost **oficiální dokumentace** a checkout v
  `external/ardupilot`, ne fórum;
- pro čísla o tomhle stroji má přednost **repozitář**, protože jeho modely a
  parametry jsou odvozené a okomentované;
- kde jsem měl jen abstrakt nebo výsledek vyhledávání, je to napsané.

## A. Vrtule, aerodynamika a měřítko

### A1. Brandt, Selig — Propeller Performance Data at Low Reynolds Numbers

- Primární měřicí práce, AIAA 2011-1255.
- PDF: [m-selig.ae.illinois.edu](https://m-selig.ae.illinois.edu/pubs/BrandtSelig-2011-AIAA-2011-1255-LRN-Propellers.pdf)
- Podporuje: rozsah `Re` 50 000–100 000 jako pracovní oblast malých vrtulí,
  měřených 79 vrtulí, pokles účinnosti při nižším `Re`.
- Omezení přenosu: většina měřených vrtulí je 9–11", tedy **větší** než obě
  vrtule tohoto projektu. Použito jako důkaz trendu a jako důkaz toho, že pod
  `Re ≈ 25 000` systematická data prostě nejsou.

### A2. Deters, Ananda, Selig — Reynolds Number Effects on Small-Scale Propellers

- Primární měřicí práce, AIAA 2014-2151.
- PDF: [m-selig.ae.illinois.edu](https://m-selig.ae.illinois.edu/pubs/DetersAnandaSelig-2014-AIAA-2014-2151.pdf)
- Podporuje: účinnost o 7,5–15 % nižší u malých průměrů, zisk přes 10 % při
  zdvojnásobení `Re`.
- Omezení: měřeno na konkrétních vrtulích bez ductu.

### A3. UIUC Propeller Data Site

- Databáze měření: [m-selig.ae.illinois.edu/props/propDB.html](https://m-selig.ae.illinois.edu/props/propDB.html)
- Použito jako referenční bod pro to, co je a není publikované.

### A4. Rapid Design Process of Shrouded Rotors (University of Glasgow)

- PDF: [eprints.gla.ac.uk/227960](http://eprints.gla.ac.uk/227960/2/227960.pdf)
- Ověřeno čtením textu PDF: práce zkoumá plášť NACA 7312 na **5" Gemfan**
  vrtuli, tahovou stolicí i CFD, a mění **vůli špičky 0,6 %, 1,11 % a 3,6 %**.
- Podporuje: přínos ductu je funkce expanzního poměru a vůle špičky, ne
  přítomnosti krytu.
- Omezení: **záměrně z ní necituji procentní zisk.** Extrakce tabulek z PDF
  nebyla dost spolehlivá na to, aby se číslo dalo zapsat jako doložené, a
  cinewhoopový vstřikovaný duct navíc není navržený difuzor.

### A5. Mueller, Lee, D'Andrea — Design and Control of Drones

- Recenzovaný přehled, Annual Review of Control, Robotics, and Autonomous
  Systems, 2022.
- PDF: [HiPeRLab](https://hiperlab.berkeley.edu/wp-content/uploads/2021/09/2021_DesignAndControlOfDrones.pdf)
- Podporuje: kompromis účinnost–obratnost a závislost ideálního výkonu na tahu
  a ploše disku. Stejný zdroj používá i [rešerše roje](../reserseRoju/05_zdroje.md).

## B. ArduPilot: ladění, filtrace a pohon

Oficiální dokumentace, ověřená k datu nahoře. Autoritativní pro implementační
detail je ale checkout v `external/ardupilot` (`8b9ea7004582`, 9. 9. 2026).

### B1. Motor Thrust Scaling

- [ardupilot.org/copter/docs/motor-thrust-scaling.html](https://ardupilot.org/copter/docs/motor-thrust-scaling.html) — **staženo a přečteno**.
- Podporuje: `MOT_THST_EXPO` jako tvar tahové křivky, výchozí 0,65, měření na
  tahové stolici, a hodnoty spíš 0–0,2 u ESC s vlastní linearizací.
- Doplňkově [Thrust Expo WebTool](https://firmware.ardupilot.org/Tools/WebTools/ThrustExpo/).

### B2. Dynamický harmonický notch a ESC telemetrie

- [Managing Gyro Noise with the Dynamic Harmonic Notch Filters](https://ardupilot.org/copter/docs/common-imu-notch-filtering.html)
- [ESC Telemetry Based Harmonic Notch Setup](https://ardupilot.org/copter/docs/common-esc-telem-based-notch.html)
- [ESC Telemetry](https://ardupilot.org/copter/docs/common-esc-telemetry.html)
- Podporuje: `INS_HNTCH_MODE = 3` pro zdroj frekvence z ESC, RPM po signálové
  lince u AM32, BLHeli32 32.7+ a BLHeli_S 16.73+, aktualizace až 400 Hz při
  obousměrném DShotu proti ~100 Hz u sériové telemetrie.

### B3. Ladicí průvodce (MethodicConfigurator)

- [TUNING_GUIDE_ArduCopter](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter.html)
- Podporuje: výchozí zisky cílí na 9–12" vrtuli, menší vrtule potřebují nižší
  rate gainy, `INS_GYRO_FILTER` 80 Hz pro 5" a kotvy pro `FLTD`/`FLTT`.
- Tytéž kotvy jsou už zapsané ve
  [výzkumu rotorů](../workflow/research_rotor_simulation.md), který je zdejším
  primárním záznamem.

### B4. Řízení a režimy

- [Copter Attitude Control](https://ardupilot.org/dev/docs/apmcopter-programming-attitude-control-2.html)
- [Copter Position Control and Navigation](https://ardupilot.org/dev/docs/code-overview-copter-poscontrol-and-navigation.html)
- [Guided Mode](https://ardupilot.org/copter/docs/ac2_guidedmode.html) — `GUID_TIMEOUT`
- [Optical Flow Sensor Setup](https://ardupilot.org/copter/docs/common-optical-flow-sensor-setup.html)

## C. Algoritmy řízení jednoho stroje

### C1. Smeur, Chu, de Croon — Cascaded INDI for MAV Disturbance Rejection

- Preprint: [arXiv:1701.07254](https://arxiv.org/abs/1701.07254)
- Podporuje: INDI nahrazuje modelové členy měřením, robustnost vůči neznámé
  dynamice a poruchám.
- Omezení: **nalezeno přes rešerši, čten abstrakt a popis, ne celý text.**
  Metoda navíc stojí na kvalitě úhlového zrychlení, což je na tomhle rámu
  nejzašuměnější veličina.

### C2. Learned INDI for Quadrotors with and without Slung Payloads

- Preprint: [arXiv:2503.09441](https://arxiv.org/abs/2503.09441)
- Podporuje: současný směr vývoje INDI směrem k měnícímu se nákladu.
- Omezení: čten abstrakt.

### C3. Kaufmann et al. — Champion-level drone racing using deep RL (Swift)

- Nature 620, 982–987 (2023). DOI: [10.1038/s41586-023-06419-4](https://doi.org/10.1038/s41586-023-06419-4)
- Podporuje: naučená politika na úrovni lidských mistrů, kombinace simulace a
  reálných dat.
- Omezení: známá trať, vlastní vizuální lokalizace, závodní úloha. Není to
  důkaz, že se naučená politika hodí na indoor mapování.

### C4. Eschmann et al. — Learning to Fly in Seconds

- Preprint: [arXiv:2311.13081](https://arxiv.org/abs/2311.13081)
- Podporuje: end-to-end politika až na otáčky motorů, 18 s tréninku, nasazení
  na mikrokontrolér.
- Omezení: čten abstrakt a popis; platí pro jejich platformu a jejich model.

### C5. What Matters in Learning A Zero-Shot Sim-to-Real RL Policy

- Preprint: [arXiv:2412.11764](https://arxiv.org/abs/2412.11764)
- Podporuje: seznam faktorů rozhodujících o přenosu (vstupy politiky,
  regularizace hladkosti akcí, systémová identifikace, selektivní randomizace).
- Použito hlavně jako argument, že **randomizace potřebuje naměřený rozsah**.

### C6. Sdíleno s rešerší roje

Geometrické řízení na SE(3) (Lee, Leok, McClamroch) a minimum-snap trajektorie
(Mellinger, Kumar) jsou plně odkázané v
[reserseRoju/05](../reserseRoju/05_zdroje.md);
tady se na ně jen navazuje a nejsou duplikovány.

## D. Bezpečnost a provoz

- Svatý a kol., *Evaluation of the drone-human collision consequences*,
  Heliyon 8(11), 2022. DOI: [10.1016/j.heliyon.2022.e11677](https://doi.org/10.1016/j.heliyon.2022.e11677).
  Podporuje: hmotnost ani jednoduchý energetický práh nevystihují mechanismus
  poranění.
- Provozní pravidla EASA jsou zpracovaná v
  [reserseRoju/05 §E2](../reserseRoju/05_zdroje.md) a nejsou tu opakována.
  Tahle rešerše k nim nepřidává nic než poznámku, že 250 g je v tomhle projektu
  **informace, ne limit** (rozhodnutí z 10. 9. 2026).

## E. Zdroje uvnitř repozitáře

Odsud pocházejí **všechna konkrétní čísla** o obou dracích. Nejsou to externí
důkazy, jsou to autority projektu:

| Zdroj | Co z něj je |
| --- | --- |
| [`config/ardupilot_params.parm`](../ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params.parm) | CineLog: 0,306 kg, autorita 689 rad/s², mez 0,065–0,080, `MOT_THST_HOVER` 0,46 |
| [`config/ardupilot_params_pavo20.parm`](../ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params_pavo20.parm) | Pavo20: 0,22934 kg, 583 rad/s², naměřený sweep, `MOT_THST_HOVER` 0,53 |
| `models*/openipc_cinewhoop/model.sdf` | `Ct` 0,2103, `motorConstant`, `maxRotVelocity`, setrvačnosti, časové konstanty motoru |
| [`spec/10_implementation_spec.md`](../spec/10_implementation_spec.md) | geometrie, konvence, rozhodovací pravidla nodů |
| [`spec/realna_stavba_dronu/10_pavo20.md`](../spec/realna_stavba_dronu/10_pavo20.md) | hmotnostní rozpočet, disk 182/98 cm², metoda výpočtu výdrže |
| [`spec/realna_stavba_dronu/12_reserse_motoru.md`](../spec/realna_stavba_dronu/12_reserse_motoru.md) | motory, tah 230 g u LAVA + D2.2-3, elektrické limity |
| [`spec/realna_stavba_dronu/09_kudy_do_ros.md`](../spec/realna_stavba_dronu/09_kudy_do_ros.md) | AP_DDS nemá scan, `AP_Proximity` 8 sektorů, rozpočet linky |
| [`workflow/research_rotor_simulation.md`](../workflow/research_rotor_simulation.md) | kotvy ladění, `INS_GYRO_FILTER`, `MOT_THST_EXPO` 0,55 pro 5" |
| [`workflow/decisions.md`](../workflow/decisions.md), [`backlog.md`](../workflow/backlog.md), [`troubleshooting.md`](../workflow/troubleshooting.md) | historie rozhodnutí, otevřené položky, saturace mixéru a odlet do 54 m |
| `scripts/sweep_rate_gains.sh`, `scripts/rate_step_response.py` | metodika měření, kterou tahle rešerše doporučuje převzít i jinam |

## F. Co je doložené a co je můj závěr

| Tvrzení | Status |
| --- | --- |
| ideální indukovaný výkon roste jako `1/D` při konstantním tahu | doloženo teorií hybnosti (A5) |
| malé vrtule pracují pod rozsahem publikovaných měření | doloženo A1, A2 + výpočet z modelu |
| přínos ductu závisí na vůli špičky a expanzním poměru | doloženo A4 |
| duct na tomhle stroji přidává nebo ubírá účinnost | **neznámé**; nikdo neměřil |
| Pavo20 má nižší úhlovou autoritu než CineLog | vypočteno z modelu obou draků |
| mez ladění je na obou dracích 0,065–0,080 | **naměřeno** v simulaci |
| ta mez platí i na železe | **neplatí zaručeně**; simulace nemá šum ani rezonanci |
| `MOT_THST_EXPO 1.0` je artefakt simulace | odvozeno z modelu rotoru + B1 |
| propad napětí mění zisk smyčky o ~35 % | výpočet z `(14,0/17,4)²`, nezměřeno |
| INDI je pro tuhle třídu relevantní alternativa | doporučení této rešerše, opřené o C1 |
| naučená politika nenahradí chybějící měření | závěr této rešerše, opřený o C5 |
| rotační energie vrtule převyšuje translační při indoor rychlostech | **řádový odhad** ze setrvačností modelu, které nejsou pro Pavo20 přepočítané |
| Reynoldsova čísla 25 000 a 28 000 | výpočet s **odhadnutou tětivou** listu; řád jistý, druhá číslice ne |

# Zdroje a způsob práce s nimi

Stav kontroly odkazů: **19. 9. 2026**.

Zdroje jsou seřazeny podle tématu a typu. Pro fyziku a algoritmy mají přednost
primární recenzované práce; přehledové články slouží k mapování oboru. Pro
konkrétní chování ArduPilotu a ROS 2 mají přednost oficiální dokumentace a
zdrojový kód verze přítomné v repozitáři. Produktové blogy a diskusní fóra
nejsou použity jako podklad pro výkonové závěry.

## A. Fyzika, konstrukce a řízení jednoho dronu

### A1. Kushleyev, Mellinger, Kumar – Towards a Swarm of Agile Micro Quadrotors

- Primární konferenční práce, Robotics: Science and Systems, 2012.
- PDF: [roboticsproceedings.org](https://www.roboticsproceedings.org/rss08/p28.pdf)
- Podporuje: škálování hmotnosti a momentu setrvačnosti, vyšší úhlovou
  obratnost menších kvadrokoptér, těsné formace a experiment s 20 stroji.
- Omezení přenosu: zkoumaný stroj měl přibližně 73 g a 8cm vrtule. Projektový
  cinewhoop má přibližně 306 g, ducts a senzorový náklad; čísla nelze přímo
  převzít, pouze fyzikální trend.

### A2. Mueller, Lee, D’Andrea – Design and Control of Drones

- Recenzovaný přehled v Annual Review of Control, Robotics, and Autonomous
  Systems, 2022 (preprint zveřejněn 2021).
- PDF: [HiPeRLab, UC Berkeley](https://hiperlab.berkeley.edu/wp-content/uploads/2021/09/2021_DesignAndControlOfDrones.pdf)
- Podporuje: kompromis účinnost–obratnost, závislost ideálního výkonu na tahu a
  průměru vrtule, vliv hmoty daleko od těžiště, vrstevnatou architekturu
  estimator–planner–controller a přehled robustního řízení.
- Omezení: obecný přehled neposkytuje výkon konkrétní kombinace motoru, 3"
  vrtule a ductu.

### A3. Lee, Leok, McClamroch – Control of Complex Maneuvers … on SE(3)

- Primární práce, CDC 2010.
- Preprint: [arXiv:1003.2005](https://arxiv.org/abs/1003.2005)
- Podporuje: nelineární model na `SE(3)`, geometrickou chybu orientace,
  regulaci attitude/position/velocity a téměř globální vlastnosti.
- Omezení: matematický model a numerické příklady nejsou hotový regulator pro
  současný ArduPilot frame.

### A4. Mellinger, Kumar – Minimum Snap Trajectory Generation and Control

- Primární práce, IEEE ICRA 2011.
- DOI: [10.1109/ICRA.2011.5980409](https://doi.org/10.1109/ICRA.2011.5980409)
- Podporuje: diferenciální plochost kvadrokoptéry v používaném režimu a hladké
  polynomické trajektorie minimalizující snap.
- Omezení: neřeší samo o sobě ztrátu komunikace ani multi-agent konflikt.

### A5. Mettler, Dever, Feron – Scaling Effects and Dynamic Characteristics

- Primární časopisecká práce, Journal of Guidance, Control, and Dynamics 27(3),
  2004.
- DOI: [10.2514/1.10336](https://doi.org/10.2514/1.10336)
- Podporuje: obecné škálovací trendy dynamiky miniaturních rotorcraft.
- Omezení: práce vychází i z klasických vrtulníků většího měřítka; pro moderní
  elektrický 3" quad slouží jako teoretické pozadí.

### A6. ArduPilot – lokální řízení a odhad stavu

- Oficiální dokumentace:
  - [Copter Attitude Control](https://ardupilot.org/dev/docs/apmcopter-programming-attitude-control-2.html)
  - [Copter Position Control and Navigation](https://ardupilot.org/dev/docs/code-overview-copter-poscontrol-and-navigation.html)
  - [EKF Navigation Overview](https://ardupilot.org/dev/docs/extended-kalman-filter.html)
  - [Optical Flow Sensor Setup](https://ardupilot.org/copter/docs/common-optical-flow-sensor-setup.html)
- Podporuje: skutečné vrstvy ArduCopteru, PID/FF attitude a rate smyčky,
  kaskádu pozičního řízení a integraci optical flow/rangefinderu.
- Verze dokumentace se může měnit; pro implementační detail je autoritativní
  checkout v `external/ardupilot` a následný SITL test.

## B. Základy multi-agent a rojového řízení

### B1. Reynolds – Flocks, Herds, and Schools

- Původní práce, SIGGRAPH 1987.
- Autorská stránka: [red3d.com](https://www.red3d.com/cwr/papers/1987/boids.html)
- Podporuje: lokální pravidla cohesion, separation a velocity matching.
- Omezení: jde o distribuovaný behaviorální model počítačové animace, ne o
  bezpečnostní regulátor kvadrokoptéry s dynamickými limity.

### B2. Olfati-Saber – Flocking for Multi-Agent Dynamic Systems

- Primární práce, IEEE Transactions on Automatic Control 51(3), 2006.
- PDF: [flocking_tac06-engineering.pdf](https://hal.elte.hu/~vicsek/downloads/papers/flocking_tac06-engineering.pdf)
- DOI: [10.1109/TAC.2005.864190](https://doi.org/10.1109/TAC.2005.864190)
- Podporuje: grafový a potenciálový formalismus flockingu, role sousedství,
  koheze, sladění a překážek, analýzu fragmentace.
- Omezení: podmínky důkazu se musí znovu ověřit při saturaci, zpoždění a
  konkrétní letové dynamice.

### B3. Cortés, Martínez, Karatas, Bullo – Coverage Control

- Primární práce, IEEE Transactions on Robotics and Automation 20(2), 2004.
- Preprint: [arXiv:math/0212212](https://arxiv.org/abs/math/0212212)
- DOI: [10.1109/TRA.2004.824698](https://doi.org/10.1109/TRA.2004.824698)
- Podporuje: decentralizované gradientní řízení pokrytí, Voroného rozklad a
  centroidální konfigurace.
- Omezení: základní formulace neobsahuje kompletní 3D dynamiku, překážky,
  baterie ani multi-robot SLAM.

### B4. Vásárhelyi et al. – Optimized Flocking … Confined Environments

- Primární experimentální práce, Science Robotics 3(20), 2018.
- DOI: [10.1126/scirobotics.aat3536](https://doi.org/10.1126/scirobotics.aat3536)
- Data: [Dryad dataset](https://doi.org/10.5061/dryad.mq85r61)
- Podporuje: nutnost modelovat pohybová omezení, zpoždění, komunikaci,
  perturbace a překážky; hardwarovou validaci hejna 30 kvadrokoptér.
- Omezení: jejich platforma, lokalizace a rádiová infrastruktura se liší od
  OpenIPC cinewhoopu.

### B5. Zhou et al. – UAV Swarm Intelligence: Recent Advances

- Recenzovaný přehled, IEEE Access 8, 2020.
- DOI: [10.1109/ACCESS.2020.3028865](https://doi.org/10.1109/ACCESS.2020.3028865)
- Podporuje: vrstvení problému na rozhodování, plánování, control a komunikaci
  a poskytuje širší bibliografickou mapu.
- Omezení: přehled sám není validační důkaz konkrétního algoritmu.

## C. Kolizní bezpečnost a multi-agent plánování

### C1. van den Berg et al. – ORCA / Reciprocal n-body Collision Avoidance

- Primární práce a autorský software, ISRR 2011.
- Stránka projektu: [Optimal Reciprocal Collision Avoidance](https://gamma-web.iacs.umd.edu/ORCA/)
- PDF: [ORCA.pdf](https://gamma.cs.unc.edu/ORCA/publications/ORCA.pdf)
- Podporuje: velocity obstacles, rozdělení odpovědnosti mezi agenty a rychlé
  lineární programování.
- Omezení: základní ORCA nepokrývá automaticky plnou dynamiku a motorové limity
  kvadrokoptéry ani nekooperujícího souseda.

### C2. Tordesillas, How – MADER

- Primární práce, IEEE Transactions on Robotics 38(1), 2022.
- Preprint: [arXiv:2010.11061](https://arxiv.org/abs/2010.11061)
- Kód: [mit-acl/mader](https://github.com/mit-acl/mader)
- Podporuje: decentralizované asynchronní plánování 3D trajektorií, sdílení
  committed trajektorií a check–recheck bezpečnost.
- Omezení: závislosti a palubní výpočet neodpovídají současnému projektu bez
  companion computeru.

### C3. Kondo et al. – Robust MADER

- Primární práce, 2022/2023.
- Preprint: [arXiv:2209.13667](https://arxiv.org/abs/2209.13667)
- Podporuje: explicitní práci s komunikačním zpožděním, dvoufázovou publikaci
  trajektorie a delay check.
- Omezení: deklarovaná záruka platí při splnění modelových a komunikačních
  předpokladů dané práce.

### C4. Zhou et al. – EGO-Swarm

- Primární práce, IEEE ICRA 2021.
- Preprint: [arXiv:2011.04183](https://arxiv.org/abs/2011.04183)
- Kód: [EnderMandS/ego-swarm](https://github.com/EnderMandS/ego-swarm)
- Podporuje: plně decentralizované asynchronní plánování v neznámém členitém
  prostředí, palubní zdroje a nespolehlivé sdílení trajektorií.
- Omezení: není to plugin do ArduPilot AP_DDS; předpokládá vlastní onboard
  vnímání a výpočet.

### C5. Gonçalves et al. – Safe Multi-Agent Drone Control Using CBF

- Primární práce, Robotics and Autonomous Systems 172, 2024.
- DOI: [10.1016/j.robot.2023.104601](https://doi.org/10.1016/j.robot.2023.104601)
- Podporuje: lehký dvouvrstvý regulátor, control barrier functions, QP a
  experimentální multi-drone validaci.
- Omezení: CBF záruky jsou vázány na model, aktuálnost stavu a dostupné vstupy.

### C6. Adajania et al. – AMSwarm

- Primární práce, 2023.
- Preprint: [arXiv:2303.04856](https://arxiv.org/abs/2303.04856)
- Podporuje: škálovatelné online trajektorie a experimenty až s 12 Crazyflie;
  vhodná reference pro srovnání optimalizačních metod.
- Omezení: výsledky výkonu jsou pro jejich model, scénáře a hardware.

### C7. Balázs et al. – Decentralized Traffic Management of Autonomous Drones

- Primární open-access práce, Swarm Intelligence 19, 2025; online 2024.
- DOI: [10.1007/s11721-024-00241-y](https://doi.org/10.1007/s11721-024-00241-y)
- Podporuje: lokální vysílání polohy, rychlosti a cíle, kombinaci prediktivního
  plánování se sense-and-avoid, simulace do 5000 agentů a polní demonstraci 100
  autonomních kvadrokoptér.
- Omezení: řeší hlavně 2D provoz a vrstvený 3D prostor venku. Autoři výslovně
  upozorňují, že při stochastickém šumu nelze deklarovat nulové riziko.

## D. Výzkumné platformy a middleware

### D1. Preiss et al. – Crazyswarm

- Primární systémová práce, IEEE ICRA 2017.
- DOI: [10.1109/ICRA.2017.7989376](https://doi.org/10.1109/ICRA.2017.7989376)
- Podporuje: praktickou architekturu velkého roje nanoquadrotorů a oddělení
  lokální stabilizace od vyšší orchestrace.

### D2. Crazyswarm2

- Aktivní open-source ROS 2 testbed.
- Dokumentace: [imrclab.github.io/crazyswarm2](https://imrclab.github.io/crazyswarm2/)
- Kód: [IMRCLab/crazyswarm2](https://github.com/IMRCLab/crazyswarm2)
- Podporuje: ROS 2 namespacing, simulaci a skupinové API jako architektonickou
  inspiraci.
- Omezení: používá Crazyflie ekosystém, ne ArduPilot/OpenIPC.

### D3. ROS 2 – QoS a discovery

- Oficiální dokumentace:
  - [Quality of Service settings](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html)
  - [Improved Dynamic Discovery](https://docs.ros.org/en/rolling/Tutorials/Advanced/Improved-Dynamic-Discovery.html)
  - [Fast DDS Discovery Server](https://docs.ros.org/en/rolling/Tutorials/Advanced/Discovery-Server/Discovery-Server.html)
- Podporuje: reliability, history, deadline, lifespan a liveliness a upozorňuje
  na režii distribuovaného discovery a multicast na Wi-Fi.
- Poznámka: odkazy pokrývají více ROS distribucí; implementace projektu je
  Jazzy a musí se testovat proti skutečně zvolenému RMW.

### D4. ArduPilot – více vozidel, AP_DDS a failsafe

- Oficiální dokumentace:
  - [Using SITL – Swarming](https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html)
  - [Guided Mode](https://ardupilot.org/copter/docs/ac2_guidedmode.html)
  - [GCS Failsafe](https://ardupilot.org/copter/docs/gcs-failsafe.html)
  - [Object Avoidance with BendyRuler](https://ardupilot.org/copter/docs/common-oa-bendyruler.html)
  - [Using SITL with Gazebo](https://ardupilot.org/dev/docs/sitl-with-gazebo.html)
- Zdrojový kód v tomto repozitáři:
  - [`AP_DDS/README.md`](../external/ardupilot/libraries/AP_DDS/README.md)
  - [`AP_DDS_ExternalControl.cpp`](../external/ardupilot/libraries/AP_DDS/AP_DDS_ExternalControl.cpp)
  - [`AP_DDS_Client.cpp`](../external/ardupilot/libraries/AP_DDS/AP_DDS_Client.cpp)
- Podporuje: více SITL instancí, unikátní SysID, AP_DDS namespacing, frame
  konverzi `cmd_vel`, Guided timeout a možnosti failsafe.
- Lokálně ověřený commit: `8b9ea7004582`, datum 9. 9. 2026. Při aktualizaci
  submodulu se mají znovu zkontrolovat topic names a timeout semantics.

## E. Bezpečnost nárazu a pravidla provozu

### E1. Svatý, Nouzovský, Mičunek a Frydrýn – Evaluation of Drone-Human Collision Consequences

- Primární open-access experimentální práce, Heliyon 8(11), 2022.
- Článek: [PubMed Central](https://pmc.ncbi.nlm.nih.gov/articles/PMC9708620/)
- DOI: [10.1016/j.heliyon.2022.e11677](https://doi.org/10.1016/j.heliyon.2022.e11677)
- Podporuje: omezení samotné hmotnosti nebo kinetické energie jako univerzální
  míry poranění a potřebu hodnotit konstrukci a mechanismus nárazu.

### E2. EASA – otevřená kategorie UAS

- Aktuální oficiální přehled:
  [Open Category – Low Risk](https://www.easa.europa.eu/en/domains/drones-air-mobility/operating-drone/open-category-low-risk-civil-drones)
- Oficiální FAQ:
  [Open category](https://www.easa.europa.eu/en/the-agency/faqs/open-category),
  [FPV a VLOS](https://www.easa.europa.eu/en/faq/140037)
- Konsolidovaná pravidla, revize červen 2026:
  [Easy Access Rules for UAS](https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-unmanned-aircraft-systems)
- Podporuje: podmínky kategorií A1/A2/A3, hranici 250 g, VLOS a skutečnost, že
  pod 250 g neznamená bezpodmínečný autonomní provoz.
- Omezení: provozovatel musí před letem ověřit české zóny, registraci, pojištění
  a konkrétní provozní scénář. Tato rešerše není právní stanovisko.

## F. Projektové zdroje pro konkrétní čísla

Následující dokumenty nejsou externí vědecké důkazy. Jsou autoritou pro to, co
projekt skutečně modeluje a zamýšlí:

- [Specifikace projektu](../spec/README.md)
- [Implementační specifikace](../spec/10_implementation_spec.md)
- [ROS 2 rozhraní](../spec/04_ros_rozhrani.md)
- [Reálná stavba dronu](../spec/realna_stavba_dronu/README.md)
- [Kudy se sken dostane do ROS 2](../spec/realna_stavba_dronu/09_kudy_do_ros.md)
- [Pavo20 jako alternativní nosič](../spec/realna_stavba_dronu/10_pavo20.md)

Z nich pocházejí hodnoty 3" vrtule, rozvoru, rotorové obálky, hmotnosti 0,306
kg, senzorů a omezení současné datové cesty. Pokud se rozchází starší návrhový
dokument s `spec/10_implementation_spec.md`, podle projektového README platí
implementační specifikace.

## G. Co je doložený výsledek a co doporučení této rešerše

| Tvrzení | Status |
| --- | --- |
| menší kvadrokoptéry mají při škálování vyšší úhlovou obratnost | doloženo A1/A2 |
| větší vrtule mají při stejném tahu výhodu v ideální účinnosti | doloženo A2, teorie hybnosti |
| reálný flocking musí řešit zpoždění a pohybové limity | doloženo B4 |
| AP_DDS umí namespace `v<MAV_SYSID>` | ověřeno D4 a lokálním zdrojovým kódem |
| první verze má být centralizovaná/hierarchická | doporučení pro dostupný hardware |
| první algoritmus má být virtual structure + safety filter | doporučení, které se musí experimentálně porovnat |
| konkrétní `d_safe` | zatím neznámé; musí vzniknout měřením |
| současný 0,306kg dron je vhodný pro fyzický roj | zatím neprokázané |
| plný LD06 sken zaručí lokální avoidance při ztrátě linky | neplatí v současné navržené datové cestě |

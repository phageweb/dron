# Reference MicoAir743v2-AIO-45A

Ověřeno a staženo 21. 10. 2026 z [e-shopu výrobce](https://store.micoair.com/product/micoair743v2-aio-45a/).
Fotografie slouží jako referenční podklad výrobce, nejsou naším návrhem ani zdrojem PCB.

- [H743V2-AIO.webp](./H743V2-AIO.webp): horní a spodní strana.
  [Originál](https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO.webp).
- [WiringDiagram.webp](./WiringDiagram.webp): vnější konektory a periferie.
  [Originál](https://store.micoair.com/wp-content/uploads/2025/03/WiringDiagram.webp).
- [Specifikace a pinout](https://micoair.com/flightcontroller_micoair743v2_aio_45a/).
  Její odkazy na fotografie na doméně `micoair.com` při kontrole vracely 404;
  výše uvedené obrázky na `store.micoair.com` fungují.

## Orientace pro porovnání

Na levé fotografii (horní strana) jsou bateriové pady dole. USB je vlevo dole,
microSD nad procesorem, GPS nahoře a DJI VTX vpravo nahoře. Na pravé fotografii
(spodní strana) je konektor UART1/UART6 nahoře a UART4 vpravo dole.
Spodek je samostatný pohled na otočenou desku: jeho souřadnice nelze přímo
přenést do horního pohledu KiCadu. Před porovnáním je nutné sjednotit projekci
podle montážních otvorů a motorových/bateriových padů.

Vlastní deska zatím používá obvod a rozmístění výkonové části OpenAIO, USB
a microSD jsou proto vůči této referenci jinde. Profil `micoair-v2` upravuje
přiřazení pinů, nikoliv automaticky geometrii celé desky. Další přeskládání má
vycházet z této fotografie správné revize a z úniků BGA; přesné souřadnice
součástek ani skryté vrstvy nejsou fotografií doložené.

Oproti referenci nadále máme ICM-42688-P místo BMI088, vlastní napájení VTX
10 V a jiné měření napětí/proudu. MicoAir firmware proto nelze bez úprav použít.

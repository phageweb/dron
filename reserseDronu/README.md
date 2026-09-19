# Rešerše jednoho dronu: velikost, řízení, systémy

Stav rešerše: **19. 9. 2026**. Psáno proti stavu větve `feat/pavo20-airframe`
a proti simulačním modelům, které v ní skutečně létají.

Tahle složka odpovídá na tři otázky o **jednom stroji**, ne o roji:

1. co vlastně kupuje a co stojí průměr vrtule kolem tří palců;
2. jaké algoritmy řídí takový stroj a který z nich má smysl tady;
3. z jakých systémů se dron skládá a který z nich je dnes úzké hrdlo.

Čtvrtý dokument ji porovnává s [rešerší roje](../reserseRoju/README.md), která
v repozitáři už je. Obě vznikly ve stejný den a překrývají se v kapitole o
jednom dronu; porovnání říká, kde se shodují, kde se rozcházejí a co je v každé
z nich navíc.

## Nejdůležitější závěr

**„Tři palce" už není rozhodnutí, které tenhle projekt dělá.** Repozitář má
dva zkalibrované draky, létá s oběma proti stejným checkům a liší se v průměru
vrtule skoro o třetinu:

| | CineLog30 V3 | Pavo20 Pro 4S |
| --- | ---: | ---: |
| vrtule | 3" (76,2 mm) | 2,2" (55,9 mm) |
| simulovaná hmotnost | 0,306 kg | 0,229 kg |
| plocha disku | 182,4 cm² | 98,1 cm² |
| plošné zatížení | 165 N/m² | 229 N/m² |
| tah/hmotnost | 4,65 | 3,52 |
| úhlová autorita v rollu | 689 rad/s² | 583 rad/s² |
| naměřená mez rate gainu | 0,065–0,080 | 0,065–0,080 |

Otázka „je 3" dobrá volba" se tedy dá nahradit ostřejší otázkou, na kterou má
projekt vlastní data: **co se stane, když se při stejném nákladu zmenší vrtule.**
Odpověď z ideální teorie hybnosti při **stejné hmotnosti** je nepříjemná:

```text
ideální indukovaný výkon ve visu ~ 1/D    (při konstantním tahu)
```

Pro 0,306 kg vychází 33,5 W na 2,2", 24,6 W na 3", 18,4 W na 4" a 14,8 W na 5".
Zmenšení z 3" na 2,2" tedy stojí **+36 % indukovaného výkonu**, a úspora 77 g,
kterou Pavo20 přináší, z toho vrátí jen část: 21,8 W proti 24,6 W, tedy **12 %**.

Z toho plynou tři věty, které platí pro celý projekt:

1. **Průměr vrtule neurčuje výdrž.** Určuje ji energie baterie a fixní odběr
   (video až 15 W). Vrtule mění účinnost, se kterou se energie utrácí, a mění ji
   méně, než se od čísla „3 palce" čeká.
2. **Průměr vrtule neurčuje obratnost.** Tu určuje moment setrvačnosti a součin
   tahu s ramenem. V tomhle repozitáři to je doložené: přidání LD06 na stožár
   zhruba **zdvojnásobilo** setrvačnost v pitchi a zneplatnilo naladění, zatímco
   změna draku z 3" na 2,2" posunula autoritu jen o 15 % a **na naměřené mezi
   ladění se to neprojevilo**.
3. **Průměr vrtule určuje, co se kam vejde, jak vysoko je plošné zatížení a jak
   hluboko je vrtule pod použitelným Reynoldsovým číslem.** To jsou skutečné
   důsledky, a ani jeden z nich není v katalogu.

Co je naopak dnes nedoladěné a rozhoduje o tom, jestli stroj poletí dobře, není
velikost draku, ale **rozpočet fáze a linearizace tahu**: `MOT_THST_EXPO 1.0` je
identita simulovaného rotoru, ne vlastnost skutečné vrtule, a v parametrech není
nastavený ani jeden filtr. Detaily v [02](./02_algoritmy_rizeni.md).

## Obsah

- [01 – Velikost, vrtule a co za to](./01_velikost_a_vrtule.md): škálování,
  teorie hybnosti proti vlastním číslům projektu, Reynolds, ducty, energie,
  brzdná dráha, bezpečnost a kdy 3" prohrává.
- [02 – Algoritmy řízení](./02_algoritmy_rizeni.md): kaskáda, alokace a její
  saturace, naměřená mez rate loopu, rozpočet fáze, linearizace tahu, propad
  napětí, odhad stavu a alternativy včetně INDI a naučených politik.
- [03 – Systémy](./03_systemy.md): dekompozice stroje, volba firmwaru, ESC a
  RPM telemetrie, senzory, tři rádia na jedné palubě, a která tabulka parametrů
  je artefakt simulace.
- [04 – Porovnání s rešerší roje](./04_porovnani_s_reserseRoju.md): shody,
  rozpory, co má každá navíc a co s tím dál.
- [05 – Zdroje](./05_zdroje.md): co je doložené, čím, a kde končí přenositelnost.

## Rozsah a co tahle rešerše není

- Neřeší roj. To dělá [reserseRoju](../reserseRoju/README.md) a dělá to dobře;
  tahle složka je vrstva pod ním.
- Nenahrazuje [implementační specifikaci](../spec/10_implementation_spec.md).
  Kde se čísla rozcházejí, platí ona a
  [kusovník Pavo20](../spec/realna_stavba_dronu/11_kusovnik_pavo20.md).
- Aerodynamická čísla jsou **ideální teorie hybnosti**, tedy horní mez. Skutečný
  příkon je typicky násobek; poměry mezi konfiguracemi jsou použitelné, absolutní
  hodnoty ne.
- Reynoldsova čísla níž stojí na **odhadnuté tětivě** listu (8 mm pro 3", 6 mm
  pro 2,2"). Řád je jistý, druhá platná číslice ne.
- Nic z toho nenahrazuje tahovou stolici. Tři místa, kde se to říká, nejsou
  opatrnost, ale seznam věcí, které dnes nikdo nezměřil.

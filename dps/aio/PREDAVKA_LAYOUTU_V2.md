# Předávka: dokončení layoutu AIO V2 přes rozmístění

21. 10. 2026. Nejprve přečíst [rešerši a návrh](./RESERSE_LAYOUTU_V2.md).
Uživatel dovoluje přesuny všech potřebných součástek, preferuje podobnost
MicoAir743v2-AIO-45A a řešení rozmístěním. Nepokračovat přidáváním obchvatů
po zemních rovinách, zmenšováním odstupů ani skrytím hlášení DRC.

## 1. Správný výchozí bod

**Použít celý projekt `build/aio/micoair-route-20261021/project/`.**
Má 21 nespojených, 0 DRC error, 0 neočekávaných ERC/parity hlášení a soulad
hwdefu s V2. SHA256 desky:
`7cd789d58f495afbf154aed1bb417479bda5f9eac8a72332e2f37c036518dd88`.
Další otisky a audit jsou v [reports/2026-10-21/](./reports/2026-10-21/summary.json).

Celý výchozí projekt je navíc uložen v
`research-v2/baseline-v2.tar.gz`, protože `build/` není verzovaný.
Archiv obsahuje adresář `project/` a přesné soubory kontroluje
`research-v2/baseline-manifest.json`. Jde o archiv nedokončeného návrhu,
nikoliv výrobní balík. Archivovaný `NAVRH.md` je historický; aktuální instrukce
jsou v tomto dokumentu a rešerši.

Vytvoření nové pracovní kopie z kořene repozitáře:

```sh
mkdir -p build/aio/layout-v2-work
tar -xzf dps/aio/research-v2/baseline-v2.tar.gz \
  -C build/aio/layout-v2-work --keep-old-files
sha256sum build/aio/layout-v2-work/project/aio.kicad_pcb
```

Adresář musí být nový; při kolizi názvu zvolit jiný. Hlavní `dps/aio/aio.kicad_pcb`
má stále 22 nespojených a jiný profil. Nemíchat jeho schéma/hwdef s kandidátem.

### Pokusy, které nepřebírat automaticky

| Adresář pod `build/aio/` | Výsledek | Rozhodnutí |
| --- | --- | --- |
| `micoair-route-20261021` | 30 → 21 po trasování a prošití GND | Výchozí V2 kandidát. |
| `micoair-layout-20261021` | Experimenty se signály na L2, část dodatečných změn bez finální kontroly | Odložený směr, nepoužít. |
| `micoair-reroute-20261021` | 20 po dvou průchodech, nová cesta SWCLK po L2 | Nepoužít: lepší počet nevyhovuje požadovanému řešení. |
| `micoair-placement-20261021` | 21 po přesunu R301/TP304/TP319 a lokálním trasování; 0 DRC error při dosavadních pravidlech | Jen zdroj poznatků. SWCLK se spojil, SD_CMD zůstal otevřený. Není zlepšením a nemá úplnou mechanickou kontrolu. |

Poslední pokus: R301 (69,85; 62,15; 0°), TP304 (72,75; 69,20; 90°),
TP319 (72,30; 58,00; 90°). **Tyto souřadnice nejsou schválené osazení.**
Zejména TP304 zasahuje do courtyard U301; vypnutá kontrola to nezachytila.
Nepřebírat jeho polohu bez mechanického posouzení a případné opravy.

## 2. Příprava před přesuny

1. Doplnit skutečné courtyard/body obrysy U8, U303, J301 a J302 podle
   identifikovaného výrobku a jeho výkresu. U konektorů přidat prostor pro
   protikus/kartu. Nepovažovat prázdný seznam kolizí za důkaz, když obrys chybí.
   Výrobní dokumenty pro J301 C5187472 a J302 C498185 jsou dohledané v rešerši;
   u J302 ověřit rozdíl označení obecného výkresu TF-021B a varianty H265.
2. Na pracovní kopii zapnout `missing_courtyard`, `malformed_courtyard`,
   `courtyards_overlap` a `copper_edge_clearance` alespoň jako warning;
   zaznamenat výchozí nálezy. Globální ignorování nepřenášet do závěrečné kontroly.
   Úmyslný přesah konkrétního konektoru přes okraj zdůvodnit individuálně.
3. Zobrazit současně osazení obou stran a mapu L1–L8. Zakreslit místa, která
   obsazuje pouzdro MCU, napájení, motorové fáze, prokovy a držení v rámu.
   Fotografie MicoAiru je vzor, nikoliv překryv mědi v měřítku.
4. Vytvořit soupis přesouvaných bloků: reference součástek, lokální vodiče,
   prokovy, připojení napájení a případné plochy. Přesun součástky nepřenese
   automaticky všechny související měděné objekty. Nekopírovat staré vodiče
   na nové pady jiné sítě.

Výstup: `placement-inputs.md`, opravené knihovny/instance, obrázek obou stran
a report se známými mechanickými nálezy. Teprve poté porovnávat polohy.

## 3. První konkrétní úprava: slot a jižní okraj MCU

U301 zatím ponechat (75,90; 64,10), 180°. Tím se omezí rozsah přetrasování
a zůstane srovnatelný stav úniků BGA.

1. **J302 zkusit 90° → 270°**, první kandidát se stejným středem
   (66,81; 65,99). Kontakty se přesunou z x=65,56 na x=68,06 směrem k MCU.
   Ověřit tělo, obrácené pořadí kontaktů, GND kotvy a směr vysouvání karty.
   Pokud místo nevyhoví mechanicky, stejnou orientaci posunout v západní
   oblasti mezi MCU a hranou; neotáčet naslepo na 0°.
2. Odstranit pouze dotčené trasy SD a jejich zbytečné úniky/odbočky,
   umístit pull-upy mimo zamýšlené koridory. Společné napájení nemažeš celé:
   odpojit a obnovit lokální větev, zkontrolovat všechny její spotřebiče.
3. Vyhradit oddělený přístup k A9/A10 pro SWCLK/SWDIO. TP304 a ostatní servisní
   pady umístit na dostupný okraj s místem pro hrot, mimo courtyard MCU,
   SD slot a kabely. R301 přiblížit k úniku F7, ověřit také +3.3V přívod.
4. Natrasovat celou SD skupinu a SWD jako jeden balík. Kontrolovat CK/CMD/D0–D3
   i pull-up odbočky. Jedna opravená síť za cenu druhé není přijaté řešení.

**Přijmout krok**, když SD a SWD nemají nespojené větve, nejsou nové elektrické
ani mechanické kolize a nevzniklo nové vedení po GND. Dočasné zvýšení počtu
nespojených během odstraňování starých cest je očekávané; hodnotí se až celý krok.
Pokud se konflikt pouze přesouvá, nepřidávat další routerové výjimky: přejít na
společné rozmístění v bodě 5.

## 4. Druhý krok: IMU a malé periferie

Po uvolnění jižního prostoru zkusit umístit celý BMI270 blok k padům A5–A8/C6
U301. Zahrnout jeho lokální kondenzátory, CS odpor a přívody 1,8/3,3 V.
Předem ověřit, že spodní ESC a jejich spínací plochy tuto oblast neznehodnotí.
ICM-42688-P posoudit současně podle všech SPI/INT padů, ne pouze chybějícího SCK.

| Blok / síť | Konkrétní postup |
| --- | --- |
| BMI270 | Prioritně spojit všech pět chybějících signálů jako skupinu; vytvořit krátký koridor MCU–IMU s referenční zemí. |
| ICM42688 | Doplnit SCK a znovu posoudit stávající MISO/MOSI/CS/INT po přesunech; lokální blokování držet u pouzdra. |
| GPS J303 | Jeho signály vycházejí z K9/J9 na severozápadě MCU. Pokud jižní umístění blokuje IMU, přesunout konektor na vhodný úsek severní hrany spolu s obslužnými pasivy; ověřit kabel a montážní otvor. |
| UART1/RC J305 | Zespodu může zůstat, pokud zůstane přístupný a uvolní koridory; prověřit přechody vrstev před návrhem cest. RC_RX má dvě chybějící větve včetně JP202. |
| UART8 TP313/314, PWM11 TP319, LD06 TP201 | Přesouvat jako dostupné pájecí/testovací body k příslušným únikům; nepřenášet k nim dlouhou cestu napříč FC. |
| PDR_ON | Odpor i větev napájení připojit bez blokování SD/SWD a bez umístění pod cizí pouzdro. |
| +10V_VTX | U201 + okolí přesunout jako celek, pokud to zkrátí silovou cestu. Šířku určit podle zatížení, délky, tloušťky a prokovů. |
| ESC_CURRENT | Zachovat Kelvinovo snímání shuntu a analogový přívod; při přesunu nepropojovat snímací a silovou návratovou cestu nahodile. |

Po rotaci IMU určit osy z datasheetu, footprintu a směru letu. Aktualizovat
rotace v hwdefu; `ROTATION_NONE` není automaticky správně ani při 0° v KiCadu.

## 5. Když lokální přesuny nestačí: společný layout FC

Tento krok je preferovaný před dalšími obchvaty. Vytvořit **čtyři hrubé varianty
rozmístění**, jednu pro každou rotaci MCU 0/90/180/270°. Nespouštět čtyři dlouhé
autorouty. V každé přemístit s MCU jeho blokování, VCAP, krystal a servisní
pasivy; periferie postavit k odpovídajícím skupinám vývodů z tabulky v rešerši.

U každé varianty uložit jen srovnatelný návrhový list:

- Pohled obou stran, skutečné obrysy a prostor kabelů/karty.
- Délky přímých spojů USB, SD a obou IMU po skupinách, nikoliv pouze celkový součet.
- Dostupné signálové koridory a průchody prokovů přes všechny potřebné vrstvy.
- Dotčené bloky ESC/bucků a rozsah jejich nutného přetrasování.
- Dostupnost portů proti referenční fotografii V2 a rámu dronu.

Vyřadit varianty s mechanickou kolizí, neproveditelnými prokovy nebo špatnými
výkonovými smyčkami. Ze zbylých zvolit tu s nejmenším křížením sběrnic a
rozumnou délkou IMU/SD/USB; vzhled podle fotografie použít jako další kritérium.
U nejlepší varianty **ručně ověřit úniky nejhůře dostupných BGA padů** a hlavní
sběrnice před trasováním UARTů a testpadů.

Pokud překáží ESC, přesunout související budič, MOSFETy, blokování, bootstrap
a lokální spoje jako funkční celek. Ověřit gate smyčky, SW plochy, výkonové
průřezy a tepelnou cestu. Nevymazat plošně zděděnou silovou měď, aby prošel
autorouter. Pro novou orientaci MCU znovu navrhnout escape, nepoužívat staré
souřadnicové předpoklady skriptu `vyved_bga.py`.

## 6. Pořadí trasování a opravy automatizace

Před trasováním rezervovat napájení, návraty a výrobně možné průchody. Poté
lokální MCU napájení/VCAP/krystal, obě IMU, SD, USB, SWD/PDR, motorové řízení
a analogové měření, nakonec UART/I2C a volné pady. Pořadí může reagovat na
konkrétní překážku, nesmí ale obětovat dříve schválenou sběrnici bez kontroly.

Konkrétní pasti současných skriptů:

- `gen/trasuj.py` zkouší `dict.fromkeys((width, CLASS["Default"][0]))`.
  Tím může silový spoj zúžit z 0,3 na 0,09 mm. **Před použitím na silové sítě
  tento obecný fallback zakázat.** Nutné lokální zúžení vyžaduje vlastní posouzení;
  pouhý soulad s defaultní minimální šířkou nestačí.
- `gen/vyved_bga.py` má sadu kuliček `BURIED` odvozenou od starého okolí.
  Není optimalizátorem nového umístění a po přesunu/rotaci MCU se nesmí slepě spustit.
- `--rozmisti --znovu` není cílený přesun. Použít vlastní malý skript s explicitním
  seznamem reference → poloha/rotace, případně KiCad a zaznamenanou tabulkou.
- `--route-only --passes 0` **není čistý audit**: může upravit escape a prošití.
- `--check` odmítá kombinaci `--profile micoair-v2`. Bez profilu umí zkontrolovat
  existující kandidát a jeho hwdef, ale výstup označí `current` a takto generuje
  tabulky. Pro čistou předávku používat níže uvedené přímé kontroly nebo nejprve
  opravit rozlišení „audit existujícího profilu“ v automatizaci.
- Automatický výběr nejlepší desky vyžaduje méně nespojených. To se hodí pro
  dotrasování, nikoliv pro mezikrok přesunu s roztrženými cestami. Oddělit
  kontrolní bod rozmístění od přijetí kompletně přetrasovaného bloku.
- Generátor standardně volí `current`; profil V2 a odpovídající hwdef zachovat
  společně. Transformace hwdefu V2 není určena k libovolnému opakování nad již
  transformovaným výstupem. Použít původní vstup a explicitní profil.

## 7. Kontroly a předání výsledku

Příkazy z kořene repozitáře; výstupní reporty mají nové názvy. Refill níže je
na pracovní kopii, `--save-board` aktualizuje její rozlití.

```sh
nix develop ./dps -c kicad-cli pcb drc --schematic-parity \
  --refill-zones --save-board --format json \
  -o build/aio/layout-v2-work/drc.json \
  build/aio/layout-v2-work/project/aio.kicad_pcb

nix develop ./dps -c kicad-cli sch erc --format json \
  -o build/aio/layout-v2-work/erc.json \
  build/aio/layout-v2-work/project/aio.kicad_sch

nix develop ./dps -c kicad-cli sch export netlist --format kicadxml \
  -o build/aio/layout-v2-work/netlist.xml \
  build/aio/layout-v2-work/project/aio.kicad_sch
```

Vyhodnocení známých výjimek a pinoutu, standardní Python bez pcbnew:

```sh
python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, 'dps/aio/gen')
from kontrola import summarize, net_pins, reference_diff, firmware_errors
p = Path('build/aio/layout-v2-work')
read = lambda name: json.loads((p / name).read_text())
score = summarize(read('drc.json'), read('erc.json'),
                  json.loads(Path('dps/aio/gen/vyjimky.json').read_text()))
pins = net_pins(p / 'netlist.xml')
result = dict(score=score, reference_differences=reference_diff(pins),
              firmware_errors=firmware_errors(pins,
                (p / 'project/hwdef/Pavo20AIO/hwdef.dat').read_text()))
print(json.dumps(result, indent=2, ensure_ascii=False))
PY
```

Tento výpis se musí přečíst; sám nemá návratový kód sign-off kontroly.
Známé ERC/parity výjimky se porovnávají podle identity, ne pouhým počtem 18/14.
Falešné „SD_D0 není propojeno“ z grafu délek routeru rozhodnout skutečnou
konektivitou KiCadu; samotný log délek není kontrola dokončení.

Pro každý přijatý krok uložit před/po: souřadnice, diff pravidel, SHA256 desky,
nespojené sítě, DRC/ERC/parity/pinout, obrázky osazení i dotčených vrstev.
Neměnit potichu globální severity ani výrobní limity kvůli lepšímu výsledku.

Hotový layout musí mít 0 nespojených, 0 neočekávaných ERC/parity/pinout chyb,
vyřešené elektrické i mechanické nálezy a proveditelné prokovy. Dále zkontrolovat
proudové průřezy, napájecí úbytky, zemní návraty, orientace IMU, pin 1 konektorů
a rám. Závěrečný report zvlášť označí, co ještě čeká na výrobní DFM a prototyp.
Při převzetí do hlavního projektu přenést související PCB/schémata/hwdef/knihovny
a upravit výchozí profil generování, aby další běh nevrátil staré zapojení.

## Zadání pro navazujícího agenta

> Pokračuj podle dps/aio/PREDAVKA_LAYOUTU_V2.md a RESERSE_LAYOUTU_V2.md.
> Použij archivovaný V2 základ s 21 nespojenými. Nejdřív oprav podklady
> pro mechanické kontroly, potom prověř J302 270° a společné rozmístění
> SD/SWD/IMU. Přesouvat smíš i další bloky; nepřidávej obchvaty po GND,
> nezeslabuj pravidla a nepoužívej automatické zúžení silových sítí.
> Každý krok předej s konkrétním před/po a skutečným DRC/ERC/pinout auditem.
> Pokud lokální přesuny jen vymění chybějící spoje, proveď srovnání čtyř
> rozmístění FC podle bodu 5 a dotrasuj nejlepší proveditelnou variantu.

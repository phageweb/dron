# Protokol OTRA — Walksnail Ascent Lite+ přes USB

Lite+ připojený USB-C kablem k PC i VRX Pro na svém USB-C mluví binárním
protokolem, kterému tady podle hlavičky říkáme **OTRA**. Používá ho Caddx PC Tool: čte jím informace
o zařízení (HW verze, SN, firmware, **teplota**) a nahrává firmware.
Veřejně popsaný nikde není. Tenhle popis je z odpovědi Lite+ a z kódu
PC Tool V2.2.9 (.NET), zjištěno 13. 10. 2026.

Značky: **[změřeno]** na skutečném Lite+, **[kód]** vyčteno z PC Toolu,
**[odhad]** nepotvrzené.

## Připojení

| | |
| --- | --- |
| USB Lite+ | `1d76:0101`, „Vendor SerialGadget“, sériové číslo `CX24`, bcdDevice 5.10 (uvnitř Linux 5.10) [změřeno] |
| USB VRX Pro | `1d77:a4a2`, „AscentVRX VRX Gadget (RNDIS+UVC+ACM)“, OTRA na rozhraní 4 (ACM) [změřeno] |
| V PC | `/dev/ttyACMn` přes `cdc_acm`, rychlost nehraje roli (USB CDC) [změřeno] |
| Port | na USB 3 portu notebooku „Cannot enable. Maybe the USB cable is bad?“; na USB 2 hubu funguje [změřeno] |
| Napájení | z USB, baterie netřeba (manuál Ascent Lite) |
| Chování | sám nic neposílá; na cokoli odpoví zprávou [změřeno] |

## Rámec

Každá zpráva = **36bajtová hlavička + data**. Všechna čísla little-endian.

| Offset | Typ | Požadavek (PC → VTX) | Odpověď (VTX → PC) | Zdroj |
| ---: | --- | --- | --- | --- |
| 0 | 4 B | `"OTRA"` (`0x4152544F` jako u32) | `"OTRA"` | kód + změřeno |
| 4 | u16 | `0x0CDC` (konstanta) | `0x0CDC` | kód + změřeno |
| 6 | u16 | **1** = požadavek | **2** = odpověď; PC Tool jinou odpověď zahodí | kód + změřeno |
| 8 | u16 | 0 | 0 | kód + změřeno |
| 10 | u16 | `0xABCD` | 0 | kód; v odpovědi změřeno |
| 12 | u32 | **číslo příkazu** | číslo příkazu, na který odpovídá; u neznámého 0 | kód; [odhad] pro odpověď |
| 16 | u16 | 2 | 2 | kód + změřeno |
| 18 | u16 | 0 | 0 | kód + změřeno |
| 20 | u32 | **délka dat** za hlavičkou | délka dat | kód + změřeno |
| 24 | u32 | pořadové číslo, PC Tool ho zvyšuje s každou zprávou | ? (0 v odpovědi na nesmysl) | kód |
| 28 | u32 | parametr volajícího, u dotazů 0 | ? | kód |
| 32 | u32 | **CRC32** | CRC32 | kód + změřeno |

**CRC32** je standardní (zlib, polynom `0xEDB88320`, init a xorout
`0xFFFFFFFF`), počítané přes celou 36bajtovou hlavičku s **vynulovaným
polem CRC** a za ní data:

```python
h = bytearray(header36); h[32:36] = b"\0\0\0\0"
crc = zlib.crc32(bytes(h) + payload)
```

Ověřeno na skutečné odpovědi Lite+ [změřeno].

PC Tool přijatou odpověď odmítne, když je kratší než 36 B, nemá `OTRA`,
na offsetu 6 nemá 2, délka na offsetu 20 nesedí s daty nebo nesedí CRC
[kód]. Jedna kontrolní funkce navíc chce na offsetu 12 příkaz 119, je tedy
jen pro odpověď na 119.

## Příkazy

Z volání v PC Toolu [kód]. Názvy jsou odhad podle souvislostí, protože
jména metod ani texty se z poškozeného instalátoru nepodařilo vytáhnout.

| Příkaz | Data | Co nejspíš dělá | Bezpečné? |
| ---: | --- | --- | --- |
| 60 (`0x3C`) | žádná | **informace o zařízení včetně teploty**, viz níž | **čtení**, ověřeno na VRX |
| 114 (`0x72`) | žádná | část aktualizace firmwaru | ne, nezkoušet |
| 115 (`0x73`) | s daty | část aktualizace firmwaru | ne |
| 116 (`0x74`) | data po **5120 B** | přenos souboru firmwaru po blocích | **ne** |
| 117 (`0x75`) | žádná | část aktualizace firmwaru | ne |
| 118 (`0x76`) | žádná | část aktualizace firmwaru | ne |
| 119 (`0x77`) | ? | odpověď se zvlášť kontroluje, nejspíš výsledek aktualizace | ne |

Příkazy 114–119 se volají z kódu, který dělí soubor na bloky po 5120 B
a hlídá jejich součet. To je aktualizace firmwaru. **Neposílat**: nedokončená
aktualizace může z Lite+ udělat cihlu. Třetí obal posílání má ještě jedno
volání, jehož číslo příkazu se nepodařilo přečíst.

## Příkaz 60: informace o zařízení [změřeno na VRX Pro i Lite+]

Odpověď má 300 bajtů dat, u obou zařízení stejně rozložených. Texty jsou
ASCII doplněné nulami.

| Offset | Velikost | Obsah | VRX Pro | Lite+ |
| ---: | ---: | --- | --- | --- |
| 0x00 | 4 | ? (`00 00 10 00`) | | |
| 0x04 | 32 | verze | `18.21.10` | prázdné |
| 0x24 | 64 | model | `Ascent_VRX_pro` | `Ascent_lite_plus` |
| 0x64 | i32 | **teplota v °C** | 42–46 | **64** |
| 0x68 | 64 | firmware | `Ascent_VRX_Pro_18_21_10` | `Ascent_H_Sky_18_21_10` |
| 0xA8 | 32 | sériové číslo | `0452` | `1_0643` |
| 0xC8 | 36 | hardware | `Ascent-VRX-Pro-V3.0-6.0` | `FPV-Ascent-Sky-472-V1.3-1.1` |
| 0xEC | 64 | stav | `OK` | `OK` |

Měřeno 13. 10. 2026, Lite+ na stole napájený z USB. Že je 0x64 teplota,
potvrzuje to, že se číslo mění (VRX 42 → 43 → 42 → 46 °C) a že sedí
s PC Toolem, který vedle HW, SN a firmwaru ukazuje právě teplotu.

Odpověď přijde do ~1 s. Druhý dotaz na tomtéž otevřeném portu s 0,8 s
čekání jednou nedostal odpověď. Spolehlivé je pro každý dotaz port otevřít,
čekat až 2,5 s a zavřít.

## Odpověď na neznámý příkaz [změřeno]

Na `\r\n` přišlo 104 bajtů:

```text
4f 54 52 41  dc 0c  02 00  00 00  00 00  00 00 00 00  02 00  00 00
"OTRA"       0x0CDC odp.   0      0      příkaz 0     2      0
44 00 00 00  00 00 00 00  00 00 00 00  e2 86 75 51
délka 68     pořadí 0     0            CRC32 ok
ff ff ff ff  "unkonwn cmd" + nuly do 64 B
stav −1      text chyby (překlep je od výrobce)
```

Data odpovědi tedy podle všeho začínají **i32 stavem** (−1 = chyba,
nejspíš 0 = v pořádku) a za ním jsou užitečná data [odhad z jediné
odpovědi].

## Nástroj

`vrx/otra.py` najde zařízení Ascent na USB a vypíše jejich informace,
nebo pošle jeden příkaz a vypíše surovou odpověď s kontrolou CRC.
Příkazy 114–119 odmítne poslat.

```sh
python3 vrx/otra.py                   # VRX /dev/ttyACM0: version=18.21.10, ..., temp_c=42, ...
python3 vrx/otra.py /dev/ttyACM0 60
```

`vrx/vrx.py` se ptá každé 2 s a teploty ukazuje v okně.

## Co zbývá ověřit

- Jestli VRX zná teplotu VTX přes rádio. V odpovědi na 60 je jen jedna
  teplota a ta je vlastní. Další čtecí příkazy neznáme.
- Význam prvních 4 bajtů odpovědi na 60.
- Lite+ se **asi minutu po prvním připojení k PC sám odpojil**
  (22:33:20 → 22:34:31). Příčina není známá: přehřátí, napájení z USB,
  nebo reakce na nesmyslnou zprávu. Po novém připojení odpovídá.
- Dva programy, které se ptají na stejném portu najednou (třeba dvě
  okna `vrx.py`), si mohou odpovědi přebírat. Pouštět jen jeden.

## Jak se to zjistilo

Instalátor `CADDX_PC_Tool_V2.2.9_win_Setup.exe` je Inno Setup 6.7 s balíčkem
Velopack. innoextract 1.10-dev ho nerozbalí. Ruční rozbalení zipu uvnitř
se po ~620 kB poškodí, ale začátek .NET aplikace s kódem protokolu je
čitelný. Z IL kódu jsou vyčtené funkce:

- sestavení hlavičky: konstanty `OTRA`, `0x0CDC`, `0xABCD`, pořadí polí,
- kontrola odpovědi: délka ≥ 36, `OTRA`, offset 6 = 2, délka na 20, CRC na 32,
- výpočet CRC: hlavička se zkopíruje, `Array.Clear(h, 32, 4)`, CRC přes hlavičku a data,
- místa volání s čísly příkazů.

Nic se nespouštělo, Wine nebylo potřeba.

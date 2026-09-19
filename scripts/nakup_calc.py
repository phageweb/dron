# -*- coding: utf-8 -*-
"""Nakupni kalkulace dronu: CZ/EU (vc. Allegro) vs AliExpress, s dopravou.
Kurzy CNB 11. 9. 2026."""

EUR, USD, PLN = 24.260, 20.927, 5.609

def kc(v, cur="CZK"):
    return v * {"CZK":1.0, "EUR":EUR, "USD":USD, "PLN":PLN}[cur]

# --- DOPRAVA (Kc za zasilku) -------------------------------------------
# overeno = z webu obchodu; odhad = typicka sazba, uprav podle kosiku
SHIP = {
    "Aerodrone CZ":  (99,  "odhad"),
    "Rotorama CZ":   (89,  "overeno: 89 adresa / 59 Zasilkovna, bez limitu zdarma"),
    "FPV24 DE":      (kc(9.90,"EUR"),  "odhad z jejich AT tarifu <100 EUR"),
    "RCTech DE":     (kc(12.00,"EUR"), "odhad; LiPo jen pozemni prepravou"),
    "Rotorama EU":   (kc(9.90,"EUR"),  "odhad - a nize ukazu, ze ji nepotrebujes"),
    "Import CN":     (kc(20.00,"USD"), "odhad pro LD06 ze Sunhokey"),
    "AliExpress":    (kc(3.00,"EUR"),  "odhad na prodejce; casto 0, ale pomalu"),
    "Allegro PL":    (kc(20.00,"PLN"), "odhad; nekteri prodejci do CZ draz"),
}

# --- POLOZKY -----------------------------------------------------------
# (nazev, ks, CZ/EU cena za ks v Kc, obchod, AE/CN cena za ks v Kc nebo None, poznamka)
ITEMS = [
 ("GEPRC CineLog30 V3 ram",      1, kc(1490),          "Aerodrone CZ", None,
  "AE cenu V3 ramu se neporadilo overit; stare CL30 ~30-35 USD"),
 ("SPEEDX2 1404 3850KV motor",   4, kc(379),           "Rotorama CZ",  kc(14.99,"USD"),
  "14,99 USD = cenik GEPRC; AE byva +-stejne"),
 ("HQProp DT76mmX3 V2 (sada)",   3, kc(79),            "Rotorama CZ",  kc(2.50,"USD"),
  "rozdil v radu desetikorun, nema smysl resit"),
 ("MicoAir H743 V2 45A AIO",     1, kc(2090),          "Rotorama CZ",  kc(74.99,"USD"),
  "74,99 USD = oficialni MicoAir store"),
 ("SpeedyBee Nano ELRS RX",      1, kc(12.90,"EUR"),   "FPV24 DE",     kc(10.99,"USD"),
  "10,99 USD Banggood; na Rotorame nebyl skladem"),
 ("MicoAir MTF-02P",             1, kc(499),           "Rotorama CZ",  None,
  "!! 499 Kc na rotorama.CZ, kusovnik posila na rotorama.COM za 20,49 EUR"),
 ("Tattu 4S LiHV 750 long XT30", 3, kc(19.90,"EUR"),   "RCTech DE",    None,
  "LiPo se z CN letecky neposila - AE varianta prakticky neexistuje"),
 ("LDRobot LD06",                1, kc(75.50,"USD"),   "Import CN",    kc(75.50,"USD"),
  "uz ted dovoz; Allegro LD06/LD19 395 zl"),
 ("EMAX Wyvern Link Alpha",      1, kc(2019),          "Rotorama CZ",  None,
  "!! 2019 Kc na rotorama.CZ vs 82,39 EUR = 1999 Kc na rotorama.DE"),
]

print("="*74)
print("1) CENA ZBOZI - CZ/EU vs Cina (bez dopravy)")
print("="*74)
print(f"{'Dil':<32}{'ks':>3}{'CZ/EU':>10}{'CN':>10}{'rozdil':>10}")
tot_cz = tot_cn = 0
for n, q, cz, shop, cn, note in ITEMS:
    a = cz*q
    tot_cz += a
    if cn is None:
        print(f"{n:<32}{q:>3}{a:>10.0f}{'-':>10}{'-':>10}")
        tot_cn += a
    else:
        b = cn*q
        tot_cn += b
        print(f"{n:<32}{q:>3}{a:>10.0f}{b:>10.0f}{a-b:>+10.0f}")
print("-"*74)
print(f"{'CELKEM zbozi':<35}{tot_cz:>10.0f}{tot_cn:>10.0f}{tot_cz-tot_cn:>+10.0f}")

print()
print("="*74)
print("2) DOPRAVA - kolik zasilek podle ktereho planu")
print("="*74)

def plan(name, mapping, extra_ship=()):
    zbozi = 0
    shops = {}
    for n, q, cz, shop, cn, note in ITEMS:
        s = mapping.get(n, shop)
        if s is None:
            continue
        price = cn if (s == "AliExpress" and cn) else cz
        zbozi += price*q
        shops.setdefault(s, []).append(n)
    dop = sum(SHIP[s][0] for s in shops) + sum(SHIP[s][0] for s in extra_ship)
    print(f"\n{name}")
    for s, its in sorted(shops.items()):
        print(f"   {s:<16}{SHIP[s][0]:>6.0f} Kc   {', '.join(i[:26] for i in its)}")
    print(f"   {'zbozi':<16}{zbozi:>6.0f} Kc")
    print(f"   {'doprava':<16}{dop:>6.0f} Kc  ({len(shops)} zasilek)")
    print(f"   {'CELKEM':<16}{zbozi+dop:>6.0f} Kc")
    return zbozi+dop

# RunCam varianta se neuvazuje, model pouziva Wyvern.
a = plan("A) Kusovnik tak, jak je napsany (6 zasilek)",
         {"MicoAir MTF-02P": "Rotorama EU", "EMAX Wyvern Link Alpha": "Rotorama EU"})
b = plan("B) Konsolidovane - MTF-02P a Wyvern z rotorama.CZ (5 zasilek)", {})
c = plan("C) B + motory, AIO, vrtule a RX z AliExpressu (5 zasilek)",
         {"SPEEDX2 1404 3850KV motor": "AliExpress",
          "MicoAir H743 V2 45A AIO": "AliExpress",
          "HQProp DT76mmX3 V2 (sada)": "AliExpress",
          "SpeedyBee Nano ELRS RX": "AliExpress"})
d = plan("D) B + jen AIO z AliExpressu (6 zasilek)",
         {"MicoAir H743 V2 45A AIO": "AliExpress"})

print()
print("="*74)
print("3) ROZDILY PROTI PLANU B")
print("="*74)
for nm, v in [("A kusovnik", a), ("C vse co jde z AE", c), ("D jen AIO z AE", d)]:
    print(f"   {nm:<22}{v-b:>+8.0f} Kc")

print()
print("="*74)
print("4) VYPLATI SE DANOU POLOZKU BRAT Z ALIEXPRESSU?")
print("   marginalni test: usetreno na zbozi minus 1 zasilka navic z AE")
print("="*74)
ae_ship = SHIP["AliExpress"][0]
for n, q, cz, shop, cn, note in ITEMS:
    if cn is None:
        print(f"   {n:<32}  n/a   {note}")
        continue
    save = (cz-cn)*q
    net = save - ae_ship
    verdict = "VYPLATI SE" if net > 300 else ("hranicni" if net > 0 else "NEVYPLATI")
    print(f"   {n:<32}{save:>+7.0f} zbozi {net:>+7.0f} po doprave  {verdict}")

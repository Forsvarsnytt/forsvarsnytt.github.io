"""
Forsvarsnytt – informasjon om landene i konfliktkartet.

Når man trykker på et land i konfliktkartet, vises:
  - norsk navn og medlemskap (NATO, EU, atommakt, fast medlem i FNs sikkerhetsråd), fra listene under
  - en kort beskrivelse fra land.txt, for landene som har det
  - konfliktene på Forsvarsnytt som landet er en del av (fra konflikter.txt, i nettleseren)
  - siste nytt som nevner landet, fra sakene på siden og arkivet

Listene over medlemskap er stabile, men må oppdateres hvis et land blir med i eller går ut av NATO eller EU.
"""

import json
import re
from pathlib import Path

ROT = Path(__file__).parent
FIL = ROT / "land.txt"
MAKS_NYHETER = 6

NAVN = {
    "Afghanistan": "Afghanistan", "Albania": "Albania", "Algeria": "Algerie", "Angola": "Angola", "Argentina": "Argentina",
    "Armenia": "Armenia", "Australia": "Australia", "Austria": "Østerrike", "Azerbaijan": "Aserbajdsjan",
    "Bangladesh": "Bangladesh", "Belarus": "Hviterussland", "Belgium": "Belgia", "Belize": "Belize", "Benin": "Benin",
    "Bhutan": "Bhutan", "Bolivia": "Bolivia", "Bosnia and Herzegovina": "Bosnia-Hercegovina", "Botswana": "Botswana",
    "Brazil": "Brasil", "Brunei": "Brunei", "Bulgaria": "Bulgaria", "Burkina Faso": "Burkina Faso", "Burundi": "Burundi",
    "Cambodia": "Kambodsja", "Cameroon": "Kamerun", "Canada": "Canada", "Central African Republic": "Den sentralafrikanske republikk",
    "Chad": "Tsjad", "Chile": "Chile", "China": "Kina", "Colombia": "Colombia", "Costa Rica": "Costa Rica", "Croatia": "Kroatia",
    "Cuba": "Cuba", "Cyprus": "Kypros", "Czechia": "Tsjekkia", "Democratic Republic of the Congo": "Den demokratiske republikken Kongo",
    "Denmark": "Danmark", "Djibouti": "Djibouti", "Dominican Republic": "Den dominikanske republikk", "East Timor": "Øst-Timor",
    "Ecuador": "Ecuador", "Egypt": "Egypt", "El Salvador": "El Salvador", "Equatorial Guinea": "Ekvatorial-Guinea",
    "Eritrea": "Eritrea", "Estonia": "Estland", "Ethiopia": "Etiopia", "Falkland Islands": "Falklandsøyene", "Fiji": "Fiji",
    "Finland": "Finland", "France": "Frankrike", "French Southern and Antarctic Lands": "De franske sørterritoriene",
    "Gabon": "Gabon", "Gambia": "Gambia", "Georgia": "Georgia", "Germany": "Tyskland", "Ghana": "Ghana", "Greece": "Hellas",
    "Greenland": "Grønland", "Guatemala": "Guatemala", "Guinea": "Guinea", "Guinea-Bissau": "Guinea-Bissau", "Guyana": "Guyana",
    "Haiti": "Haiti", "Honduras": "Honduras", "Hungary": "Ungarn", "Iceland": "Island", "India": "India", "Indonesia": "Indonesia",
    "Iran": "Iran", "Iraq": "Irak", "Ireland": "Irland", "Israel": "Israel", "Italy": "Italia", "Ivory Coast": "Elfenbenskysten",
    "Jamaica": "Jamaica", "Japan": "Japan", "Jordan": "Jordan", "Kazakhstan": "Kasakhstan", "Kenya": "Kenya", "Kosovo": "Kosovo",
    "Kuwait": "Kuwait", "Kyrgyzstan": "Kirgisistan", "Laos": "Laos", "Latvia": "Latvia", "Lebanon": "Libanon", "Lesotho": "Lesotho",
    "Liberia": "Liberia", "Libya": "Libya", "Lithuania": "Litauen", "Luxembourg": "Luxembourg", "Madagascar": "Madagaskar",
    "Malawi": "Malawi", "Malaysia": "Malaysia", "Mali": "Mali", "Mauritania": "Mauritania", "Mexico": "Mexico", "Moldova": "Moldova",
    "Mongolia": "Mongolia", "Montenegro": "Montenegro", "Morocco": "Marokko", "Mozambique": "Mosambik", "Myanmar": "Myanmar",
    "Namibia": "Namibia", "Nepal": "Nepal", "Netherlands": "Nederland", "New Caledonia": "Ny-Caledonia", "New Zealand": "New Zealand",
    "Nicaragua": "Nicaragua", "Niger": "Niger", "Nigeria": "Nigeria", "North Korea": "Nord-Korea", "North Macedonia": "Nord-Makedonia",
    "Northern Cyprus": "Nord-Kypros", "Norway": "Norge", "Oman": "Oman", "Pakistan": "Pakistan", "Palestine": "Palestina",
    "Panama": "Panama", "Papua New Guinea": "Papua Ny-Guinea", "Paraguay": "Paraguay", "Peru": "Peru", "Philippines": "Filippinene",
    "Poland": "Polen", "Portugal": "Portugal", "Puerto Rico": "Puerto Rico", "Qatar": "Qatar", "Republic of Serbia": "Serbia",
    "Republic of the Congo": "Republikken Kongo", "Romania": "Romania", "Russia": "Russland", "Rwanda": "Rwanda",
    "Saudi Arabia": "Saudi-Arabia", "Senegal": "Senegal", "Sierra Leone": "Sierra Leone", "Slovakia": "Slovakia",
    "Slovenia": "Slovenia", "Solomon Islands": "Salomonøyene", "Somalia": "Somalia", "Somaliland": "Somaliland",
    "South Africa": "Sør-Afrika", "South Korea": "Sør-Korea", "South Sudan": "Sør-Sudan", "Spain": "Spania", "Sri Lanka": "Sri Lanka",
    "Sudan": "Sudan", "Suriname": "Surinam", "Sweden": "Sverige", "Switzerland": "Sveits", "Syria": "Syria", "Taiwan": "Taiwan",
    "Tajikistan": "Tadsjikistan", "Thailand": "Thailand", "The Bahamas": "Bahamas", "Togo": "Togo",
    "Trinidad and Tobago": "Trinidad og Tobago", "Tunisia": "Tunisia", "Turkey": "Tyrkia", "Turkmenistan": "Turkmenistan",
    "Uganda": "Uganda", "Ukraine": "Ukraina", "United Arab Emirates": "De forente arabiske emirater", "United Kingdom": "Storbritannia",
    "United Republic of Tanzania": "Tanzania", "United States of America": "USA", "Uruguay": "Uruguay", "Uzbekistan": "Usbekistan",
    "Vanuatu": "Vanuatu", "Venezuela": "Venezuela", "Vietnam": "Vietnam", "Western Sahara": "Vest-Sahara", "Yemen": "Jemen",
    "Zambia": "Zambia", "Zimbabwe": "Zimbabwe", "eSwatini": "Eswatini",
}
# engelske navn slik de vanligvis står i nyhetene, når kartnavnet er annerledes
ENGELSK = {
    "Republic of Serbia": "Serbia", "United States of America": "United States, US, USA, U.S.", "United Kingdom": "UK, Britain, United Kingdom",
    "Democratic Republic of the Congo": "DR Congo, DRC, Congo", "United Republic of Tanzania": "Tanzania", "Czechia": "Czechia, Czech Republic",
    "Ivory Coast": "Ivory Coast, Côte d'Ivoire", "The Bahamas": "Bahamas", "eSwatini": "Eswatini", "Palestine": "Palestine, Palestinian, Gaza, West Bank",
    "Republic of the Congo": "Republic of the Congo", "Turkey": "Turkey, Türkiye",
}

NATO = {"Albania", "Belgium", "Bulgaria", "Canada", "Croatia", "Czechia", "Denmark", "Estonia", "Finland", "France", "Germany",
        "Greece", "Hungary", "Iceland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Montenegro", "Netherlands", "North Macedonia",
        "Norway", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden", "Turkey", "United Kingdom",
        "United States of America", "Greenland"}  # Grønland er en del av Kongeriket Danmark
EU = {"Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia", "Finland", "France", "Germany",
      "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Netherlands", "Poland", "Portugal",
      "Romania", "Slovakia", "Slovenia", "Spain", "Sweden"}  # Malta er for lite til å vises på kartet
ATOM = {"United States of America", "Russia", "China", "United Kingdom", "France", "India", "Pakistan", "North Korea"}
SIKKERHETSRAADET = {"United States of America", "Russia", "China", "United Kingdom", "France"}
NABO = {"Sweden", "Finland", "Russia"}


def les_tekster():
    """land.txt: «## Norsk navn (Kartnavn)», så «tekst:» og eventuelt «søkeord:»."""
    tekster, l_ = {}, None
    if not FIL.exists():
        return tekster
    for linje in FIL.read_text(encoding="utf-8").splitlines():
        l = linje.strip()
        if l.startswith("## "):
            m = re.match(r"## .*\((.+)\)\s*$", l)
            l_ = m.group(1).strip() if m else None
            if l_:
                tekster[l_] = {"tekst": "", "sokeord": []}
        elif l_ and ":" in l and not l.startswith("#"):
            felt, verdi = (x.strip() for x in l.split(":", 1))
            felt = felt.lower().replace("ø", "o")
            if felt == "tekst":
                tekster[l_]["tekst"] = verdi
            elif felt == "sokeord":
                tekster[l_]["sokeord"] = [x.strip() for x in verdi.split(",") if x.strip()]
    return tekster


def lag(saker, kartnavn):
    tekster = les_tekster()
    alle = {s["lenke"]: s for s in saker}
    arkiv = ROT / "data" / "arkiv"
    if arkiv.exists():
        for f in arkiv.glob("*.json"):
            for s in json.loads(f.read_text(encoding="utf-8")):
                alle.setdefault(s["lenke"], s)
    alle = sorted(alle.values(), key=lambda s: s.get("tid") or "", reverse=True)

    ut = {}
    for k in kartnavn:
        t = tekster.get(k, {"tekst": "", "sokeord": []})
        medlem = []
        if k in NABO: medlem.append("Nabo til Norge")
        if k in NATO: medlem.append("NATO")
        if k in EU: medlem.append("EU")
        if k in SIKKERHETSRAADET: medlem.append("Fast medlem i FNs sikkerhetsråd")
        if k in ATOM: medlem.append("Atommakt")
        ord_ = t["sokeord"] or [k, NAVN.get(k, k)] + [x.strip() for x in ENGELSK.get(k, "").split(",") if x.strip()]
        deler = [re.escape(o) if (o.isupper() and len(o) <= 4) else "(?i:" + re.escape(o) + ")" for o in set(ord_)]
        m = re.compile(r"(?<![\w-])(" + "|".join(deler) + r")(?![\w-])")
        treff = [s for s in alle if m.search(s["tittel"])]
        ut[k] = {"navn": NAVN.get(k, k), "medlem": medlem, "tekst": t["tekst"], "antall": len(treff),
                 "nyheter": [{"tittel": s["tittel"], "lenke": s["lenke"], "kilde": s["kilde"], "tid": s.get("tid")}
                             for s in treff[:MAKS_NYHETER]]}
    return ut

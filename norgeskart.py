"""
Forsvarsnytt – Norgeskartet med Forsvarets tjenestesteder.

Leser forsvaret-steder.txt (åpne opplysninger fra Forsvarets egne sider om tjenestestedene)
og finner nyheter om hvert sted blant sakene på siden og i arkivet.
Kartet (data/norgeskart.json) er laget fra Natural Earth 1:50m, public domain.
"""

import json
import re
from pathlib import Path

ROT = Path(__file__).parent
FIL = ROT / "forsvaret-steder.txt"
KART = ROT / "data" / "norgeskart.json"
MAKS_NYHETER = 8
GRENER = {
    "hæren": "Hæren",
    "sjøforsvaret": "Sjøforsvaret",
    "luftforsvaret": "Luftforsvaret",
    "heimevernet": "Heimevernet",
    "spesialstyrker": "Spesialstyrkene",
    "cyber": "Cyberforsvaret",
    "utdanning": "Skoler og utdanning",
    "felles": "Ledelse, logistikk og støtte",
    "nato": "NATO og allierte",
}


def les_steder():
    steder, s = [], None
    if not FIL.exists():
        return steder
    for linje in FIL.read_text(encoding="utf-8").splitlines():
        l = linje.strip()
        if l.startswith("## "):
            s = {"navn": l[3:].strip(), "posisjon": None, "kommune": "", "gren": "felles", "lenke": "",
                 "tekst": "", "sokeord": [], "avdelinger": []}
            steder.append(s)
        elif s is None or not l or l.startswith("#"):
            continue
        elif l.startswith("- "):
            d = [x.strip() for x in l[2:].split("|")]
            if len(d) >= 2 and d[1]:
                gren = d[0].lower() if d[0].lower() in GRENER else "felles"
                s["avdelinger"].append({"gren": gren, "navn": d[1], "info": d[2] if len(d) > 2 else ""})
        elif ":" in l:
            felt, verdi = (x.strip() for x in l.split(":", 1))
            felt = felt.lower().replace("ø", "o")
            if felt == "posisjon":
                try:
                    lat, lon = (float(x) for x in verdi.split(","))
                    s["posisjon"] = [lat, lon]
                except ValueError:
                    pass
            elif felt == "gren":
                s["gren"] = verdi.lower() if verdi.lower() in GRENER else "felles"
            elif felt == "sokeord":
                s["sokeord"] = [x.strip() for x in verdi.split(",") if x.strip()]
            elif felt in ("kommune", "tekst"):
                s[felt] = verdi
            elif felt == "lenke" and verdi.startswith("http"):
                s["lenke"] = verdi
    return [s for s in steder if s["posisjon"]]


def lag(saker):
    """Returnerer {"steder", "grener", "kart"} eller None hvis noe mangler."""
    steder = les_steder()
    if not steder or not KART.exists():
        return None

    alle = {s["lenke"]: s for s in saker}
    arkiv = ROT / "data" / "arkiv"
    if arkiv.exists():
        for f in arkiv.glob("*.json"):
            for s in json.loads(f.read_text(encoding="utf-8")):
                alle.setdefault(s["lenke"], s)
    alle = sorted(alle.values(), key=lambda s: s.get("tid") or "", reverse=True)

    for st in steder:
        ord_ = st.pop("sokeord") or [re.sub(r"\s*\(.*?\)", "", st["navn"])]
        # store bokstaver betyr noe for korte forkortelser (FSK, FOH, GSV), ellers ikke
        deler = [re.escape(o) if o.isupper() else "(?i:" + re.escape(o) + ")" for o in ord_]
        m = re.compile(r"\b(" + "|".join(deler) + r")\b")
        treff = [s for s in alle if m.search(s["tittel"] + " " + (s.get("ingress") or ""))]
        st["antall"] = len(treff)
        st["nyheter"] = [{"tittel": s["tittel"], "lenke": s["lenke"], "kilde": s["kilde"], "tid": s.get("tid")}
                         for s in treff[:MAKS_NYHETER]]

    kart = json.loads(KART.read_text(encoding="utf-8"))
    return {"steder": steder, "grener": GRENER, "kart": kart["land"], "info": kart["_info"]}

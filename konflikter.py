"""
Forsvarsnytt – konfliktkartet.

Leser konflikter.txt og finner nyheter om hver konflikt blant sakene på siden og i arkivet.
Kartet (data/verdenskart.json) er Natural Earth 1:110m, public domain, med Krim flyttet til Ukraina.
"""

import json
import re
from pathlib import Path

ROT = Path(__file__).parent
FIL = ROT / "konflikter.txt"
KART = ROT / "data" / "verdenskart.json"
MAKS_NYHETER = 12


def les_konflikter():
    konflikter, k = [], None
    if not FIL.exists():
        return konflikter
    for linje in FIL.read_text(encoding="utf-8").splitlines():
        l = linje.strip()
        if l.startswith("## "):
            k = {"navn": l[3:].strip(), "type": "konflikt", "posisjon": None, "land": [], "siden": "", "sokeord": [], "tekst": ""}
            konflikter.append(k)
        elif k is not None and l and not l.startswith("#") and ":" in l:
            felt, verdi = (d.strip() for d in l.split(":", 1))
            felt = felt.lower().replace("ø", "o")
            if felt == "type":
                k["type"] = verdi.lower() if verdi.lower() in ("krig", "konflikt", "spenning") else "konflikt"
            elif felt == "posisjon":
                try:
                    lat, lon = (float(x) for x in verdi.split(","))
                    k["posisjon"] = [lat, lon]
                except ValueError:
                    pass
            elif felt == "land":
                k["land"] = [x.strip() for x in verdi.split(",") if x.strip()]
            elif felt == "siden":
                k["siden"] = verdi
            elif felt == "sokeord":
                k["sokeord"] = [x.strip().lower() for x in verdi.split(",") if x.strip()]
            elif felt == "tekst":
                k["tekst"] = verdi
    return [k for k in konflikter if k["posisjon"]]


def lag(saker):
    """Returnerer konfliktene med nyheter, og kartet."""
    konflikter = les_konflikter()
    if not konflikter:
        return [], None

    # alle kjente saker: de ferske (med ingress der det er lov) og arkivet (bare overskrifter)
    alle = {s["lenke"]: s for s in saker}
    arkiv = ROT / "data" / "arkiv"
    if arkiv.exists():
        for f in arkiv.glob("*.json"):
            for s in json.loads(f.read_text(encoding="utf-8")):
                alle.setdefault(s["lenke"], s)
    alle = sorted(alle.values(), key=lambda s: s.get("tid") or "", reverse=True)

    for k in konflikter:
        if k["sokeord"]:
            m = re.compile(r"\b(" + "|".join(re.escape(o) for o in k["sokeord"]) + r")\b", re.I)
            treff = [s for s in alle if m.search(s["tittel"] + " " + (s.get("ingress") or ""))]
        else:
            treff = []
        k["antall"] = len(treff)
        k["nyheter"] = [{"tittel": s["tittel"], "lenke": s["lenke"], "kilde": s["kilde"], "tid": s.get("tid")}
                        for s in treff[:MAKS_NYHETER]]
        del k["sokeord"]

    kart = json.loads(KART.read_text(encoding="utf-8"))["land"] if KART.exists() else None
    return konflikter, kart

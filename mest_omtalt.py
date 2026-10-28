"""
Forsvarsnytt – finner de mest omtalte sakene uten AI.

Sakene lagres i et lite arkiv (data/arkiv/ÅÅÅÅ-MM-DD.json, én fil per dag).
Saker fra ulike kilder som deler flere viktige ord i overskriften, regnes som
samme hendelse. Hendelsene rangeres etter hvor mange ulike kilder som skriver om dem.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROT = Path(__file__).parent
ARKIV = ROT / "data" / "arkiv"
DAGER_I_ARKIV = 35

STOPPORD = set("""
og i på til av for med som er en et ei det den de om fra etter har var ikke vil kan seg sin sitt sine
nå nye ny nytt mer mot under over ved da når hva hvem hvorfor hvordan blir ble skal må får fikk etter
the a an of to in on for and with as at by from is are was were be been has have had after over says
said say new will would could its it into amid than more about up out not but who what how why this
that these those his her their they he she we you our us also first just may can could now year years
week day days news live latest update updates report reports amid during against between
""".split())


def ord_i(tittel):
    return {o for o in re.findall(r"[a-zæøåäöüéáí0-9][a-zæøåäöüéáí0-9-]{2,}", tittel.lower())
            if o not in STOPPORD and not o.isdigit()}


# ---------- arkiv ----------

def oppdater_arkiv(saker, nå, beholdes=lambda s: True):
    """Legger nye saker inn i dagsfilene og returnerer alle arkiverte saker.
    Saker der beholdes(sak) er False (f.eks. fra kilder som er fjernet), slettes fra arkivet."""
    ARKIV.mkdir(parents=True, exist_ok=True)
    per_dag = {}
    for s in saker:
        if not s["tid"]:
            continue
        dag = s["tid"][:10]
        per_dag.setdefault(dag, []).append(
            {k: s[k] for k in ("tittel", "lenke", "kilde", "tema", "tid")})
    for dag, nye in per_dag.items():
        fil = ARKIV / f"{dag}.json"
        gamle = json.loads(fil.read_text(encoding="utf-8")) if fil.exists() else []
        kjente = {s["lenke"] for s in gamle}
        tillegg = [s for s in nye if s["lenke"] not in kjente]
        if tillegg:
            samlet = sorted(gamle + tillegg, key=lambda s: s["tid"])
            fil.write_text(json.dumps(samlet, ensure_ascii=False, indent=0), encoding="utf-8")

    grense = (nå - timedelta(days=DAGER_I_ARKIV)).date().isoformat()
    alle = []
    for fil in sorted(ARKIV.glob("*.json")):
        if fil.stem < grense:
            fil.unlink()  # rydder bort det som er eldre enn arkivet skal holde
            continue
        innhold = json.loads(fil.read_text(encoding="utf-8"))
        beholdt = [s for s in innhold if beholdes(s)]
        if len(beholdt) != len(innhold):
            fil.write_text(json.dumps(beholdt, ensure_ascii=False, indent=0), encoding="utf-8")
        alle += beholdt
    return alle


# ---------- gruppering og rangering ----------

def grupper(saker):
    """Grupperer saker som handler om det samme. Bruker en indeks for å holde det raskt."""
    grupper_, indeks = [], {}
    for s in sorted(saker, key=lambda s: s["tid"]):
        ordene = ord_i(s["tittel"])
        if len(ordene) < 2:
            continue
        kandidater = {}
        for o in ordene:
            for g in indeks.get(o, ()):
                kandidater[g] = kandidater.get(g, 0) + 1
        beste, beste_score = None, 0.0
        for g, felles in kandidater.items():
            if felles < 2:
                continue
            for medlem_ord in grupper_[g]["ord_liste"][-15:]:
                f = len(ordene & medlem_ord)
                score = f / min(len(ordene), len(medlem_ord))
                if f >= 2 and score >= 0.5 and score > beste_score:
                    beste, beste_score = g, score
        if beste is None:
            beste = len(grupper_)
            grupper_.append({"saker": [], "ord_liste": []})
        grupper_[beste]["saker"].append(s)
        grupper_[beste]["ord_liste"].append(ordene)
        for o in ordene:
            indeks.setdefault(o, set()).add(beste)
    return grupper_


def rangert(saker, maks):
    resultat = []
    for g in grupper(saker):
        kilder = {s["kilde"] for s in g["saker"]}
        if len(kilder) < 2:  # bare hendelser som minst to ulike kilder skriver om
            continue
        # tittel: den saken som deler flest ord med resten av gruppa
        alle_ord = {}
        for ordene in g["ord_liste"]:
            for o in ordene:
                alle_ord[o] = alle_ord.get(o, 0) + 1
        sentral = max(range(len(g["saker"])),
                      key=lambda i: sum(alle_ord[o] for o in g["ord_liste"][i]))
        resultat.append((len(kilder), len(g["saker"]), g["saker"][-1]["tid"], g, sentral))
    resultat.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)

    punkter = []
    for antall_kilder, antall_saker, _, g, sentral in resultat[:maks]:
        lenker, sett = [], set()
        for s in reversed(g["saker"]):  # nyeste først, én lenke per kilde
            if s["kilde"] not in sett:
                sett.add(s["kilde"])
                lenker.append({"kilde": s["kilde"], "lenke": s["lenke"]})
        temaer = [s["tema"] for s in g["saker"]]
        punkter.append({
            "tittel": g["saker"][sentral]["tittel"],
            "tekst": f"Omtalt i {antall_saker} saker fra {antall_kilder} "
                     f"{'kilde' if antall_kilder == 1 else 'kilder'}.",
            "tema": max(set(temaer), key=temaer.count),
            "lenker": lenker[:6],
        })
    return punkter


def lag(saker_naa, nå_oslo, beholdes=lambda s: True):
    nå = nå_oslo.astimezone(timezone.utc)
    arkiv = oppdater_arkiv(saker_naa, nå, beholdes)
    # slå sammen arkiv og ferske saker, uten duplikater
    alle = {s["lenke"]: s for s in arkiv}
    for s in saker_naa:
        if s["tid"]:
            alle.setdefault(s["lenke"], s)
    alle = list(alle.values())

    def innen(dager):
        grense = (nå - timedelta(days=dager)).isoformat()
        return [s for s in alle if s["tid"] >= grense]

    res = {}
    for type_, dager, periode, maks in (("dag", 1, "Siste 24 timer", 8),
                                        ("uke", 7, "Siste 7 dager", 10),
                                        ("maaned", 30, "Siste 30 dager", 12)):
        punkter = rangert(innen(dager), maks)
        res[type_] = {"type": type_, "modus": "omtalt", "periode": periode, "ingress": "",
                      "punkter": punkter, "laget": nå_oslo.isoformat()} if punkter else None
    eldste = min((s["tid"] for s in alle), default=None)
    if eldste:
        dager_data = (nå - datetime.fromisoformat(eldste)).days + 1
        for t, d in (("uke", 7), ("maaned", 30)):
            if res[t] and dager_data < d:
                res[t]["grunnlag"] = f"Arkivet har foreløpig bare {dager_data} dager med saker"
    return res

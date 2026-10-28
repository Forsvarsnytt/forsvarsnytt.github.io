"""
Forsvarsnytt – leser «Ukens hjørne» fra mappen ukens/.

Hver uke er én tekstfil, for eksempel ukens/2026-44.md. Den nyeste vises på siden,
og de eldre vises under «Tidligere uker». Se ukens/MAL.md for hvordan filen skrives.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROT = Path(__file__).parent
MAPPE = ROT / "ukens"


def les_fil(fil):
    uke = {"fil": fil.stem, "tittel": fil.stem, "lesetips": [], "sporsmal": []}
    del_ = None
    avsnitt = []

    def avslutt_avsnitt():
        if del_ == "sporsmal" and avsnitt:
            uke["sporsmal"].append(" ".join(avsnitt))
        avsnitt.clear()

    for linje in fil.read_text(encoding="utf-8").splitlines():
        l = linje.strip()
        if l.startswith("<!--"):
            continue
        if l.startswith("## "):
            avslutt_avsnitt()
            navn = l[3:].lower()
            del_ = "lesetips" if "lesetips" in navn else "sporsmal" if "spørsmål" in navn or "sporsmal" in navn else None
        elif l.startswith("# "):
            uke["tittel"] = l[2:].strip()
        elif not l:
            avslutt_avsnitt()
        elif del_ == "lesetips" and l.startswith(("-", "*")):
            innhold = l[1:].strip()
            m = re.match(r"(https?://\S+)\s*[|–-]?\s*(.*)", innhold)
            if m:
                uke["lesetips"].append({"lenke": m.group(1), "kommentar": m.group(2).strip()})
        elif del_ == "sporsmal":
            if l.startswith(("-", "*")):
                avslutt_avsnitt()
                uke["sporsmal"].append(l[1:].strip())
            else:
                avsnitt.append(l)
    avslutt_avsnitt()
    return uke


def lag(saker):
    """Returnerer ukene, nyeste først. Lesetips får tittel og kilde fra sakene der lenken finnes."""
    if not MAPPE.exists():
        return []
    kjente = {s["lenke"]: s for s in saker}
    arkiv = ROT / "data" / "arkiv"
    if arkiv.exists():
        for f in arkiv.glob("*.json"):
            for s in json.loads(f.read_text(encoding="utf-8")):
                kjente.setdefault(s["lenke"], s)

    uker = []
    for fil in sorted(MAPPE.glob("*.md"), reverse=True):
        if fil.stem.upper() == "MAL":
            continue
        uke = les_fil(fil)
        for tips in uke["lesetips"]:
            sak = kjente.get(tips["lenke"])
            tips["tittel"] = sak["tittel"] if sak else None
            tips["kilde"] = sak["kilde"] if sak else urlparse(tips["lenke"]).netloc.removeprefix("www.")
        if uke["lesetips"] or uke["sporsmal"]:
            uker.append(uke)
    return uker

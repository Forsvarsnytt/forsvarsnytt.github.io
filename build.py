"""
Forsvarsnytt – henter forsvars- og sikkerhetsnyheter fra RSS-kilder,
sorterer dem etter tema og lager en ferdig nettside i mappen site/.

Kjør:  python build.py
Bruker bare Pythons innebygde biblioteker (Python 3.9 eller nyere).
"""

import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

import mest_omtalt
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROT = Path(__file__).parent
UT = ROT / "site"
OSLO = ZoneInfo("Europe/Oslo")
INTERN = ROT / "intern" / "saker.json"
ATOM = "{http://www.w3.org/2005/Atom}"


# ---------- henting og lesing av RSS/Atom ----------

def hent(url):
    if "://" not in url:  # lokal fil, brukes til testing
        return Path(url).read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "Forsvarsnytt/1.0 (hobbyprosjekt)"})
    with urllib.request.urlopen(req, timeout=20) as svar:
        return svar.read()


def les_dato(tekst):
    if not tekst:
        return None
    tekst = tekst.strip()
    try:
        d = parsedate_to_datetime(tekst)  # RSS-format: "Wed, 28 Oct 2026 18:00:00 +0100"
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(tekst.replace("Z", "+00:00"))  # Atom-format
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


MEDIA = "{http://search.yahoo.com/mrss/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
BILDETYPER = re.compile(r"\.(jpe?g|png|webp|gif)(\?|$)", re.I)


def finn_bilde(el, *tekster):
    """Finner bildet kilden har lagt ved saken (media:content, media:thumbnail, enclosure eller <img>)."""
    kandidater = []
    for m in el.iter(f"{MEDIA}content"):
        if m.get("medium") == "image" or (m.get("type") or "").startswith("image") or BILDETYPER.search(m.get("url", "")):
            kandidater.append((int(m.get("width") or 0), m.get("url")))
    for m in el.iter(f"{MEDIA}thumbnail"):
        kandidater.append((int(m.get("width") or 0), m.get("url")))
    for tag in ("enclosure", f"{ATOM}link"):
        for e in el.findall(tag):
            if (e.get("type") or "").startswith("image"):
                kandidater.append((0, e.get("url") or e.get("href")))
    kandidater = [(b, u) for b, u in kandidater if u and u.startswith("https://")]
    if kandidater:
        passende = [k for k in kandidater if k[0] <= 1200] or kandidater
        return max(passende, key=lambda k: k[0])[1]
    for tekst in tekster:  # bilde inne i selve teksten
        m = re.search(r'<img[^>]+src="(https://[^"]+)"', html.unescape(tekst or ""))
        if m:
            return m.group(1)
    return None


def les_feed(data):
    """Gir en liste med dicts: tittel, lenke, ingress, tid, bilde."""
    rot = ET.fromstring(data)
    saker = []
    for item in rot.iter("item"):  # RSS 2.0
        saker.append({
            "tittel": item.findtext("title"),
            "lenke": (item.findtext("link") or "").strip(),
            "ingress": item.findtext("description"),
            "tid": les_dato(item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date")),
            "bilde": finn_bilde(item, item.findtext("description"), item.findtext(CONTENT)),
        })
    for entry in rot.iter(f"{ATOM}entry"):  # Atom
        lenke = ""
        for l in entry.findall(f"{ATOM}link"):
            if l.get("rel", "alternate") == "alternate":
                lenke = l.get("href", "")
                break
        saker.append({
            "tittel": entry.findtext(f"{ATOM}title"),
            "lenke": lenke,
            "ingress": entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content"),
            "tid": les_dato(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")),
            "bilde": finn_bilde(entry, entry.findtext(f"{ATOM}content"), entry.findtext(f"{ATOM}summary")),
        })
    return saker


# ---------- tekst og temaer ----------

def lag_matcher(ord_liste):
    """Korte ord (≤4 tegn) må matche hele ordet, lengre ord kan være starten av et ord."""
    deler = []
    for o in ord_liste:
        e = re.escape(o.lower())
        deler.append(rf"\b{e}\b" if len(o) <= 4 else rf"\b{e}")
    return re.compile("|".join(deler)) if deler else None


def rens(tekst, maks=700):
    """Fjerner HTML og kutter lange tekster, helst ved slutten av en setning."""
    tekst = html.unescape(tekst or "")
    tekst = re.sub(r"<[^>]+>", " ", tekst)
    tekst = re.sub(r"\s+", " ", tekst).strip()
    if len(tekst) <= maks:
        return tekst
    kutt = tekst[:maks]
    slutt = max(kutt.rfind(". "), kutt.rfind("! "), kutt.rfind("? "))
    if slutt > maks * 0.5:
        return kutt[: slutt + 1]
    return kutt[:-1].rsplit(" ", 1)[0] + "…"


# ---------- hovedprogram ----------

def hent_saker(cfg):
    temaer = cfg["temaer"]
    matchere = {t["id"]: lag_matcher(t["ord"]) for t in temaer}
    sikkerhet = lag_matcher(cfg["sikkerhetsord"])
    grense = datetime.now(timezone.utc) - timedelta(days=cfg["dager_tilbake"])

    saker, sett, status = [], set(), []
    for k in cfg["kilder"]:
        try:
            innhold = les_feed(hent(k["url"]))
        except Exception as feil:  # én kilde som feiler skal ikke stoppe resten
            status.append((k["navn"], f"FEIL: {type(feil).__name__}: {str(feil)[:100]}"))
            continue

        antall = 0
        for e in innhold[: cfg["maks_per_kilde"]]:
            tittel = rens(e["tittel"], 200)
            lenke = e["lenke"]
            if not tittel or not lenke.startswith("http"):
                continue
            nokkel = re.sub(r"\W+", "", tittel.lower())[:80]
            if nokkel in sett:
                continue
            if e["tid"] and e["tid"] < grense:
                continue
            ingress = rens(e["ingress"])
            tekst = f"{tittel} {ingress}".lower()

            treff = {tid: len(m.findall(tekst)) for tid, m in matchere.items() if m}
            beste = max(treff, key=treff.get) if treff and max(treff.values()) > 0 else None
            if k["filter"] and not beste and not sikkerhet.search(tekst):
                continue  # generell kilde, men ikke en forsvars-/sikkerhetssak

            sett.add(nokkel)
            saker.append({
                "tittel": tittel,
                "ingress": ingress,
                "lenke": lenke,
                "kilde": k["navn"],
                "tema": beste or k["tema"],
                "bilde": e["bilde"],
                # vises bare når kilden har gitt lov (se feeds.json)
                "vis_ingress": bool(k.get("vis_ingress")),
                "vis_bilde": bool(k.get("vis_bilder")),
                "tid": e["tid"].astimezone(timezone.utc).isoformat() if e["tid"] else None,
            })
            antall += 1
        status.append((k["navn"], f"{antall} saker"))

    saker.sort(key=lambda s: s["tid"] or "", reverse=True)
    for navn, s in status:
        print(f"  {navn:20} {s}")
    if not saker:
        sys.exit("Ingen saker hentet – sjekk kildene i feeds.json")
    return saker


def til_js(data):
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def offentlig(s):
    """Det som faktisk publiseres: overskrift, lenke, kilde, tema og tid.
    Ingress og bilde tas bare med fra kilder som har gitt lov."""
    return {
        "tittel": s["tittel"], "lenke": s["lenke"], "kilde": s["kilde"], "tema": s["tema"], "tid": s["tid"],
        "ingress": s["ingress"] if s.get("vis_ingress") else "",
        "bilde": s["bilde"] if s.get("vis_bilde") else None,
    }


def main():
    cfg = json.loads((ROT / "feeds.json").read_text(encoding="utf-8"))
    UT.mkdir(exist_ok=True)
    INTERN.parent.mkdir(exist_ok=True)

    if "--bare-side" in sys.argv:  # bruk sakene som allerede er hentet, bare lag siden på nytt
        saker = json.loads(INTERN.read_text(encoding="utf-8"))
    else:
        saker = hent_saker(cfg)
        # full versjon lagres bare lokalt under kjøringen (brukes til sortering/oppsummering), publiseres aldri
        INTERN.write_text(json.dumps(saker, ensure_ascii=False), encoding="utf-8")
    saker = [offentlig(s) for s in saker]
    repo = os.environ.get("GITHUB_REPOSITORY")
    kontakt = f"https://github.com/{repo}/issues" if repo else "#"

    # mest omtalte saker (gratis, uten AI)
    opps = mest_omtalt.lag(saker, datetime.now(OSLO))

    # AI-oppsummeringer tar over der de finnes og er ferske
    opps_fil = ROT / "data" / "oppsummeringer.json"
    if opps_fil.exists():
        lagret = json.loads(opps_fil.read_text(encoding="utf-8"))
        idag = datetime.now(OSLO).date()
        ai = {"dag": (lagret.get("dager") or [None])[-1], "uke": lagret.get("uke"), "maaned": lagret.get("maaned")}
        maks_alder = {"dag": 2, "uke": 8, "maaned": 32}
        for t, o in ai.items():
            if o and (idag - datetime.fromisoformat(o["laget"]).date()).days <= maks_alder[t]:
                opps[t] = o

    mal = (ROT / "mal.html").read_text(encoding="utf-8")
    nå = datetime.now(OSLO).strftime("%d.%m.%Y kl. %H:%M")
    side = (mal
            .replace("/*DATA*/null", til_js(saker))
            .replace("/*OPPS*/null", til_js(opps))
            .replace("/*TEMAER*/null", til_js([{"id": t["id"], "navn": t["navn"]} for t in cfg["temaer"]]))
            .replace("{{OPPDATERT}}", nå)
            .replace("{{KONTAKT}}", kontakt))
    (UT / "index.html").write_text(side, encoding="utf-8")
    print(f"Laget site/index.html med {len(saker)} saker")


if __name__ == "__main__":
    main()

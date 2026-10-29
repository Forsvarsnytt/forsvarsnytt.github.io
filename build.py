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
import ukens
import konflikter
import norgeskart
import landinfo
import undersider
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
    if maks is None or len(tekst) <= maks:
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
    # temaord teller også i filteret, unntatt helt generelle ord (f.eks. «Norway»)
    generelle = set(cfg.get("generelle_ord", []))
    filterord = lag_matcher([o for t in temaer for o in t["ord"] if o not in generelle]) or re.compile("(?!)")
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
            tittel = rens(e["tittel"], None)  # titler skal aldri endres eller kortes ned
            lenke = e["lenke"]
            if not tittel or not lenke.startswith("http"):
                continue
            nokkel = re.sub(r"\W+", "", tittel.lower())[:80]
            if nokkel in sett:
                continue
            if e["tid"] and e["tid"] < grense:
                continue
            if e["tid"] and e["tid"] > datetime.now(timezone.utc):
                e["tid"] = datetime.now(timezone.utc)  # saker datert fram i tid (f.eks. varslede arrangementer) vises som nye
            ingress = rens(e["ingress"], None if k.get("vis_ingress") else 700)  # tillatt ingress vises uendret
            tekst = f"{tittel} {ingress}".lower()

            treff = {tid: len(m.findall(tekst)) for tid, m in matchere.items() if m}
            beste = max(treff, key=treff.get) if treff and max(treff.values()) > 0 else None
            if k["filter"] and not sikkerhet.search(tekst) and not filterord.search(tekst):
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
                "kreditering": k.get("kreditering"),  # kildens krav til kreditering, f.eks. BBC
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


def les_ordliste():
    """Leser ordliste.txt: «FORKORTELSE = forklaring», grupper med «## Navn»."""
    fil = ROT / "ordliste.txt"
    grupper, gruppe = [], None
    if not fil.exists():
        return grupper
    for linje in fil.read_text(encoding="utf-8").splitlines():
        l = linje.strip()
        if l.startswith("## "):
            gruppe = {"navn": l[3:].strip(), "ord": []}
            grupper.append(gruppe)
        elif l and not l.startswith("#") and "=" in l:
            kort, lang = (d.strip() for d in l.split("=", 1))
            if gruppe is None:
                gruppe = {"navn": "Forkortelser", "ord": []}
                grupper.append(gruppe)
            gruppe["ord"].append({"kort": kort, "lang": lang})
    return grupper


TIDSLINJE_KATEGORIER = {"ukraina": "Ukraina-krigen", "nato": "NATO og allianser", "norge": "Norge",
                         "midtosten": "Midtøsten", "afrika": "Afrika", "verden": "Verden"}


def les_tidslinje():
    """Leser tidslinje.txt: «## ÅÅÅÅ-MM-DD | kategori | Overskrift», tekst og «kilde: Navn | lenke»."""
    fil = ROT / "tidslinje.txt"
    hendelser, h = [], None
    if not fil.exists():
        return hendelser
    for linje in fil.read_text(encoding="utf-8").splitlines():
        l = linje.strip()
        if l.startswith("## "):
            deler = [d.strip() for d in l[3:].split("|")]
            if len(deler) == 3 and re.match(r"\d{4}-\d{2}-\d{2}$", deler[0]):
                h = {"dato": deler[0], "kategori": deler[1].lower() if deler[1].lower() in TIDSLINJE_KATEGORIER else "verden",
                     "tittel": deler[2], "tekst": "", "kilde": None}
                hendelser.append(h)
            else:
                h = None
        elif h is not None and l and not l.startswith("#"):
            if l.lower().startswith("kilde:"):
                navn, _, lenke = l[6:].partition("|")
                lenke = lenke.strip()
                if lenke.startswith("http"):
                    h["kilde"] = {"navn": navn.strip(), "lenke": lenke}
            else:
                h["tekst"] = (h["tekst"] + " " + l).strip()
    return sorted(hendelser, key=lambda h: h["dato"])


def til_js(data):
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def offentlig(s):
    """Det som faktisk publiseres: overskrift, lenke, kilde, tema og tid.
    Ingress og bilde tas bare med fra kilder som har gitt lov."""
    return {
        "tittel": s["tittel"], "lenke": s["lenke"], "kilde": s["kilde"], "tema": s["tema"], "tid": s["tid"],
        "ingress": s["ingress"] if s.get("vis_ingress") else "",
        "bilde": s["bilde"] if s.get("vis_bilde") else None,
        "kreditering": s.get("kreditering"),
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
    # arkivet skal bare inneholde saker fra kilder som fortsatt er i bruk, og som passerer filteret
    kilder = {k["navn"]: k for k in cfg["kilder"]}
    def beholdes(s):
        return s["kilde"] in kilder
    opps = mest_omtalt.lag(saker, datetime.now(OSLO), beholdes)
    uker = ukens.lag(saker)  # «Ukens hjørne» fra mappen ukens/
    konfliktliste, kart = konflikter.lag(saker)  # konfliktkartet fra konflikter.txt
    norge = norgeskart.lag(saker)  # Norgeskartet fra forsvaret-steder.txt
    land = landinfo.lag(saker, kart or {})  # landbeskrivelser i konfliktkartet fra land.txt

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

    # tilbakemeldingsknappen: egen lenke fra feeds.json (f.eks. et skjema), ellers et nytt GitHub-innspill
    tilbakemelding = cfg.get("tilbakemelding_url") or (f"https://github.com/{repo}/issues/new?title=Tilbakemelding" if repo else "#")

    mal = (ROT / "mal.html").read_text(encoding="utf-8")
    nå = datetime.now(OSLO).strftime("%d.%m.%Y kl. %H:%M")
    epost = til_js(cfg["kontakt_epost"][::-1] if cfg.get("kontakt_epost") else None)

    # temasider fra mappen sider/: samme stil og banner som forsiden
    stil = re.search(r"<style>(.*?)</style>", mal, re.S).group(1)
    banner = re.search(r'<header class="banner">(.*?)<div class="banner-innhold">', mal, re.S).group(1)
    banner = re.sub(r'<button class="banner-pause".*?</button>', "", banner, flags=re.S)
    sidetitler = []

    def meny(aktiv):
        lenker = [("./", "Forsiden")] + sidetitler
        deler = []
        for f, t in lenker:
            gjeldende = ' aria-current="page"' if f == aktiv else ""
            deler.append(f'<a href="{f}"{gjeldende}>{html.escape(t)}</a>')
        return '<nav class="temameny" aria-label="Sider"><div>' + "".join(deler) + "</div></nav>"

    def sett_meny(liste):
        sidetitler[:] = liste

    # kildenes krav til kreditering (f.eks. «Fra BBC News»), slik at det kan vises overalt der sakene dukker opp
    kreditering = {k["navn"]: k["kreditering"] for k in cfg["kilder"] if k.get("kreditering")}

    felles = {"meny": meny, "sett_meny": sett_meny, "topp": banner, "oppdatert": nå, "kontakt": "#", "epost": epost,
              "kreditering": kreditering}
    side_mal = (ROT / "side-mal.html").read_text(encoding="utf-8") if (ROT / "side-mal.html").exists() else None
    if side_mal:
        _, temasider = undersider.lag(saker, side_mal, stil, felles)
        for filnavn, innhold in temasider.items():
            (UT / filnavn).write_text(innhold, encoding="utf-8")
        print(f"Laget {len(temasider)} temasider: {', '.join(temasider)}")

    side = (mal
            .replace("{{TEMAMENY}}", meny("./"))
            .replace("/*KREDITERING*/null", til_js(kreditering))
            .replace("/*DATA*/null", til_js(saker))
            .replace("/*OPPS*/null", til_js(opps))
            .replace("/*UKER*/null", til_js(uker))
            .replace("/*KONFLIKTER*/null", til_js(konfliktliste))
            .replace("/*KART*/null", til_js(kart))
            .replace("/*NORGE*/null", til_js(norge))
            .replace("/*LAND*/null", til_js(land))
            .replace("/*TIDSLINJE*/null", til_js({"hendelser": les_tidslinje(), "kategorier": TIDSLINJE_KATEGORIER}))
            .replace("/*ORDLISTE*/null", til_js(les_ordliste()))
            .replace("{{TILBAKEMELDING}}", tilbakemelding)
            .replace("/*TEMAER*/null", til_js([{"id": t["id"], "navn": t["navn"]} for t in cfg["temaer"]]))
            .replace("{{OPPDATERT}}", nå)
            .replace("{{KONTAKT}}", kontakt)
            .replace("/*EPOST*/null", epost))
    (UT / "index.html").write_text(side, encoding="utf-8")
    print(f"Laget site/index.html med {len(saker)} saker")


if __name__ == "__main__":
    main()

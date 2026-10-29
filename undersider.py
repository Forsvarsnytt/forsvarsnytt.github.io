"""
Forsvarsnytt – temasider (teknologi, langtidsplanen, beredskap …).

Hver side er en tekstfil i mappen sider/, skrevet i et enkelt format:

  # Sidetittel                      tittel øverst på siden
  > Ingress                         kort innledning
  ## Seksjon / ### Underoverskrift  overskrifter
  vanlig tekst                      avsnitt (tom linje skiller avsnitt)
  - punkt                           punktliste
  [ ] punkt                         sjekkliste (leseren kan krysse av, huskes i nettleseren)
  !! 600 mrd | forklaring           nøkkeltall (flere etter hverandre blir en rad)
  @ 2022-06 | Tittel | tekst | Kildenavn | https://lenke    hendelse i en tidslinje
  kilde: Navn | https://lenke       kildelenke
  :::merknad tekst                  uthevet merknad
  :::nyheter ord1, ord2, ...        siste saker fra Forsvarsnytt som inneholder ordene (oppdateres automatisk)

I tekst kan du skrive **fet tekst** og [lenketekst](https://lenke).
Linjer som starter med # og et mellomrom etter to tegn (#! eller #-) regnes ikke som kommentarer;
kommentarer skrives som <!-- ... -->.
"""

import html
import json
import re
from pathlib import Path

ROT = Path(__file__).parent
MAPPE = ROT / "sider"
MND = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
       "september", "oktober", "november", "desember"]


def inline(tekst):
    t = html.escape(tekst, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               lambda m: f'<a href="{html.escape(m.group(2))}" target="_blank" rel="noopener">{m.group(1)}</a>', t)
    return t


def lenke(navn, url):
    return f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(navn)} ↗</a>'


def slug(tekst):
    t = tekst.lower().replace("æ", "ae").replace("ø", "o").replace("å", "a")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def kjente_saker(saker):
    alle = {s["lenke"]: s for s in saker}
    arkiv = ROT / "data" / "arkiv"
    if arkiv.exists():
        for f in arkiv.glob("*.json"):
            for s in json.loads(f.read_text(encoding="utf-8")):
                alle.setdefault(s["lenke"], s)
    return sorted(alle.values(), key=lambda s: s.get("tid") or "", reverse=True)


def nyhetsblokk(ord_, alle, maks=10):
    m = re.compile(r"\b(" + "|".join(re.escape(o) for o in ord_) + r")\b", re.I)
    treff = [s for s in alle if m.search(s["tittel"] + " " + (s.get("ingress") or ""))][:maks]
    if not treff:
        return '<div class="u-tom">Ingen saker om dette ennå. Lista fylles automatisk når kildene skriver om temaet.</div>'
    rader = []
    for s in treff:
        dato = ""
        if s.get("tid"):
            a, mnd, d = s["tid"][:10].split("-")
            dato = f" · {int(d)}. {MND[int(mnd) - 1]}"
        rader.append(f'<li><a href="{html.escape(s["lenke"])}" target="_blank" rel="noopener">{html.escape(s["tittel"])}</a>'
                     f'<small>{html.escape(s["kilde"])}{dato}</small></li>')
    return '<ul class="u-nyheter">' + "".join(rader) + "</ul>"


def render(fil, alle):
    """Gjør en tekstfil om til (tittel, ingress, html, innholdsfortegnelse)."""
    linjer = re.sub(r"<!--.*?-->", "", fil.read_text(encoding="utf-8"), flags=re.S).splitlines()
    ut, toc, tittel, ingress = [], [], fil.stem, ""
    i = 0
    avsnitt = []

    def tom_avsnitt():
        if avsnitt:
            ut.append("<p>" + inline(" ".join(avsnitt)) + "</p>")
            avsnitt.clear()

    while i < len(linjer):
        l = linjer[i].strip()
        if not l:
            tom_avsnitt(); i += 1; continue
        if l.startswith("# "):
            tom_avsnitt(); tittel = l[2:].strip()
        elif l.startswith("> "):
            tom_avsnitt(); ingress = l[2:].strip()
        elif l.startswith("## "):
            tom_avsnitt(); t = l[3:].strip(); toc.append((slug(t), t))
            ut.append(f'<h2 id="{slug(t)}">{inline(t)}</h2>')
        elif l.startswith("### "):
            tom_avsnitt(); ut.append(f"<h3>{inline(l[4:].strip())}</h3>")
        elif l.startswith("- "):
            tom_avsnitt(); punkter = []
            while i < len(linjer) and linjer[i].strip().startswith("- "):
                punkter.append("<li>" + inline(linjer[i].strip()[2:]) + "</li>"); i += 1
            ut.append("<ul>" + "".join(punkter) + "</ul>"); continue
        elif l.startswith("[ ] "):
            tom_avsnitt(); punkter = []
            while i < len(linjer) and linjer[i].strip().startswith("[ ] "):
                tekst = linjer[i].strip()[4:]
                nokkel = slug(fil.stem + "-" + tekst)[:80]
                punkter.append(f'<li><label><input type="checkbox" data-nokkel="{nokkel}"><span>{inline(tekst)}</span></label></li>'); i += 1
            ut.append('<ul class="u-sjekk">' + "".join(punkter) + "</ul>"); continue
        elif l.startswith("!! "):
            tom_avsnitt(); fliser = []
            while i < len(linjer) and linjer[i].strip().startswith("!! "):
                tall, _, tekst = linjer[i].strip()[3:].partition("|")
                fliser.append(f'<div class="u-flis"><b>{inline(tall.strip())}</b><span>{inline(tekst.strip())}</span></div>'); i += 1
            ut.append('<div class="u-fliser">' + "".join(fliser) + "</div>"); continue
        elif l.startswith("@ "):
            tom_avsnitt(); rader = []
            while i < len(linjer) and linjer[i].strip().startswith("@ "):
                d = [x.strip() for x in linjer[i].strip()[2:].split("|")]
                if len(d) >= 5:
                    dato, tit, tekst, knavn, kurl = d[:5]
                    a, _, mnd = dato.partition("-")
                    vis = f"{MND[int(mnd) - 1]} {a}" if mnd else a
                    rader.append(f'<div class="u-hend"><div class="u-dato">{html.escape(vis)}</div><h3>{inline(tit)}</h3>'
                                 f'<p>{inline(tekst)}</p><div class="u-kilde">Kilde: {lenke(knavn, kurl)}</div></div>')
                i += 1
            ut.append('<div class="u-tid">' + "".join(rader) + "</div>"); continue
        elif l.lower().startswith("kilde:"):
            tom_avsnitt(); navn, _, url = l[6:].partition("|")
            if url.strip().startswith("http"):
                ut.append(f'<div class="u-kilde">Kilde: {lenke(navn.strip(), url.strip())}</div>')
        elif l.startswith(":::merknad"):
            tom_avsnitt(); ut.append(f'<div class="u-merknad">{inline(l[10:].strip())}</div>')
        elif l.startswith(":::nyheter"):
            tom_avsnitt(); ord_ = [o.strip() for o in l[10:].split(",") if o.strip()]
            ut.append(nyhetsblokk(ord_, alle))
        else:
            avsnitt.append(l)
        i += 1
    tom_avsnitt()
    return tittel, ingress, "\n".join(ut), toc


def lag(saker, mal_html, stil, felles):
    """Lager én HTML-side per tekstfil i sider/. Returnerer [(filnavn, tittel)] for menyen."""
    if not MAPPE.exists():
        return [], {}
    alle = kjente_saker(saker)
    sider = []
    for fil in sorted(MAPPE.glob("*.txt")):
        tittel, ingress, innhold, toc = render(fil, alle)
        sider.append((re.sub(r"^\d+-", "", fil.stem) + ".html", tittel, ingress, innhold, toc))  # «1-teknologi.txt» → teknologi.html
    meny = [(f, t) for f, t, *_ in sider]
    felles["sett_meny"](meny)  # menyen må kjenne alle sidene før sidene lages
    resultat = {}
    for filnavn, tittel, ingress, innhold, toc in sider:
        toc_html = "".join(f'<a href="#{s}">{html.escape(t)}</a>' for s, t in toc)
        side = (mal_html
                .replace("{{STIL}}", stil)
                .replace("{{TITTEL}}", html.escape(tittel))
                .replace("{{INGRESS}}", inline(ingress))
                .replace("{{INNHOLD}}", innhold)
                .replace("{{TOC}}", toc_html)
                .replace("{{MENY}}", felles["meny"](filnavn))
                .replace("{{FELLES_TOPP}}", felles["topp"])
                .replace("{{OPPDATERT}}", felles["oppdatert"])
                .replace("{{KONTAKT}}", felles["kontakt"])
                .replace("/*EPOST*/null", felles["epost"]))
        resultat[filnavn] = side
    return meny, resultat

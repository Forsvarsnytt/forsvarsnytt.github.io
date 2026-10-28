"""
Forsvarsnytt – lager oppsummeringer av de viktigste sakene med Claude.

  python oppsummer.py dag      dagens viktigste saker (fra site/saker.json)
  python oppsummer.py uke      ukens viktigste, bygget på dagsoppsummeringene
  python oppsummer.py maaned   månedens viktigste, bygget på dagsoppsummeringene
  python oppsummer.py alle     alle tre
  python oppsummer.py auto     dag hver gang, uke på søndager, måned siste dag i måneden

Krever miljøvariabelen ANTHROPIC_API_KEY. Resultatet lagres i data/oppsummeringer.json.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROT = Path(__file__).parent
DATA = ROT / "data" / "oppsummeringer.json"
SAKER = ROT / "intern" / "saker.json"  # lokal fil fra build.py, publiseres ikke
OSLO = ZoneInfo("Europe/Oslo")
MAKS_TEGN = 200_000  # holder hvert kall godt under 100 000 tokens

MANEDER = ["januar", "februar", "mars", "april", "mai", "juni", "juli",
           "august", "september", "oktober", "november", "desember"]
UKEDAGER = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]

SYSTEM = """Du er redaktør for Forsvarsnytt, en nyhetsoversikt for norske offiserskadetter \
og andre som følger forsvar og sikkerhetspolitikk.

Du får en nummerert liste med nyhetssaker. Velg ut de viktigste sett fra et norsk forsvars- og \
sikkerhetsperspektiv: hendelser som påvirker Norges sikkerhet, NATO, krigen i Ukraina, \
nordområdene, store konflikter og viktige endringer i verdens militære styrker. \
Slå sammen saker som handler om samme hendelse.

Regler:
- Skriv på norsk bokmål, nøkternt og saklig, med egne ord. Ikke kopier formuleringer fra sakene.
- Bruk bare informasjon som står i sakene. Ikke legg til fakta, tall eller vurderinger du ikke har grunnlag for.
- Er noe uklart eller omstridt i kildene, si det.
- Svar KUN med JSON, uten forklaring rundt, på dette formatet:
{"ingress": "2–3 setninger om det overordnede bildet",
 "punkter": [{"tittel": "kort overskrift", "tekst": "2–3 setninger", "tema": "temaid", "kilder": [1, 4]}]}
"kilder" er numrene på sakene punktet bygger på. Gyldige temaid: {temaer}."""


# ---------- hjelpefunksjoner ----------

def les_json(sti, standard):
    try:
        return json.loads(sti.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return standard


def norsk_dato(d):
    return f"{UKEDAGER[d.weekday()]} {d.day}. {MANEDER[d.month - 1]}"


def kall_claude(system, tekst, modell):
    nokkel = os.environ.get("ANTHROPIC_API_KEY")
    body = json.dumps({
        "model": modell,
        "max_tokens": 3000,
        "system": system,
        "messages": [{"role": "user", "content": tekst}],
    }).encode()
    req = urllib.request.Request(
        os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages", data=body, method="POST",
        headers={"x-api-key": nokkel, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as svar:
            data = json.loads(svar.read())
    except urllib.error.HTTPError as feil:
        sys.exit(f"Feil fra Claude API ({feil.code}): {feil.read().decode()[:500]}")
    svartekst = "".join(b.get("text", "") for b in data.get("content", []))
    bruk = data.get("usage", {})
    print(f"  tokens inn: {bruk.get('input_tokens')}, ut: {bruk.get('output_tokens')}")
    start, slutt = svartekst.find("{"), svartekst.rfind("}")
    if start < 0 or slutt < 0:
        sys.exit(f"Fant ikke JSON i svaret:\n{svartekst[:500]}")
    return json.loads(svartekst[start: slutt + 1])


def rydd(svar, lenker_for, gyldige_temaer):
    """Sjekker svaret fra Claude og bytter saksnummer med ekte lenker."""
    punkter = []
    for p in svar.get("punkter", [])[:12]:
        if not isinstance(p, dict) or not p.get("tittel") or not p.get("tekst"):
            continue
        lenker, sett = [], set()
        for n in p.get("kilder", []):
            for l in lenker_for.get(n, []) if isinstance(n, int) else []:
                if l["lenke"] not in sett:
                    sett.add(l["lenke"])
                    lenker.append(l)
        punkter.append({
            "tittel": str(p["tittel"]).strip(),
            "tekst": str(p["tekst"]).strip(),
            "tema": p.get("tema") if p.get("tema") in gyldige_temaer else None,
            "lenker": lenker[:6],
        })
    if not punkter:
        sys.exit("Svaret inneholdt ingen gyldige punkter.")
    return {"ingress": str(svar.get("ingress", "")).strip(), "punkter": punkter}


# ---------- de tre typene ----------

def lag_dag(cfg, temaer, nå):
    saker = les_json(SAKER, [])
    grense = nå - timedelta(hours=24)
    aktuelle = [s for s in saker if s["tid"] and datetime.fromisoformat(s["tid"]) >= grense]
    if len(aktuelle) < 3:
        print("  for få saker siste døgn – hopper over")
        return None
    linjer, lenker_for, tegn = [], {}, 0
    for i, s in enumerate(aktuelle, 1):
        linje = f"[{i}] ({s['tema']}, {s['kilde']}) {s['tittel']} — {s['ingress'][:250]}"
        tegn += len(linje)
        if tegn > MAKS_TEGN:
            break
        linjer.append(linje)
        lenker_for[i] = [{"kilde": s["kilde"], "lenke": s["lenke"]}]
    print(f"  {len(linjer)} saker fra siste døgn")
    instruks = "Velg 5–8 viktigste saker fra siste døgn.\n\n" + "\n".join(linjer)
    svar = kall_claude(SYSTEM.replace("{temaer}", ", ".join(temaer)), instruks, cfg["ai_modell"])
    res = rydd(svar, lenker_for, temaer)
    res.update({"type": "dag", "dato": nå.date().isoformat(),
                "periode": norsk_dato(nå).capitalize(), "laget": nå.isoformat()})
    return res


def lag_periode(type_, cfg, temaer, nå, dager):
    if type_ == "uke":
        start = (nå - timedelta(days=nå.weekday())).date()
        slutt = start + timedelta(days=6)
        uke = start.isocalendar()[1]
        periode = f"Uke {uke} ({start.day}. {MANEDER[start.month-1][:3]} – {slutt.day}. {MANEDER[slutt.month-1][:3]})"
        antall = "6–10"
    else:
        start = nå.date().replace(day=1)
        slutt = nå.date()
        periode = f"{MANEDER[nå.month - 1].capitalize()} {nå.year}"
        antall = "8–12"
    utvalg = [d for d in dager if start.isoformat() <= d["dato"] <= slutt.isoformat()]
    if not utvalg:
        print("  ingen dagsoppsummeringer i perioden – hopper over")
        return None
    linjer, lenker_for, n = [], {}, 0
    for d in sorted(utvalg, key=lambda d: d["dato"]):
        for p in d["punkter"]:
            n += 1
            linjer.append(f"[{n}] {d['periode']}: {p['tittel']} — {p['tekst']}")
            lenker_for[n] = p["lenker"]
    print(f"  bygger på {len(utvalg)} dagsoppsummeringer ({n} punkter)")
    instruks = (f"Under er dagsoppsummeringer fra perioden {periode}. Lag en samlet oppsummering "
                f"med de {antall} viktigste sakene og utviklingstrekkene i perioden.\n\n" + "\n".join(linjer))
    svar = kall_claude(SYSTEM.replace("{temaer}", ", ".join(temaer)), instruks, cfg["ai_modell"])
    res = rydd(svar, lenker_for, temaer)
    res.update({"type": type_, "periode": periode, "laget": nå.isoformat(),
                "grunnlag": f"Bygget på {len(utvalg)} dagsoppsummeringer"})
    return res


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Ingen ANTHROPIC_API_KEY – hopper over AI-oppsummering (siden viser «mest omtalt» i stedet).")
        return
    hva = sys.argv[1] if len(sys.argv) > 1 else "auto"
    cfg = json.loads((ROT / "feeds.json").read_text(encoding="utf-8"))
    cfg.setdefault("ai_modell", "claude-haiku-5-5")
    temaer = [t["id"] for t in cfg["temaer"]]
    nå = datetime.now(OSLO)

    if hva == "auto":
        typer = ["dag"]
        if nå.weekday() == 6:
            typer.append("uke")
        if (nå + timedelta(days=1)).month != nå.month:
            typer.append("maaned")
    elif hva == "alle":
        typer = ["dag", "uke", "maaned"]
    elif hva in ("dag", "uke", "maaned"):
        typer = [hva]
    else:
        sys.exit(f"Ukjent valg: {hva}")

    data = les_json(DATA, {"dager": [], "uke": None, "maaned": None})
    for t in typer:
        print(f"Lager {t}-oppsummering …")
        if t == "dag":
            res = lag_dag(cfg, temaer, nå)
            if res:
                data["dager"] = [d for d in data["dager"] if d["dato"] != res["dato"]] + [res]
                data["dager"] = sorted(data["dager"], key=lambda d: d["dato"])[-62:]
        else:
            res = lag_periode(t, cfg, temaer, nå, data["dager"])
            if res:
                data[t] = res

    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Lagret data/oppsummeringer.json")


if __name__ == "__main__":
    main()

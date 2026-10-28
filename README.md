# Forsvarsnytt

Nettsiden ligger på **https://forsvarsnytt.github.io**.

En nettside som samler forsvars- og sikkerhetsnyheter fra Norge og verden på ett sted, sortert etter tema: Norge, Ukraina, Nordområdene og NATO, Afrika, Midtøsten, Verdens styrker og Verden ellers.

Siden oppdateres automatisk hver time og ligger gratis på GitHub Pages.

## Filene

| Fil | Hva den gjør |
|---|---|
| `feeds.json` | Kildene (RSS-strømmer) og nøkkelordene som avgjør tema. **Her gjør du de fleste endringer.** |
| `build.py` | Henter nyhetene, filtrerer og sorterer dem, og lager `site/index.html`. |
| `mal.html` | Utseendet på nettsiden (farger, layout, faner og søk). |
| `.github/workflows/oppdater.yml` | Får GitHub til å kjøre `build.py` hver time og publisere siden. |

## Slik får du siden på nett (ca. 15 minutter)

1. **Lag en GitHub-konto** på github.com hvis du ikke har en.
2. **Lag et nytt repository**: trykk «New», kall det for eksempel `forsvarsnytt`, velg **Public** og trykk «Create repository».
3. **Last opp filene**: trykk «uploading an existing file» og dra inn hele innholdet i mappen, også `.github`-mappen. Trykk «Commit changes».
   - Hvis `.github`-mappen ikke blir med (skjulte mapper kan forsvinne ved opplasting): velg «Add file → Create new file», skriv `.github/workflows/oppdater.yml` som filnavn, og lim inn innholdet fra filen.
4. **Slå på GitHub Pages**: gå til **Settings → Pages**, og under «Source» velger du **GitHub Actions**.
5. **Kjør første oppdatering**: gå til fanen **Actions**, velg «Oppdater Forsvarsnytt» og trykk **Run workflow**.
6. Etter et par minutter ligger siden på `https://<organisasjonsnavn>.github.io` (repoet må hete `<organisasjonsnavn>.github.io`).

## Sjekk at kildene virker

Noen RSS-adresser endrer seg over tid. Åpne den siste kjøringen under **Actions → bygg → python build.py**. Der står det hvor mange saker hver kilde ga:

```
  Kyiv Independent     24 saker
  Forsvarets forum     FEIL: HTTPError: HTTP Error 404: Not Found
```

Står det `FEIL`, er adressen feil eller kilden blokkerer automatisk henting. Søk etter «<kildenavn> RSS» og bytt adressen i `feeds.json`, eller fjern kilden.

## Gjøre endringer

- **Legge til en kilde**: legg til en linje under `"kilder"` i `feeds.json`. Bruk `"filter": true` for generelle nyhetskilder (da tas bare sikkerhetsrelaterte saker med) og `"filter": false` for rene forsvarskilder.
- **Forbedre temasorteringen**: legg til ord under `"temaer"`. En sak havner i temaet med flest treff. Uten treff havner den i kildens standardtema.
- **Nytt tema**: legg til et nytt tema med `id`, `navn` og `ord`. Fanen dukker opp av seg selv.
- **Endre utseende**: farger og skrift ligger øverst i `mal.html`.

Du kan redigere filene rett i GitHub i nettleseren (blyant-ikonet). Siden bygges på nytt hver gang du lagrer.

## Mest omtalt og oppsummeringer

Øverst på siden vises **mest omtalte saker** siste døgn, uke og måned. Det er hendelser som flere kilder skriver om samtidig, og det er gratis og automatisk (`mest_omtalt.py`). For å kunne vise uke og måned lagres et lite arkiv i `data/arkiv/`, én fil per dag. Arkivet lagres i repoet hver kveld.

**AI-oppsummeringer (valgfritt):** Legger du inn en API-nøkkel fra console.anthropic.com som secret med navnet `ANTHROPIC_API_KEY` (Settings → Secrets and variables → Actions), skriver Claude en oppsummering på norsk hver kveld (`oppsummer.py`). Den erstatter «mest omtalt» automatisk. Modellen velges med `ai_modell` i `feeds.json`.

## Teste på egen maskin (valgfritt)

Krever Python 3.9 eller nyere, ingen ekstra pakker.

```
python build.py
```

Åpne så `site/index.html` i nettleseren.

## Opphavsrett og regler

- **Som standard publiseres bare overskrift, kilde, tidspunkt og lenke.** Overskrifter og lenker regnes normalt ikke som gjengivelse av verket, og EUs opphavsrettsdirektiv (artikkel 15) gjør uttrykkelig unntak for lenker og svært korte utdrag.
- **Ingress og bilder fra kildene vises ikke**, fordi de er vernet og flere kilder forbyr gjenbruk i vilkårene sine. Vil du vise dem for en kilde, må kilden ha gitt tillatelse eller ha en åpen lisens. Da settes `"vis_ingress": true` og/eller `"vis_bilder": true` på kilden i `feeds.json`, sammen med `"tillatelse": "<hvor tillatelsen står>"`.
- **Sjekk vilkårene før du legger til en ny kilde.** Står det at innhold ikke kan brukes på andre nettsider, eller at automatisk innhenting er forbudt, skal kilden ikke brukes. Al Jazeera og Defense News er tatt ut av denne grunnen.
- Illustrasjonene på siden er tegnet for siden og kan brukes fritt.
- Bunnen av siden har en kontaktlenke, slik at utgivere kan be om endringer. Slike henvendelser skal følges opp raskt.
- Bruk bare åpne kilder, og aldri informasjon du har fått gjennom tjenesten.

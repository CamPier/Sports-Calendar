# 🏀 Basketball Calendar

Calendari **ICS** aggiornati automaticamente per seguire NBA, EuroLeague, EuroCup e Lega Basket (LBA) direttamente in Google Calendar, Apple Calendar o Outlook.

> **Demo live:** `https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO/`

---

## Calendari disponibili

| Liga | URL abbonamento | Download |
|------|----------------|---------|
| 🏀 NBA 2025-26 | `…/nba.ics` | [nba.ics](docs/nba.ics) |
| 🇪🇺 EuroLeague + EuroCup 2025-26 | `…/euroleague.ics` | [euroleague.ics](docs/euroleague.ics) |
| 🇮🇹 LBA Legabasket 2025-26 | `…/lba.ics` | [lba.ics](docs/lba.ics) |
| ⭐ Tutto insieme | `…/all.ics` | [all.ics](docs/all.ics) |

---

## Come abbonare il calendario

### Google Calendar
1. Apri [Google Calendar](https://calendar.google.com)
2. Clicca **"+"** accanto a *Altri calendari* → **Da URL**
3. Incolla l'URL del file `.ics` che vuoi
4. Clicca **Aggiungi calendario**

### Apple Calendar
`File → Nuovo abbonamento calendario → incolla URL → Aggiungi`

### Outlook
`Aggiungi calendario → Da Internet → incolla URL → Importa`

---

## Come funziona

```
GitHub Actions (2×/giorno)
       │
       ▼
   src/main.py
   ├── fetchers/nba.py        → cdn.nba.com/static/json/…
   ├── fetchers/euroleague.py → api-live.euroleague.net
   └── fetchers/lba.py        → legabasket.it
       │
       ▼
  calendar_generator.py → genera file .ics
       │
       ▼
  docs/*.ics   ← serviti via GitHub Pages
```

Il workflow GitHub Actions gira **due volte al giorno** (05:00 e 13:00 UTC) e aggiorna i file ICS solo se ci sono cambiamenti.  
I file sono serviti da **GitHub Pages** — gli URL rimangono stabili, così il tuo calendario si aggiorna da solo.

---

## Installazione locale

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO.git
cd YOUR_REPO
pip install -r requirements.txt
python src/main.py
# → I file .ics vengono scritti in docs/
```

---

## Deploy su GitHub (passo per passo)

### 1. Crea il repo su GitHub

```bash
git init
git add .
git commit -m "feat: initial basketball calendar"
gh repo create YOUR_REPO --public --push --source .
```

### 2. Abilita GitHub Pages

Vai su **Settings → Pages → Source: Deploy from a branch → `main` / `docs`** e salva.

### 3. Forza il primo aggiornamento

Vai su **Actions → "Update Basketball Calendars" → Run workflow**.

Dopo ~2 minuti trovi i file `.ics` in `docs/` e la landing page su:  
`https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO/`

---

## Personalizzazione

### Cambiare stagione LBA

Apri `src/fetchers/lba.py` e aggiorna:

```python
CURRENT_SEASON_ID = 28  # ← numero stagione sul sito legabasket.it
```

### Aggiungere altre leghe

Crea `src/fetchers/mia_lega.py` con una funzione `fetch_games() -> list[dict]`,  
poi aggiungila in `src/main.py` nella lista `CALENDARS`.

Schema standard di un game dict:

```python
{
    "id": "unique_string",
    "competition": "Nome lega",
    "home_team": "Nome squadra casa",
    "away_team": "Nome squadra ospite",
    "datetime_utc": datetime(2025, 10, 22, 19, 30, tzinfo=timezone.utc),
    "venue": "Nome arena",
    "city": "Città",
    "status": "scheduled" | "live" | "finished",
    "home_score": 110,   # o None se non ancora giocata
    "away_score": 98,
    "round": "Giornata 1",
}
```

---

## Fonti dati

| Liga | Fonte |
|------|-------|
| NBA | [cdn.nba.com](https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json) — feed ufficiale NBA |
| EuroLeague | [api-live.euroleague.net](https://api-live.euroleague.net) — API ufficiale EuroLeague |
| LBA | [legabasket.it](https://www.legabasket.it) — sito ufficiale Lega Basket |

---

## Licenza

MIT — usa, modifica e condividi liberamente.

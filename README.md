# 🏆 Sports Calendar

Calendari **ICS** aggiornati automaticamente per seguire i tuoi sport preferiti direttamente in Google Calendar, Apple Calendar o Outlook — senza registrazioni, senza app, gratis.

> **Demo live:** `(https://campier.github.io/Sports-Calendar/`

---

## Calendari disponibili

### 🏀 Basket
| Competizione | File | Download |
|---|---|---|
| NBA 2025-26 | `…/nba.ics` | [nba.ics](docs/nba.ics) |
| EuroLeague + EuroCup 2025-26 | `…/euroleague.ics` | [euroleague.ics](docs/euroleague.ics) |
| LBA Legabasket 2025-26 | `…/lba.ics` | [lba.ics](docs/lba.ics) |

### ⚽ Calcio
| Competizione | File | Download |
|---|---|---|
| Serie A 2025-26 | `…/serie_a.ics` | [serie_a.ics](docs/serie_a.ics) |
| Champions League 2025-26 | `…/champions_league.ics` | [champions_league.ics](docs/champions_league.ics) |

### 🏎 Motorsport
| Competizione | File | Download |
|---|---|---|
| Formula 1 2026 (FP1·FP2·FP3·Quali·Gara) | `…/f1.ics` | [f1.ics](docs/f1.ics) |
| MotoGP 2026 | `…/motogp.ics` | [motogp.ics](docs/motogp.ics) |

### 🎾 Tennis
| Competizione | File | Download |
|---|---|---|
| ATP + WTA 2026 | `…/tennis.ics` | [tennis.ics](docs/tennis.ics) |

### ⭐ Tutto insieme
| | File | Download |
|---|---|---|
| Tutti gli sport | `…/all.ics` | [all.ics](docs/all.ics) |

---

## Come abbonare il calendario

### Google Calendar
1. Apri [Google Calendar](https://calendar.google.com)
2. Clicca **"+"** accanto a *Altri calendari* → **Da URL**
3. Incolla l'URL del file `.ics` che vuoi
4. Clicca **Aggiungi calendario**

> Google Calendar sincronizza i feed esterni ogni 12-24 ore. Per forzare l'aggiornamento: **Impostazioni → [nome calendario] → Aggiorna calendario**.

### Apple Calendar
`File → Nuovo abbonamento calendario → incolla URL → Aggiungi`

### Outlook
`Aggiungi calendario → Da Internet → incolla URL → Importa`

---

## Come funziona

```
GitHub Actions (2×/giorno: 05:00 e 13:00 UTC)
       │
       ▼
   src/main.py
   ├── fetchers/nba.py              → ESPN scoreboard API
   ├── fetchers/euroleague.py       → api-live.euroleague.net (v2)
   ├── fetchers/lba.py              → legabasket.it (internal API)
   ├── fetchers/serie_a.py          → ESPN soccer API (ita.1)
   ├── fetchers/champions_league.py → ESPN soccer API (uefa.champions)
   ├── fetchers/f1.py               → Jolpica API (Ergast successor)
   ├── fetchers/motogp.py           → api.pulselive.motogp.com
   └── fetchers/tennis.py           → ESPN tennis ATP + WTA
       │
       ▼
  calendar_generator.py → genera file .ics
       │
       ▼
  docs/*.ics   ← serviti via GitHub Pages (URL stabili)
```

Il workflow aggiorna i file ICS **solo se ci sono cambiamenti** — nessun commit inutile.  
Gli URL rimangono sempre stabili: abbonati una volta e il calendario si aggiorna da solo.

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

### 1. Pubblica il repo su GitHub
Usa **GitHub Desktop → Publish repository** oppure da terminale:
```bash
gh repo create YOUR_REPO --public --push --source .
```

### 2. Abilita GitHub Pages
**Settings → Pages → Source: Deploy from a branch → `master` (o `main`) / `/docs`** → Save.

### 3. Primo aggiornamento manuale
**Actions → "Update Basketball Calendars" → Run workflow**

Dopo ~2 minuti i calendari sono live su:
`https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO/`

---

## Aggiungere una nuova lega

1. Crea `src/fetchers/mia_lega.py` con una funzione `fetch_games() -> list[dict]`
2. Aggiungila in `src/main.py` nella lista `CALENDARS`

Schema standard di un evento:

```python
{
    "id": "unique_string",
    "competition": "Nome competizione",
    "home_team": "Squadra/Atleta casa",
    "away_team": "Squadra/Atleta ospite",
    "datetime_utc": datetime(2026, 9, 1, 19, 0, tzinfo=timezone.utc),
    "venue": "Nome arena/circuito",
    "city": "Città",
    "status": "scheduled" | "live" | "finished",
    "home_score": 3,    # o None se non ancora giocata
    "away_score": 1,
    "round": "Giornata 1",
    # Opzionali per motorsport:
    "summary_override": "🏎 Testo personalizzato evento",
    "datetime_end": datetime(...),  # se diverso da +2h30
}
```

---

## Fonti dati

| Sport | Competizione | Fonte |
|---|---|---|
| 🏀 Basket | NBA | [ESPN scoreboard API](https://site.api.espn.com) |
| 🏀 Basket | EuroLeague / EuroCup | [api-live.euroleague.net](https://api-live.euroleague.net) — API ufficiale |
| 🏀 Basket | LBA | [legabasket.it](https://www.legabasket.it) — API interna |
| ⚽ Calcio | Serie A | [ESPN soccer API](https://site.api.espn.com) — `ita.1` |
| ⭐ Calcio | Champions League | [ESPN soccer API](https://site.api.espn.com) — `uefa.champions` |
| 🏎 Motorsport | Formula 1 | [Jolpica API](https://api.jolpi.ca/ergast/) — successor of Ergast |
| 🏍 Motorsport | MotoGP | [api.pulselive.motogp.com](https://api.pulselive.motogp.com) — API ufficiale |
| 🎾 Tennis | ATP + WTA | [ESPN tennis API](https://site.api.espn.com) |

---

## Licenza

MIT — usa, modifica e condividi liberamente.

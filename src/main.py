"""Entry point: fetch all leagues and write ICS files to docs/."""

import logging
import sys
from datetime import date
from pathlib import Path

from calendar_generator import build_calendar, write_ics
from fetchers import champions_league, euroleague, f1, lba, motogp, nba, serie_a, tennis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).parent.parent / "docs"

# Season labels are derived at runtime so they never go stale. Cross-year
# seasons (basket, calcio) roll over in July; motorsport and tennis follow
# the calendar year.
_TODAY = date.today()
_SEASON_START = _TODAY.year if _TODAY.month >= 7 else _TODAY.year - 1
SEASON = f"{_SEASON_START}-{str(_SEASON_START + 1)[-2:]}"   # es. "2026-27"
YEAR = _TODAY.year

CALENDARS = [
    # ── Basket ────────────────────────────────────────────────────────────────
    {
        "key": "nba",
        "fetcher": nba.fetch_games,
        "name": f"NBA {SEASON}",
        "description": f"Calendario completo NBA {SEASON}: Regular Season e Playoffs",
        "filename": "nba.ics",
    },
    {
        "key": "euroleague",
        "fetcher": euroleague.fetch_games,
        "name": f"EuroLeague & EuroCup {SEASON}",
        "description": f"Calendario EuroLeague e EuroCup {SEASON}",
        "filename": "euroleague.ics",
    },
    {
        "key": "lba",
        "fetcher": lba.fetch_games,
        "name": f"LBA Legabasket {SEASON}",
        "description": f"Calendario Lega Basket Serie A {SEASON}",
        "filename": "lba.ics",
    },
    # ── Calcio ────────────────────────────────────────────────────────────────
    {
        "key": "serie_a",
        "fetcher": serie_a.fetch_games,
        "name": f"Serie A {SEASON}",
        "description": f"Calendario Serie A TIM {SEASON}",
        "filename": "serie_a.ics",
    },
    {
        "key": "champions_league",
        "fetcher": champions_league.fetch_games,
        "name": f"UEFA Champions League {SEASON}",
        "description": f"Calendario UEFA Champions League {SEASON}",
        "filename": "champions_league.ics",
    },
    # ── Motorsport ────────────────────────────────────────────────────────────
    {
        "key": "f1",
        "fetcher": f1.fetch_games,
        "name": f"Formula 1 {YEAR}",
        "description": f"Calendario Formula 1 {YEAR}: tutte le sessioni (FP1, FP2, FP3, Qualifiche, Gara)",
        "filename": "f1.ics",
    },
    {
        "key": "motogp",
        "fetcher": motogp.fetch_games,
        "name": f"MotoGP {YEAR}",
        "description": f"Calendario MotoGP {YEAR}: tutti i Grand Prix",
        "filename": "motogp.ics",
    },
    # ── Tennis ────────────────────────────────────────────────────────────────
    {
        "key": "tennis",
        "fetcher": tennis.fetch_games,
        "name": f"Tennis ATP & WTA {YEAR}",
        "description": f"Calendario ATP e WTA {YEAR}: Grand Slam e principali tornei",
        "filename": "tennis.ics",
    },
]


def main() -> None:
    all_games: list[dict] = []

    for cfg in CALENDARS:
        logger.info("Fetching %s...", cfg["name"])
        try:
            games = cfg["fetcher"]()
        except Exception as exc:
            logger.error("Fetcher %s crashed: %s", cfg["key"], exc)
            games = []

        logger.info("%s: %d events fetched", cfg["key"].upper(), len(games))

        try:
            cal = build_calendar(games, cfg["name"], cfg["description"])
            write_ics(cal, DOCS_DIR / cfg["filename"])
        except Exception as exc:
            logger.error("Calendar build/write failed for %s: %s", cfg["key"], exc)
            continue
        all_games.extend(games)

    # Combined calendar — tutti gli sport
    combined = build_calendar(
        all_games,
        "🏆 Sports Calendar — tutti gli sport",
        "NBA · EuroLeague · LBA · Serie A · F1 · MotoGP · Tennis",
    )
    write_ics(combined, DOCS_DIR / "all.ics")

    logger.info("Done. Total events: %d", len(all_games))


if __name__ == "__main__":
    main()

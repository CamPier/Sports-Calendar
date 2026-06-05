"""Entry point: fetch all leagues and write ICS files to docs/."""

import logging
import sys
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

CALENDARS = [
    # ── Basket ────────────────────────────────────────────────────────────────
    {
        "key": "nba",
        "fetcher": nba.fetch_games,
        "name": "NBA 2025-26",
        "description": "Calendario completo NBA 2025-26: Regular Season e Playoffs",
        "filename": "nba.ics",
    },
    {
        "key": "euroleague",
        "fetcher": euroleague.fetch_games,
        "name": "EuroLeague & EuroCup 2025-26",
        "description": "Calendario EuroLeague e EuroCup 2025-26",
        "filename": "euroleague.ics",
    },
    {
        "key": "lba",
        "fetcher": lba.fetch_games,
        "name": "LBA Legabasket 2025-26",
        "description": "Calendario Lega Basket Serie A 2025-26",
        "filename": "lba.ics",
    },
    # ── Calcio ────────────────────────────────────────────────────────────────
    {
        "key": "serie_a",
        "fetcher": serie_a.fetch_games,
        "name": "Serie A 2025-26",
        "description": "Calendario Serie A TIM 2025-26",
        "filename": "serie_a.ics",
    },
    {
        "key": "champions_league",
        "fetcher": champions_league.fetch_games,
        "name": "UEFA Champions League 2025-26",
        "description": "Calendario UEFA Champions League 2025-26",
        "filename": "champions_league.ics",
    },
    # ── Motorsport ────────────────────────────────────────────────────────────
    {
        "key": "f1",
        "fetcher": f1.fetch_games,
        "name": "Formula 1 2026",
        "description": "Calendario Formula 1 2026: tutte le sessioni (FP1, FP2, FP3, Qualifiche, Gara)",
        "filename": "f1.ics",
    },
    {
        "key": "motogp",
        "fetcher": motogp.fetch_games,
        "name": "MotoGP 2026",
        "description": "Calendario MotoGP 2026: tutti i Grand Prix",
        "filename": "motogp.ics",
    },
    # ── Tennis ────────────────────────────────────────────────────────────────
    {
        "key": "tennis",
        "fetcher": tennis.fetch_games,
        "name": "Tennis ATP & WTA 2026",
        "description": "Calendario ATP e WTA 2026: Grand Slam e principali tornei",
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

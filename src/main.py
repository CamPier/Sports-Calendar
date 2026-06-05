"""Entry point: fetch all leagues and write ICS files to docs/."""

import logging
import sys
from pathlib import Path

from calendar_generator import build_calendar, write_ics
from fetchers import euroleague, lba, nba

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).parent.parent / "docs"

CALENDARS = [
    {
        "key": "nba",
        "fetcher": nba.fetch_games,
        "competitions": ["NBA"],
        "name": "NBA 2025-26",
        "description": "Calendario completo NBA 2025-26: Regular Season e Playoffs",
        "filename": "nba.ics",
    },
    {
        "key": "euroleague",
        "fetcher": euroleague.fetch_games,
        "competitions": ["EuroLeague", "EuroCup"],
        "name": "EuroLeague & EuroCup 2025-26",
        "description": "Calendario EuroLeague e EuroCup 2025-26",
        "filename": "euroleague.ics",
    },
    {
        "key": "lba",
        "fetcher": lba.fetch_games,
        "competitions": ["LBA"],
        "name": "LBA Legabasket 2025-26",
        "description": "Calendario Lega Basket Serie A 2025-26",
        "filename": "lba.ics",
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

        logger.info("%s: %d games fetched", cfg["key"].upper(), len(games))

        cal = build_calendar(games, cfg["name"], cfg["description"])
        write_ics(cal, DOCS_DIR / cfg["filename"])
        all_games.extend(games)

    # Combined calendar
    combined = build_calendar(
        all_games,
        "🏀 Basket Completo 2025-26",
        "NBA + EuroLeague + EuroCup + LBA — calendario unificato",
    )
    write_ics(combined, DOCS_DIR / "all.ics")

    logger.info("Done. Total events: %d", len(all_games))


if __name__ == "__main__":
    main()

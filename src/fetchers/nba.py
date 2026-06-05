"""Fetches the full NBA season schedule from the official CDN."""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

NBA_SCHEDULE_URL = (
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BasketballCalendar/1.0)",
    "Accept": "application/json",
    "Referer": "https://www.nba.com/",
}


def fetch_games() -> list[dict]:
    """Return list of NBA game dicts for the current season."""
    try:
        resp = requests.get(NBA_SCHEDULE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("NBA fetch failed: %s", exc)
        return []

    games = []
    league_schedule = data.get("leagueSchedule", {})
    for game_date in league_schedule.get("gameDates", []):
        for g in game_date.get("games", []):
            try:
                dt_utc = _parse_utc(g.get("gameTimeUTC", ""))
                if dt_utc is None:
                    continue

                home = g.get("homeTeam", {})
                away = g.get("awayTeam", {})
                home_name = f"{home.get('teamCity', '')} {home.get('teamName', '')}".strip()
                away_name = f"{away.get('teamCity', '')} {away.get('teamName', '')}".strip()

                games.append(
                    {
                        "id": g.get("gameId", ""),
                        "competition": "NBA",
                        "home_team": home_name,
                        "away_team": away_name,
                        "home_tricode": home.get("teamTricode", ""),
                        "away_tricode": away.get("teamTricode", ""),
                        "datetime_utc": dt_utc,
                        "venue": home.get("teamCity", ""),
                        "status": _map_status(g.get("gameStatus", 1)),
                        "home_score": home.get("score"),
                        "away_score": away.get("score"),
                        "series_text": g.get("seriesText", ""),
                    }
                )
            except Exception as exc:
                logger.warning("Skipping NBA game %s: %s", g.get("gameId"), exc)

    logger.info("NBA: fetched %d games", len(games))
    return games


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _map_status(code: int) -> str:
    return {1: "scheduled", 2: "live", 3: "finished"}.get(code, "scheduled")

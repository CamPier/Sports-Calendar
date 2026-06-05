"""Fetches the full NBA season schedule from the official CDN."""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

NBA_SCHEDULE_URLS = [
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json",
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


def fetch_games() -> list[dict]:
    """Return list of NBA game dicts for the current season."""
    data = None
    for url in NBA_SCHEDULE_URLS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            logger.info("NBA: loaded schedule from %s", url)
            break
        except Exception as exc:
            logger.warning("NBA fetch failed (%s): %s", url, exc)

    if data is None:
        logger.error("NBA: all schedule URLs failed")
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

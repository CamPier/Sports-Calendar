"""Fetches football schedules from the ESPN soccer API.

The public `fetch_espn_soccer` function is shared with other football fetchers.
"""

import logging
from datetime import date, datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SportsCalendar/1.0)",
    "Accept": "application/json",
}


def fetch_games() -> list[dict]:
    """Return Serie A match events for the current season."""
    return fetch_espn_soccer("ita.1", "Serie A")


def fetch_espn_soccer(league: str, competition_name: str) -> list[dict]:
    """Shared helper — fetch any ESPN soccer league by code."""
    start, end = _season_window()
    return _fetch_range(league, competition_name, start, end)


def _season_window() -> tuple[date, date]:
    today = date.today()
    if today.month in (6, 7):
        return date(today.year - 1, 8, 1), date(today.year, 6, 30)
    season_start_year = today.year if today.month >= 8 else today.year - 1
    return date(season_start_year, 8, 1), date(season_start_year + 1, 6, 30)


def _fetch_range(league: str, competition_name: str, start: date, end: date) -> list[dict]:
    url = ESPN_BASE.format(league=league)
    games: list[dict] = []
    seen: set[str] = set()
    cursor = start

    while cursor <= end:
        next_month_day1 = date(
            cursor.year if cursor.month < 12 else cursor.year + 1,
            cursor.month % 12 + 1,
            1,
        )
        window_end = min(next_month_day1 - timedelta(days=1), end)
        params = {
            "dates": f"{cursor.strftime('%Y%m%d')}-{window_end.strftime('%Y%m%d')}",
            "limit": 500,
        }
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("%s %s: %s", competition_name, cursor.strftime("%Y-%m"), exc)
            cursor = next_month_day1
            continue

        for event in data.get("events", []):
            game = _parse_event(event, competition_name)
            if game and game["id"] not in seen:
                seen.add(game["id"])
                games.append(game)

        cursor = next_month_day1

    logger.info("%s: fetched %d matches", competition_name, len(games))
    return games


def _parse_event(event: dict, competition_name: str) -> dict | None:
    try:
        competitions = event.get("competitions", [])
        if not competitions:
            return None
        comp = competitions[0]

        raw_date = event.get("date") or comp.get("date") or ""
        dt_utc = _parse_utc(raw_date)
        if dt_utc is None:
            return None

        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})

        home_name = home.get("team", {}).get("displayName", "TBD")
        away_name = away.get("team", {}).get("displayName", "TBD")
        home_abbr = home.get("team", {}).get("abbreviation", "")
        away_abbr = away.get("team", {}).get("abbreviation", "")

        status_obj = comp.get("status", {}).get("type", {})
        completed = status_obj.get("completed", False)
        state = status_obj.get("state", "pre")
        if completed:
            game_status = "finished"
        elif state == "in":
            game_status = "live"
        else:
            game_status = "scheduled"

        home_score = int(home.get("score", 0)) if completed else None
        away_score = int(away.get("score", 0)) if completed else None

        venue = comp.get("venue", {})
        venue_name = venue.get("fullName", "") if isinstance(venue, dict) else ""
        city = (venue.get("address") or {}).get("city", "") if isinstance(venue, dict) else ""

        return {
            "id": event.get("id", ""),
            "competition": competition_name,
            "home_team": home_name,
            "away_team": away_name,
            "home_tricode": home_abbr,
            "away_tricode": away_abbr,
            "datetime_utc": dt_utc,
            "venue": venue_name,
            "city": city,
            "status": game_status,
            "home_score": home_score,
            "away_score": away_score,
        }
    except Exception as exc:
        logger.debug("%s event parse error: %s", competition_name, exc)
        return None


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

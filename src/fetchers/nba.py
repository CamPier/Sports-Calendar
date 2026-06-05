"""Fetches the full NBA season schedule.

Primary source: ESPN scoreboard API (works from server/CI environments).
Fallback: NBA official CDN JSON.
"""

import logging
from datetime import date, datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

# ESPN scoreboard — permissive, works from GitHub Actions
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# NBA CDN — works locally but often blocked on cloud IPs
NBA_CDN_URLS = [
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json",
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
]

ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BasketballCalendar/1.0)",
    "Accept": "application/json",
}

CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# NBA 2025-26 season window
SEASON_START = date(2025, 10, 1)
SEASON_END = date(2026, 7, 1)


def fetch_games() -> list[dict]:
    """Try ESPN first, fall back to NBA CDN."""
    games = _fetch_espn()
    if games:
        logger.info("NBA (ESPN): %d games", len(games))
        return games

    logger.warning("NBA ESPN fetch returned 0 — trying NBA CDN fallback")
    games = _fetch_nba_cdn()
    logger.info("NBA (CDN): %d games", len(games))
    return games


# ── ESPN ──────────────────────────────────────────────────────────────────────

def _fetch_espn() -> list[dict]:
    """Fetch full season by iterating month-by-month via ESPN scoreboard."""
    games: list[dict] = []
    seen: set[str] = set()

    cursor = SEASON_START
    while cursor < SEASON_END:
        # Build a ~1-month window
        if cursor.month == 12:
            next_month = cursor.replace(year=cursor.year + 1, month=1, day=1)
        else:
            next_month = cursor.replace(month=cursor.month + 1, day=1)
        window_end = min(next_month - timedelta(days=1), SEASON_END)

        params = {
            "dates": f"{cursor.strftime('%Y%m%d')}-{window_end.strftime('%Y%m%d')}",
            "limit": 500,
        }
        try:
            resp = requests.get(ESPN_URL, params=params, headers=ESPN_HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("ESPN NBA %s: %s", cursor.strftime("%Y-%m"), exc)
            cursor = next_month
            continue

        for event in data.get("events", []):
            game = _parse_espn_event(event)
            if game and game["id"] not in seen:
                seen.add(game["id"])
                games.append(game)

        cursor = next_month

    return games


def _parse_espn_event(event: dict) -> dict | None:
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

        home_team = home.get("team", {})
        away_team = away.get("team", {})
        home_name = home_team.get("displayName", "TBD")
        away_name = away_team.get("displayName", "TBD")

        status = comp.get("status", {}).get("type", {})
        state = status.get("state", "pre")
        completed = status.get("completed", False)
        if completed:
            game_status = "finished"
        elif state == "in":
            game_status = "live"
        else:
            game_status = "scheduled"

        home_score = int(home.get("score", 0)) if completed else None
        away_score = int(away.get("score", 0)) if completed else None

        venue = comp.get("venue", {})
        venue_name = venue.get("fullName", "")
        city = (venue.get("address") or {}).get("city", "")

        series = (comp.get("series") or {}).get("summary", "")

        return {
            "id": event.get("id", ""),
            "competition": "NBA",
            "home_team": home_name,
            "away_team": away_name,
            "home_tricode": home_team.get("abbreviation", ""),
            "away_tricode": away_team.get("abbreviation", ""),
            "datetime_utc": dt_utc,
            "venue": venue_name,
            "city": city,
            "status": game_status,
            "home_score": home_score,
            "away_score": away_score,
            "series_text": series,
        }
    except Exception as exc:
        logger.debug("ESPN event parse error: %s", exc)
        return None


# ── NBA CDN fallback ──────────────────────────────────────────────────────────

def _fetch_nba_cdn() -> list[dict]:
    data = None
    for url in NBA_CDN_URLS:
        try:
            resp = requests.get(url, headers=CDN_HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            logger.info("NBA CDN: loaded from %s", url)
            break
        except Exception as exc:
            logger.warning("NBA CDN failed (%s): %s", url, exc)

    if data is None:
        return []

    games = []
    for game_date in data.get("leagueSchedule", {}).get("gameDates", []):
        for g in game_date.get("games", []):
            try:
                dt_utc = _parse_utc(g.get("gameTimeUTC", ""))
                if dt_utc is None:
                    continue
                home = g.get("homeTeam", {})
                away = g.get("awayTeam", {})
                games.append({
                    "id": g.get("gameId", ""),
                    "competition": "NBA",
                    "home_team": f"{home.get('teamCity','')} {home.get('teamName','')}".strip(),
                    "away_team": f"{away.get('teamCity','')} {away.get('teamName','')}".strip(),
                    "home_tricode": home.get("teamTricode", ""),
                    "away_tricode": away.get("teamTricode", ""),
                    "datetime_utc": dt_utc,
                    "venue": home.get("teamCity", ""),
                    "status": {1: "scheduled", 2: "live", 3: "finished"}.get(
                        g.get("gameStatus", 1), "scheduled"
                    ),
                    "home_score": home.get("score"),
                    "away_score": away.get("score"),
                    "series_text": g.get("seriesText", ""),
                })
            except Exception as exc:
                logger.debug("CDN game parse error: %s", exc)
    return games


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

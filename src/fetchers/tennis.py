"""Fetches ATP and WTA tennis events from ESPN."""

import logging
from datetime import date, datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

ESPN_ATP_URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard"
ESPN_WTA_URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SportsCalendar/1.0)",
    "Accept": "application/json",
}

# Rolling window: 7 days ago → 7 days ahead (aggiornato ad ogni run)
DAYS_BACK = 7
DAYS_AHEAD = 7


def fetch_games() -> list[dict]:
    """Return ATP + WTA tennis events for the current 2-week window (7 giorni fa → 7 giorni avanti)."""
    today = date.today()
    start = today - timedelta(days=DAYS_BACK)
    end = today + timedelta(days=DAYS_AHEAD)

    atp = _fetch_circuit("ATP", ESPN_ATP_URL, start, end)
    wta = _fetch_circuit("WTA", ESPN_WTA_URL, start, end)
    return atp + wta


def _fetch_circuit(circuit: str, url: str, start: date, end: date) -> list[dict]:
    games: list[dict] = []
    seen: set[str] = set()

    # Fetch the entire window in a single request (max 14 days, well within ESPN limits)
    params = {
        "dates": f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}",
        "limit": 500,
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Tennis %s fetch error: %s", circuit, exc)
        return games

    for event in data.get("events", []):
        game = _parse_event(event, circuit)
        if game and game["id"] not in seen:
            seen.add(game["id"])
            games.append(game)

    logger.info("Tennis %s: %d events", circuit, len(games))
    return games


def _parse_event(event: dict, circuit: str) -> dict | None:
    try:
        competitions = event.get("competitions", [])
        comp = competitions[0] if competitions else {}

        raw_date = event.get("date") or comp.get("date") or ""
        dt_utc = _parse_utc(raw_date)
        if dt_utc is None:
            return None

        competitors = comp.get("competitors", [])

        if len(competitors) >= 2:
            # Individual match
            p1 = competitors[0].get("athlete", {}) or competitors[0].get("team", {})
            p2 = competitors[1].get("athlete", {}) or competitors[1].get("team", {})
            home_name = p1.get("displayName") or p1.get("name") or "Player 1"
            away_name = p2.get("displayName") or p2.get("name") or "Player 2"
            home_abbr = p1.get("abbreviation") or p1.get("shortName") or ""
            away_abbr = p2.get("abbreviation") or p2.get("shortName") or ""

            status_obj = comp.get("status", {}).get("type", {})
            completed = status_obj.get("completed", False)
            state = status_obj.get("state", "pre")
            game_status = "finished" if completed else ("live" if state == "in" else "scheduled")

            h_score = competitors[0].get("score")
            a_score = competitors[1].get("score")
        else:
            # Tournament-level event
            home_name = event.get("name") or event.get("shortName") or "Tournament"
            away_name = circuit
            home_abbr = away_abbr = ""
            game_status = "scheduled"
            h_score = a_score = None

        venue = comp.get("venue", {}) if comp else {}
        venue_name = venue.get("fullName", "") if isinstance(venue, dict) else ""
        city = (venue.get("address") or {}).get("city", "") if isinstance(venue, dict) else ""

        tour_name = event.get("name") or event.get("shortName") or ""

        return {
            "id": event.get("id", ""),
            "competition": f"Tennis {circuit}",
            "home_team": home_name,
            "away_team": away_name,
            "home_tricode": home_abbr,
            "away_tricode": away_abbr,
            "datetime_utc": dt_utc,
            "venue": venue_name,
            "city": city,
            "status": game_status,
            "home_score": h_score,
            "away_score": a_score,
            "round": tour_name,
        }
    except Exception as exc:
        logger.debug("Tennis event parse error: %s", exc)
        return None


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

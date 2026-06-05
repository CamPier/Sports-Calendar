"""Fetches EuroLeague and EuroCup schedules from the official live API (v2)."""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api-live.euroleague.net/v2/competitions"

COMPETITIONS = {
    "EuroLeague": ("E", "E2025"),
    "EuroCup": ("U", "U2025"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BasketballCalendar/1.0)",
    "Accept": "application/json",
}

PAGE_SIZE = 200


def fetch_games() -> list[dict]:
    """Return combined list of EuroLeague + EuroCup game dicts."""
    all_games: list[dict] = []
    for competition, (comp_code, season_code) in COMPETITIONS.items():
        all_games.extend(_fetch_competition(competition, comp_code, season_code))
    return all_games


def _fetch_competition(competition: str, comp_code: str, season_code: str) -> list[dict]:
    url = f"{BASE_URL}/{comp_code}/seasons/{season_code}/games"
    games: list[dict] = []
    offset = 0

    while True:
        params = {"limit": PAGE_SIZE, "offset": offset}
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if resp.status_code == 404:
                logger.warning("%s season %s not found (404)", competition, season_code)
                break
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("%s fetch error at offset %d: %s", competition, offset, exc)
            break

        batch = data.get("data", [])
        if not batch:
            break

        for g in batch:
            try:
                game = _parse_game(g, competition)
                if game:
                    games.append(game)
            except Exception as exc:
                logger.debug("Skipping EL game: %s", exc)

        total = data.get("total", 0)
        offset += len(batch)
        if offset >= total or len(batch) < PAGE_SIZE:
            break

    logger.info("%s: fetched %d games", competition, len(games))
    return games


def _parse_game(g: dict, competition: str) -> dict | None:
    raw_date = g.get("utcDate") or g.get("date") or ""
    if not raw_date:
        return None

    dt_utc = _parse_utc(raw_date)
    if dt_utc is None:
        return None

    # v2 API uses "local" (home) and "road" (away)
    local = g.get("local") or {}
    road = g.get("road") or {}
    local_club = local.get("club") or {}
    road_club = road.get("club") or {}

    home_name = local_club.get("name") or local_club.get("alias") or "TBD"
    away_name = road_club.get("name") or road_club.get("alias") or "TBD"
    home_code = local_club.get("code") or local_club.get("tvCode") or ""
    away_code = road_club.get("code") or road_club.get("tvCode") or ""

    venue = g.get("venue") or {}
    venue_name = venue.get("name") or "" if isinstance(venue, dict) else str(venue)
    city = venue.get("city") or "" if isinstance(venue, dict) else ""

    phase = (g.get("phaseType") or {}).get("code") or ""
    group = (g.get("group") or {}).get("name") or ""

    played = g.get("played", False)
    status = "finished" if played else "scheduled"

    home_score = (local.get("score") if played else None)
    away_score = (road.get("score") if played else None)

    game_code = g.get("gameCode") or g.get("identifier") or ""
    season_code = (g.get("season") or {}).get("code") or ""
    uid = f"{season_code}-{phase}-{game_code}"

    return {
        "id": uid,
        "competition": competition,
        "home_team": home_name,
        "away_team": away_name,
        "home_tricode": home_code,
        "away_tricode": away_code,
        "datetime_utc": dt_utc,
        "venue": venue_name,
        "city": city,
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
        "round": g.get("round") or g.get("roundName") or "",
        "phase": group or phase,
    }


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(value[:19], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None

"""Fetches Lega Basket (LBA) schedule from legabasket.it internal API."""

import logging
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.legabasket.it"
CHAMPIONSHIPS_URL = f"{BASE_URL}/api/championships/get-championships"
CALENDAR_URL = f"{BASE_URL}/api/championships/get-championships-calendar-by-id"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.legabasket.it/",
}

# Leagues that correspond to Serie A (cs_id=1 = Serie A bucket)
SERIE_A_NAMES = {"regular season a", "playoff serie a", "play off a"}


def fetch_games() -> list[dict]:
    """Return all LBA games for the two most recent Serie A competitions."""
    comp_ids = _get_current_season_ids()
    if not comp_ids:
        logger.warning("LBA: could not determine current season competition IDs")
        return []

    all_games: list[dict] = []
    for comp_id, comp_name in comp_ids:
        games = _fetch_competition(comp_id, comp_name)
        all_games.extend(games)

    logger.info("LBA: total %d games fetched", len(all_games))
    return all_games


def _get_current_season_ids() -> list[tuple[int, str]]:
    """Return [(id, name)] for the two most recent Serie A competitions."""
    all_comps: list[dict] = []
    page = 1
    while True:
        try:
            r = requests.get(
                CHAMPIONSHIPS_URL,
                params={"items": 100, "cs_id": 1, "page": page},
                headers=HEADERS,
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.error("LBA championships list error (page %d): %s", page, exc)
            break

        batch = data.get("competitions", [])
        if not batch:
            break
        all_comps.extend(batch)
        pagination = data.get("pagination", {})
        if not pagination.get("next_page"):
            break
        page += 1

    if not all_comps:
        return []

    # Filter to Serie A (name contains relevant keywords)
    serie_a = [
        c for c in all_comps
        if any(kw in c.get("name", "").lower() for kw in SERIE_A_NAMES)
    ]

    # Take the two highest-year entries (Regular Season + Playoff of current season)
    max_year = max(c.get("year", 0) for c in serie_a)
    current = [(c["id"], c["name"]) for c in serie_a if c.get("year") == max_year]
    logger.info("LBA current season (year=%d): %s", max_year, current)
    return current


def _fetch_competition(comp_id: int, comp_name: str) -> list[dict]:
    """Fetch all matches for a single competition by iterating over every day."""
    # First call without day filter to get the list of days
    try:
        r = requests.get(CALENDAR_URL, params={"id": comp_id}, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.error("LBA comp %d initial fetch error: %s", comp_id, exc)
        return []

    days = (data.get("filters") or {}).get("days", [])
    if not days:
        # If no days filter, parse what we already have
        return _parse_matches(data.get("matches") or [], comp_name)

    all_games: list[dict] = []
    seen_ids: set[str] = set()

    for day in days:
        event_serial = day.get("event_serial")
        if event_serial is None:
            continue
        try:
            r = requests.get(
                CALENDAR_URL,
                params={"id": comp_id, "d": event_serial},
                headers=HEADERS,
                timeout=20,
            )
            r.raise_for_status()
            d = r.json()
        except Exception as exc:
            logger.warning("LBA comp %d day %s error: %s", comp_id, event_serial, exc)
            continue

        for game in _parse_matches(d.get("matches") or [], comp_name):
            if game["id"] not in seen_ids:
                seen_ids.add(game["id"])
                all_games.append(game)

    logger.info("LBA %s (id=%d): %d games", comp_name, comp_id, len(all_games))
    return all_games


def _parse_matches(matches: list, comp_name: str) -> list[dict]:
    games = []
    for m in matches:
        try:
            game = _normalise(m, comp_name)
            if game:
                games.append(game)
        except Exception as exc:
            logger.debug("LBA parse error match %s: %s", m.get("id"), exc)
    return games


def _normalise(m: dict, comp_name: str) -> dict | None:
    raw_dt = m.get("match_datetime", "")
    if not raw_dt:
        return None

    dt_utc = _parse_date(raw_dt)
    if dt_utc is None:
        return None

    match_id = str(m.get("id", ""))
    status_raw = str(m.get("game_status", "0"))
    status = {"0": "scheduled", "1": "live", "2": "finished"}.get(status_raw, "scheduled")

    home_score = m.get("home_final_score")
    away_score = m.get("visitor_final_score")

    day_name = m.get("day_name", "").encode("latin-1", errors="replace").decode("utf-8", errors="replace")
    comp_display = f"LBA – {comp_name}"
    if "playoff" in comp_name.lower() or "play off" in comp_name.lower():
        comp_display = "LBA Playoff"

    return {
        "id": match_id,
        "competition": "LBA",
        "home_team": m.get("h_team_name", "TBD"),
        "away_team": m.get("v_team_name", "TBD"),
        "home_tricode": m.get("h_club_code", ""),
        "away_tricode": m.get("v_club_code", ""),
        "datetime_utc": dt_utc,
        "venue": m.get("plant_name", ""),
        "city": m.get("town_name", ""),
        "status": status,
        "home_score": home_score if status == "finished" else None,
        "away_score": away_score if status == "finished" else None,
        "round": day_name or m.get("day_code", ""),
        "phase": comp_display,
    }


def _parse_date(value: str) -> datetime | None:
    """Parse ISO date strings, including those with timezone offset like +02:00."""
    try:
        dt = datetime.fromisoformat(value)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    # Fallback: strip trailing milliseconds
    try:
        clean = value[:19]
        dt = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S")
        # Assume CET (UTC+1) when no tz info
        dt = dt.replace(tzinfo=timezone(timedelta(hours=1)))
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

"""Fetches Formula 1 season schedule from Jolpica API (Ergast successor).

Creates separate calendar events for each session:
FP1, FP2, FP3, Sprint Qualifying, Sprint, Qualifying, Race.
"""

import logging
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

JOLPICA_URL = "https://api.jolpi.ca/ergast/f1/{season}.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SportsCalendar/1.0)",
    "Accept": "application/json",
}

SESSION_CONFIG = {
    "FirstPractice":      ("🏎 FP1",             timedelta(hours=1)),
    "SecondPractice":     ("🏎 FP2",             timedelta(hours=1)),
    "ThirdPractice":      ("🏎 FP3",             timedelta(hours=1)),
    "SprintQualifying":   ("🏎 Sprint Qualifying", timedelta(hours=1)),
    "Sprint":             ("🏎 Sprint",           timedelta(minutes=45)),
    "Qualifying":         ("🏎 Qualifiche",       timedelta(hours=1)),
    "Race":               ("🏆 Gara",             timedelta(hours=2)),
}


def fetch_games() -> list[dict]:
    """Return list of F1 session events for the current season."""
    season = _current_season()
    races = _fetch_season(season)
    if not races:
        # Try previous season as fallback
        races = _fetch_season(season - 1)
    return races


def _current_season() -> int:
    from datetime import date
    today = date.today()
    # F1 season runs ~March to November; use current year
    return today.year


def _fetch_season(season: int) -> list[dict]:
    url = JOLPICA_URL.format(season=season)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("F1 fetch failed (season %d): %s", season, exc)
        return []

    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    events: list[dict] = []

    for race in races:
        race_name = race.get("raceName", "Grand Prix")
        circuit = race.get("Circuit", {})
        venue = circuit.get("circuitName", "")
        city = circuit.get("Location", {}).get("locality", "")
        country = circuit.get("Location", {}).get("country", "")
        location = ", ".join(filter(None, [city, country]))
        round_num = race.get("round", "")

        for session_key, (label, duration) in SESSION_CONFIG.items():
            session_data = race.get(session_key)
            if not session_data:
                continue
            dt_utc = _parse_session(session_data)
            if dt_utc is None:
                continue

            uid = f"f1-{season}-r{round_num}-{session_key.lower()}"
            home_team = f"Round {round_num} — {race_name}"

            events.append({
                "id": uid,
                "competition": "F1",
                "home_team": race_name,
                "away_team": label,
                "home_tricode": f"R{round_num}",
                "away_tricode": "",
                "datetime_utc": dt_utc,
                "datetime_end": dt_utc + duration,
                "venue": venue,
                "city": location,
                "status": "finished" if dt_utc < datetime.now(timezone.utc) else "scheduled",
                "home_score": None,
                "away_score": None,
                "round": f"Round {round_num}",
                "phase": session_key,
                "summary_override": f"{label} — {race_name}",
            })

    logger.info("F1 %d: %d session events from %d races", season, len(events), len(races))
    return events


def _parse_session(session: dict) -> datetime | None:
    date_str = session.get("date", "")
    time_str = session.get("time", "")
    if not date_str:
        return None
    raw = f"{date_str}T{time_str}" if time_str else f"{date_str}T12:00:00Z"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

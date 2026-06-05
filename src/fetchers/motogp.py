"""Fetches MotoGP season schedule from the official PulseLive API."""

import logging
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

API_URL = "https://api.pulselive.motogp.com/motogp/v1/events"
SEASONS_URL = "https://api.pulselive.motogp.com/motogp/v1/results/seasons"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SportsCalendar/1.0)",
    "Accept": "application/json",
    "Referer": "https://www.motogp.com/",
}


def fetch_games() -> list[dict]:
    """Return MotoGP Grand Prix events for the current season."""
    season_year = _current_season_year()
    events = _fetch_season(season_year)
    if not events:
        events = _fetch_season(season_year - 1)
    return events


def _current_season_year() -> int:
    from datetime import date
    return date.today().year


def _fetch_season(year: int) -> list[dict]:
    try:
        resp = requests.get(API_URL, params={"seasonYear": year}, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        raw_events = resp.json()
    except Exception as exc:
        logger.error("MotoGP fetch failed (year %d): %s", year, exc)
        return []

    games: list[dict] = []
    for event in raw_events:
        if event.get("kind") != "GP":
            continue
        try:
            game = _parse_event(event, year)
            if game:
                games.append(game)
        except Exception as exc:
            logger.debug("MotoGP event parse error: %s", exc)

    logger.info("MotoGP %d: %d Grand Prix events", year, len(games))
    return games


def _parse_event(event: dict, year: int) -> dict | None:
    raw_start = event.get("date_start", "")
    raw_end = event.get("date_end", "")
    if not raw_start:
        return None

    dt_start = _parse_dt(raw_start)
    if dt_start is None:
        return None

    # Race day is the last day of the weekend
    dt_end = _parse_dt(raw_end) if raw_end else (dt_start + timedelta(days=2))
    race_dt = dt_end.replace(hour=13, minute=0, second=0) if dt_end else dt_start

    circuit = event.get("circuit") or {}
    circuit_name = circuit.get("name", "") if isinstance(circuit, dict) else str(circuit)

    # Clean up circuit name encoding issues
    try:
        circuit_name = circuit_name.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    country_code = event.get("country", "")
    name = (event.get("name") or "").strip()
    seq = event.get("sequence", "")
    uid = f"motogp-{year}-{seq or name[:20].replace(' ', '-').lower()}"

    categories = [c.get("name", "") for c in (event.get("categories") or []) if isinstance(c, dict)]
    classes = ", ".join(filter(None, categories)) or "MotoGP · Moto2 · Moto3"

    now = datetime.now(timezone.utc)
    status = "finished" if race_dt < now else "scheduled"

    return {
        "id": uid,
        "competition": "MotoGP",
        "home_team": name,
        "away_team": "Gara",
        "home_tricode": country_code,
        "away_tricode": "",
        "datetime_utc": race_dt,
        "datetime_end": race_dt + timedelta(hours=2),
        "venue": circuit_name,
        "city": "",
        "status": status,
        "home_score": None,
        "away_score": None,
        "round": f"Round {seq}" if seq else "",
        "phase": classes,
        "summary_override": f"🏍 {name}",
        "weekend_start": dt_start,
        "weekend_end": dt_end,
    }


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt.astimezone(timezone.utc)
    except ValueError:
        try:
            dt = datetime.fromisoformat(value[:19])
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

"""Converts game dicts into ICS calendar files."""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from icalendar import Calendar, Event, vText

logger = logging.getLogger(__name__)

COMPETITION_COLORS = {
    "NBA": "#C9082A",
    "EuroLeague": "#003DA5",
    "EuroCup": "#0080C8",
    "LBA": "#008751",
    "Serie A": "#1A56DB",
    "Champions League": "#1B1464",
    "F1": "#E10600",
    "MotoGP": "#CC0000",
    "Tennis ATP": "#4CAF50",
    "Tennis WTA": "#E91E8C",
}

COMPETITION_EMOJI = {
    "NBA": "🏀",
    "EuroLeague": "🇪🇺",
    "EuroCup": "⭐",
    "LBA": "🇮🇹",
    "Serie A": "⚽",
    "Champions League": "⭐",
    "F1": "🏎",
    "MotoGP": "🏍",
    "Tennis ATP": "🎾",
    "Tennis WTA": "🎾",
}

PRODID = "-//Basketball Calendar//EN"
VERSION = "2.0"


def build_calendar(games: list[dict], name: str, description: str) -> Calendar:
    """Return an icalendar.Calendar populated with the given games."""
    cal = Calendar()
    cal.add("PRODID", PRODID)
    cal.add("VERSION", VERSION)
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("METHOD", "PUBLISH")
    cal.add("X-WR-CALNAME", vText(name))
    cal.add("X-WR-CALDESC", vText(description))
    cal.add("X-WR-TIMEZONE", "UTC")
    cal.add("REFRESH-INTERVAL;VALUE=DURATION", "PT6H")
    cal.add("X-PUBLISHED-TTL", "PT6H")

    for game in games:
        try:
            event = _make_event(game)
            cal.add_component(event)
        except Exception as exc:
            logger.warning("Skipping event %s: %s", game.get("id"), exc)

    return cal


def _make_event(game: dict) -> Event:
    competition = game.get("competition", "")
    home = game.get("home_team", "TBD")
    away = game.get("away_team", "TBD")
    dt_utc: datetime = game["datetime_utc"]
    status = game.get("status", "scheduled")

    # Allow fetchers to provide a custom summary (e.g. F1, MotoGP)
    if game.get("summary_override"):
        summary = game["summary_override"]
    else:
        emoji = COMPETITION_EMOJI.get(competition, "🏆")
        summary = f"{emoji} {away} @ {home}"
        if status == "finished":
            h_score = game.get("home_score")
            a_score = game.get("away_score")
            if h_score is not None and a_score is not None:
                summary += f" ({a_score}-{h_score})"

    lines = [f"Competizione: {competition}"]
    if home and home != away:
        lines.append(f"Casa: {home}")
    if away:
        lines.append(f"Ospite: {away}")
    if game.get("venue"):
        lines.append(f"Circuito/Arena: {game['venue']}")
    if game.get("city"):
        lines.append(f"Città: {game['city']}")
    if game.get("round"):
        lines.append(f"Giornata/Round: {game['round']}")
    if game.get("series_text"):
        lines.append(f"Serie: {game['series_text']}")
    if game.get("phase"):
        lines.append(f"Fase: {game['phase']}")
    if status == "finished":
        h = game.get("home_score")
        a = game.get("away_score")
        if h is not None and a is not None:
            lines.append(f"Risultato: {home} {h} - {a} {away}")
    lines.append(f"Stato: {status}")

    uid = _stable_uid(competition, game.get("id", ""), dt_utc, home, away)

    event = Event()
    event.add("UID", uid)
    event.add("SUMMARY", summary)
    dt_end = game.get("datetime_end") or (dt_utc + timedelta(hours=2, minutes=30))
    event.add("DTSTART", dt_utc)
    event.add("DTEND", dt_end)
    event.add("DESCRIPTION", "\n".join(lines))
    event.add("STATUS", "CONFIRMED" if status != "live" else "TENTATIVE")
    event.add("TRANSP", "TRANSPARENT")

    if game.get("venue"):
        location_parts = [game["venue"]]
        if game.get("city"):
            location_parts.append(game["city"])
        event.add("LOCATION", ", ".join(location_parts))

    color = COMPETITION_COLORS.get(competition, "#888888")
    event.add("COLOR", color)
    event["X-APPLE-CALENDAR-COLOR"] = color

    return event


def _stable_uid(competition: str, game_id: str, dt: datetime, home: str, away: str) -> str:
    """Deterministic UID so the same game updates instead of duplicating."""
    if game_id:
        raw = f"{competition}-{game_id}"
    else:
        raw = f"{competition}-{home}-{away}-{dt.isoformat()}"
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"{digest}@basketball-calendar.github.io"


def write_ics(cal: Calendar, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cal.to_ical())
    logger.info("Written %s (%d bytes)", path, path.stat().st_size)

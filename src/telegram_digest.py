"""Send a daily Telegram digest of the events in docs/all.ics.

The digest covers a 24h window in Italian time, from DAY_START_HOUR today to
DAY_START_HOUR tomorrow, so that overnight games (NBA, motorsport in Asia)
show up in the morning message of the day they are watched.

Environment:
    TELEGRAM_BOT_TOKEN   token from @BotFather (required)
    TELEGRAM_CHAT_ID     chat that receives the digest (required)
    COMPETITIONS         optional comma-separated filter, e.g. "NBA,Serie A,F1"
"""

import html
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

from calendar_generator import COMPETITION_EMOJI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

ICS_PATH = Path(__file__).parent.parent / "docs" / "all.ics"
TZ = ZoneInfo("Europe/Rome")
DAY_START_HOUR = 6
TELEGRAM_LIMIT = 4096
SITE_URL = "https://campier.github.io/Sports-Calendar/"
BUTTONS_PER_ROW = 3

# Competition (as written in the ICS description) -> per-league ICS file.
COMPETITION_FILES = {
    "NBA": "nba.ics",
    "EuroLeague": "euroleague.ics",
    "EuroCup": "euroleague.ics",
    "LBA": "lba.ics",
    "Serie A": "serie_a.ics",
    "Champions League": "champions_league.ics",
    "F1": "f1.ics",
    "MotoGP": "motogp.ics",
    "Tennis ATP": "tennis.ics",
    "Tennis WTA": "tennis.ics",
}

WEEKDAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
          "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def load_events(start: datetime, end: datetime, competitions: set[str]) -> list[dict]:
    cal = Calendar.from_ical(ICS_PATH.read_bytes())
    events = []
    for ev in cal.walk("VEVENT"):
        dt = ev.get("DTSTART").dt
        if not isinstance(dt, datetime):
            continue
        dt = dt.astimezone(TZ)
        if not start <= dt < end:
            continue

        description = str(ev.get("DESCRIPTION", ""))
        first_line = description.split("\n", 1)[0]
        competition = first_line.removeprefix("Competizione: ").strip() or "Altro"
        if competitions and competition not in competitions:
            continue

        events.append({
            "dt": dt,
            "competition": competition,
            "summary": _strip_emoji(str(ev.get("SUMMARY", ""))),
        })
    return sorted(events, key=lambda e: e["dt"])


def _strip_emoji(summary: str) -> str:
    """Drop the leading emoji: the digest already shows it in the group header."""
    head, _, rest = summary.partition(" ")
    return rest if rest and not any(c.isalnum() for c in head) else summary


def build_message(events: list[dict], day: datetime) -> str:
    title = f"🗓 <b>Sport di oggi — {WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}</b>"
    if not events:
        return f"{title}\n\nNessun evento in programma. 😴"

    groups: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        groups[ev["competition"]].append(ev)

    parts = [title]
    # Groups ordered by their first event, so the day reads chronologically.
    for competition, items in groups.items():
        emoji = COMPETITION_EMOJI.get(competition, "🏆")
        lines = [f"\n{emoji} <b>{html.escape(competition)}</b>"]
        for ev in items:
            lines.append(f"<code>{ev['dt']:%H:%M}</code> {html.escape(ev['summary'])}")
        parts.append("\n".join(lines))
    return "\n".join(parts)


def gcal_url(filename: str) -> str:
    """Google Calendar subscribe link, same as the site's buttons.

    Telegram only accepts http(s)/tg links in buttons, so no webcal://.
    """
    return "https://www.google.com/calendar/render?cid=" + quote(SITE_URL + filename, safe="")


def build_keyboard(events: list[dict]) -> dict:
    """Link buttons: one per league in today's digest, then all sports + site."""
    buttons, seen = [], set()
    for ev in events:
        filename = COMPETITION_FILES.get(ev["competition"])
        if not filename or filename in seen:
            continue
        seen.add(filename)
        emoji = COMPETITION_EMOJI.get(ev["competition"], "🏆")
        buttons.append({"text": f"{emoji} {ev['competition']}", "url": gcal_url(filename)})

    rows = [buttons[i:i + BUTTONS_PER_ROW] for i in range(0, len(buttons), BUTTONS_PER_ROW)]
    rows.append([
        {"text": "📅 Tutti gli sport", "url": gcal_url("all.ics")},
        {"text": "🌐 Sito", "url": SITE_URL},
    ])
    return {"inline_keyboard": rows}


def split_message(text: str) -> list[str]:
    """Split on line boundaries to stay under Telegram's per-message limit."""
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > TELEGRAM_LIMIT:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current)
    return chunks


def send(token: str, chat_id: str, text: str, keyboard: dict) -> None:
    chunks = split_message(text)
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        # Buttons go under the last chunk, where the reader ends up.
        if i == len(chunks) - 1:
            payload["reply_markup"] = keyboard
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"Telegram API error {resp.status_code}: {resp.text}")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    competitions = {c.strip() for c in os.environ.get("COMPETITIONS", "").split(",") if c.strip()}

    now = datetime.now(TZ)
    start = now.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    if now < start:
        start -= timedelta(days=1)
    end = start + timedelta(days=1)

    events = load_events(start, end, competitions)
    message = build_message(events, start)
    keyboard = build_keyboard(events)
    logger.info("%d events between %s and %s", len(events), start, end)

    if not token or not chat_id:
        # Dry run: handy for previewing the digest locally.
        print(message)
        for row in keyboard["inline_keyboard"]:
            print("  ".join(f"[{b['text']}]" for b in row))
        return
    send(token, chat_id, message, keyboard)
    logger.info("Digest sent")


if __name__ == "__main__":
    main()

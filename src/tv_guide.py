"""Find where today's events are on Italian TV, using Sky Italia's EPG.

Sky's public guide API (the one behind guidatv.sky.it) lists not only the Sky
Sport channels but also DAZN 1-4 on Sky, SuperTennis, Rai Sport, Rai 1-3 and
TV8, so a single source covers most live sport in Italy. Events are matched to
listings by time window plus team / session / tournament names.

Streaming-only rights never appear in an EPG, so competitions whose every
event is guaranteed on a platform get a fixed fallback (COMPETITION_DEFAULTS).
"""

import difflib
import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

SKY_API = "https://apid.sky.it/gtv/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SportsCalendar/1.0)",
    "Accept": "application/json",
}
# The events endpoint silently caps its results (~700 per call), so the day
# is fetched in slices small enough to always stay under the cap.
SLICE = timedelta(hours=4)

# Free-to-air channels that carry live sport, besides the "Sport e Calcio" category.
FREE_CHANNELS = {"Rai 1 HD", "Rai 2 HD", "Rai 3 HD", "TV8 HD", "Canale 5 HD", "Italia 1 HD", "20 HD", "Cielo HD", "Nove HD"}
# Sport channels that only air replays or non-competitive programmes.
SKIP_CHANNELS = {"Sky Sport Legend", "Sky Sport24", "EQUtv", "Horse TV HD", "CACCIA e Pesca", "Caccia e PESCA"}

# Platforms that carry every event of the competition, shown even without an EPG hit.
COMPETITION_DEFAULTS = {
    "Serie A": ["DAZN"],             # all 380 matches, rights until 2028-29
    "NBA": ["NBA League Pass"],
}

# A live broadcast starts at most this long before the event (pre-show)...
MAX_LEAD = timedelta(hours=2)
# ...or this long after it, and is still on air this long after the start.
MAX_LAG = timedelta(minutes=20)
MIN_OVERLAP = timedelta(minutes=30)

MAX_CHANNELS = 3

STOPWORDS = {
    "fc", "cf", "bc", "ac", "as", "ss", "ssc", "us", "afc", "sc", "kk", "bk", "sk", "cd",
    "club", "basket", "basketball", "calcio", "football", "the", "and", "de", "del", "di",
    "atp", "wta", "open", "masters", "grand", "prix", "championships", "tournament",
    "international", "cup", "tennis", "group", "rolex", "bnp", "paribas", "trophy",
}

# F1 summary prefix -> (words the Sky title must contain, words it must not).
F1_SESSIONS = {
    "FP1": (["libere 1"], []),
    "FP2": (["libere 2"], []),
    "FP3": (["libere 3"], []),
    "Qualifiche": (["qualific"], ["sprint"]),
    "Sprint Qualifying": (["sprint", "qualific"], []),
    "Sprint": (["sprint"], ["qualific"]),
}
F1_RACE = (["gara"], ["sprint"])


def fetch_listings(start: datetime, end: datetime) -> list[dict]:
    """Sky EPG listings for the sport channels between start and end.

    Returns [] on any network/API error: TV info is a nice-to-have and must
    never stop the digest from going out.
    """
    try:
        channels = _sport_channel_ids()
        listings: dict[str, dict] = {}
        cursor = start
        while cursor < end:
            stop = min(cursor + SLICE, end)
            for item in _fetch_events(channels, cursor, stop):
                listings[item["id"]] = item
            cursor = stop
    except Exception as exc:
        logger.warning("Sky EPG unavailable, sending digest without TV info: %s", exc)
        return []
    logger.info("Sky EPG: %d listings", len(listings))
    return list(listings.values())


def _sport_channel_ids() -> list[str]:
    resp = requests.get(f"{SKY_API}/channels", params={"env": "DTH"}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    ids = []
    for ch in resp.json()["channels"]:
        name = ch.get("name", "").strip()
        is_sport = ch.get("category", {}).get("name") == "Sport e Calcio"
        if (is_sport or name in FREE_CHANNELS) and name not in SKIP_CHANNELS:
            ids.append(str(ch["id"]))
    return ids


def _fetch_events(channels: list[str], start: datetime, end: datetime) -> list[dict]:
    params = {
        "from": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pageSize": 999,
        "pageNum": 0,
        "env": "DTH",
        "channels": ",".join(channels),
    }
    resp = requests.get(f"{SKY_API}/events", params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    items = []
    for ev in resp.json().get("events", []):
        content = ev.get("content", {})
        if content.get("genre", {}).get("name") != "Sport":
            continue
        items.append({
            "id": ev["eventId"],
            "start": datetime.fromisoformat(ev["starttime"].replace("Z", "+00:00")),
            "end": datetime.fromisoformat(ev["endtime"].replace("Z", "+00:00")),
            "title": ev.get("eventTitle") or content.get("contentTitle") or "",
            "synopsis": ev.get("eventSynopsis") or "",
            "subgenre": content.get("subgenre", {}).get("name", ""),
            "channel": _channel_label(ev["channel"]),
            "number": ev["channel"].get("number", 0),
        })
    return items


def _channel_label(channel: dict) -> str:
    name = re.sub(r"\s+HD$", "", channel.get("name", "").strip())
    number = channel.get("number")
    if name == "Sky Sport":          # the numbered extra channels (251-259)
        return f"Sky Sport {number}"
    return f"{name} ({number})" if number else name


def channels_for(event: dict, listings: list[dict], day_start: datetime, day_end: datetime) -> list[str]:
    """EPG channels showing the event live, best guess, ordered by channel number."""
    competition = event["competition"]
    if competition.startswith("Tennis"):
        matches = [l for l in listings if _tennis_match(event, l, day_start, day_end)]
    else:
        matcher = {"F1": _f1_match, "MotoGP": _motogp_match}.get(competition, _team_match)
        matches = [l for l in listings if _on_air(event["dt"], l) and matcher(event, l)]

    seen, labels = set(), []
    for listing in sorted(matches, key=lambda l: l["number"]):
        if listing["channel"] not in seen:
            seen.add(listing["channel"])
            labels.append(listing["channel"])
    return labels[:MAX_CHANNELS]


def _on_air(dt: datetime, listing: dict) -> bool:
    """True if the listing plausibly is the live broadcast, not a replay."""
    return (dt - MAX_LEAD <= listing["start"] <= dt + MAX_LAG
            and listing["end"] >= dt + MIN_OVERLAP)


def _team_match(event: dict, listing: dict) -> bool:
    home, away = event.get("home"), event.get("away")
    if not home or not away or " - " not in listing["title"]:
        return False
    left, _, right = listing["title"].partition(" - ")
    left, right = _tokens(left), _tokens(right)
    home, away = _tokens(home), _tokens(away)
    return ((_similar(home, left) and _similar(away, right))
            or (_similar(home, right) and _similar(away, left)))


def _f1_match(event: dict, listing: dict) -> bool:
    text = _norm(f"{listing['title']} {listing['synopsis']} {listing['channel']}")
    if listing["subgenre"] != "Motori" or not re.search(r"\bf1\b|formula 1|formula uno", text):
        return False
    session = event["summary"].split(" — ")[0] if " — " in event["summary"] else ""
    required, forbidden = F1_SESSIONS.get(session, F1_RACE)
    title = _norm(listing["title"])
    return all(w in title for w in required) and not any(w in title for w in forbidden)


def _motogp_match(event: dict, listing: dict) -> bool:
    text = _norm(f"{listing['title']} {listing['synopsis']} {listing['channel']}")
    title = _norm(listing["title"])
    return ("motogp" in text and "gara" in title
            and not re.search(r"moto2|moto3|sprint|superbike|sbk", title))


def _tennis_match(event: dict, listing: dict, day_start: datetime, day_end: datetime) -> bool:
    # Tennis events are whole tournaments with a nominal start time, so any
    # tennis listing of the day that names the tournament counts.
    if listing["subgenre"] != "Tennis" or not day_start <= listing["start"] < day_end:
        return False
    tournament = _tokens(event.get("home") or event["summary"])
    text = set(_norm(f"{listing['title']} {listing['synopsis']}").split())
    return bool(tournament & text)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).split() if len(t) >= 3 and t not in STOPWORDS}


def _similar(a: set[str], b: set[str]) -> bool:
    """Some word in common, tolerating Italian spellings (Barcelona/Barcellona)."""
    for x in a:
        for y in b:
            if x == y or (min(len(x), len(y)) >= 5 and (x.startswith(y) or y.startswith(x))):
                return True
            if difflib.SequenceMatcher(None, x, y).ratio() >= 0.85:
                return True
    return False

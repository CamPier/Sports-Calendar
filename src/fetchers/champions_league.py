"""Fetches UEFA Champions League schedule from ESPN soccer API."""

from fetchers.serie_a import fetch_espn_soccer


def fetch_games() -> list[dict]:
    """Return Champions League match events for the current season."""
    return fetch_espn_soccer("uefa.champions", "Champions League")

"""Headlines from the day of a run, for the occasional topical nod.

Reads a public RSS feed (BBC News top stories by default). Only titles and
links are used, and Claude is told to leave grim stories alone.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import httpx

log = logging.getLogger(__name__)

DEFAULT_FEED = "https://feeds.bbci.co.uk/news/rss.xml"
MAX_HEADLINES = 10


def parse(xml_text: str, limit: int = MAX_HEADLINES) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    headlines = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            headlines.append({"title": title, "url": link})
        if len(headlines) >= limit:
            break
    return headlines


def fetch(http: httpx.Client, feed_url: str = DEFAULT_FEED) -> list[dict[str, str]]:
    """Today's headlines, or an empty list if the feed is unavailable."""
    try:
        response = http.get(feed_url, timeout=10, follow_redirects=True)
        response.raise_for_status()
        return parse(response.text)
    except (httpx.HTTPError, ET.ParseError):
        log.warning("News feed unavailable", exc_info=True)
        return []

"""Pure helpers: default-name detection, soundtrack matching, recent form."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# Strava's automatic names, e.g. "Morning Run", "Lunch Trail Run", "Evening Run".
DEFAULT_NAME = re.compile(
    r"^\s*((morning|lunch|afternoon|evening|night)\s+)?"
    r"(run|trail run|virtual run|treadmill run|walk|hike|ride)\s*$",
    re.IGNORECASE,
)
REROLL_SUFFIX = ":("


def parse_time(value: str) -> datetime:
    """Strava and Spotify both send ISO 8601 with a trailing Z."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_default_name(name: str | None) -> bool:
    return not (name or "").strip() or bool(DEFAULT_NAME.match(name))


def wants_reroll(name: str | None) -> bool:
    return (name or "").rstrip().endswith(REROLL_SUFFIX)


@dataclass(frozen=True)
class Track:
    artist: str
    title: str
    uri: str
    url: str
    played_at: str

    def line(self) -> str:
        return f"{self.artist} - {self.title}"


def soundtrack(items: list[dict], start: datetime, end: datetime, grace_s: int) -> list[Track]:
    """Tracks from Spotify's recently-played list that belong to the run.

    Spotify stamps each play with `played_at`, close to when the song
    finished, so we keep songs finishing between the start of the run and a
    short grace period after it ends. Returned oldest first.
    """
    window_end = end + timedelta(seconds=grace_s)
    tracks = []
    for item in items:
        track = item.get("track") or {}
        played = item.get("played_at")
        if not played or not track.get("uri"):
            continue
        if not (start <= parse_time(played) <= window_end):
            continue
        tracks.append(
            Track(
                artist=", ".join(a.get("name", "") for a in track.get("artists", [])) or "Unknown",
                title=track.get("name", "Unknown"),
                uri=track["uri"],
                url=(track.get("external_urls") or {}).get("spotify", ""),
                played_at=played,
            )
        )
    tracks.sort(key=lambda t: t.played_at)
    return tracks


@dataclass(frozen=True)
class Form:
    runs_last_7_days: int  # including this one
    runs_last_30_days: int  # including this one
    streak_days: int  # consecutive days with a run, ending on the day of this run
    days_since_previous: int | None

    def short(self) -> str:
        return f"{ordinal(self.runs_last_7_days)} run in 7 days"


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def recent_form(this_start: datetime, previous_starts: list[datetime]) -> Form:
    """previous_starts: start times of other runs before this one."""
    earlier = sorted(s for s in previous_starts if s < this_start)
    week = sum(1 for s in earlier if this_start - s <= timedelta(days=7)) + 1
    month = sum(1 for s in earlier if this_start - s <= timedelta(days=30)) + 1

    days: set[date] = {s.date() for s in earlier} | {this_start.date()}
    streak, cursor = 0, this_start.date()
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)

    since = (this_start.date() - earlier[-1].date()).days if earlier else None
    return Form(week, month, streak, since)

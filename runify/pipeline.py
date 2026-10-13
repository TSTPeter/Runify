"""What happens after a run lands on Strava.

1. Skip anything that isn't a run, or that the runner has named themselves.
2. Gather the soundtrack (Spotify), weather (Met Office via Open-Meteo) and
   recent form (Strava).
3. Make a public playlist of the soundtrack.
4. Ask Claude for a name and a one-line reflection.
5. Write the name and description back to Strava.

Everything gathered is saved per activity, so a reroll (ending the name with
":(") only asks Claude again rather than rebuilding the playlist.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

import httpx

from . import news as news_mod
from . import weather as weather_mod
from .config import Settings
from .namer import Namer
from .oauth import NotConnected
from .running import (
    Form,
    Track,
    is_default_name,
    parse_time,
    recent_form,
    soundtrack,
    wants_reroll,
)
from .spotify import SpotifyClient
from .store import Store
from .strava import StravaClient

log = logging.getLogger(__name__)

MAX_DESCRIPTION_TRACKS = 60
STALE_SECONDS = 15 * 60  # a "processing" record older than this was interrupted


def build_description(
    tracks: list[Track],
    weather: weather_mod.Weather | None,
    form: Form,
    line: str,
    playlist_url: str | None,
    runner_text: str = "",
    news: dict | None = None,
) -> str:
    summary = []
    if tracks:
        summary.append(f"🎧 {len(tracks)} track{'s' if len(tracks) != 1 else ''}")
    if weather:
        summary.append(f"{weather.emoji} {weather.short()}")
    summary.append(f"🔥 {form.short()}")

    parts = []
    if runner_text.strip():
        parts.append(runner_text.strip())
    parts.append(" · ".join(summary))
    if line:
        parts.append(line)
    if news:
        parts.append(f"📰 {news['title']}" + (f" ({news['url']})" if news.get("url") else ""))
    if tracks:
        heading = "Soundtrack"
        if playlist_url:
            heading += f" (playlist: {playlist_url})"
        lines = [f"{i}. {t.line()}" for i, t in enumerate(tracks[:MAX_DESCRIPTION_TRACKS], 1)]
        if len(tracks) > MAX_DESCRIPTION_TRACKS:
            lines.append(f"…and {len(tracks) - MAX_DESCRIPTION_TRACKS} more in the playlist")
        parts.append(heading + "\n" + "\n".join(lines))
    return "\n\n".join(parts)


def _matching_headline(chosen: str, headlines: list[dict]) -> dict | None:
    """The headline Claude says it used, if it really is one of ours."""
    wanted = chosen.strip().casefold()
    if not wanted:
        return None
    return next((h for h in headlines if h["title"].strip().casefold() == wanted), None)


def _facts(
    activity: dict, tracks: list[Track], weather, form: Form, headlines: list[dict] | None = None
) -> dict[str, Any]:
    distance_km = (activity.get("distance") or 0) / 1000
    moving = activity.get("moving_time") or activity.get("elapsed_time") or 0
    pace = None
    if distance_km > 0.1 and moving:
        secs = moving / distance_km
        pace = f"{int(secs // 60)}:{int(secs % 60):02d} per km"
    local = parse_time(activity.get("start_date_local") or activity["start_date"])
    return {
        "sport": activity.get("sport_type") or activity.get("type"),
        "distance_km": round(distance_km, 2),
        "moving_time_minutes": round(moving / 60),
        "pace": pace,
        "elevation_gain_m": activity.get("total_elevation_gain"),
        "local_start": local.strftime("%A %d %B, %H:%M"),
        "songs_in_order": [t.line() for t in tracks],
        "weather": asdict(weather) if weather else None,
        "recent_form": asdict(form),
        "news_headlines": [h["title"] for h in headlines or []],
    }


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        http: httpx.Client,
        strava: StravaClient,
        spotify: SpotifyClient,
        namer: Namer,
    ) -> None:
        self.settings = settings
        self.store = store
        self.http = http
        self.strava = strava
        self.spotify = spotify
        self.namer = namer

    # Entry point from the webhook

    def handle(self, activity_id: int) -> str:
        """Returns a short status string, mainly for logs and tests."""
        activity = self.strava.get_activity(activity_id)
        sport = activity.get("sport_type") or activity.get("type")
        if sport not in self.settings.sport_types:
            return f"skipped: {sport}"

        key = f"activity_{activity_id}"
        record = self.store.get(key)
        name = activity.get("name") or ""

        if record and record.get("status") == "done":
            if wants_reroll(name):
                return self._reroll(activity_id, key, record, name)
            return "skipped: already named"
        if record and record.get("status") == "processing" and time.time() - record.get("since", 0) < STALE_SECONDS:
            return "skipped: in progress"
        if not is_default_name(name):
            return "skipped: named by runner"

        self.store.set(key, {"status": "processing", "since": time.time()})
        try:
            return self._first_pass(activity, key)
        except Exception:
            self.store.set(key, {"status": "failed"})
            raise

    def _first_pass(self, activity: dict, key: str) -> str:
        start = parse_time(activity["start_date"])
        end = start + timedelta(seconds=activity.get("elapsed_time") or 0)

        tracks = self._tracks(start, end)
        weather = self._weather(activity, start)
        form = self._form(activity)
        headlines = news_mod.fetch(self.http, self.settings.news_feed_url)
        facts = _facts(activity, tracks, weather, form, headlines)
        naming = self.namer.name_run(facts)

        playlist = self._playlist(naming.name, start, tracks)
        runner_text = activity.get("description") or ""
        news = _matching_headline(naming.headline, headlines)
        description = build_description(
            tracks, weather, form, naming.line, playlist and playlist["url"], runner_text, news
        )
        self.strava.update_activity(activity["id"], naming.name, description)

        self.store.set(
            key,
            {
                "status": "done",
                "facts": facts,
                "names": [naming.name],
                "runner_text": runner_text,
                "tracks": [asdict(t) for t in tracks],
                "weather": asdict(weather) if weather else None,
                "form": asdict(form),
                "playlist": playlist,
                "headlines": headlines,
            },
        )
        log.info("Named activity %s: %s", activity["id"], naming.name)
        return f"named: {naming.name}"

    def _reroll(self, activity_id: int, key: str, record: dict, current: str) -> str:
        rejected = record.get("names", []) + [current.rstrip()[:-2].strip()]
        naming = self.namer.name_run(record["facts"], avoid=rejected)
        tracks = [Track(**t) for t in record.get("tracks", [])]
        weather = weather_mod.Weather(**record["weather"]) if record.get("weather") else None
        form = Form(**record["form"])
        playlist = record.get("playlist")
        if playlist:
            try:
                self.spotify.rename_playlist(playlist["id"], self._playlist_name(naming.name, record))
            except (httpx.HTTPError, NotConnected):
                log.warning("Could not rename playlist for %s", activity_id)
        news = _matching_headline(naming.headline, record.get("headlines", []))
        description = build_description(
            tracks,
            weather,
            form,
            naming.line,
            playlist and playlist["url"],
            record.get("runner_text", ""),
            news,
        )
        self.strava.update_activity(activity_id, naming.name, description)
        record["names"] = rejected + [naming.name]
        self.store.set(key, record)
        return f"rerolled: {naming.name}"

    # Gathering, each part optional so one failure never blocks the rest

    def _tracks(self, start: datetime, end: datetime) -> list[Track]:
        if not self.spotify.tokens.is_connected():
            return []
        before_ms = int((end + timedelta(seconds=self.settings.track_grace_seconds)).timestamp() * 1000)
        try:
            items = self.spotify.recently_played(before_ms)
        except httpx.HTTPError:
            log.exception("Spotify recently played failed")
            return []
        return soundtrack(items, start, end, self.settings.track_grace_seconds)

    def _weather(self, activity: dict, start: datetime) -> weather_mod.Weather | None:
        latlng = activity.get("start_latlng") or []
        if len(latlng) != 2:
            return None  # treadmill or GPS off
        return weather_mod.fetch(self.http, latlng[0], latlng[1], start, activity.get("elapsed_time") or 0)

    def _form(self, activity: dict) -> Form:
        this_local = parse_time(activity.get("start_date_local") or activity["start_date"])
        start_epoch = int(parse_time(activity["start_date"]).timestamp())
        try:
            recent = self.strava.list_activities(start_epoch - 31 * 86400, start_epoch)
        except httpx.HTTPError:
            log.exception("Strava activity list failed")
            recent = []
        previous = [
            parse_time(a.get("start_date_local") or a["start_date"])
            for a in recent
            if (a.get("sport_type") or a.get("type")) in self.settings.sport_types and a.get("id") != activity["id"]
        ]
        return recent_form(this_local, previous)

    def _playlist_name(self, run_name: str, record_or_start: Any) -> str:
        if isinstance(record_or_start, datetime):
            day = record_or_start.strftime("%d %b %Y")
        else:
            day = record_or_start["facts"]["local_start"]
        return f"{run_name} · {day}"[:100]

    def _playlist(self, run_name: str, start: datetime, tracks: list[Track]) -> dict | None:
        if not tracks:
            return None
        try:
            created = self.spotify.create_playlist(
                self._playlist_name(run_name, start),
                "The soundtrack to one run, gathered automatically from Strava and Spotify.",
                self.settings.playlist_public,
            )
            self.spotify.add_to_playlist(created["id"], [t.uri for t in tracks])
        except (httpx.HTTPError, NotConnected):
            log.exception("Playlist creation failed")
            return None
        return {"id": created["id"], "url": (created.get("external_urls") or {}).get("spotify", "")}

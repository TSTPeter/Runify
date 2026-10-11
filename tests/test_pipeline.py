import copy

import httpx
import respx

from runify import weather
from runify.config import Settings
from runify.namer import Naming
from runify.pipeline import Pipeline
from runify.store import MemoryStore

from .fixtures import ACTIVITY, OPEN_METEO, RECENT, RECENTLY_PLAYED


class FakeTokens:
    def __init__(self, connected=True):
        self.connected = connected

    def is_connected(self):
        return self.connected

    def get(self, field):
        return 42


class FakeStrava:
    def __init__(self, activity):
        self.activity = activity
        self.tokens = FakeTokens()
        self.updates = []

    def get_activity(self, activity_id):
        return copy.deepcopy(self.activity)

    def list_activities(self, after, before):
        return RECENT

    def update_activity(self, activity_id, name, description):
        self.updates.append((activity_id, name, description))
        self.activity["name"] = name


class FakeSpotify:
    def __init__(self, connected=True):
        self.tokens = FakeTokens(connected)
        self.playlists = []
        self.renamed = []

    def recently_played(self, before_ms):
        return RECENTLY_PLAYED

    def create_playlist(self, name, description, public):
        self.playlists.append({"name": name, "public": public, "uris": []})
        return {"id": "pl1", "external_urls": {"spotify": "https://open.spotify.com/playlist/pl1"}}

    def add_to_playlist(self, playlist_id, uris):
        self.playlists[-1]["uris"].extend(uris)

    def rename_playlist(self, playlist_id, name):
        self.renamed.append(name)


class FakeNamer:
    def __init__(self):
        self.calls = []

    def name_run(self, facts, avoid=None):
        self.calls.append((facts, avoid))
        return Naming(name=f"Drizzle Queen {len(self.calls)}", line="The wind had opinions.")


def make(activity=ACTIVITY, spotify_connected=True):
    settings = Settings(store_backend="memory")
    strava = FakeStrava(copy.deepcopy(activity))
    spotify = FakeSpotify(spotify_connected)
    namer = FakeNamer()
    pipeline = Pipeline(settings, MemoryStore(), httpx.Client(), strava, spotify, namer)
    return pipeline, strava, spotify, namer


@respx.mock
def test_first_pass_names_and_describes():
    respx.get(weather.API).mock(return_value=httpx.Response(200, json=OPEN_METEO))
    pipeline, strava, spotify, namer = make()

    assert pipeline.handle(1001) == "named: Drizzle Queen 1"

    _, name, description = strava.updates[0]
    assert name == "Drizzle Queen 1"
    assert description.splitlines()[0] == "🎧 3 tracks · 🌦 11°C, light drizzle, SW 12 mph · 🔥 3rd run in 7 days"
    assert "The wind had opinions." in description
    assert "Soundtrack (playlist: https://open.spotify.com/playlist/pl1)" in description
    assert "1. Test Artist 2 - Test Song 2" in description
    assert spotify.playlists[0]["uris"] == ["spotify:track:test2", "spotify:track:test3", "spotify:track:test4"]
    assert spotify.playlists[0]["public"] is True

    facts = namer.calls[0][0]
    assert facts["songs_in_order"][0] == "Test Artist 2 - Test Song 2"
    assert facts["weather"]["source"] == "Met Office (via Open-Meteo)"
    assert facts["recent_form"]["streak_days"] == 3


@respx.mock
def test_second_event_does_not_rename_again():
    respx.get(weather.API).mock(return_value=httpx.Response(200, json=OPEN_METEO))
    pipeline, strava, _, _ = make()
    pipeline.handle(1001)
    assert pipeline.handle(1001) == "skipped: already named"
    assert len(strava.updates) == 1


@respx.mock
def test_reroll_keeps_playlist_and_avoids_old_names():
    respx.get(weather.API).mock(return_value=httpx.Response(200, json=OPEN_METEO))
    pipeline, strava, spotify, namer = make()
    pipeline.handle(1001)
    strava.activity["name"] = "Drizzle Queen 1 :("

    assert pipeline.handle(1001) == "rerolled: Drizzle Queen 2"
    assert namer.calls[1][1] == ["Drizzle Queen 1", "Drizzle Queen 1"]
    assert len(spotify.playlists) == 1
    assert spotify.renamed and spotify.renamed[0].startswith("Drizzle Queen 2")
    assert "Soundtrack (playlist: https://open.spotify.com/playlist/pl1)" in strava.updates[1][2]


def test_runner_named_run_is_left_alone():
    pipeline, strava, _, namer = make({**ACTIVITY, "name": "Hill reps with the club"})
    assert pipeline.handle(1001) == "skipped: named by runner"
    assert not strava.updates and not namer.calls


def test_rides_are_ignored():
    pipeline, strava, _, _ = make({**ACTIVITY, "sport_type": "Ride"})
    assert pipeline.handle(1001) == "skipped: Ride"


def test_treadmill_without_spotify():
    pipeline, strava, spotify, _ = make({**ACTIVITY, "start_latlng": []}, spotify_connected=False)
    pipeline.handle(1001)
    description = strava.updates[0][2]
    assert description.splitlines()[0] == "🔥 3rd run in 7 days"
    assert "Soundtrack" not in description
    assert not spotify.playlists


@respx.mock
def test_runner_description_is_kept_on_top():
    respx.get(weather.API).mock(return_value=httpx.Response(200, json=OPEN_METEO))
    pipeline, strava, _, _ = make({**ACTIVITY, "description": "Legs like jelly."})
    pipeline.handle(1001)
    assert strava.updates[0][2].startswith("Legs like jelly.\n\n🎧 3 tracks")

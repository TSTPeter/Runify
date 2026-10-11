import httpx
import respx

from runify.spotify import API, SpotifyClient
from runify.store import MemoryStore


def client():
    store = MemoryStore()
    store.set("token_spotify", {"access_token": "a", "refresh_token": "r", "expires_at": 9_999_999_999})
    return SpotifyClient(httpx.Client(), store, "id", "secret")


@respx.mock
def test_create_playlist_falls_back_to_user_path():
    respx.post(f"{API}/me/playlists").mock(return_value=httpx.Response(404))
    respx.get(f"{API}/me").mock(return_value=httpx.Response(200, json={"id": "testuser"}))
    created = respx.post(f"{API}/users/testuser/playlists").mock(
        return_value=httpx.Response(201, json={"id": "pl1"})
    )
    assert client().create_playlist("n", "d", True)["id"] == "pl1"
    assert created.called


@respx.mock
def test_add_uses_items_endpoint_in_batches_of_100():
    route = respx.post(f"{API}/playlists/pl1/items").mock(return_value=httpx.Response(201, json={}))
    client().add_to_playlist("pl1", [f"spotify:track:{i}" for i in range(150)])
    assert route.call_count == 2


@respx.mock
def test_expired_token_is_refreshed_and_saved():
    store = MemoryStore()
    store.set("token_spotify", {"access_token": "old", "refresh_token": "r", "expires_at": 0})
    respx.post("https://accounts.spotify.com/api/token").mock(
        return_value=httpx.Response(200, json={"access_token": "new", "expires_in": 3600})
    )
    played = respx.get(f"{API}/me/player/recently-played").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    SpotifyClient(httpx.Client(), store, "id", "secret").recently_played(0)
    assert played.calls[0].request.headers["Authorization"] == "Bearer new"
    assert store.get("token_spotify")["refresh_token"] == "r"

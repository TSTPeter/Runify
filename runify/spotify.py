"""Spotify Web API: recently played tracks and per-run playlists.

Reference: https://developer.spotify.com/documentation/web-api
The February 2026 changes renamed playlist "tracks" to "items":
https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide
Where an endpoint moved, we try the current path first and fall back to the
older one, so the app keeps working whichever way Spotify has settled.
"""

from __future__ import annotations

import base64
from typing import Any
from urllib.parse import urlencode

import httpx

from .oauth import TokenKeeper
from .store import Store

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
SCOPES = "user-read-recently-played playlist-modify-public playlist-modify-private"


class SpotifyClient:
    def __init__(self, http: httpx.Client, store: Store, client_id: str, client_secret: str) -> None:
        self._http = http
        self._client_id = client_id
        self._client_secret = client_secret
        self.tokens = TokenKeeper(store, "token_spotify", self._refresh)

    # OAuth

    def authorise_url(self, redirect_uri: str, state: str) -> str:
        query = {
            "client_id": self._client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(query)}"

    def _basic_auth(self) -> dict[str, str]:
        raw = f"{self._client_id}:{self._client_secret}".encode()
        return {"Authorization": "Basic " + base64.b64encode(raw).decode()}

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        response = self._http.post(
            TOKEN_URL,
            headers=self._basic_auth(),
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        )
        response.raise_for_status()
        token = response.json()
        self.tokens.save(token)
        return token

    def _refresh(self, refresh_token: str) -> dict[str, Any]:
        response = self._http.post(
            TOKEN_URL,
            headers=self._basic_auth(),
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        response.raise_for_status()
        return response.json()

    # Reading

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens.access_token()}"}

    def recently_played(self, before_ms: int) -> list[dict[str, Any]]:
        """Up to 50 tracks played before the given time, newest first."""
        response = self._http.get(
            f"{API}/me/player/recently-played",
            headers=self._headers(),
            params={"limit": 50, "before": before_ms},
        )
        response.raise_for_status()
        return response.json().get("items", [])

    def _user_id(self) -> str:
        response = self._http.get(f"{API}/me", headers=self._headers())
        response.raise_for_status()
        return response.json()["id"]

    # Writing

    def create_playlist(self, name: str, description: str, public: bool) -> dict[str, Any]:
        body = {"name": name, "description": description, "public": public}
        response = self._http.post(f"{API}/me/playlists", headers=self._headers(), json=body)
        if response.status_code in (403, 404, 405):
            response = self._http.post(
                f"{API}/users/{self._user_id()}/playlists", headers=self._headers(), json=body
            )
        response.raise_for_status()
        return response.json()

    def add_to_playlist(self, playlist_id: str, uris: list[str]) -> None:
        for start in range(0, len(uris), 100):
            body = {"uris": uris[start : start + 100]}
            response = self._http.post(
                f"{API}/playlists/{playlist_id}/items", headers=self._headers(), json=body
            )
            if response.status_code in (404, 405):
                response = self._http.post(
                    f"{API}/playlists/{playlist_id}/tracks", headers=self._headers(), json=body
                )
            response.raise_for_status()

    def rename_playlist(self, playlist_id: str, name: str) -> None:
        response = self._http.put(
            f"{API}/playlists/{playlist_id}", headers=self._headers(), json={"name": name}
        )
        response.raise_for_status()

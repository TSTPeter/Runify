"""Strava API: OAuth, reading activities, writing the name and description.

Reference: https://developers.strava.com/docs/reference/
Webhooks:  https://developers.strava.com/docs/webhooks/
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from .oauth import TokenKeeper
from .store import Store

AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
API = "https://www.strava.com/api/v3"
SCOPES = "read,activity:read_all,activity:write"


class StravaClient:
    def __init__(self, http: httpx.Client, store: Store, client_id: str, client_secret: str) -> None:
        self._http = http
        self._client_id = client_id
        self._client_secret = client_secret
        self.tokens = TokenKeeper(store, "token_strava", self._refresh)

    # OAuth

    def authorise_url(self, redirect_uri: str, state: str) -> str:
        query = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": SCOPES,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(query)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = self._http.post(
            TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        token = response.json()
        athlete = token.pop("athlete", {}) or {}
        token["athlete_id"] = athlete.get("id")
        self.tokens.save(token)
        return token

    def _refresh(self, refresh_token: str) -> dict[str, Any]:
        response = self._http.post(
            TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()

    # Activities

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens.access_token()}"}

    def get_activity(self, activity_id: int) -> dict[str, Any]:
        response = self._http.get(f"{API}/activities/{activity_id}", headers=self._headers())
        response.raise_for_status()
        return response.json()

    def list_activities(self, after_epoch: int, before_epoch: int) -> list[dict[str, Any]]:
        response = self._http.get(
            f"{API}/athlete/activities",
            headers=self._headers(),
            params={"after": after_epoch, "before": before_epoch, "per_page": 100},
        )
        response.raise_for_status()
        return response.json()

    def update_activity(self, activity_id: int, name: str, description: str) -> None:
        response = self._http.put(
            f"{API}/activities/{activity_id}",
            headers=self._headers(),
            json={"name": name, "description": description},
        )
        response.raise_for_status()

    # Webhook subscription (one per Strava app)

    def list_subscriptions(self) -> list[dict[str, Any]]:
        response = self._http.get(
            f"{API}/push_subscriptions",
            params={"client_id": self._client_id, "client_secret": self._client_secret},
        )
        response.raise_for_status()
        return response.json()

    def create_subscription(self, callback_url: str, verify_token: str) -> dict[str, Any]:
        response = self._http.post(
            f"{API}/push_subscriptions",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "callback_url": callback_url,
                "verify_token": verify_token,
            },
        )
        response.raise_for_status()
        return response.json()

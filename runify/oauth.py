"""OAuth token bookkeeping shared by the Strava and Spotify clients.

Both services hand out a short-lived access token and a refresh token. We
keep both in the store and refresh a few minutes before expiry. Either
service may issue a new refresh token on refresh, so we always save
whatever comes back.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .store import Store

REFRESH_MARGIN_SECONDS = 300


class NotConnected(RuntimeError):
    """Raised when a service has not been authorised yet."""


class TokenKeeper:
    def __init__(
        self,
        store: Store,
        key: str,
        refresh: Callable[[str], dict[str, Any]],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._key = key
        self._refresh = refresh
        self._clock = clock

    def save(self, token: dict[str, Any]) -> None:
        existing = self._store.get(self._key) or {}
        merged = {**existing, **{k: v for k, v in token.items() if v is not None}}
        if "expires_in" in token and "expires_at" not in token:
            merged["expires_at"] = int(self._clock()) + int(token["expires_in"])
        self._store.set(self._key, merged)

    def is_connected(self) -> bool:
        return bool((self._store.get(self._key) or {}).get("refresh_token"))

    def access_token(self) -> str:
        token = self._store.get(self._key)
        if not token or not token.get("refresh_token"):
            raise NotConnected(self._key)
        if token.get("expires_at", 0) - REFRESH_MARGIN_SECONDS <= self._clock():
            self.save(self._refresh(token["refresh_token"]))
            token = self._store.get(self._key) or {}
        return token["access_token"]

    def get(self, field: str) -> Any:
        return (self._store.get(self._key) or {}).get(field)

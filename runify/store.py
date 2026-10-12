"""A tiny key/value store for OAuth tokens and per-run records.

Production uses Firestore (free tier is plenty for one runner). Tests and
local runs use the in-memory version.
"""

from __future__ import annotations

import copy
from typing import Any, Protocol


class Store(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...

    def set(self, key: str, value: dict[str, Any]) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        value = self._data.get(key)
        return copy.deepcopy(value) if value is not None else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = copy.deepcopy(value)


class FirestoreStore:
    """Stores each key as a document in one collection."""

    def __init__(self, collection: str = "runify") -> None:
        from google.cloud import firestore  # imported lazily so tests need no GCP

        self._collection = firestore.Client().collection(collection)

    def get(self, key: str) -> dict[str, Any] | None:
        snapshot = self._collection.document(key).get()
        return snapshot.to_dict() if snapshot.exists else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._collection.document(key).set(value)


def make_store(backend: str) -> Store:
    if backend == "memory":
        return MemoryStore()
    if backend == "firestore":
        return FirestoreStore()
    raise ValueError(f"Unknown STORE_BACKEND: {backend!r}")

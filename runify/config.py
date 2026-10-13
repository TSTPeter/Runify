"""Settings, read from environment variables.

Secrets (client secrets, API keys, the setup key) are injected by the host,
for example Google Secret Manager mounted as environment variables on Cloud
Run. Nothing secret lives in this repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    # Public address of this app, e.g. https://runs.peterfotheringham.com
    base_url: str = field(default_factory=lambda: _env("BASE_URL").rstrip("/"))

    strava_client_id: str = field(default_factory=lambda: _env("STRAVA_CLIENT_ID"))
    strava_client_secret: str = field(default_factory=lambda: _env("STRAVA_CLIENT_SECRET"))
    # Any random string; Strava echoes it back when confirming the webhook.
    strava_verify_token: str = field(default_factory=lambda: _env("STRAVA_VERIFY_TOKEN"))

    spotify_client_id: str = field(default_factory=lambda: _env("SPOTIFY_CLIENT_ID"))
    spotify_client_secret: str = field(default_factory=lambda: _env("SPOTIFY_CLIENT_SECRET"))

    # The Anthropic SDK reads ANTHROPIC_API_KEY itself; listed here for clarity.
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    claude_model: str = field(default_factory=lambda: _env("CLAUDE_MODEL", "claude-opus-5-5"))

    # Protects the /connect and /admin routes. A long random string.
    setup_key: str = field(default_factory=lambda: _env("SETUP_KEY"))

    # "firestore" in production, "memory" for local runs and tests.
    store_backend: str = field(default_factory=lambda: _env("STORE_BACKEND", "firestore"))

    # Strava sport types to name. Others are left alone.
    sport_types: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            s.strip() for s in _env("SPORT_TYPES", "Run,TrailRun,VirtualRun").split(",") if s.strip()
        )
    )

    # Wait before processing so Spotify has registered the last song.
    process_delay_seconds: int = field(
        default_factory=lambda: int(_env("PROCESS_DELAY_SECONDS", "60"))
    )
    # Songs that finish up to this long after the run still count.
    track_grace_seconds: int = field(
        default_factory=lambda: int(_env("TRACK_GRACE_SECONDS", "180"))
    )
    # Headlines for the topical nod in the name. Any RSS feed works.
    news_feed_url: str = field(
        default_factory=lambda: _env("NEWS_FEED_URL", "https://feeds.bbci.co.uk/news/rss.xml")
    )
    playlist_public: bool = field(
        default_factory=lambda: _env("PLAYLIST_PUBLIC", "true").lower() == "true"
    )

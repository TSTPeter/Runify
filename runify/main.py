"""Web routes: Strava webhook, one-off OAuth connections, and a status page."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from functools import lru_cache

import anthropic
import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .config import Settings
from .namer import Namer
from .pipeline import Pipeline
from .spotify import SpotifyClient
from .store import make_store
from .strava import StravaClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("runify")

app = FastAPI(title="Runify", docs_url=None, redoc_url=None)


@lru_cache
def get_pipeline() -> Pipeline:
    settings = Settings()
    store = make_store(settings.store_backend)
    http = httpx.Client(timeout=20)
    return Pipeline(
        settings=settings,
        store=store,
        http=http,
        strava=StravaClient(http, store, settings.strava_client_id, settings.strava_client_secret),
        spotify=SpotifyClient(http, store, settings.spotify_client_id, settings.spotify_client_secret),
        namer=Namer(anthropic.Anthropic(), settings.claude_model),
    )


def _state(settings: Settings, service: str) -> str:
    return hmac.new(settings.setup_key.encode(), service.encode(), hashlib.sha256).hexdigest()[:32]


def _require_key(pipeline: Pipeline, key: str) -> None:
    expected = pipeline.settings.setup_key
    if not expected or not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=403, detail="Wrong or missing setup key")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def home(key: str = "", pipeline: Pipeline = Depends(get_pipeline)) -> str:
    _require_key(pipeline, key)
    strava = "connected" if pipeline.strava.tokens.is_connected() else f'<a href="/connect/strava?key={key}">connect</a>'
    spotify = "connected" if pipeline.spotify.tokens.is_connected() else f'<a href="/connect/spotify?key={key}">connect</a>'
    return f"""<!doctype html><meta name=viewport content="width=device-width">
<title>Runify setup</title>
<body style="font-family:system-ui;max-width:36rem;margin:2rem auto;padding:0 1rem">
<h1>Runify setup</h1>
<p>Strava: {strava}</p>
<p>Spotify: {spotify}</p>
<p>Strava webhook: <a href="/admin/subscribe?key={key}">check or create</a></p>
</body>"""


# OAuth connections, done once each from a browser


@app.get("/connect/strava")
def connect_strava(key: str = "", pipeline: Pipeline = Depends(get_pipeline)):
    _require_key(pipeline, key)
    s = pipeline.settings
    return RedirectResponse(pipeline.strava.authorise_url(f"{s.base_url}/callback/strava", _state(s, "strava")))


@app.get("/callback/strava")
def callback_strava(code: str = "", state: str = "", scope: str = "", pipeline: Pipeline = Depends(get_pipeline)):
    if not hmac.compare_digest(state, _state(pipeline.settings, "strava")):
        raise HTTPException(status_code=403, detail="Bad state")
    if "activity:write" not in scope:
        return HTMLResponse("Please tick the box allowing the app to update your activities, then try again.", 400)
    pipeline.strava.exchange_code(code)
    return HTMLResponse("Strava connected. You can close this tab.")


@app.get("/connect/spotify")
def connect_spotify(key: str = "", pipeline: Pipeline = Depends(get_pipeline)):
    _require_key(pipeline, key)
    s = pipeline.settings
    return RedirectResponse(pipeline.spotify.authorise_url(f"{s.base_url}/callback/spotify", _state(s, "spotify")))


@app.get("/callback/spotify")
def callback_spotify(code: str = "", state: str = "", pipeline: Pipeline = Depends(get_pipeline)):
    if not hmac.compare_digest(state, _state(pipeline.settings, "spotify")):
        raise HTTPException(status_code=403, detail="Bad state")
    pipeline.spotify.exchange_code(code, f"{pipeline.settings.base_url}/callback/spotify")
    return HTMLResponse("Spotify connected. You can close this tab.")


@app.get("/admin/subscribe")
def subscribe(key: str = "", pipeline: Pipeline = Depends(get_pipeline)):
    """Registers this app's webhook with Strava (only one is allowed per app)."""
    _require_key(pipeline, key)
    existing = pipeline.strava.list_subscriptions()
    if existing:
        return {"status": "already subscribed", "subscriptions": existing}
    s = pipeline.settings
    created = pipeline.strava.create_subscription(f"{s.base_url}/webhook", s.strava_verify_token)
    return {"status": "subscribed", "subscription": created}


# Strava webhook


@app.get("/webhook")
def webhook_verify(request: Request, pipeline: Pipeline = Depends(get_pipeline)):
    params = request.query_params
    if params.get("hub.mode") != "subscribe" or not hmac.compare_digest(
        params.get("hub.verify_token", ""), pipeline.settings.strava_verify_token
    ):
        raise HTTPException(status_code=403, detail="Bad verify token")
    return JSONResponse({"hub.challenge": params.get("hub.challenge", "")})


def _process(pipeline: Pipeline, activity_id: int, delay: int) -> None:
    if delay:
        time.sleep(delay)
    try:
        log.info("Activity %s: %s", activity_id, pipeline.handle(activity_id))
    except Exception:
        log.exception("Activity %s failed", activity_id)


@app.post("/webhook")
async def webhook_event(request: Request, background: BackgroundTasks, pipeline: Pipeline = Depends(get_pipeline)):
    """Strava wants a 200 within two seconds, so the real work runs afterwards."""
    event = await request.json()
    if event.get("object_type") != "activity":
        return {"ok": True}
    athlete_id = pipeline.strava.tokens.get("athlete_id")
    if athlete_id is None or event.get("owner_id") != athlete_id:
        return {"ok": True}

    aspect = event.get("aspect_type")
    if aspect == "create":
        background.add_task(_process, pipeline, int(event["object_id"]), pipeline.settings.process_delay_seconds)
    elif aspect == "update" and "title" in (event.get("updates") or {}):
        background.add_task(_process, pipeline, int(event["object_id"]), 0)
    return {"ok": True}

from fastapi.testclient import TestClient

from runify import main
from runify.config import Settings


class FakePipeline:
    def __init__(self):
        self.settings = Settings(
            store_backend="memory", strava_verify_token="verify-me", setup_key="setup", process_delay_seconds=0
        )
        self.handled = []

        class Tokens:
            def get(self, field):
                return 42

        class Strava:
            tokens = Tokens()

        self.strava = Strava()

    def handle(self, activity_id):
        self.handled.append(activity_id)
        return "named"


def make_client():
    fake = FakePipeline()
    main.app.dependency_overrides[main.get_pipeline] = lambda: fake
    return TestClient(main.app), fake


def test_webhook_verification():
    client, _ = make_client()
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "abc"})
    assert ok.json() == {"hub.challenge": "abc"}
    bad = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "abc"})
    assert bad.status_code == 403


def test_create_and_title_events_are_processed():
    client, fake = make_client()
    event = {"object_type": "activity", "owner_id": 42, "object_id": 1001}
    client.post("/webhook", json={**event, "aspect_type": "create"})
    client.post("/webhook", json={**event, "aspect_type": "update", "updates": {"title": "x :("}})
    client.post("/webhook", json={**event, "aspect_type": "update", "updates": {"type": "Ride"}})
    client.post("/webhook", json={**event, "aspect_type": "delete"})
    assert fake.handled == [1001, 1001]


def test_other_athletes_are_ignored():
    client, fake = make_client()
    client.post("/webhook", json={"object_type": "activity", "owner_id": 7, "object_id": 5, "aspect_type": "create"})
    assert fake.handled == []


def test_setup_routes_need_the_key():
    client, _ = make_client()
    assert client.get("/connect/strava").status_code == 403
    assert client.get("/", params={"key": "wrong"}).status_code == 403


def test_health_avoids_cloud_run_reserved_path():
    # Cloud Run answers paths ending in "z" (such as /healthz) itself.
    client, _ = make_client()
    assert client.get("/health").json() == {"ok": True}

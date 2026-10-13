import inspect
import json
from types import SimpleNamespace

import anthropic

from runify.namer import Namer


class FakeMessages:
    def __init__(self, text, stop_reason="end_turn"):
        self.text, self.stop_reason, self.kwargs = text, stop_reason, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=self.text)]
        )


def fake_client(text):
    messages = FakeMessages(text)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_request_shape_and_cleaning():
    client, messages = fake_client(json.dumps({"name": '"Rain Again \u2014 Again"', "line": "Soggy but smug.", "headline": " Marrow wins "}))
    naming = Namer(client, "claude-opus-5-5").name_run({"distance_km": 5}, avoid=["Old Name"])

    assert naming.name == "Rain Again, Again"
    assert naming.headline == "Marrow wins"
    assert messages.kwargs["model"] == "claude-opus-5-5"
    assert messages.kwargs["fallbacks"] == "default"
    assert messages.kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert messages.kwargs["output_config"]["format"]["type"] == "json_schema"
    assert "Old Name" in messages.kwargs["messages"][0]["content"]


def test_sdk_accepts_every_argument_we_send():
    _, messages = fake_client('{"name": "x", "line": "y", "headline": ""}')
    Namer(SimpleNamespace(beta=SimpleNamespace(messages=messages)), "m").name_run({})
    accepted = inspect.signature(anthropic.resources.beta.messages.Messages.create).parameters
    assert set(messages.kwargs) <= set(accepted)


def test_prompt_puts_run_weather_and_news_before_songs():
    from runify.namer import SCHEMA, SYSTEM

    assert SYSTEM.index("The run itself") < SYSTEM.index("The weather") < SYSTEM.index("The news")
    assert "Never joke about deaths" in SYSTEM
    assert "say nothing\nabout music" in SYSTEM
    assert SCHEMA["required"] == ["name", "line", "headline"]

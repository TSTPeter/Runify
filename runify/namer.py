"""Claude writes the run's name and a one-line reflection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import anthropic

SYSTEM = """You name Strava runs for one particular runner.

Style: wry and a little poetic, fond of puns on song titles and lyrics from the
soundtrack of the run. Warm, never mean. Never generic ("Morning Miles",
"Sunday Shuffle"). British English. Do not use em-dashes.

You get the run's facts as JSON: distance, pace, time of day, the songs played
during the run in order, the weather, and how often they have run lately.
Weave in whatever is most striking. A lyric pun is best when a song fits the
conditions (a rain song in drizzle, a comeback song after a long gap), but do
not force it.

Return:
- name: at most 60 characters, no surrounding quotes, at most one emoji.
- line: one sentence, at most 140 characters, a wry or poetic observation about
  this run that adds something the name did not say.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "line": {"type": "string"},
    },
    "required": ["name", "line"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Naming:
    name: str
    line: str


def _clean(text: str, limit: int) -> str:
    text = text.replace(" \u2014 ", ", ").replace("\u2014", ", ")
    text = " ".join(text.split()).strip().strip('"')
    return text[:limit].rstrip()


class Namer:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self._model = model

    def name_run(self, facts: dict[str, Any], avoid: list[str] | None = None) -> Naming:
        prompt = "Run facts:\n" + json.dumps(facts, indent=2, ensure_ascii=False)
        if avoid:
            prompt += "\n\nThe runner rejected these names, so try a different angle:\n" + "\n".join(
                f"- {n}" for n in avoid
            )
        response = self._client.beta.messages.create(
            model=self._model,
            max_tokens=2000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            # On a safety decline, let the API re-run the request on a suitable model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Claude declined to name this run")
        text = next(block.text for block in response.content if block.type == "text")
        data = json.loads(text)
        return Naming(name=_clean(data["name"], 60), line=_clean(data["line"], 140))

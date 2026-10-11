import httpx
import respx

from runify import weather
from runify.running import parse_time

from .fixtures import OPEN_METEO


def test_compass():
    assert [weather.compass(d) for d in (0, 20, 46, 180, 225, 359)] == ["N", "N", "NE", "S", "SW", "N"]


def test_parse_picks_nearest_hour():
    w = weather.parse(OPEN_METEO, parse_time("2026-10-05T07:15:00Z"), "test")
    assert w.short() == "11°C, light drizzle, SW 12 mph"
    assert w.emoji == "🌦"


@respx.mock
def test_fetch_falls_back_when_met_office_has_gaps():
    empty = {"hourly": {"time": ["2026-10-05T07:00"], "temperature_2m": [None]}}
    route = respx.get(weather.API).mock(
        side_effect=[httpx.Response(200, json=empty), httpx.Response(200, json=OPEN_METEO)]
    )
    with httpx.Client() as http:
        w = weather.fetch(http, 55.95, -3.19, parse_time("2026-10-05T07:00:00Z"), 1800)
    assert route.call_count == 2
    assert route.calls[0].request.url.params["models"] == "ukmo_seamless"
    assert w.source == "Open-Meteo"


@respx.mock
def test_fetch_uses_met_office_first():
    respx.get(weather.API).mock(return_value=httpx.Response(200, json=OPEN_METEO))
    with httpx.Client() as http:
        w = weather.fetch(http, 55.95, -3.19, parse_time("2026-10-05T07:00:00Z"), 1800)
    assert w.source == "Met Office (via Open-Meteo)"

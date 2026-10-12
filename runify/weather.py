"""Weather at the time and place of a run.

Uses Open-Meteo with the UK Met Office "seamless" model (UKV 2 km over the
UK, global 10 km elsewhere), falling back to Open-Meteo's best model where
the Met Office data has gaps. No API key needed; free for non-commercial use.
https://open-meteo.com/en/docs/ukmo-api
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

API = "https://api.open-meteo.com/v1/forecast"
HOURLY = (
    "temperature_2m,apparent_temperature,precipitation,weather_code,"
    "wind_speed_10m,wind_direction_10m,relative_humidity_2m"
)
MODELS = ("ukmo_seamless", "best_match")

# WMO weather interpretation codes, as used by Open-Meteo.
WMO = {
    0: ("clear sky", "☀️"),
    1: ("mainly clear", "🌤"),
    2: ("partly cloudy", "⛅"),
    3: ("overcast", "☁️"),
    45: ("fog", "🌫"),
    48: ("freezing fog", "🌫"),
    51: ("light drizzle", "🌦"),
    53: ("drizzle", "🌦"),
    55: ("heavy drizzle", "🌧"),
    56: ("freezing drizzle", "🌧"),
    57: ("heavy freezing drizzle", "🌧"),
    61: ("light rain", "🌦"),
    63: ("rain", "🌧"),
    65: ("heavy rain", "🌧"),
    66: ("freezing rain", "🌧"),
    67: ("heavy freezing rain", "🌧"),
    71: ("light snow", "🌨"),
    73: ("snow", "🌨"),
    75: ("heavy snow", "❄️"),
    77: ("snow grains", "🌨"),
    80: ("light showers", "🌦"),
    81: ("showers", "🌧"),
    82: ("violent showers", "⛈"),
    85: ("snow showers", "🌨"),
    86: ("heavy snow showers", "❄️"),
    95: ("thunderstorm", "⛈"),
    96: ("thunderstorm with hail", "⛈"),
    99: ("thunderstorm with heavy hail", "⛈"),
}

COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


@dataclass(frozen=True)
class Weather:
    temperature_c: float
    feels_like_c: float | None
    conditions: str
    emoji: str
    wind_mph: float
    wind_from: str
    precipitation_mm: float | None
    humidity_pct: float | None
    source: str

    def short(self) -> str:
        """e.g. '11°C, light drizzle, SW 12 mph'"""
        return f"{round(self.temperature_c)}°C, {self.conditions}, {self.wind_from} {round(self.wind_mph)} mph"


def compass(degrees: float) -> str:
    return COMPASS[int(((degrees % 360) + 22.5) // 45) % 8]


def _pick_hour(times: list[str], moment: datetime) -> int:
    target = moment.astimezone(timezone.utc).replace(tzinfo=None)
    parsed = [datetime.fromisoformat(t) for t in times]
    return min(range(len(parsed)), key=lambda i: abs(parsed[i] - target))


def parse(payload: dict, moment: datetime, source: str) -> Weather | None:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        return None
    i = _pick_hour(times, moment)

    def value(name: str):
        series = hourly.get(name) or []
        return series[i] if i < len(series) else None

    temperature = value("temperature_2m")
    code = value("weather_code")
    wind = value("wind_speed_10m")
    direction = value("wind_direction_10m")
    if temperature is None or code is None or wind is None or direction is None:
        return None
    conditions, emoji = WMO.get(int(code), ("unsettled", "🌡"))
    return Weather(
        temperature_c=float(temperature),
        feels_like_c=value("apparent_temperature"),
        conditions=conditions,
        emoji=emoji,
        wind_mph=float(wind),
        wind_from=compass(float(direction)),
        precipitation_mm=value("precipitation"),
        humidity_pct=value("relative_humidity_2m"),
        source=source,
    )


def fetch(http: httpx.Client, lat: float, lon: float, start: datetime, elapsed_s: int) -> Weather | None:
    """Weather at the middle of the run, or None if nothing usable came back."""
    middle = start + timedelta(seconds=elapsed_s / 2)
    day = middle.astimezone(timezone.utc).date().isoformat()
    for model in MODELS:
        params = {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "hourly": HOURLY,
            "start_date": day,
            "end_date": day,
            "timezone": "GMT",
            "wind_speed_unit": "mph",
            "models": model,
        }
        try:
            response = http.get(API, params=params, timeout=15)
            response.raise_for_status()
        except httpx.HTTPError:
            continue
        source = "Met Office (via Open-Meteo)" if model == "ukmo_seamless" else "Open-Meteo"
        weather = parse(response.json(), middle, source)
        if weather:
            return weather
    return None

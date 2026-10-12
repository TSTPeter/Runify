"""Synthetic test data. Nothing here describes a real person or run."""

ACTIVITY = {
    "id": 1001,
    "name": "Morning Run",
    "description": "",
    "sport_type": "Run",
    "start_date": "2026-10-05T07:00:00Z",
    "start_date_local": "2026-10-05T08:00:00Z",
    "elapsed_time": 1800,
    "moving_time": 1750,
    "distance": 5000.0,
    "total_elevation_gain": 42.0,
    "start_latlng": [55.95, -3.19],
}

RECENT = [
    {"id": 990, "sport_type": "Run", "start_date": "2026-10-04T07:00:00Z", "start_date_local": "2026-10-04T08:00:00Z"},
    {"id": 991, "sport_type": "Ride", "start_date": "2026-10-03T07:00:00Z", "start_date_local": "2026-10-03T08:00:00Z"},
    {"id": 992, "sport_type": "Run", "start_date": "2026-10-03T07:00:00Z", "start_date_local": "2026-10-03T08:00:00Z"},
    {"id": 993, "sport_type": "Run", "start_date": "2026-09-20T07:00:00Z", "start_date_local": "2026-09-20T08:00:00Z"},
]


def track(n: int, played_at: str) -> dict:
    return {
        "played_at": played_at,
        "track": {
            "name": f"Test Song {n}",
            "uri": f"spotify:track:test{n}",
            "artists": [{"name": f"Test Artist {n}"}],
            "external_urls": {"spotify": f"https://open.spotify.com/track/test{n}"},
        },
    }


RECENTLY_PLAYED = [
    track(5, "2026-10-05T07:40:00Z"),  # after the grace period: excluded
    track(4, "2026-10-05T07:31:00Z"),  # inside the grace period
    track(3, "2026-10-05T07:20:00Z"),
    track(2, "2026-10-05T07:04:00Z"),
    track(1, "2026-10-05T06:58:00Z"),  # before the run: excluded
]

OPEN_METEO = {
    "hourly": {
        "time": ["2026-10-05T06:00", "2026-10-05T07:00", "2026-10-05T08:00"],
        "temperature_2m": [9.0, 10.6, 12.0],
        "apparent_temperature": [7.0, 8.1, 10.0],
        "precipitation": [0.0, 0.2, 0.0],
        "weather_code": [3, 51, 2],
        "wind_speed_10m": [10.0, 12.4, 14.0],
        "wind_direction_10m": [200.0, 225.0, 240.0],
        "relative_humidity_2m": [80, 88, 75],
    }
}

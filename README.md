# Runify

Every time a run lands on Strava with a default name ("Morning Run" and so
on), this app:

1. finds the songs you played on Spotify between the start and end of the run;
2. makes a public Spotify playlist of exactly those songs;
3. looks up the weather at the start point using the Met Office model (via
   Open-Meteo), falling back to Open-Meteo's best model;
4. counts how often you have run lately (runs in 7 and 30 days, streak, days
   since the last one);
5. reads the day's BBC News headlines;
6. asks Claude for a wry name built from the run itself, the weather and,
   when one suits, a light nod to the news (never grim stories), plus a
   one-line reflection;
7. writes the name and description back to Strava.

A description looks like this:

```
🎧 9 tracks · 🌦 11°C, light drizzle, SW 12 mph · 🔥 4th run in 7 days

The wind had opinions; so did the bassline.

📰 Village fete crowns giant marrow champion (https://www.bbc.co.uk/news/...)

Soundtrack (playlist: https://open.spotify.com/playlist/...)
1. Artist - Song
2. Artist - Song
```

## Rules it follows

- **Your names win.** It only touches runs with a Strava default name. Name a
  run yourself and it is left alone.
- **Reroll.** Don't like the name? Add `:(` to the end of it on Strava and it
  will try again, avoiding the names you have already rejected. The playlist
  is renamed to match rather than rebuilt.
- **Your words stay.** If you typed a description before it ran, yours stays
  at the top.
- **Graceful gaps.** No GPS (treadmill), Spotify not connected, or no music:
  those parts are simply left out.
- Runs only (`Run`, `TrailRun`, `VirtualRun`). Change `SPORT_TYPES` to add more.

Switch off naming in Bandók, otherwise the two apps race to rename the same run.

## How it fits together

```
Strava ──webhook──▶ Cloud Run (this app) ──▶ Spotify: recently played, new playlist
                         │                 ──▶ Open-Meteo: Met Office weather
                         │                 ──▶ Strava: recent runs
                         │                 ──▶ Claude: name and one-liner
                         ▼
                    Firestore (tokens and one record per run)
                         │
                         └──▶ Strava: update name and description
```

Strava expects a reply to its webhook within two seconds, so the app replies
at once and does the work in the background, after a 60 second pause so
Spotify has registered your last song. Cloud Run must therefore be deployed
with CPU always allocated (see the setup guide).

| File | What it does |
| --- | --- |
| `runify/main.py` | Web routes: Strava webhook, one-off connect pages |
| `runify/pipeline.py` | The steps above, and the description layout |
| `runify/running.py` | Default-name rules, matching songs to the run, recent form |
| `runify/weather.py` | Open-Meteo lookup and plain-English conditions |
| `runify/news.py` | The day's headlines from an RSS feed (`NEWS_FEED_URL`) |
| `runify/namer.py` | The Claude prompt (edit `SYSTEM` to change the voice) |
| `runify/strava.py`, `spotify.py` | API clients and OAuth |
| `runify/store.py` | Firestore, or in-memory for tests |

## Setting it up

Follow [docs/setup-with-claude-for-chrome.md](docs/setup-with-claude-for-chrome.md).
It is written so you can hand each part to Claude in Chrome, with clear stops
where you need to log in or handle a secret yourself.

## Running the tests

```
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

All test data is synthetic (`tests/fixtures.py`).

## Things worth knowing

- **Spotify history is short.** Spotify only keeps your last 50 plays, so a
  run uploaded many hours later, after lots more listening, can lose songs.
  Songs only count once played for 30 seconds or more. Podcasts don't appear.
- **Spotify's 2026 rules.** Apps in development mode need the owner to have
  Premium and allow up to 5 users, which suits a personal app.
  ([Spotify, Feb 2026](https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security))
- **Weather is modelled, not observed.** It is the Met Office model's value
  for the hour nearest the middle of your run, at your start point.
  ([Open-Meteo UK Met Office API](https://open-meteo.com/en/docs/ukmo-api))
- **Strava's API terms** restrict how activity data is used, including with
  AI. This app sends one run's summary to Claude to write a caption for your
  own activity, which is a different thing from model training, but read the
  [Strava API Agreement](https://www.strava.com/legal/api) yourself.
- **Costs.** Cloud Run, Firestore and Open-Meteo all sit inside free tiers for
  one runner. Claude costs roughly 1 to 2p per run; set a spend limit in the
  Claude Console.

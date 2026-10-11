from datetime import datetime, timezone

from runify.running import (
    is_default_name,
    ordinal,
    parse_time,
    recent_form,
    soundtrack,
    wants_reroll,
)

from .fixtures import RECENTLY_PLAYED


def test_default_names():
    for name in ["Morning Run", "lunch run", "Evening Trail Run", "Night Run", "Run", "", None]:
        assert is_default_name(name), name
    for name in ["Hill reps", "Morning Run with Sam", "Parkrun"]:
        assert not is_default_name(name), name


def test_reroll():
    assert wants_reroll("Drizzle and Dancing Queen :(")
    assert not wants_reroll("Drizzle and Dancing Queen :)")


def test_soundtrack_window_and_order():
    start = parse_time("2026-10-05T07:00:00Z")
    end = parse_time("2026-10-05T07:30:00Z")
    tracks = soundtrack(RECENTLY_PLAYED, start, end, grace_s=180)
    assert [t.title for t in tracks] == ["Test Song 2", "Test Song 3", "Test Song 4"]
    assert tracks[0].line() == "Test Artist 2 - Test Song 2"


def test_recent_form():
    utc = timezone.utc
    this = datetime(2026, 10, 5, 8, tzinfo=utc)
    previous = [datetime(2026, 10, 4, 8, tzinfo=utc), datetime(2026, 10, 3, 8, tzinfo=utc), datetime(2026, 9, 20, 8, tzinfo=utc)]
    form = recent_form(this, previous)
    assert form.runs_last_7_days == 3
    assert form.runs_last_30_days == 4
    assert form.streak_days == 3
    assert form.days_since_previous == 1
    assert form.short() == "3rd run in 7 days"


def test_first_run_ever():
    form = recent_form(datetime(2026, 10, 5, tzinfo=timezone.utc), [])
    assert (form.runs_last_7_days, form.streak_days, form.days_since_previous) == (1, 1, None)


def test_ordinal():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 111)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "111th"
    ]

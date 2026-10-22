from datetime import date, datetime, timezone

import pytest

from scriptmatria import astro


def test_meeus_worked_example_49a():
    # New moon of 1977 Feb, k = -283: JDE 2443192.65118 (Astronomical Algorithms, ex. 49.a)
    assert astro.phase_jde(-283) == pytest.approx(2443192.65118, abs=1e-5)


@pytest.mark.parametrize("k,expected", [
    # Published phase times (UTC), January 2024 and the 2024-04-08 eclipse new moon.
    (296.75, datetime(2024, 1, 4, 3, 30)),
    (297.0, datetime(2024, 1, 11, 11, 57)),
    (297.25, datetime(2024, 1, 18, 3, 52)),
    (297.5, datetime(2024, 1, 25, 17, 54)),
    (300.0, datetime(2024, 4, 8, 18, 21)),
])
def test_phase_times_within_two_minutes(k, expected):
    got = astro.phase_utc(k)
    assert abs((got - expected.replace(tzinfo=timezone.utc)).total_seconds()) <= 120


def test_principal_phase_on_its_day():
    m = astro.moon_phase(date(2024, 1, 25))
    assert m["phase"] == "Full Moon" and m["principal_phase_utc"] == "2024-01-25 17:54 UTC"
    assert m["days_to_full_moon"] == 0
    assert astro.moon_phase(date(2024, 4, 8))["principal_phase_utc"] == "2024-04-08 18:21 UTC"


@pytest.mark.parametrize("d,name", [
    (date(2024, 1, 14), "Waxing Crescent"),
    (date(2024, 1, 21), "Waxing Gibbous"),
    (date(2024, 1, 28), "Waning Gibbous"),
    (date(2024, 1, 7), "Waning Crescent"),
])
def test_intermediate_phase_names(d, name):
    m = astro.moon_phase(d)
    assert m["phase"] == name and m["principal_phase_utc"] is None


def test_timezone_moves_the_calendar_day():
    # Full moon 2026-10-26 04:11 UTC is still the evening of Oct 25 in Los Angeles.
    assert astro.moon_phase(date(2026, 10, 26))["phase"] == "Full Moon"
    assert astro.moon_phase(date(2026, 10, 25))["phase"] == "Waxing Gibbous"
    assert astro.moon_phase(date(2026, 10, 25), "America/Los_Angeles")["phase"] == "Full Moon"
    assert astro.moon_phase(date(2026, 10, 26), "America/Los_Angeles")["phase"] == "Waning Gibbous"


def test_moon_age_and_countdowns():
    m = astro.moon_phase(date(2026, 10, 22))
    assert m["phase"] == "Waxing Gibbous"
    assert 11 < m["moon_age_days"] < 13
    assert m["days_to_full_moon"] == 4


@pytest.mark.parametrize("d,sign", [
    (date(2026, 1, 1), "Capricorn"), (date(2026, 1, 19), "Capricorn"), (date(2026, 1, 20), "Aquarius"),
    (date(2026, 2, 18), "Aquarius"), (date(2026, 2, 19), "Pisces"), (date(2026, 3, 20), "Pisces"),
    (date(2026, 3, 21), "Aries"), (date(2026, 4, 20), "Taurus"), (date(2026, 5, 21), "Gemini"),
    (date(2026, 6, 21), "Cancer"), (date(2026, 7, 23), "Leo"), (date(2026, 8, 23), "Virgo"),
    (date(2026, 9, 23), "Libra"), (date(2026, 10, 22), "Libra"), (date(2026, 10, 23), "Scorpio"),
    (date(2026, 11, 22), "Sagittarius"), (date(2026, 12, 21), "Sagittarius"),
    (date(2026, 12, 22), "Capricorn"), (date(2000, 2, 29), "Pisces"),
])
def test_zodiac_boundaries(d, sign):
    assert astro.zodiac_sign(d) == sign

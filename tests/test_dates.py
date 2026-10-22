from datetime import date, timedelta

import pytest

from scriptmatria import dates


def test_audit_anniversary_case():
    s = dates.birthday_spans(date(2020, 6, 1), date(2021, 6, 1))
    assert s["total_days"] == 365
    assert (s["age_years"], s["ymd_months"], s["ymd_days"]) == (1, 0, 0)
    assert s["days_since_birthday"] == 0 and s["days_until_birthday"] == 0


def test_ymd_never_negative_across_leap_years():
    for birth in (date(1992, 2, 29), date(1999, 12, 31), date(2000, 3, 1), date(2003, 1, 31)):
        d = birth
        while d < date(2009, 1, 1):
            y, m, dd = dates.ymd(birth, d)
            assert y >= 0 and 0 <= m < 12 and dd >= 0
            d += timedelta(days=13)


def test_feb29_birthday_observed_feb28():
    s = dates.birthday_spans(date(2000, 2, 29), date(2021, 2, 28))
    assert s["days_since_birthday"] == 0
    assert s["age_years"] == 21  # same Feb 28 convention for the year boundary
    s = dates.birthday_spans(date(2000, 2, 29), date(2024, 3, 1))
    assert s["days_since_birthday"] == 1 and s["age_years"] == 24


def test_since_plus_until_is_birthday_year_length():
    s = dates.birthday_spans(date(1998, 3, 14), date(2026, 10, 22))
    assert s == {"total_days": 10449, "age_years": 28, "ymd_months": 7, "ymd_days": 8,
                 "days_since_birthday": 222, "days_until_birthday": 143, "total_weeks": 1492}


def test_end_before_start_rejected():
    with pytest.raises(ValueError):
        dates.ymd(date(2020, 1, 2), date(2020, 1, 1))


def test_date_numerology_reference_date():
    assert dates.date_numerology(date(2026, 10, 22)) == {
        "DN1": 78, "DN2": 42, "DN3": 15, "DN4": 58, "DN5": 13, "DOY": 295, "DAYS_LEFT": 70}
    assert dates.date_numerology(date(2024, 12, 31))["DAYS_LEFT"] == 0
    assert dates.date_numerology(date(2024, 12, 31))["DOY"] == 366
    assert dates.weekday(date(2026, 10, 22)) == "Thursday"

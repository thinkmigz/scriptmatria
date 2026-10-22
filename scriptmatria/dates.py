"""Birthday spans and calendar codes.

Each span is a distinct, labeled anchor; they are never substituted for one
another. Feb 29 birthdays: observance in non-leap years is a pending rule
(rulebook §13), so any span that depends on it is returned as None (UNVERIFIED)
instead of being guessed.
"""

import calendar
from datetime import date


def _is_leapling(birth: date) -> bool:
    return birth.month == 2 and birth.day == 29


def _add_months(d: date, months: int) -> tuple[date, bool]:
    """d plus whole months, and whether the day had to be clamped (e.g. Feb 29 -> Feb 28)."""
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last)), d.day > last


def ymd(start: date, end: date) -> tuple[int, int, int] | None:
    """Exact calendar years, months and remaining days from start to end, or None
    when the answer depends on how a missing day (Feb 29) is observed."""
    if end < start:
        raise ValueError("end date precedes start date")
    months = (end.year - start.year) * 12 + (end.month - start.month)
    anchor, clamped = _add_months(start, months)
    if anchor > end:
        months -= 1
        anchor, clamped = _add_months(start, months)
    if clamped and _is_leapling(start):
        return None
    return months // 12, months % 12, (end - anchor).days


def _leapling_last_next(birth: date, event: date) -> tuple[date | None, date | None]:
    """Most recent and next Feb 29 birthdays, or None where a non-leap year makes
    the observed date ambiguous."""
    y = event.year
    if calendar.isleap(y) and event == date(y, 2, 29):
        return event, event
    ambiguous = not calendar.isleap(y) and date(y, 2, 28) <= event < date(y, 3, 1)
    last_year = y if event >= date(y, 3, 1) else y - 1
    next_year = y if event < date(y, 2, 28) or (calendar.isleap(y) and event < date(y, 2, 29)) else y + 1
    last = date(last_year, 2, 29) if calendar.isleap(last_year) and not ambiguous else None
    nxt = date(next_year, 2, 29) if calendar.isleap(next_year) and not ambiguous else None
    return last, nxt


def birthday_spans(birth: date, event: date) -> dict[str, int | None]:
    """Spans from birth to the local event date. None means UNVERIFIED (Feb 29 pending).
    An event-day birthday gives days_since = days_until = 0."""
    total = (event - birth).days
    exact = ymd(birth, event)
    if _is_leapling(birth):
        last, nxt = _leapling_last_next(birth, event)
    else:
        this_year = date(event.year, birth.month, birth.day)
        last = this_year if this_year <= event else date(event.year - 1, birth.month, birth.day)
        nxt = this_year if this_year >= event else date(event.year + 1, birth.month, birth.day)
    return {
        "total_days": total,
        "age_years": exact[0] if exact else None,
        "ymd_months": exact[1] if exact else None,
        "ymd_days": exact[2] if exact else None,
        "days_since_birthday": (event - last).days if last else None,
        "days_until_birthday": (nxt - event).days if nxt else None,
        "total_weeks": total // 7,
    }


def _digits(n: int) -> list[int]:
    return [int(c) for c in str(n)]


def date_numerology(d: date) -> dict[str, int]:
    """DN1-DN5, day of year, days left in the year (formulas in the rule registry)."""
    m, day, y = d.month, d.day, d.year
    century, yy = divmod(y, 100)
    doy = d.timetuple().tm_yday
    return {
        "DN1": m + day + century + yy,
        "DN2": m + day + sum(_digits(y)),
        "DN3": sum(_digits(m)) + sum(_digits(day)) + sum(_digits(y)),
        "DN4": m + day + yy,
        "DN5": sum(_digits(m)) + sum(_digits(day)) + sum(_digits(yy)),
        "DOY": doy,
        "DAYS_LEFT": (366 if calendar.isleap(y) else 365) - doy,
    }


WEEKDAY_PLANETS = {
    "Sunday": "Sun", "Monday": "Moon", "Tuesday": "Mars", "Wednesday": "Mercury",
    "Thursday": "Jupiter", "Friday": "Venus", "Saturday": "Saturn",
}


def weekday(d: date) -> str:
    return calendar.day_name[d.weekday()]


def ruling_planet(d: date) -> str:
    return WEEKDAY_PLANETS[weekday(d)]

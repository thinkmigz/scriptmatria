"""Birthday spans and calendar codes.

Each span is a distinct, labeled anchor; they are never substituted for one
another. Convention for Feb 29 birthdays: in non-leap years the anniversary is
observed on Feb 28.
"""

import calendar
from datetime import date


def _anniversary(birth: date, year: int) -> date:
    day = birth.day
    if birth.month == 2 and day == 29 and not calendar.isleap(year):
        day = 28
    return date(year, birth.month, day)


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def ymd(start: date, end: date) -> tuple[int, int, int]:
    """Exact calendar years, months and remaining days from start to end."""
    if end < start:
        raise ValueError("end date precedes start date")
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if _add_months(start, months) > end:
        months -= 1
    days = (end - _add_months(start, months)).days
    return months // 12, months % 12, days


def birthday_spans(birth: date, event: date) -> dict[str, int]:
    years, months, days = ymd(birth, event)
    last = _anniversary(birth, event.year)
    if last > event:
        last = _anniversary(birth, event.year - 1)
    nxt = _anniversary(birth, last.year + 1)
    if _anniversary(birth, event.year) == event:
        nxt = event
    total = (event - birth).days
    return {
        "total_days": total,
        "age_years": years,
        "ymd_months": months,
        "ymd_days": days,
        "days_since_birthday": (event - last).days,
        "days_until_birthday": (nxt - event).days,
        "total_weeks": total // 7,
    }


def _digits(n: int) -> list[int]:
    return [int(c) for c in str(n)]


def date_numerology(d: date) -> dict[str, int]:
    """DN1-DN5 (Gematrinator-style), day of year, days left in the year."""
    m, day, y = d.month, d.day, d.year
    century, yy = divmod(y, 100)
    doy = d.timetuple().tm_yday
    return {
        "DN1": m + day + century + yy,
        "DN2": m + day + sum(_digits(y)),
        "DN3": sum(_digits(m)) + sum(_digits(day)) + sum(_digits(y)),
        "DN4": m + day + yy,
        "DN5": sum(_digits(m)) + sum(_digits(day)) + yy,
        "DOY": doy,
        "DAYS_LEFT": (366 if calendar.isleap(y) else 365) - doy,
    }


def weekday(d: date) -> str:
    return calendar.day_name[d.weekday()]

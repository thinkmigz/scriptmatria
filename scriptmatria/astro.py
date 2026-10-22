"""Moon phase and tropical zodiac.

Moon phases use the true-phase algorithm from Jean Meeus, *Astronomical
Algorithms* (2nd ed., ch. 49), accurate to about a minute, with a fixed
ΔT = 69 s (TT → UTC). A date's phase is judged over its whole calendar day in
the event's timezone (UTC unless one is supplied); moon age is measured at the
event time if given, else local noon. If a principal phase instant
falls inside that day the date takes that name, otherwise it takes the
intermediate name following the most recent principal phase.

Zodiac signs use the conventional fixed tropical sun-sign date table below. The
Sun's real ingress moves by about a day from year to year; the fixed table is the
locked convention, so the same date always yields the same sign.
"""

import math
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

SYNODIC_MONTH = 29.530588861
DELTA_T_SECONDS = 69
_J2000_UNIX_EPOCH_JD = 2440587.5  # JD of 1970-01-01 00:00 UTC

PRINCIPAL = {0.0: "New Moon", 0.25: "First Quarter", 0.5: "Full Moon", 0.75: "Last Quarter"}
AFTER = {"New Moon": "Waxing Crescent", "First Quarter": "Waxing Gibbous",
         "Full Moon": "Waning Gibbous", "Last Quarter": "Waning Crescent"}

# (sign, start month, start day); each sign runs until the next one starts.
ZODIAC = [
    ("Capricorn", 1, 1), ("Aquarius", 1, 20), ("Pisces", 2, 19), ("Aries", 3, 21),
    ("Taurus", 4, 20), ("Gemini", 5, 21), ("Cancer", 6, 21), ("Leo", 7, 23),
    ("Virgo", 8, 23), ("Libra", 9, 23), ("Scorpio", 10, 23), ("Sagittarius", 11, 22),
    ("Capricorn", 12, 22),
]

# Periodic terms, Meeus ch. 49: (coefficient, E power, multiples of M, M', F, Ω).
_NEW = [(-0.40720, 0, 0, 1, 0, 0), (0.17241, 1, 1, 0, 0, 0), (0.01608, 0, 0, 2, 0, 0),
        (0.01039, 0, 0, 0, 2, 0), (0.00739, 1, -1, 1, 0, 0), (-0.00514, 1, 1, 1, 0, 0),
        (0.00208, 2, 2, 0, 0, 0)]
_FULL = [(-0.40614, 0, 0, 1, 0, 0), (0.17302, 1, 1, 0, 0, 0), (0.01614, 0, 0, 2, 0, 0),
         (0.01043, 0, 0, 0, 2, 0), (0.00734, 1, -1, 1, 0, 0), (-0.00515, 1, 1, 1, 0, 0),
         (0.00209, 2, 2, 0, 0, 0)]
_NEW_FULL_SHARED = [
    (-0.00111, 0, 0, 1, -2, 0), (-0.00057, 0, 0, 1, 2, 0), (0.00056, 1, 1, 2, 0, 0),
    (-0.00042, 0, 0, 3, 0, 0), (0.00042, 1, 1, 0, 2, 0), (0.00038, 1, 1, 0, -2, 0),
    (-0.00024, 1, -1, 2, 0, 0), (-0.00017, 0, 0, 0, 0, 1), (-0.00007, 0, 2, 1, 0, 0),
    (0.00004, 0, 0, 2, -2, 0), (0.00004, 0, 3, 0, 0, 0), (0.00003, 0, 1, 1, -2, 0),
    (0.00003, 0, 0, 2, 2, 0), (-0.00003, 0, 1, 1, 2, 0), (0.00003, 0, -1, 1, 2, 0),
    (-0.00002, 0, -1, 1, -2, 0), (-0.00002, 0, 1, 3, 0, 0), (0.00002, 0, 0, 4, 0, 0),
]
_QUARTER = [
    (-0.62801, 0, 0, 1, 0, 0), (0.17172, 1, 1, 0, 0, 0), (-0.01183, 1, 1, 1, 0, 0),
    (0.00862, 0, 0, 2, 0, 0), (0.00804, 0, 0, 0, 2, 0), (0.00454, 1, -1, 1, 0, 0),
    (0.00204, 2, 2, 0, 0, 0), (-0.00180, 0, 0, 1, -2, 0), (-0.00070, 0, 0, 1, 2, 0),
    (-0.00040, 0, 0, 3, 0, 0), (-0.00034, 1, -1, 2, 0, 0), (0.00032, 1, 1, 0, 2, 0),
    (0.00032, 1, 1, 0, -2, 0), (-0.00028, 2, 2, 1, 0, 0), (0.00027, 1, 1, 2, 0, 0),
    (-0.00017, 0, 0, 0, 0, 1), (-0.00005, 0, -1, 1, -2, 0), (0.00004, 0, 0, 2, 2, 0),
    (-0.00004, 0, 1, 1, 2, 0), (0.00004, 0, -2, 1, 0, 0), (0.00003, 0, 1, 1, -2, 0),
    (0.00003, 0, 3, 0, 0, 0), (0.00002, 0, 0, 2, -2, 0), (0.00002, 0, -1, 1, 2, 0),
    (-0.00002, 0, 1, 3, 0, 0),
]
_PLANETARY = [  # (coefficient, A0, A·k)
    (0.000325, 299.77, 0.107408), (0.000165, 251.88, 0.016321), (0.000164, 251.83, 26.651886),
    (0.000126, 349.42, 36.412478), (0.000110, 84.66, 18.206239), (0.000062, 141.74, 53.303771),
    (0.000060, 207.14, 2.453732), (0.000056, 154.84, 7.306860), (0.000047, 34.52, 27.261239),
    (0.000042, 207.19, 0.121824), (0.000040, 291.34, 1.844379), (0.000037, 161.72, 24.198154),
    (0.000035, 239.56, 25.513099), (0.000023, 331.55, 3.592518),
]


def phase_jde(k: float) -> float:
    """Julian Ephemeris Day of the true phase k (integer = new, +.25/.5/.75 = FQ/full/LQ)."""
    t = k / 1236.85
    jde = (2451550.09766 + SYNODIC_MONTH * k + 0.00015437 * t**2
           - 0.000000150 * t**3 + 0.00000000073 * t**4)
    e = 1 - 0.002516 * t - 0.0000074 * t**2
    rad = math.radians
    m = rad(2.5534 + 29.10535670 * k - 0.0000014 * t**2 - 0.00000011 * t**3)
    mp = rad(201.5643 + 385.81693528 * k + 0.0107582 * t**2 + 0.00001238 * t**3
             - 0.000000058 * t**4)
    f = rad(160.7108 + 390.67050284 * k - 0.0016118 * t**2 - 0.00000227 * t**3
            + 0.000000011 * t**4)
    om = rad(124.7746 - 1.56375588 * k + 0.0020672 * t**2 + 0.00000215 * t**3)

    frac = round(k % 1, 2)
    terms = {0.0: _NEW + _NEW_FULL_SHARED, 0.5: _FULL + _NEW_FULL_SHARED}.get(frac, _QUARTER)
    jde += sum(c * e**ep * math.sin(a * m + b * mp + cf * f + d * om)
               for c, ep, a, b, cf, d in terms)
    if frac in (0.25, 0.75):
        w = (0.00306 - 0.00038 * e * math.cos(m) + 0.00026 * math.cos(mp)
             - 0.00002 * math.cos(mp - m) + 0.00002 * math.cos(mp + m) + 0.00002 * math.cos(2 * f))
        jde += w if frac == 0.25 else -w
    jde += sum(c * math.sin(rad(a0 + ak * k - (0.009173 * t**2 if i == 0 else 0)))
               for i, (c, a0, ak) in enumerate(_PLANETARY))
    return jde


def phase_utc(k: float) -> datetime:
    jd_ut = phase_jde(k) - DELTA_T_SECONDS / 86400
    dt = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=jd_ut - _J2000_UNIX_EPOCH_JD)
    return dt.replace(microsecond=0) + timedelta(seconds=round(dt.microsecond / 1e6))


def _phases_around(d: date) -> list[tuple[datetime, str]]:
    k0 = math.floor((d.year + (d.timetuple().tm_yday - 1) / 365.25 - 2000) * 12.3685)
    out = []
    for i in range(-8, 9):
        k = k0 + i * 0.25
        out.append((phase_utc(k), PRINCIPAL[round(k % 1, 2)]))
    return sorted(out)


def moon_phase(d: date, tz: str | None = None, at: time | None = None) -> dict:
    """Phase for calendar day d. Moon age is measured at `at` (local), or at noon."""
    zone = ZoneInfo(tz) if tz else timezone.utc
    start = datetime.combine(d, time.min, zone).astimezone(timezone.utc)
    end = datetime.combine(d + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    when = datetime.combine(d, at or time(12), zone).astimezone(timezone.utc)
    phases = _phases_around(d)

    on_day = [(t, n) for t, n in phases if start <= t < end]
    prev_new = max(t for t, n in phases if n == "New Moon" and t <= when)
    next_full = min(t for t, n in phases if n == "Full Moon" and t >= start)
    next_new = min(t for t, n in phases if n == "New Moon" and t >= start)
    if on_day:
        name, exact = on_day[0][1], on_day[0][0]
    else:
        name, exact = AFTER[max((t, n) for t, n in phases if t < start)[1]], None

    local = lambda t: t.astimezone(zone).date()  # noqa: E731
    return {
        "phase": name,
        "principal_phase_utc": ((exact + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M UTC")
                                if exact else None),
        "moon_age_days": round((when - prev_new).total_seconds() / 86400, 1),
        "measured_at": f"{(at or time(12)).strftime('%H:%M')} local",
        "days_to_full_moon": (local(next_full) - d).days,
        "days_to_new_moon": (local(next_new) - d).days,
        "timezone": tz or "UTC",
    }


def zodiac_sign(d: date) -> str:
    sign = ZODIAC[0][0]
    for name, month, day in ZODIAC:
        if (d.month, d.day) >= (month, day):
            sign = name
    return sign

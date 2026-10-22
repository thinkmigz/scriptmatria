# scriptmatria

A lite, deterministic **TAG-ONLY** ritual decoder for player milestones. It is a clean rebuild of Zilla's mathematical core, following the October 2026 audit:

- one canonical math library
- every rule has an ID and a version
- PIGR-A and PIGR-B are judged separately
- dependent hits aren't counted as independent confirmation
- every comparison, hit or miss, is logged

It reads local files only. There are no network calls, no scoring, no picks and no automation.

> Alignments are mathematical observations, not predictions. No rule here has demonstrated predictive value; that belongs to a separate research process.

## Install

```bash
python3 -m pip install -e ".[test]"   # Python 3.11+, no runtime dependencies
```

## Use

```bash
scriptmatria decode examples/sample_decode.json --out decodes --print
scriptmatria decode examples/sample_decodes.csv
scriptmatria gematria "Sample Town Rockets"
```

Each decode writes these files:

- `decodes/<id>.md`: the decode grid, a finding sentence, dependent hits and the comparison ledger
- `decodes/<id>.json`: the full audit record, with inputs, input SHA-256, registry version, every comparison and the classification
- `decodes/grid.csv`: one row per test per decode, ready for Excel

Identical inputs always produce byte-identical output.

### Example output (from the audit's illustration)

| Test | Finding | Result |
| --- | --- | --- |
| Prime milestone | 23 is the 9th prime | ✓ Exact |
| Reverse prime | 23 → 32, not prime | No hit |
| PIGR-B | 83 is the 23rd prime | ✓ Exact |
| PIGR-A | no value equals 9 (index of 23); 2 values checked | No hit |
| Jersey | jersey = 23 = milestone 23 | ✓ Exact |
| Birthday interval | Birthday not supplied | Unverified |
| Triple Prime Sync | 2 prime hit(s) from 2 families … needs 3 families and 3 numbers | Not qualified |

With an event date, birthday and timezone (the `full-example` decode), the grid also shows:

| Test | Finding | Result |
| --- | --- | --- |
| Weekday | Thursday | Tag |
| Moon phase | Waxing Gibbous · age 12.0 d · full in 4 d, new in 18 d (America/New_York) | Tag |
| Birth moon | Waning Gibbous · age 15.8 d · full in 28 d, new in 14 d (UTC) | Tag |
| Zodiac | event in Libra season; player is Pisces | No hit |

## Input

JSON is either `{"decodes": [...]}` or a list. Required fields are `id`, `player` and `milestone`. Anything missing is reported as **Unverified** and never inferred.

```json
{
  "id": "full-example",
  "player": "Example Athlete",
  "stat_category": "points",
  "current": 40,
  "milestone": 41,
  "birthday": "1998-03-14",
  "jersey": 7,
  "event_date": "2026-10-22",
  "timezone": "America/New_York",
  "team": "Example City Comets",
  "opponent": "Sample Town Rockets",
  "phrases": [{"entity": "opponent", "phrase": "Rockets"}, {"entity": "team", "phrase": "Comets"}],
  "values":  [{"entity": "opponent", "label": "authorized value", "value": 83}]
}
```

- `phrases` are run through all five ciphers. `values` are numbers you supply directly, and each needs a label saying where it came from.
- `entity` is one of `opponent`, `team`, `player` or `event`. Only opponent sources count as Type A. Team, player and event sources are reported as self-referential.
- `timezone` is optional (IANA name). It sets which calendar day the moon phase is judged on; without it, UTC is used.
- CSV uses the same column names. Use `phrases` = `entity:phrase|entity:phrase` and `values` = `entity:label=value|...`.

## What it computes

| Engine | Values |
| --- | --- |
| Gematria | English Ordinal (EO), Full Reduction (FR), Reverse Ordinal (RO), Reverse Reduction (RR), Chaldean (CH) |
| Primes | prime status, 1-based prime index, nth prime, reverse prime |
| Birthday | total days, exact years/months/days (never negative), days since and until birthday, total weeks |
| Calendar | DN1–DN5, day of year, days left, weekday |
| Moon | phase name, exact principal-phase time, moon age, days to next full and new moon (event date, and birth date in UTC) |
| Zodiac | tropical sun sign for the event date and the birthday |
| Symbolic | Skull & Bones {149, 41, 76, 322}, Jesuit {144, 153, 72} |

The rules and conventions live in [`scriptmatria/registry/rules_v1.json`](scriptmatria/registry/rules_v1.json):

| Rule | Qualifies when |
| --- | --- |
| PRIME-M | milestone M is prime |
| REVPRIME-M | reverse(M) is prime (palindromes excluded) |
| PIGR-A | M is prime and prime_index(M) == G |
| PIGR-B | G is prime and prime_index(G) == M |
| TYPEA | opponent gematria/value == M |
| GEM-SELF | team/player/event gematria/value == M |
| JERSEY / BDAY / DN | jersey / a birthday span / a calendar code == M |
| SYM | a value is in a locked symbolic set (reported separately and never counted as prime evidence) |
| ZODIAC-SYNC | the event falls in the player's own sun-sign season (symbolic, never structural) |

### Moon phase and zodiac conventions

- **Moon phase** uses the true-phase algorithm from Jean Meeus, *Astronomical Algorithms* (2nd ed., ch. 49), which is accurate to about a minute. The tests check it against the book's worked example and against published 2024 phase times.
  - A date is named New Moon, First Quarter, Full Moon or Last Quarter when that exact moment falls within the calendar day in the event timezone.
  - Otherwise the date is Waxing Crescent, Waxing Gibbous, Waning Gibbous or Waning Crescent, depending on which principal phase came last.
  - Moon age is measured at local noon.
  - Moon phase is a descriptive tag and is never matched against the milestone.
- **Zodiac** uses a fixed tropical date table: Aries 3/21, Taurus 4/20, Gemini 5/21, Cancer 6/21, Leo 7/23, Virgo 8/23, Libra 9/23, Scorpio 10/23, Sagittarius 11/22, Capricorn 12/22, Aquarius 1/20, Pisces 2/19. The Sun's real ingress shifts by about a day from year to year, so the table is the locked convention.

**Prime Cluster** means 3 or more prime-related hits. **Triple Prime Sync** needs 3 or more prime-related hits drawn from at least 3 distinct source families and at least 3 distinct numbers.

When several hits restate the same number, the report lists them under **Dependent hits**.

## Not in v1 (possible later modules)

- mirror, concat and SACB/EACB bridges
- extended ciphers
- point scoring
- research and calibration lab: prospective grading and baselines
- counterfactual (shuffle) controls
- signal rarity analysis
- rule-version simulator
- Telegram and scheduled runs

## Tests

```bash
python3 -m pytest
```

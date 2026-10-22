"""Reference case from the Zilla 3.0 workflow: Fictional Player A, career HR #23,
born 2000-06-01, jersey #23, game 2026-10-21, opponent gematria 83 (not yet tied
to a phrase). Every expected value below is hand-checked."""

import json
from datetime import date
from pathlib import Path

import pytest

from scriptmatria import dates, gematria, inputs, report, rules

EXAMPLE = Path(__file__).parent.parent / "examples" / "mlb_career_hr.json"
GAME, BORN = date(2026, 10, 21), date(2000, 6, 1)


@pytest.fixture(scope="module")
def result():
    (req,) = inputs.load(EXAMPLE)
    return report.decode(req, rules.load_registry())


def test_birthday_card():
    s = dates.birthday_spans(BORN, GAME)
    assert (s["age_years"], s["ymd_months"], s["ymd_days"]) == (26, 4, 20)
    assert s["total_days"] == 9638
    assert s["days_since_birthday"] == 142 and s["days_until_birthday"] == 223


def test_date_card():
    assert dates.date_numerology(GAME) == {
        "DN1": 77, "DN2": 41, "DN3": 14, "DN4": 57, "DN5": 12, "DOY": 294, "DAYS_LEFT": 71}
    assert (dates.weekday(GAME), dates.ruling_planet(GAME)) == ("Wednesday", "Mercury")


def test_mercury_gematria():
    # M E R C U R Y: FR 4+5+9+3+3+9+7 = 40; RR 5+4+9+6+6+9+2 = 41; CH 4+5+2+3+6+2+1 = 23
    assert gematria.all_values("Mercury") == {"EO": 103, "FR": 40, "RO": 86, "RR": 41, "CH": 23}


def test_grid(result):
    grid = {g["test"]: g["result"] for g in result["grid"]}
    assert grid["Prime milestone"] == "✓ Exact"
    assert grid["Reverse prime"] == "No hit"
    assert grid["PIGR-A"] == "No hit"
    assert grid["PIGR-B"] == "Source pending"
    assert grid["Opponent Type A"] == "No hit"
    assert grid["Jersey"] == "✓ Exact"
    assert grid["Date numerology"] == "No hit"
    assert grid["Weekday & planet gematria"] == "✓ Exact"  # Mercury CH = 23
    assert grid["Symbolic codes"] == "✓ Exact"  # DN2 = 41 and Mercury RR = 41 (Skull and Bones)
    assert grid["Triple Prime Sync"] == "Not qualified"


def test_summary_row(result):
    row = result["summary"]
    assert row["Birthday span (days)"] == 9638
    assert row["Prime index"] == 9
    assert row["PIGR-B"] == "Conditional (source pending)"
    assert row["Jersey sync"] == "Yes"
    assert row["Date match"] == "No direct milestone-to-DN match"
    assert row["Weekday / planet"] == "Wednesday / Mercury (gematria match)"
    assert "DN2=41 Skull and Bones" in row["Skull/Jesuit"]
    assert row["Triple Prime"] == "No"
    assert row["Decode status"] == "Partial, source verification required"
    assert row["Milestone type"] == "cumulative"


def test_dependent_23_restatements(result):
    group = next(d for d in result["classification"]["dependency_groups"] if d["number"] == 23)
    assert group["dependent"] and len(group["hits"]) == 3  # prime milestone, jersey, Mercury CH


def test_example_file_is_the_reference():
    raw = json.loads(EXAMPLE.read_text())["decodes"][0]
    assert raw["milestone"] == 23 and raw["birthday"] == "2000-06-01" and raw["event_date"] == "2026-10-21"

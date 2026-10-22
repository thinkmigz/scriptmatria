"""Control test, Excel output, freeze/amend and grading."""

import json
import zipfile

import pytest

from scriptmatria import cli, control, dates, gematria, grading, inputs, report, rules
from datetime import date

REGISTRY = rules.load_registry()
BASE = {"id": "w", "player": "P", "milestone": 23, "jersey": 23, "event_date": "2026-10-21"}


def test_monday_and_moon_gematria():
    # M O N D A Y / M O O N, hand-computed from the cipher tables
    assert gematria.all_values("Monday") == {"EO": 72, "FR": 27, "RO": 90, "RR": 27, "CH": 22}
    assert gematria.all_values("Moon") == {"EO": 57, "FR": 21, "RO": 51, "RR": 15, "CH": 23}


@pytest.mark.parametrize("d,day,planet", [
    (date(2026, 10, 18), "Sunday", "Sun"), (date(2026, 10, 19), "Monday", "Moon"),
    (date(2026, 10, 20), "Tuesday", "Mars"), (date(2026, 10, 21), "Wednesday", "Mercury"),
    (date(2026, 10, 22), "Thursday", "Jupiter"), (date(2026, 10, 23), "Friday", "Venus"),
    (date(2026, 10, 24), "Saturday", "Saturn"),
])
def test_ruling_planets(d, day, planet):
    assert (dates.weekday(d), dates.ruling_planet(d)) == (day, planet)


def test_monday_moon_hits():
    monday = {"id": "x", "player": "P", "event_date": "2026-10-19"}
    moon = report.decode(inputs.parse_request({**monday, "milestone": 57}), REGISTRY)
    assert any(r["rule_id"] == "PLANET-GEM" and r["hit"] and r["cipher"] == "EO" for r in moon["records"])
    day = report.decode(inputs.parse_request({**monday, "milestone": 72}), REGISTRY)
    assert any(r["rule_id"] == "DAY-GEM" and r["hit"] and r["cipher"] == "EO" for r in day["records"])


def test_control_test_universe():
    ctl = control.control_test(inputs.parse_request(BASE), REGISTRY)
    assert ctl["alternatives"] == 20 and "23" not in ctl["per_milestone"]
    assert ctl["universe"] == "milestones 13–33 excluding 23"
    small = control.control_test(inputs.parse_request({**BASE, "milestone": 3}), REGISTRY)
    assert small["alternatives"] == 12  # 1..13 excluding 3; never below 1


def test_freeze_then_amend_never_overwrites(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps([BASE]))
    out = tmp_path / "out"
    assert cli.main(["decode", str(src), "--out", str(out)]) == 0
    first = (out / "w.json").read_bytes()
    assert cli.main(["decode", str(src), "--out", str(out)]) == 0  # unchanged: nothing new
    assert not (out / "w.v2.json").exists()
    src.write_text(json.dumps([{**BASE, "jersey": 7}]))
    assert cli.main(["decode", str(src), "--out", str(out)]) == 0
    assert (out / "w.json").read_bytes() == first
    v2 = json.loads((out / "w.v2.json").read_text())
    assert v2["frozen"] == {"version": 2, "amends": "w.json"}
    ledger = [json.loads(line) for line in (out / "freeze_ledger.jsonl").read_text().splitlines()]
    assert [e["version"] for e in ledger] == [1, 2]


def test_grading_is_append_only(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps([BASE]))
    cli.main(["decode", str(src), "--out", str(tmp_path)])
    before = (tmp_path / "w.json").read_bytes()
    grading.grade(tmp_path, "w", True, 23)
    with pytest.raises(grading.GradeError):
        grading.grade(tmp_path, "w", False)
    grading.grade(tmp_path, "w", False, note="stat correction", correction=True)
    with pytest.raises(grading.GradeError):
        grading.grade(tmp_path, "missing", True)
    assert (tmp_path / "w.json").read_bytes() == before
    lines = (tmp_path / "outcomes.jsonl").read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["correction"] is True


def test_xlsx_is_a_valid_workbook(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps([BASE]))
    cli.main(["decode", str(src), "--out", str(tmp_path)])
    with zipfile.ZipFile(tmp_path / "decodes.xlsx") as z:
        assert z.testzip() is None
        names = z.namelist()
        workbook = z.read("xl/workbook.xml").decode()
        summary = z.read("xl/worksheets/sheet1.xml").decode()
    assert {"xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml", "xl/worksheets/sheet3.xml"} <= set(names)
    assert 'name="Summary"' in workbook and 'name="Evidence"' in workbook
    assert "Decode status" in summary and "Wednesday / Mercury" in summary

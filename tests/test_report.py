"""Report reconciliation, sealing, revisions, grading, research separation and the
MLB pilot reference values."""

import csv
import io
import json
import zipfile

import pytest

from conftest import MEMPHIS, ROOT, decode, snapshot
from scriptmatria import cli, dates, gematria, grading, report
from scriptmatria.rules import NO_HIT

PILOT = ROOT / "examples" / "mlb_pilot.json"


def test_pilot_reference_values(pilot):
    assert pilot["date_card"] == {"DN1": 77, "DN2": 41, "DN3": 14, "DN4": 57, "DN5": 12, "DOY": 294,
                                  "DAYS_LEFT": 71, "weekday": "Wednesday", "ruling_planet": "Mercury"}
    bc = pilot["birthday_card"]
    assert (bc["total_days"], bc["age_years"], bc["ymd_months"], bc["ymd_days"]) == (9638, 26, 4, 20)
    assert (bc["days_since_birthday"], bc["days_until_birthday"], bc["birth_mmdd"]) == (142, 223, "06/01")
    assert pilot["milestone_card"]["M-INDEX"] == 9
    assert gematria.all_values("Mercury") == {"EO": 103, "FR": 40, "RO": 86, "RR": 41, "CH": 23}
    assert gematria.all_values("Wednesday") == {"EO": 100, "FR": 37, "RO": 143, "RR": 44, "CH": 34}
    assert pilot["seal"]["event_start_utc"] == "2026-10-21T23:05:00+00:00"
    assert pilot["overlays"]["moon"]["phase"] == "Waxing Gibbous"
    assert pilot["classification"]["triple_prime_sync"] == "NOT_EVALUATED"


def test_csv_json_markdown_reconcile_to_ledger(pilot):
    hits = [r for r in pilot["records"] if r["status"] != NO_HIT]
    grid_hits = [g for g in pilot["grid"] if g["Status"] != NO_HIT]
    assert len(grid_hits) == len(hits)
    assert sorted(g["Derivation"] for g in grid_hits) == sorted(r["computation"] for r in hits)
    rows = list(csv.DictReader(io.StringIO(report.grid_csv(pilot))))
    assert [(r["Rule"], r["Derivation"], r["Status"]) for r in rows] == \
           [(g["Rule"], g["Derivation"], g["Status"]) for g in pilot["grid"]]
    md = report.to_markdown(pilot)
    for g in grid_hits:
        assert g["Derivation"] in md
    ledger = [json.loads(line) for line in report.ledger_jsonl(pilot).splitlines()]
    assert ledger == pilot["records"]
    c = pilot["classification"]["counts"]
    assert c["attempted"] == sum(1 for r in ledger if r["status"] != "UNVERIFIED")


def test_seal_and_replay_are_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert cli.main(["decode", str(PILOT), "--out", str(a)]) == 0
    assert cli.main(["decode", str(PILOT), "--out", str(b)]) == 0
    for f in sorted(a.iterdir()):
        if f.name != "freeze_ledger.jsonl":
            assert f.read_bytes() == (b / f.name).read_bytes(), f.name
    seal = json.loads((a / "freeze_ledger.jsonl").read_text().splitlines()[0])
    for key in ("input_sha256", "rule_registry_sha256", "phrase_registry_sha256", "decode_sha256",
                "created_at_utc", "event_start_utc", "sealed_before_event_start"):
        assert key in seal
    names = {f.name for f in a.iterdir()}
    stem = "MLB-2026-10-21-FIXTURE-PA_FICTIONAL-A"
    assert {f"{stem}.json", f"{stem}.md", f"{stem}.csv", f"{stem}.ledger.jsonl"} <= names


def test_corrected_snapshot_creates_linked_revision(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps([snapshot()]))
    out = tmp_path / "out"
    cli.main(["decode", str(src), "--out", str(out)])
    stem = "MLB-2026-10-21-FIXTURE-PA_FICTIONAL-A"
    original = (out / f"{stem}.json").read_bytes()
    cli.main(["decode", str(src), "--out", str(out)])
    assert not (out / f"{stem}.v2.json").exists()
    src.write_text(json.dumps([snapshot(jersey=24, current_count_source="operator correction")]))
    cli.main(["decode", str(src), "--out", str(out)])
    assert (out / f"{stem}.json").read_bytes() == original
    v2 = json.loads((out / f"{stem}.v2.json").read_text())
    assert v2["frozen"] == {"version": 2, "amends": f"{stem}.json"}
    assert [json.loads(x)["version"] for x in (out / "freeze_ledger.jsonl").read_text().splitlines()] == [1, 2]


def test_grading_append_only_with_unresolved(tmp_path):
    cli.main(["decode", str(PILOT), "--out", str(tmp_path)])
    did = "MLB-2026-10-21-FIXTURE-PA_FICTIONAL-A"
    before = (tmp_path / f"{did}.json").read_bytes()
    grading.grade(tmp_path, did, "unresolved", note="doubleheader stat correction pending")
    with pytest.raises(grading.GradeError):
        grading.grade(tmp_path, did, "achieved")
    grading.grade(tmp_path, did, "achieved", actual=23, correction=True)
    with pytest.raises(grading.GradeError):
        grading.grade(tmp_path, did, "maybe")
    assert (tmp_path / f"{did}.json").read_bytes() == before
    outcomes = [json.loads(x)["outcome"] for x in (tmp_path / "outcomes.jsonl").read_text().splitlines()]
    assert outcomes == ["UNRESOLVED", "ACHIEVED"]


def test_control_is_research_only(tmp_path, pilot):
    assert "control" not in pilot
    assert cli.main(["research", "control", str(PILOT), "--out", str(tmp_path)]) == 0
    data = json.loads(next(tmp_path.glob("*.control.json")).read_text())
    assert data["kind"] == "research/control" and data["alternatives"] == 20
    assert data["universe"] == "milestones 13–33 excluding 23"


def test_fixture_registry_via_cli(tmp_path):
    src = tmp_path / "fx.json"
    src.write_text(json.dumps([snapshot(MEMPHIS)]))
    assert cli.main(["decode", str(src), "--out", str(tmp_path / "o"),
                     "--phrases", str(ROOT / "tests" / "fixtures" / "phrases_fixture.json")]) == 0
    res = json.loads(next((tmp_path / "o").glob("FX-*.json")).read_text())
    assert any(r["rule_id"] == "PIGR-B" and r["status"] == "QUALIFIED_STRUCTURAL" for r in res["records"])


def test_xlsx_workbook(tmp_path):
    cli.main(["decode", str(PILOT), "--out", str(tmp_path)])
    with zipfile.ZipFile(tmp_path / "decodes.xlsx") as z:
        assert z.testzip() is None
        wb = z.read("xl/workbook.xml").decode()
        summary = z.read("xl/worksheets/sheet1.xml").decode()
    assert all(f'name="{n}"' in wb for n in ("Summary", "Relationships", "Evidence"))
    assert "NOT_EVALUATED" in summary and "Wednesday / Mercury" in summary


def test_deliverable_modules_exist():
    from scriptmatria import decode_report, relationship_engine, signal_validator, zilla_math
    assert zilla_math.nth_prime(23) == 83 and zilla_math.prime_index(23) == 9
    assert relationship_engine.evaluate and signal_validator.classify and decode_report.decode

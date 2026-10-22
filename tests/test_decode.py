import json
from pathlib import Path

import pytest

from scriptmatria import cli, inputs, report, rules

EXAMPLES = Path(__file__).parent.parent / "examples"
REGISTRY = rules.load_registry()


def _decode(raw):
    return report.decode(inputs.parse_request(raw), REGISTRY)


def _grid(result):
    return {g["test"]: g["result"] for g in result["grid"]}


AUDIT = {"id": "a", "player": "P", "current": 22, "milestone": 23, "jersey": 23,
         "values": [{"entity": "opponent", "label": "authorized", "value": 83}]}


def test_audit_example_grid():
    res = _decode(AUDIT)
    assert _grid(res) == {
        "Prime milestone": "✓ Exact",
        "Reverse prime": "No hit",
        "PIGR-B": "Source pending",
        "PIGR-A": "No hit",
        "Opponent Type A": "No hit",
        "Jersey": "✓ Exact",
        "Birthday interval": "Unverified",
        "Date numerology": "Unverified",
        "Weekday": "Unverified",
        "Weekday & planet gematria": "Unverified",
        "Moon phase": "Unverified",
        "Zodiac": "Unverified",
        "Symbolic codes": "No hit",
        "Prime Cluster": "Not qualified",
        "Triple Prime Sync": "Not qualified",
        "Control test": "Descriptive",
    }
    assert "prime milestone, PIGR-B (source pending), jersey" in res["finding"]
    assert res["decode_status"] == "Partial, source verification required"


def test_pigr_a_and_b_are_never_both_labeled_for_one_value():
    for m in range(2, 31):
        for g in range(1, 130):
            raw = {"id": "x", "player": "P", "milestone": m,
                   "values": [{"entity": "opponent", "label": "g", "value": g}]}
            recs, _ = rules.evaluate(inputs.parse_request(raw), REGISTRY)
            hit = {r["rule_id"] for r in recs if r["hit"] and r["rule_id"].startswith("PIGR")}
            assert hit != {"PIGR-A", "PIGR-B"}, (m, g)


def test_pigr_a_hit():
    verified = _decode({"id": "x", "player": "P", "milestone": 23, "jersey": 9})
    assert _grid(verified)["PIGR-A"] == "✓ Exact" and _grid(verified)["PIGR-B"] == "No hit"
    pending = _decode({"id": "x", "player": "P", "milestone": 23,
                       "values": [{"entity": "opponent", "label": "g", "value": 9}]})
    assert _grid(pending)["PIGR-A"] == "Source pending"


def test_triple_prime_sync_requires_three_families():
    # 23 is prime (milestone); jersey 9 = index of 23 (PIGR-A); 12/25/2026 DN1 = 12+25+20+26 = 83,
    # the 23rd prime (PIGR-B): three verified families on three distinct numbers.
    raw = {"id": "x", "player": "P", "milestone": 23, "jersey": 9, "event_date": "2026-12-25"}
    res = _decode(raw)
    cls = res["classification"]
    assert cls["prime_families"] == ["calendar", "jersey", "milestone"]
    assert cls["triple_prime_sync"] and _grid(res)["Triple Prime Sync"] == "✓ Qualified"


def test_same_family_does_not_make_triple_sync():
    # Opponent phrase "i" is 9 in EO, FR and RR: three PIGR-A hits, but one family and one number.
    raw = {"id": "x", "player": "P", "milestone": 23, "phrases": [{"entity": "opponent", "phrase": "i"}]}
    res = _decode(raw)
    assert res["classification"]["prime_hits"] == 4 and res["classification"]["prime_cluster"]
    assert not res["classification"]["triple_prime_sync"]


def test_pending_sources_never_qualify_triple_sync():
    raw = {"id": "x", "player": "P", "milestone": 23,
           "values": [{"entity": "opponent", "label": "o", "value": 83},
                      {"entity": "team", "label": "t", "value": 9}]}
    res = _decode(raw)
    assert not res["classification"]["triple_prime_sync"]
    assert len(res["classification"]["pending_hits"]) == 2
    assert res["summary"]["PIGR-A"] == res["summary"]["PIGR-B"] == "Conditional (source pending)"


def test_symbolic_never_counts_as_prime():
    res = _decode({"id": "x", "player": "P", "milestone": 41, "jersey": 41})
    cls = res["classification"]
    assert cls["prime_hits"] == 1 and cls["symbolic_count"] == 2


def test_dependent_hits_flagged():
    res = _decode(AUDIT)
    dep = [d for d in res["classification"]["dependency_groups"] if d["dependent"]]
    assert dep and dep[0]["number"] == 23


def test_missing_required_fields_rejected():
    with pytest.raises(inputs.InputError) as e:
        inputs.parse_request({"player": "", "milestone": "x"})
    assert "id: required" in str(e.value) and "player: required" in str(e.value)


def test_bad_entity_and_date_rejected():
    with pytest.raises(inputs.InputError):
        inputs.parse_request({"id": "x", "player": "P", "milestone": 3, "event_date": "10/22/2026"})
    with pytest.raises(inputs.InputError):
        inputs.parse_request({"id": "x", "player": "P", "milestone": 3,
                              "phrases": [{"entity": "coach", "phrase": "x"}]})


def test_ledger_counts_every_comparison():
    res = _decode(AUDIT)
    assert sum(v["comparisons"] for v in res["ledger"].values()) == res["total_comparisons"] == len(res["records"])


def test_json_and_csv_inputs_agree():
    js = {r.id: r for r in inputs.load(EXAMPLES / "sample_decode.json")}
    (row,) = inputs.load(EXAMPLES / "sample_decodes.csv")
    assert row.milestone == js["full-example"].milestone
    assert row.birthday == js["full-example"].birthday


def test_output_is_byte_identical_across_runs(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert cli.main(["decode", str(EXAMPLES / "sample_decode.json"), "--out", str(a)]) == 0
    assert cli.main(["decode", str(EXAMPLES / "sample_decode.json"), "--out", str(b)]) == 0
    for f in sorted(a.iterdir()):
        if f.name != "freeze_ledger.jsonl":  # the only file with a timestamp
            assert f.read_bytes() == (b / f.name).read_bytes(), f.name
    data = json.loads((a / "audit-example-23.json").read_text())
    assert data["mode"] == "TAG-ONLY" and data["registry_version"] == "2.0.0"


def test_every_rule_used_is_registered():
    raw = json.loads((EXAMPLES / "sample_decode.json").read_text())["decodes"][1]
    recs, _ = rules.evaluate(inputs.parse_request(raw), REGISTRY)
    assert {r["rule_id"] for r in recs} <= set(REGISTRY["rules"])


def test_zodiac_is_a_tag_only():
    raw = {"id": "x", "player": "P", "milestone": 5, "birthday": "1998-03-14",
           "event_date": "2026-10-25", "timezone": "America/Los_Angeles"}
    res = _decode(raw)
    assert "ZODIAC-SYNC" not in REGISTRY["rules"]
    assert res["astronomy"]["event_moon"]["phase"] == "Full Moon"
    assert res["astronomy"]["event_zodiac"] == "Scorpio" and res["astronomy"]["birth_zodiac"] == "Pisces"
    assert _grid(res)["Moon phase"] == "Tag" and _grid(res)["Birth moon"] == "Tag"
    assert _grid(res)["Zodiac"] == "Tag"
    own = _decode({"id": "x", "player": "P", "milestone": 5, "birthday": "1990-10-01", "event_date": "2026-10-10"})
    assert _grid(own)["Zodiac"] == "Tag" and own["classification"]["symbolic_count"] == 0


def test_milestone_type_validated():
    assert inputs.parse_request({"id": "x", "player": "P", "milestone": 3,
                                 "milestone_type": "threshold"}).milestone_type == "threshold"
    with pytest.raises(inputs.InputError):
        inputs.parse_request({"id": "x", "player": "P", "milestone": 3, "milestone_type": "career"})


def test_event_time_sets_moon_age():
    base = {"id": "x", "player": "P", "milestone": 3, "event_date": "2026-10-21", "timezone": "America/New_York"}
    noon = _decode(base)["astronomy"]["event_moon"]
    night = _decode({**base, "event_time": "19:05"})["astronomy"]["event_moon"]
    assert night["moon_age_days"] - noon["moon_age_days"] == pytest.approx(7.08 / 24, abs=0.1)
    assert night["phase"] == noon["phase"]
    with pytest.raises(inputs.InputError):
        inputs.parse_request({**base, "event_time": "7pm"})


def test_bad_timezone_rejected():
    with pytest.raises(inputs.InputError):
        inputs.parse_request({"id": "x", "player": "P", "milestone": 3, "timezone": "Mars/Olympus"})

import json

import pytest

from conftest import BASE, ROOT, snapshot
from scriptmatria import inputs

SCHEMA = json.loads((ROOT / "input.schema.json").read_text())


def test_schema_matches_contract():
    assert SCHEMA["required"] == list(inputs.REQUIRED)
    snap = inputs.parse_request(snapshot()).to_dict()
    derived = {"input_schema_version", "target_count"}
    assert set(SCHEMA["properties"]) == set(snap) - derived
    assert SCHEMA["properties"]["overlays"]["items"]["enum"] == list(inputs.OVERLAYS)
    assert SCHEMA["title"].endswith(inputs.INPUT_SCHEMA_VERSION)


def test_example_is_valid_and_target_is_derived():
    req = inputs.parse_request(snapshot())
    assert req.current_count == 22 and req.milestone == 23
    assert req.decode_id == "MLB-2026-10-21-FIXTURE-PA_FICTIONAL-A_HR"
    assert req.milestone_id == "HR:career:23"


@pytest.mark.parametrize("field", inputs.REQUIRED)
def test_missing_required_fields_fail_clearly(field):
    raw = {k: v for k, v in BASE.items() if k != field}
    with pytest.raises(inputs.InputError, match=f"{field}: required"):
        inputs.parse_request(raw)


def test_missing_optional_fields_are_allowed():
    raw = snapshot(birth_date=None, jersey=None, event_start_local=None, overlays=None,
                   birth_date_source=None, jersey_source=None, jersey_effective_date=None)
    req = inputs.parse_request(raw)
    assert req.birth_date is None and req.jersey is None and req.overlays == ()


@pytest.mark.parametrize("overrides,message", [
    ({"birth_date": "2027-01-01"}, "birth_date: after the event date"),
    ({"current_count_as_of": "2026-10-22T10:00:00"}, "current_count_as_of: after the event date"),
    ({"jersey_effective_date": "2026-11-01"}, "jersey_effective_date: after the event date"),
    ({"opponent_id": "NYY"}, "opponent_id: must differ"),
    ({"stat_scope": "season"}, "is not implemented"),
    ({"current_count": -1}, "must not be negative"),
    ({"timezone": "Mars/Olympus"}, "not an IANA timezone"),
    ({"overlays": ["tarot"]}, "overlays: 'tarot'"),
    ({"event_start_local": "7pm"}, "event_start_local"),
])
def test_conflicting_or_invalid_inputs_fail_the_lock(overrides, message):
    with pytest.raises(inputs.InputError, match=message):
        inputs.parse_request(snapshot(**overrides))


def test_json_and_csv_agree():
    (js,) = inputs.load(ROOT / "examples" / "mlb_pilot.json")
    (cs,) = inputs.load(ROOT / "examples" / "mlb_pilot.csv")
    assert js.to_dict() == cs.to_dict()


def test_duplicate_decodes_rejected(tmp_path):
    p = tmp_path / "dup.json"
    p.write_text(json.dumps([BASE, BASE]))
    with pytest.raises(inputs.InputError, match="duplicate"):
        inputs.load(p)


def test_stat_codes_registered():
    from conftest import REGISTRY
    assert inputs.STAT_CODES == REGISTRY["pilot_stats"]
    assert SCHEMA["properties"]["stat_code"]["enum"] == list(inputs.STAT_CODES)
    for code in inputs.STAT_CODES:
        assert inputs.parse_request(snapshot(stat_code=code)).stat_code == code
    with pytest.raises(inputs.InputError, match="stat_code: 'XYZ' is not registered"):
        inputs.parse_request(snapshot(stat_code="XYZ"))


def test_same_player_multiple_stats_are_distinct_decodes(tmp_path):
    rows = [snapshot(stat_code=c) for c in ("HR", "H", "RBI")]
    p = tmp_path / "multi.json"
    p.write_text(json.dumps(rows))
    ids = [r.decode_id for r in inputs.load(p)]
    assert ids == [f"MLB-2026-10-21-FIXTURE-PA_FICTIONAL-A_{c}" for c in ("HR", "H", "RBI")]


def test_postseason_scope_is_distinct():
    from conftest import REGISTRY
    assert inputs.STAT_SCOPES == REGISTRY["stat_scopes"]
    assert SCHEMA["properties"]["stat_scope"]["enum"] == list(inputs.STAT_SCOPES)
    career = inputs.parse_request(snapshot())
    post = inputs.parse_request(snapshot(stat_scope="postseason", current_count=3))
    assert career.decode_id.endswith("_HR") and post.decode_id.endswith("_HR-postseason")
    assert post.milestone_id == "HR:postseason:4"

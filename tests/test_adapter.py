"""MLB Stats API adapter and attestation. Network is never used: responses are
recorded-shape FIXTURES with fictional players, served by URL."""

import json
from datetime import datetime, timezone

import pytest

from conftest import MLB, REGISTRY, ROOT
from scriptmatria import attest, cli, inputs
from scriptmatria.adapters import mlb_statsapi as api

NOW = datetime(2026, 10, 22, 18, 0, tzinfo=timezone.utc)


def _person(pid, name, born, number, hr, h, rbi):
    return {"people": [{"id": pid, "fullName": name, "birthDate": born, "primaryNumber": number,
                        "stats": [{"type": {"displayName": "career"}, "group": {"displayName": "hitting"},
                                   "splits": [{"stat": {"homeRuns": hr, "hits": h, "rbi": rbi}}]}]}]}


FIXTURE = {
    "/teams/139/roster": {"roster": [{"person": {"id": 1, "fullName": "Fixture Ray One"}, "jerseyNumber": "13"},
                                     {"person": {"id": 2, "fullName": "Fixture Ray Two"}, "jerseyNumber": "7"}]},
    "/teams/158/roster": {"roster": [{"person": {"id": 3, "fullName": "Fixture Brewer One"}, "jerseyNumber": "24"},
                                     {"person": {"id": 4, "fullName": "Fixture Brewer Two"}, "jerseyNumber": "11"}]},
    # Season leaders include a traded player (id 99) who is not on the active roster.
    "teamId=139": {"stats": [{"splits": [
        {"player": {"id": 99, "fullName": "Traded Away"}, "stat": {"homeRuns": 40}},
        {"player": {"id": 1, "fullName": "Fixture Ray One"}, "stat": {"homeRuns": 38}},
        {"player": {"id": 2, "fullName": "Fixture Ray Two"}, "stat": {"homeRuns": 20}}]}]},
    "teamId=158": {"stats": [{"splits": [
        {"player": {"id": 3, "fullName": "Fixture Brewer One"}, "stat": {"homeRuns": 25}},
        {"player": {"id": 4, "fullName": "Fixture Brewer Two"}, "stat": {"homeRuns": 22}}]}]},
    "/people/1": _person(1, "Fixture Ray One", "2003-07-07", "13", 82, 410, 250),
    "/people/2": _person(2, "Fixture Ray Two", "1995-02-28", "7", 140, 900, 480),
    "/people/3": _person(3, "Fixture Brewer One", "1998-12-24", "24", 120, 700, 400),
    "/people/4": _person(4, "Fixture Brewer Two", "2004-03-11", "11", 60, 300, 190),
}


def fake_get(url: str) -> dict:
    assert url.startswith(api.BASE)
    for key, payload in FIXTURE.items():
        if (key in url) and (key.startswith("teamId") == ("/stats?" in url)):
            return payload
    raise AssertionError(f"unexpected URL {url}")


def _draft(top_hr=1, stats=("HR", "H", "RBI")):
    return api.build_draft(api.Client(fake_get), event_id="MLB-2026-10-23-TB-MIL", event_date="2026-10-23",
                           timezone_name="America/Chicago", start_local="19:00", home="MIL", away="TB",
                           stats=list(stats), top_hr=top_hr, season=2026, phrase_registry_version="0.1.0",
                           overlays=["keywords", "moon", "zodiac"], now=NOW)


def test_team_ids_cover_the_phrase_registry():
    assert set(api.TEAM_IDS) == set(MLB["teams"])
    assert api.TEAM_IDS["TB"] == 139 and api.TEAM_IDS["MIL"] == 158


def test_adapter_is_approved_in_registry():
    assert f"{api.ADAPTER_ID}@{api.ADAPTER_VERSION}" in REGISTRY["approved_adapters"]
    assert tuple(REGISTRY["approved_adapters"]) == inputs.APPROVED_ADAPTERS


def test_draft_selects_active_roster_leaders_with_provenance():
    d = _draft(top_hr=1)
    assert d["draft"] is True and d["fetched_at_utc"] == "2026-10-22T18:00:00+00:00"
    names = [p["name"] for p in d["players"]]
    assert names == ["Fixture Ray One", "Fixture Brewer One"]  # traded leader skipped
    assert len(d["decodes"]) == 6  # 2 players x 3 stats
    ray_hr = next(x for x in d["decodes"] if x["player_name"] == "Fixture Ray One" and x["stat_code"] == "HR")
    assert ray_hr["current_count"] == 82 and ray_hr["team_id"] == "TB" and ray_hr["opponent_id"] == "MIL"
    assert ray_hr["jersey"] == 13 and ray_hr["birth_date"] == "2003-07-07"
    assert ray_hr["operator_attestation"] == "" and ray_hr["adapter"] == "mlb-statsapi@0.1.0"
    assert "/people/1?hydrate=stats(group=[hitting],type=[career])" in ray_hr["current_count_source"]
    assert "regular season" in ray_hr["current_count_source"]
    assert ray_hr["player_id"] == "one-fixture-ray-1"
    assert len(d["api_calls"]) == 6 and d["content_sha256"] == api.content_hash(
        {"decodes": d["decodes"], "players": d["players"]})


def test_unattested_draft_fails_the_input_lock():
    with pytest.raises(inputs.InputError, match="operator_attestation: required"):
        inputs.parse_request(_draft()["decodes"][0])


def test_not_enough_rostered_leaders_is_an_error():
    with pytest.raises(api.AdapterError, match="TB: only 2"):
        _draft(top_hr=3)


def test_unknown_stat_or_team_rejected():
    with pytest.raises(api.AdapterError):
        _draft(stats=("SB",))
    with pytest.raises(api.AdapterError):
        api.build_draft(api.Client(fake_get), event_id="x", event_date="2026-10-23", timezone_name="UTC",
                        start_local="19:00", home="XXX", away="TB", stats=["HR"], top_hr=1, season=2026,
                        phrase_registry_version="0.1.0", overlays=[])


def test_attest_signs_and_snapshot_decodes(tmp_path):
    draft_file = tmp_path / "g1.draft.json"
    draft_file.write_text(json.dumps(_draft()))
    snap = tmp_path / "g1.json"
    rec = attest.attest(draft_file, "Test Operator", snap, now=NOW)
    assert rec["attestation"]["by"] == "Test Operator" and rec["attestation"]["operator_edited"] is False
    assert all(d["operator_attestation"].startswith("Test Operator; reviewed mlb-statsapi@0.1.0 draft")
               for d in rec["decodes"])
    with pytest.raises(attest.AttestError, match="never overwritten"):
        attest.attest(draft_file, "Test Operator", snap, now=NOW)
    out = tmp_path / "reports"
    assert cli.main(["decode", str(snap), "--out", str(out)]) == 0
    sealed = json.loads(next(out.glob("*one-fixture-ray-1_HR.json")).read_text())
    assert sealed["input"]["adapter"] == "mlb-statsapi@0.1.0"
    assert sealed["input"]["target_count"] == 83


def test_attest_refuses_edited_draft_unless_recorded(tmp_path):
    d = _draft()
    d["decodes"][0]["current_count"] += 1  # tampering after fetch
    draft_file = tmp_path / "edited.draft.json"
    draft_file.write_text(json.dumps(d))
    with pytest.raises(attest.AttestError, match="modified after it was fetched"):
        attest.attest(draft_file, "Op", tmp_path / "a.json", now=NOW)
    rec = attest.attest(draft_file, "Op", tmp_path / "b.json", allow_edits=True, now=NOW)
    assert rec["attestation"]["operator_edited"] is True
    assert "OPERATOR EDITED THE DRAFT" in rec["decodes"][0]["operator_attestation"]


def test_attest_requires_a_name(tmp_path):
    draft_file = tmp_path / "g1.draft.json"
    draft_file.write_text(json.dumps(_draft()))
    with pytest.raises(attest.AttestError, match="--by is required"):
        attest.attest(draft_file, "  ", tmp_path / "x.json")


def test_unapproved_adapter_rejected():
    raw = {**_draft()["decodes"][0], "operator_attestation": "op", "adapter": "espn@0.0.1"}
    with pytest.raises(inputs.InputError, match="adapter: 'espn@0.0.1' is not approved"):
        inputs.parse_request(raw)


def test_schema_lists_adapter():
    schema = json.loads((ROOT / "input.schema.json").read_text())
    assert schema["properties"]["adapter"]["enum"] == list(inputs.APPROVED_ADAPTERS)

"""Relationship engine and validator, including the roadmap Phase 6 fixtures."""

from conftest import FIXTURE_PHRASES, MEMPHIS, REGISTRY, decode, snapshot, statuses
from scriptmatria import gematria, inputs, rules
from scriptmatria.rules import INVALID, NO_HIT, QC, QS, RULE_CONFLICT, SN, UNVERIFIED


def _hits(res, rule_id):
    return [r for r in res["records"] if r["rule_id"] == rule_id and r["status"] not in (NO_HIT,)]


# --- Phase 6 fixtures ---------------------------------------------------------

def test_fixture_memphis_pigr_b(memphis):
    (b,) = _hits(memphis, "PIGR-B")
    assert b["status"] == QS and b["phrase"] == "Memphis" and b["cipher"] == "EO" and b["value"] == 83
    assert b["numeric_values"] == {"M": 23, "G": 83, "nth_prime(M)": 83}
    assert gematria.value("Memphis", "EO") == 83
    assert all(r["status"] == NO_HIT for r in memphis["records"]
               if r["rule_id"] == "PIGR-A" and r["value"] == 83)
    assert statuses(memphis, "M-REVPRIME") == [NO_HIT]  # 23 -> 32, not prime
    assert _hits(memphis, "JERSEY-EXACT")[0]["status"] == SN
    assert memphis["birthday_card"]["total_days"] == 9638


def test_fixture_no_match_player():
    # M = 60 matches nothing on this date (M = 100 would: Wednesday EO = 100).
    res = decode(snapshot(current_count=59, jersey=None, birth_date=None, overlays=None))
    c = res["classification"]["counts"]
    assert c["qualified_structural"] == c["qualified_calendar"] == c["symbolic_notes"] == 0
    assert c["attempted"] > 0 and res["classification"]["prime_cluster"] == "NONE"


def test_fixture_missing_birthday():
    res = decode(snapshot(birth_date=None))
    assert statuses(res, "BIRTH-SPAN-EXACT") == [UNVERIFIED]
    assert res["birthday_card"] == UNVERIFIED and res["decode_status"].startswith("Partial")


def test_fixture_duplicate_phrase_alias():
    res = decode(snapshot(MEMPHIS, opponent_id="ALIASFX"))
    rows = [g for g in res["gematria_table"] if g["subject"] == "opponent ALIASFX"]
    assert [(g["phrase"], g["kind"]) for g in rows] == [("Alias", "city/nickname"), ("Alias Alias", "full")]
    ath = decode(snapshot(opponent_id="ATH"))
    assert [g["kind"] for g in ath["gematria_table"] if g["subject"] == "opponent ATH"] == ["nickname/full"]


def test_fixture_conflicting_dates_fail():
    import pytest
    with pytest.raises(inputs.InputError):
        inputs.parse_request(snapshot(current_count_as_of="2026-10-25"))


def test_fixture_nonleap_feb29():
    res = decode(snapshot(birth_date="2000-02-29", event_date_local="2026-02-28",
                          current_count_as_of="2026-02-27", jersey_effective_date=None))
    pending = [r["right_source"] for r in res["records"]
               if r["rule_id"] == "BIRTH-SPAN-EXACT" and r["status"] == UNVERIFIED]
    assert set(pending) == {"birthday age_years", "birthday ymd_months", "birthday ymd_days",
                            "birthday days_since_birthday", "birthday days_until_birthday"}
    assert res["birthday_card"]["total_days"] == 9496


def test_fixture_source_outside_event():
    res = decode(snapshot(requested_phrases=[{"team_id": "LAD", "phrase": "Dodgers"}]))
    (bad,) = [r for r in res["records"] if r["status"] == INVALID]
    assert "not in this event" in bad["computation"]


def test_fixture_unapproved_phrase_is_invalid():
    res = decode(snapshot(requested_phrases=[{"team_id": "BOS", "phrase": "BoSox"},
                                             {"team_id": "BOS", "phrase": "red sox"}]))
    bad = [r for r in res["records"] if r["status"] == INVALID]
    assert len(bad) == 1 and "BoSox" in bad[0]["computation"]  # approved phrase (any case) is fine


def test_fixture_no_authorized_opponent_phrase():
    res = decode(snapshot(MEMPHIS, opponent_id="NOWHERE"))
    assert statuses(res, "OPP-TYPEA") == [UNVERIFIED]
    assert "no authorized opponent phrase" in _hits(res, "OPP-TYPEA")[0]["computation"]


def test_fixture_pigr_c_digit_sum_is_never_a_bridge():
    # Memphis EO 83 digit-sums to 11; M = 11 must not hit via that reduction.
    res = decode(snapshot(MEMPHIS, current_count=10, jersey=None, overlays=None))
    assert "PIGR-C" not in REGISTRY["rules"]
    for r in res["records"]:
        if r["rule_id"].startswith("PIGR") and r.get("phrase") == "Memphis" and r["cipher"] == "EO":
            assert r["status"] == NO_HIT


def test_fixture_registry_version_conflict():
    res = decode(snapshot(phrase_registry_version="0.0.9"))
    assert statuses(res, "OPP-TYPEA") == [RULE_CONFLICT] and statuses(res, "SELF-TYPEA") == [RULE_CONFLICT]
    assert "rule conflict" in res["decode_status"]


# --- Rules --------------------------------------------------------------------

def test_pigr_a_and_b_never_both_for_one_value():
    # Exhaustive over the arithmetic: no (M, G) pair satisfies both definitions.
    from scriptmatria import primes
    for m in range(2, 400):
        idx = primes.prime_index(m)
        for g in range(1, 3000):
            a = idx is not None and idx == g
            b = primes.is_prime(g) and primes.prime_index(g) == m
            assert not (a and b), (m, g)
    # and the engine labels each source value independently
    res = decode(snapshot(MEMPHIS, jersey=83, overlays=None))
    jersey = {r["rule_id"] for r in res["records"] if r["source_id"] == "jersey" and r["status"] == QS}
    assert jersey == {"PIGR-B"}


def test_pigr_a_hits_from_a_verified_source():
    res = decode(snapshot(MEMPHIS, jersey=9))  # prime_index(23) = 9
    assert any(r["source_id"] == "jersey" and r["status"] == QS for r in _hits(res, "PIGR-A"))


def test_reverse_prime_counts_palindromes():
    res = decode(snapshot(current_count=10))  # M = 11, reverse 11
    assert statuses(res, "M-REVPRIME") == [QS]


def test_overlays_are_opt_in():
    res = decode(snapshot(overlays=None))
    assert not any(r["rule_id"] == "KW-EXACT" for r in res["records"])
    assert res["overlays"] == {}
    res = decode(snapshot(overlays=["moon"], event_start_local=None))
    assert res["overlays"]["moon"]["status"] == UNVERIFIED


def test_calendar_hits_and_weekday_planet_rules(pilot):
    (planet,) = _hits(pilot, "PLANET-GEM")
    assert planet["status"] == QC and planet["phrase"] == "Mercury" and planet["cipher"] == "CH"


def test_triple_prime_not_evaluated_and_cluster_flagged():
    res = decode(snapshot(MEMPHIS, jersey=9))  # M-PRIME, PIGR-B (Memphis), PIGR-A (jersey 9)
    cls = res["classification"]
    assert cls["prime_observations"] >= 3
    assert cls["prime_cluster"] == "CANDIDATE" and cls["prime_cluster_flag"] == "DEPENDENCY_REVIEW_REQUIRED"
    assert cls["triple_prime_sync"] == "NOT_EVALUATED"


def test_dependent_restatements_grouped(pilot):
    group = next(d for d in pilot["classification"]["dependency_groups"] if d["number"] == 23)
    assert group["dependent"] and len(group["hits"]) == 3


def test_only_registered_rules_and_ciphers(pilot):
    assert {r["rule_id"] for r in pilot["records"]} <= set(REGISTRY["rules"])
    assert {r["cipher"] for r in pilot["records"]} <= set(gematria.CIPHERS) | {None}
    for r in pilot["records"]:
        assert r["rule_version"] == REGISTRY["rules"][r["rule_id"]]["version"]
        for key in ("event_id", "player_id", "milestone_id", "left_source", "right_source", "operation",
                    "numeric_values", "family", "status"):
            assert r[key] not in (None, ""), key

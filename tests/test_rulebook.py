"""The rulebook, registry and input schema must agree. A rule, version, keyword,
formula or decision that drifts in one place fails here."""

import json
import re
from datetime import date

from conftest import REGISTRY, ROOT
from scriptmatria import dates, inputs

RULEBOOK = (ROOT / "ZILLA_3_RULEBOOK.md").read_text(encoding="utf-8")


def test_rule_table_matches_registry():
    table = dict(re.findall(r"^\| ([A-Z][A-Z0-9-]+) \| (\d+\.\d+) \|", RULEBOOK, flags=re.M))
    assert table == {rid: r["version"] for rid, r in REGISTRY["rules"].items()}


def test_rule_classes_match_registry():
    rows = re.findall(r"^\| ([A-Z][A-Z0-9-]+) \| \d+\.\d+ \| .* \| (\w+) \| (yes|no) \|$", RULEBOOK, flags=re.M)
    for rid, cls, prime in rows:
        assert REGISTRY["rules"][rid]["class"] == cls, rid
        assert REGISTRY["rules"][rid]["prime_related"] == (prime == "yes"), rid


def test_versions_match():
    assert f"**Rule registry:** v{REGISTRY['registry_version']}" in RULEBOOK
    assert f"**Version:** v{REGISTRY['rulebook_version']}" in RULEBOOK
    assert f"PlayerMilestoneInput v{inputs.INPUT_SCHEMA_VERSION}" in RULEBOOK


def test_keyword_sets_match():
    for name, nums in REGISTRY["symbolic_sets"].items():
        assert f"**{name}:** {', '.join(map(str, nums))}" in RULEBOOK


def test_date_card_matches_code():
    dn = dates.date_numerology(date(2026, 10, 21))
    for code in ("DN1", "DN2", "DN3", "DN4", "DN5", "DOY"):
        assert re.search(rf"^\| {code} \|.*\*\*{dn[code]}\*\* \|$", RULEBOOK, flags=re.M), code
    assert "| DAYS_LEFT |" in RULEBOOK and f"**{dn['DAYS_LEFT']}**" in RULEBOOK


def test_planets_match_code():
    for day, planet in dates.WEEKDAY_PLANETS.items():
        assert f"{day[:3]}→{planet}" in RULEBOOK
    assert REGISTRY["conventions"]["weekday_planets"] == dates.WEEKDAY_PLANETS


def test_required_inputs_listed():
    for field in inputs.REQUIRED:
        assert f"`{field}`" in RULEBOOK, field
    schema = json.loads((ROOT / "input.schema.json").read_text())
    assert schema["required"] == list(inputs.REQUIRED)


def test_statuses_and_decisions_listed():
    for status in REGISTRY["statuses"]:
        assert f"`{status}`" in RULEBOOK, status
    assert "NOT_EVALUATED" in RULEBOOK and "DEPENDENCY_REVIEW_REQUIRED" in RULEBOOK
    assert "**Decided:** manual only" in RULEBOOK

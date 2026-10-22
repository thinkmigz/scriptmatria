"""The rulebook and the registry must agree: every registered rule appears in the
rulebook's rule table with the same version, and vice versa."""

import re
from datetime import date
from pathlib import Path

from scriptmatria import dates, rules

RULEBOOK = (Path(__file__).parent.parent / "ZILLA_3_RULEBOOK.md").read_text(encoding="utf-8")
REGISTRY = rules.load_registry()


def _rulebook_rules() -> dict[str, str]:
    return dict(re.findall(r"^\| ([A-Z][A-Z0-9-]+) \| (\d+\.\d+) \|", RULEBOOK, flags=re.M))


def test_rule_ids_and_versions_match_registry():
    assert _rulebook_rules() == {rid: r["version"] for rid, r in REGISTRY["rules"].items()}


def test_registry_version_matches():
    assert f"**Registry:** v{REGISTRY['registry_version']}" in RULEBOOK


def test_symbolic_sets_match():
    for name, nums in REGISTRY["symbolic_sets"].items():
        assert f"**{name}:** {', '.join(map(str, nums))}" in RULEBOOK


def test_date_card_example_matches_code():
    dn = dates.date_numerology(date(2026, 10, 21))
    for code in ("DN1", "DN2", "DN3", "DN4", "DN5", "DOY"):
        assert re.search(rf"^\| {code} \|.*\*\*{dn[code]}\*\* \|$", RULEBOOK, flags=re.M), code


def test_planet_table_matches_code():
    for day, planet in dates.WEEKDAY_PLANETS.items():
        assert f"{day[:3]}→{planet}" in RULEBOOK
    assert REGISTRY["conventions"]["weekday_planets"] == dates.WEEKDAY_PLANETS

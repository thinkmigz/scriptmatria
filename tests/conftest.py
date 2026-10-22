import json
from pathlib import Path

import pytest

from scriptmatria import inputs, phrases, report, rules

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
REGISTRY = rules.load_registry()
MLB = phrases.load(league="MLB")
FIXTURE_PHRASES = phrases.load(FIXTURES / "phrases_fixture.json")

BASE = json.loads((ROOT / "examples" / "mlb_pilot.json").read_text())["decodes"][0]
MEMPHIS = json.loads((FIXTURES / "memphis_pilot.json").read_text())["decodes"][0]


def snapshot(base=None, **overrides) -> dict:
    raw = {**(base or BASE), **overrides}
    return {k: v for k, v in raw.items() if v is not None}


def decode(raw: dict, phrase_reg=None) -> dict:
    req = inputs.parse_request(raw)
    reg = phrase_reg or (FIXTURE_PHRASES if req.league == "FIXTURE" else MLB)
    return report.decode(req, REGISTRY, reg)


def statuses(result: dict, rule_id: str) -> list[str]:
    return [r["status"] for r in result["records"] if r["rule_id"] == rule_id]


@pytest.fixture
def pilot():
    return decode(snapshot())


@pytest.fixture
def memphis():
    return decode(snapshot(MEMPHIS))

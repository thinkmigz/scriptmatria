"""Research lab only (rulebook §8): decode the same verified sources against
alternative milestones to describe how ordinary the actual hit count is. Never
part of a sealed decode and never a probability of the milestone."""

from dataclasses import replace

from . import rules, validator
from .inputs import DecodeRequest


def _score(req: DecodeRequest, registry: dict, phrase_reg: dict) -> tuple[int, int]:
    c = validator.classify(rules.evaluate(req, registry, phrase_reg))
    return c["counts"]["qualified_structural"] + c["counts"]["qualified_calendar"], c["prime_observations"]


def control_test(req: DecodeRequest, registry: dict, phrase_reg: dict) -> dict:
    window = registry["control"]["milestone_window"]
    m = req.milestone
    actual, actual_prime = _score(req, registry, phrase_reg)
    alternatives = [k for k in range(max(1, m - window), m + window + 1) if k != m]
    scores = {k: _score(replace(req, current_count=k - 1), registry, phrase_reg) for k in alternatives}
    hits = [h for h, _ in scores.values()]
    return {
        "decode_id": req.decode_id,
        "kind": "research/control",
        "universe": f"milestones {alternatives[0]}–{alternatives[-1]} excluding {m}",
        "alternatives": len(alternatives),
        "actual_qualified": actual,
        "actual_prime_observations": actual_prime,
        "control_mean_qualified": round(sum(hits) / len(hits), 2),
        "control_max_qualified": max(hits),
        "alternatives_at_least_as_many": sum(1 for h in hits if h >= actual),
        "per_milestone": {str(k): {"qualified": h, "prime_observations": p} for k, (h, p) in scores.items()},
        "caveat": "Descriptive rarity within a fixed universe; not evidence that the milestone is more likely.",
    }

"""Step 6: control test. Decode the same sources against alternative milestones
to see how ordinary the actual hit count is. Descriptive rarity only.
"""

from dataclasses import replace

from . import rules, validator
from .inputs import DecodeRequest


def _score(req: DecodeRequest, registry: dict) -> tuple[int, int]:
    records, _ = rules.evaluate(req, registry)
    cls = validator.classify(records)
    return cls["hit_count"], cls["prime_hits"]


def control_test(req: DecodeRequest, registry: dict) -> dict:
    window = registry["control"]["milestone_window"]
    m = req.milestone
    actual_hits, actual_prime = _score(req, registry)
    alternatives = [k for k in range(max(1, m - window), m + window + 1) if k != m]
    scores = {k: _score(replace(req, milestone=k), registry) for k in alternatives}
    hits = [h for h, _ in scores.values()]
    return {
        "universe": f"milestones {alternatives[0]}–{alternatives[-1]} excluding {m}",
        "alternatives": len(alternatives),
        "actual_hits": actual_hits,
        "actual_prime_hits": actual_prime,
        "control_mean_hits": round(sum(hits) / len(hits), 2),
        "control_max_hits": max(hits),
        "alternatives_at_least_as_many": sum(1 for h in hits if h >= actual_hits),
        "per_milestone": {str(k): {"hits": h, "prime_hits": p} for k, (h, p) in scores.items()},
    }

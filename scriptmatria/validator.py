"""Signal validator (rulebook §7). Counts statuses, groups dependent hits, and
finds Triple Prime: 3 or more qualified prime relationships in one decode.
Symbolic notes never count as structural evidence."""

from collections import Counter, defaultdict

from .rules import COMPARED, QC, QS, SN


def _family(rec: dict) -> str:
    return "milestone" if rec["rule_id"] in ("M-PRIME", "M-REVPRIME") else rec["family"]


def classify(records: list[dict]) -> dict:
    statuses = Counter(r["status"] for r in records)
    qualified = [r for r in records if r["status"] in (QS, QC)]
    noted = [r for r in records if r["status"] == SN]
    prime_obs = [r for r in records if r["status"] == QS and r["prime_related"]]

    # One number restated under several labels is one observation, not several.
    by_number: dict[int, list[str]] = defaultdict(list)
    for r in qualified + noted:
        number = r["numeric_values"]["M"] if r["rule_id"] in ("M-PRIME", "M-REVPRIME") else r["value"]
        by_number[number].append(f"{r['rule_id']} [{r['right_source']}]")
    groups = [{"number": n, "hits": sorted(h), "dependent": len(h) > 1} for n, h in sorted(by_number.items())]

    families = sorted({_family(r) for r in qualified})
    prime_families = sorted({_family(r) for r in prime_obs})
    return {
        "counts": {
            "attempted": sum(statuses[s] for s in COMPARED),
            "qualified_structural": statuses[QS],
            "qualified_calendar": statuses[QC],
            "symbolic_notes": statuses[SN],
            "no_hit": statuses["NO_HIT"],
            "invalid": statuses["INVALID"],
            "unverified": statuses["UNVERIFIED"],
            "rule_conflict": statuses["RULE_CONFLICT"],
            "distinct_qualified_families": len(families),
            "distinct_numbers": len(by_number),
        },
        "qualified_families": families,
        "dependency_groups": groups,
        "prime_observations": len(prime_obs),
        "prime_families": prime_families,
        "triple_prime": {"found": len(prime_obs) >= 3,
                         "relationships": [r["computation"] for r in prime_obs]},
    }


def ledger(records: list[dict]) -> dict:
    out: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        out[r["rule_id"]][r["status"]] += 1
    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}

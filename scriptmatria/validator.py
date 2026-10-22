"""Classify hits: evidence families, dependency groups, Prime Cluster and
Triple Prime Sync. Symbolic tags never count toward prime totals.
"""

from collections import defaultdict


def _prime_family(rec: dict) -> str:
    return "milestone" if rec["rule_id"] in ("PRIME-M", "REVPRIME-M") else rec["family"]


def classify(records: list[dict]) -> dict:
    all_hits = [r for r in records if r["hit"]]
    # Hits from numbers not yet tied to a phrase and cipher are held back as pending.
    pending = [r for r in all_hits if not r["source_verified"]]
    hits = [r for r in all_hits if r["source_verified"]]
    structural = [r for r in hits if r["evidence_class"] != "symbolic"]
    prime_hits = [r for r in hits if r["prime_related"]]

    families: dict[str, list[str]] = defaultdict(list)
    for r in structural:
        families[_prime_family(r) if r["prime_related"] else r["family"]].append(r["rule_id"])

    # Hits that restate the same number are dependent, however many labels they carry.
    by_number: dict[int, list[str]] = defaultdict(list)
    for r in structural:
        by_number[r["value"]].append(f"{r['rule_id']} [{r['label']}]")
    dependency_groups = [
        {"number": n, "hits": sorted(labels), "dependent": len(labels) > 1}
        for n, labels in sorted(by_number.items())
    ]

    prime_families = sorted({_prime_family(r) for r in prime_hits})
    prime_numbers = sorted({r["value"] for r in prime_hits})
    cluster = len(prime_hits) >= 3
    sync = len(prime_families) >= 3 and len(prime_numbers) >= 3
    if sync:
        reason = (f"{len(prime_hits)} prime hits from {len(prime_families)} families "
                  f"({', '.join(prime_families)}) on {len(prime_numbers)} distinct numbers")
    else:
        reason = (f"{len(prime_hits)} prime hit(s) from {len(prime_families)} famil"
                  f"{'y' if len(prime_families) == 1 else 'ies'}"
                  f"{' (' + ', '.join(prime_families) + ')' if prime_families else ''}"
                  f" on {len(prime_numbers)} distinct number(s); needs 3 families and 3 numbers")

    return {
        "hit_count": len(structural),
        "pending_hits": [f"{r['rule_id']} [{r['label']}]" for r in pending],
        "symbolic_count": len(hits) - len(structural),
        "families": {k: sorted(v) for k, v in sorted(families.items())},
        "dependency_groups": dependency_groups,
        "prime_hits": len(prime_hits),
        "prime_families": prime_families,
        "prime_numbers": prime_numbers,
        "prime_cluster": cluster,
        "triple_prime_sync": sync,
        "triple_prime_sync_reason": reason,
    }


def ledger(records: list[dict]) -> dict:
    out: dict[str, dict[str, int]] = {}
    for r in records:
        row = out.setdefault(r["rule_id"], {"comparisons": 0, "hits": 0})
        row["comparisons"] += 1
        row["hits"] += int(r["hit"])
    return dict(sorted(out.items()))

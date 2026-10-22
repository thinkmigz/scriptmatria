"""Turn evaluated records into the decode grid, a finding sentence and a JSON
audit record. Output is deterministic: identical inputs give identical bytes.
"""

import csv
import hashlib
import io
import json
import re
from pathlib import Path

from . import astro, dates, primes, rules, validator
from .inputs import DecodeRequest

EXACT, NO_HIT, UNVERIFIED = "✓ Exact", "No hit", "Unverified"
QUALIFIED, NOT_QUALIFIED = "✓ Qualified", "Not qualified"
TAG = "Tag"

ALIGNMENT_NAMES = {
    "PRIME-M": "prime milestone", "REVPRIME-M": "reverse prime", "PIGR-A": "PIGR-A",
    "PIGR-B": "PIGR-B", "TYPEA": "opponent Type A", "GEM-SELF": "self-referential gematria",
    "JERSEY": "jersey", "BDAY": "birthday", "DN": "date numerology", "ZODIAC-SYNC": "zodiac season",
}


def astronomy(req: DecodeRequest) -> dict:
    """Descriptive calendar tags. They are reported, never matched against the milestone."""
    out = {}
    if req.event_date:
        out["event_weekday"] = dates.weekday(req.event_date)
        out["event_moon"] = astro.moon_phase(req.event_date, req.timezone)
        out["event_zodiac"] = astro.zodiac_sign(req.event_date)
    if req.birthday:
        out["birth_moon"] = astro.moon_phase(req.birthday)
        out["birth_zodiac"] = astro.zodiac_sign(req.birthday)
    return out


def _moon_text(moon: dict) -> str:
    when = f"exact {moon['principal_phase_utc']}" if moon["principal_phase_utc"] else (
        f"full in {moon['days_to_full_moon']} d, new in {moon['days_to_new_moon']} d")
    return f"{moon['phase']} · age {moon['moon_age_days']} d · {when} ({moon['timezone']})"


def _astro_rows(astro_tags: dict, zodiac_records: list[dict]) -> list[dict]:
    birth = ([{"test": "Birth moon", "finding": _moon_text(astro_tags["birth_moon"]), "result": TAG}]
             if "birth_moon" in astro_tags else [])
    if "event_moon" not in astro_tags:
        missing = "Event date not supplied"
        return [{"test": t, "finding": missing, "result": UNVERIFIED}
                for t in ("Weekday", "Moon phase", "Zodiac")] + birth
    rows = [
        {"test": "Weekday", "finding": astro_tags["event_weekday"], "result": TAG},
        {"test": "Moon phase", "finding": _moon_text(astro_tags["event_moon"]), "result": TAG},
        *birth,
    ]
    if zodiac_records:
        rows.append(_row("Zodiac", zodiac_records))
    else:
        rows.append({"test": "Zodiac", "finding": f"event in {astro_tags['event_zodiac']} season; "
                                                  "birthday not supplied", "result": TAG})
    return rows


def _row(test, records, missing=None, none_text=None):
    """Summarize all comparisons of one rule as a single grid row."""
    if missing:
        return {"test": test, "finding": missing.capitalize(), "result": UNVERIFIED}
    hits = [r for r in records if r["hit"]]
    if hits:
        return {"test": test, "finding": "; ".join(r["computation"] for r in hits), "result": EXACT}
    if len(records) == 1:
        return {"test": test, "finding": records[0]["computation"], "result": NO_HIT}
    return {"test": test, "finding": none_text or f"0 of {len(records)} values match", "result": NO_HIT}


def decode(req: DecodeRequest, registry: dict) -> dict:
    records, unverified = rules.evaluate(req, registry)
    cls = validator.classify(records)
    m = req.milestone
    astro_tags = astronomy(req)
    by = lambda rid: [r for r in records if r["rule_id"] == rid]  # noqa: E731
    any_sources = any(r["source_id"] != "milestone" for r in by("PIGR-B"))
    idx_m = primes.prime_index(m)

    grid = [
        _row("Prime milestone", by("PRIME-M")),
        _row("Reverse prime", by("REVPRIME-M")),
        _row("PIGR-B", by("PIGR-B"), None if any_sources else "no source values supplied",
             f"no value equals {primes.nth_prime(m)} (the {rules._ordinal(m)} prime); "
             f"{len(by('PIGR-B'))} values checked"),
        _row("PIGR-A", by("PIGR-A"), None if any_sources or idx_m is None else "no source values supplied",
             f"no value equals {idx_m} (index of {m}); {len(by('PIGR-A'))} values checked"),
        _row("Opponent Type A", by("TYPEA"), unverified.get("opponent_gematria")),
    ]
    if by("GEM-SELF"):
        grid.append(_row("Self gematria", by("GEM-SELF")))
    grid += [
        _row("Jersey", by("JERSEY"), unverified.get("jersey")),
        _row("Birthday interval", by("BDAY"), unverified.get("birthday")),
        _row("Date numerology", by("DN"), unverified.get("calendar")),
        *_astro_rows(astro_tags, by("ZODIAC-SYNC")),
        _row("Symbolic codes", by("SYM"), none_text="no locked symbolic numbers present"),
        {"test": "Prime Cluster", "finding": f"{cls['prime_hits']} prime-related hit(s)",
         "result": QUALIFIED if cls["prime_cluster"] else NOT_QUALIFIED},
        {"test": "Triple Prime Sync", "finding": cls["triple_prime_sync_reason"],
         "result": QUALIFIED if cls["triple_prime_sync"] else NOT_QUALIFIED},
    ]

    present = []
    for r in records:
        name = ALIGNMENT_NAMES.get(r["rule_id"])
        if r["hit"] and name and name not in present:
            present.append(name)
    finding = (f"Alignments present: {', '.join(present)}." if present
               else "No structural alignments found.")
    finding += (" Triple Prime Sync qualified." if cls["triple_prime_sync"]
                else " The conditions for Triple Prime Sync have not been established.")

    canonical_input = json.dumps(req.to_dict(), sort_keys=True, ensure_ascii=False)
    return {
        "decode_id": req.id,
        "mode": registry["mode"],
        "registry_version": registry["registry_version"],
        "input": req.to_dict(),
        "input_sha256": hashlib.sha256(canonical_input.encode("utf-8")).hexdigest(),
        "unverified": dict(sorted(unverified.items())),
        "astronomy": astro_tags,
        "grid": grid,
        "finding": finding,
        "classification": cls,
        "ledger": validator.ledger(records),
        "total_comparisons": len(records),
        "records": records,
    }


def to_markdown(result: dict) -> str:
    inp = result["input"]
    stat = inp["stat_category"] or "stat"
    move = f"{inp['current']} → {inp['milestone']}" if inp["current"] is not None else str(inp["milestone"])
    matchup = " vs ".join(x for x in (inp["team"], inp["opponent"]) if x) or "—"
    lines = [
        f"# Scriptmatria decode — {result['decode_id']}",
        "",
        f"**{result['mode']}** · registry v{result['registry_version']} · input sha256 `{result['input_sha256'][:12]}`",
        "",
        "| Player | Stat | Milestone | Jersey | Event | Matchup |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| {inp['player']} | {stat} | {move} | {inp['jersey'] if inp['jersey'] is not None else '—'} "
        f"| {inp['event_date'] or '—'} | {matchup} |",
        "",
        "| Test | Finding | Result |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {g['test']} | {g['finding'].replace('|', '/')} | {g['result']} |" for g in result["grid"]]
    lines += ["", f"**Decode finding:** {result['finding']}", ""]

    deps = [d for d in result["classification"]["dependency_groups"] if d["dependent"]]
    if deps:
        lines += ["## Dependent hits", "",
                  "These hits restate the same number and are not independent confirmations:", ""]
        lines += [f"- **{d['number']}**: {', '.join(d['hits'])}" for d in deps]
        lines.append("")

    lines += ["## Comparison ledger", "", "| Rule | Comparisons | Hits |", "| --- | --- | --- |"]
    lines += [f"| {k} | {v['comparisons']} | {v['hits']} |" for k, v in result["ledger"].items()]
    lines += ["", f"Total comparisons: {result['total_comparisons']}", "",
              "_Alignments are mathematical observations, not predictions. "
              "No rule in this registry has demonstrated predictive value._", ""]
    return "\n".join(lines)


def to_csv(results: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["decode_id", "test", "finding", "result"])
    for res in results:
        for g in res["grid"]:
            w.writerow([res["decode_id"], g["test"], g["finding"], g["result"]])
    return buf.getvalue()


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "decode"


def write(results: list[dict], out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for res in results:
        base = out / _safe(res["decode_id"])
        md, js = base.with_suffix(".md"), base.with_suffix(".json")
        md.write_text(to_markdown(res), encoding="utf-8")
        js.write_text(json.dumps(res, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        written += [md, js]
    grid = out / "grid.csv"
    grid.write_text(to_csv(results), encoding="utf-8")
    written.append(grid)
    return written

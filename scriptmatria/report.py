"""Turn evaluated records into the decode grid, a finding sentence and a JSON
audit record. Output is deterministic: identical inputs give identical bytes.
"""

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import astro, control, dates, primes, rules, validator, xlsx
from .inputs import DecodeRequest

EXACT, NO_HIT, UNVERIFIED = "✓ Exact", "No hit", "Unverified"
QUALIFIED, NOT_QUALIFIED = "✓ Qualified", "Not qualified"
TAG, PENDING, DESCRIPTIVE = "Tag", "Source pending", "Descriptive"

ALIGNMENT_NAMES = {
    "PRIME-M": "prime milestone", "REVPRIME-M": "reverse prime", "PIGR-A": "PIGR-A",
    "PIGR-B": "PIGR-B", "TYPEA": "opponent Type A", "GEM-SELF": "self-referential gematria",
    "JERSEY": "jersey", "BDAY": "birthday", "DN": "date numerology",
    "DAY-GEM": "weekday gematria", "PLANET-GEM": "planet gematria",
}


def astronomy(req: DecodeRequest) -> dict:
    """Descriptive calendar tags. They are reported, never matched against the milestone."""
    out = {}
    if req.event_date:
        out["event_weekday"] = dates.weekday(req.event_date)
        out["event_planet"] = dates.ruling_planet(req.event_date)
        out["event_moon"] = astro.moon_phase(req.event_date, req.timezone, req.event_time)
        out["event_zodiac"] = astro.zodiac_sign(req.event_date)
    if req.birthday:
        out["birth_moon"] = astro.moon_phase(req.birthday)
        out["birth_zodiac"] = astro.zodiac_sign(req.birthday)
    return out


def _moon_text(moon: dict) -> str:
    when = f"exact {moon['principal_phase_utc']}" if moon["principal_phase_utc"] else (
        f"full in {moon['days_to_full_moon']} d, new in {moon['days_to_new_moon']} d")
    return (f"{moon['phase']} · age {moon['moon_age_days']} d at {moon['measured_at']} · {when} "
            f"({moon['timezone']})")


def _day_planet_row(records: list[dict]) -> dict:
    hits = [r for r in records if r["hit"]]
    if hits:
        return {"test": "Weekday & planet gematria", "result": EXACT,
                "finding": "; ".join(r["computation"] for r in hits)}
    words: dict[str, list[str]] = {}
    for r in records:
        words.setdefault(r["phrase"], []).append(f"{r['cipher']} {r['value']}")
    return {"test": "Weekday & planet gematria", "result": NO_HIT,
            "finding": " · ".join(f"{w} {' / '.join(v)}" for w, v in words.items()) + " — none equal M"}


def _astro_rows(astro_tags: dict, day_planet_records: list[dict]) -> list[dict]:
    birth = ([{"test": "Birth moon", "finding": _moon_text(astro_tags["birth_moon"]), "result": TAG}]
             if "birth_moon" in astro_tags else [])
    if "event_moon" not in astro_tags:
        missing = "Event date not supplied"
        return [{"test": t, "finding": missing, "result": UNVERIFIED}
                for t in ("Weekday", "Weekday & planet gematria", "Moon phase", "Zodiac")] + birth
    zodiac = f"event in {astro_tags['event_zodiac']} season"
    if "birth_zodiac" in astro_tags:
        zodiac += f"; player born {astro_tags['birth_zodiac']}"
    return [
        {"test": "Weekday", "finding": f"{astro_tags['event_weekday']} · ruled by {astro_tags['event_planet']}",
         "result": TAG},
        _day_planet_row(day_planet_records),
        {"test": "Moon phase", "finding": _moon_text(astro_tags["event_moon"]), "result": TAG},
        *birth,
        {"test": "Zodiac", "finding": zodiac, "result": TAG},
    ]


def _row(test, records, missing=None, none_text=None):
    """Summarize all comparisons of one rule as a single grid row."""
    if missing:
        return {"test": test, "finding": missing.capitalize(), "result": UNVERIFIED}
    hits = [r for r in records if r["hit"] and r["source_verified"]]
    pending = [r for r in records if r["hit"] and not r["source_verified"]]
    if hits:
        text = "; ".join(r["computation"] for r in hits)
        if pending:
            text += "; pending: " + "; ".join(r["computation"] for r in pending)
        return {"test": test, "finding": text, "result": EXACT}
    if pending:
        return {"test": test, "result": PENDING,
                "finding": "; ".join(f"{r['computation']} — {r['label']} needs its phrase and cipher"
                                     for r in pending)}
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
        *_astro_rows(astro_tags, by("DAY-GEM") + by("PLANET-GEM")),
        _row("Symbolic codes", by("SYM"), none_text="no locked symbolic numbers present"),
        {"test": "Prime Cluster", "finding": f"{cls['prime_hits']} prime-related hit(s)",
         "result": QUALIFIED if cls["prime_cluster"] else NOT_QUALIFIED},
        {"test": "Triple Prime Sync", "finding": cls["triple_prime_sync_reason"],
         "result": QUALIFIED if cls["triple_prime_sync"] else NOT_QUALIFIED},
    ]
    ctl = control.control_test(req, registry)
    grid.append({"test": "Control test", "result": DESCRIPTIVE, "finding": (
        f"{ctl['actual_hits']} verified structural hit(s); {ctl['universe']} average "
        f"{ctl['control_mean_hits']}; {ctl['alternatives_at_least_as_many']} of {ctl['alternatives']} "
        f"have as many or more")})

    present = []
    for r in records:
        name = ALIGNMENT_NAMES.get(r["rule_id"])
        if r["hit"] and name:
            name += "" if r["source_verified"] else " (source pending)"
            if name not in present:
                present.append(name)
    finding = (f"Alignments present: {', '.join(present)}." if present
               else "No structural alignments found.")
    finding += (" Triple Prime Sync qualified." if cls["triple_prime_sync"]
                else " The conditions for Triple Prime Sync have not been established.")

    missing = sorted(unverified)
    if cls["pending_hits"]:
        status = "Partial, source verification required"
    elif missing:
        status = "Partial, inputs missing: " + ", ".join(k.replace("_", " ") for k in missing)
    else:
        status = "Complete"

    canonical_input = json.dumps(req.to_dict(), sort_keys=True, ensure_ascii=False)
    result = {
        "decode_id": req.id,
        "mode": registry["mode"],
        "registry_version": registry["registry_version"],
        "input": req.to_dict(),
        "input_sha256": hashlib.sha256(canonical_input.encode("utf-8")).hexdigest(),
        "unverified": dict(sorted(unverified.items())),
        "astronomy": astro_tags,
        "grid": grid,
        "finding": finding,
        "decode_status": status,
        "classification": cls,
        "control": ctl,
        "ledger": validator.ledger(records),
        "total_comparisons": len(records),
        "records": records,
    }
    result["summary"] = summary_row(result)
    return result


def _yes(records: list[dict], rid: str) -> str:
    rs = [r for r in records if r["rule_id"] == rid and r["hit"]]
    if any(r["source_verified"] for r in rs):
        return "Yes"
    return "Conditional (source pending)" if rs else "No"


SUMMARY_COLUMNS = [
    "Decode ID", "Player", "Event date", "Stat", "Milestone type", "Current", "Next milestone",
    "Birthday span (days)", "Prime index", "Reverse prime", "PIGR-A", "PIGR-B", "Opponent Type A",
    "Jersey sync", "Birthday match", "Date match", "Weekday / planet", "Skull/Jesuit", "Moon",
    "Zodiac", "Prime Cluster", "Triple Prime", "Control (≥ actual)", "Decode status", "Registry",
]


def summary_row(res: dict) -> dict:
    """One spreadsheet row per decode (workflow step 8)."""
    inp, recs, astro_tags = res["input"], res["records"], res["astronomy"]
    span = next((r["value"] for r in recs if r["source_id"] == "birthday:total_days"), None)
    dn = [r["label"].split()[-1] for r in recs if r["rule_id"] == "DN" and r["hit"]]
    sym = [f"{r['label']}={r['value']} {r['computation'].rsplit(', a ', 1)[-1].removesuffix(' number')}"
           for r in recs if r["rule_id"] == "SYM" and r["hit"]]
    ctl, cls = res["control"], res["classification"]
    row = {
        "Decode ID": res["decode_id"],
        "Player": inp["player"],
        "Event date": inp["event_date"] or "—",
        "Stat": inp["stat_category"] or "—",
        "Milestone type": inp["milestone_type"] or "—",
        "Current": inp["current"] if inp["current"] is not None else "—",
        "Next milestone": inp["milestone"],
        "Birthday span (days)": span if span is not None else "Unverified",
        "Prime index": primes.prime_index(inp["milestone"]) or "Not prime",
        "Reverse prime": _yes(recs, "REVPRIME-M"),
        "PIGR-A": _yes(recs, "PIGR-A"),
        "PIGR-B": _yes(recs, "PIGR-B"),
        "Opponent Type A": _yes(recs, "TYPEA"),
        "Jersey sync": _yes(recs, "JERSEY") if inp["jersey"] is not None else "Unverified",
        "Birthday match": _yes(recs, "BDAY") if span is not None else "Unverified",
        "Date match": (", ".join(dn) if dn else "No direct milestone-to-DN match")
                      if inp["event_date"] else "Unverified",
        "Weekday / planet": (f"{astro_tags['event_weekday']} / {astro_tags['event_planet']}"
                             + (" (gematria match)" if "Yes" in (_yes(recs, "DAY-GEM"), _yes(recs, "PLANET-GEM"))
                                else "")) if inp["event_date"] else "Unverified",
        "Skull/Jesuit": "; ".join(sym) or "None",
        "Moon": astro_tags["event_moon"]["phase"] if "event_moon" in astro_tags else "Unverified",
        "Zodiac": astro_tags.get("event_zodiac", "Unverified"),
        "Prime Cluster": "Yes" if cls["prime_cluster"] else "No",
        "Triple Prime": "Yes" if cls["triple_prime_sync"] else "No",
        "Control (≥ actual)": f"{ctl['alternatives_at_least_as_many']} of {ctl['alternatives']}",
        "Decode status": res["decode_status"],
        "Registry": res["registry_version"],
    }
    return row


def to_markdown(result: dict) -> str:
    inp = result["input"]
    stat = inp["stat_category"] or "stat"
    move = f"{inp['current']} → {inp['milestone']}" if inp["current"] is not None else str(inp["milestone"])
    matchup = " vs ".join(x for x in (inp["team"], inp["opponent"]) if x) or "—"
    lines = [
        f"# Scriptmatria decode — {result['decode_id']}",
        "",
        f"**{result['mode']}** · registry v{result['registry_version']} · input sha256 `{result['input_sha256'][:12]}`"
        + (f" · version {result['frozen']['version']}" if "frozen" in result else "")
        + (f" (amends `{result['frozen']['amends']}`)" if result.get("frozen", {}).get("amends") else ""),
        "",
        f"**Decode status:** {result['decode_status']}",
        "",
        "| Player | Stat | Milestone | Jersey | Event | Matchup |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| {inp['player']} | {stat}{' (' + inp['milestone_type'] + ')' if inp['milestone_type'] else ''} "
        f"| {move} | {inp['jersey'] if inp['jersey'] is not None else '—'} "
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
    if result["classification"]["pending_hits"]:
        lines += ["## Source pending", "",
                  "These hits use supplied numbers with no phrase and cipher. They are not counted "
                  "until the source is verified:", ""]
        lines += [f"- {h}" for h in result["classification"]["pending_hits"]]
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


def _dump(result: dict) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def versions(out: Path, decode_id: str) -> list[Path]:
    """Frozen JSON reports for a decode, oldest first: <id>.json, <id>.v2.json, ..."""
    base = _safe(decode_id)
    found = [(1, out / f"{base}.json")] if (out / f"{base}.json").exists() else []
    for p in out.glob(f"{base}.v*.json"):
        tail = p.name[len(base) + 2:-5]
        if tail.isdigit():
            found.append((int(tail), p))
    return [p for _, p in sorted(found)]


def write(results: list[dict], out_dir: str | Path) -> list[tuple[str, Path]]:
    """Freeze each decode. Existing reports are never overwritten: identical output is
    left alone, and changed output becomes an amendment (<id>.vN). grid.csv,
    summary.csv and decodes.xlsx are views of this run and are regenerated."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    events: list[tuple[str, Path]] = []
    ledger_lines = []
    for res in results:
        existing = versions(out, res["decode_id"])
        if existing:
            prior = json.loads(existing[-1].read_text(encoding="utf-8"))
            prior_version = prior.pop("frozen", {}).get("version", len(existing))
            if prior == res:
                events.append((f"unchanged (frozen v{prior_version})", existing[-1]))
                continue
            version, amends = prior_version + 1, existing[-1].name
            base = out / f"{_safe(res['decode_id'])}.v{version}"
        else:
            version, amends = 1, None
            base = out / _safe(res["decode_id"])
        frozen = {**res, "frozen": {"version": version, "amends": amends}}
        js, md = Path(f"{base}.json"), Path(f"{base}.md")
        text = _dump(frozen)
        js.write_text(text, encoding="utf-8")
        md.write_text(to_markdown(frozen), encoding="utf-8")
        events.append((f"frozen v{version}" + (f" (amends {amends})" if amends else ""), js))
        ledger_lines.append(json.dumps({
            "decode_id": res["decode_id"], "version": version, "file": js.name, "amends": amends,
            "input_sha256": res["input_sha256"], "registry_version": res["registry_version"],
            "report_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, sort_keys=True))
    if ledger_lines:
        with (out / "freeze_ledger.jsonl").open("a", encoding="utf-8") as f:
            f.write("\n".join(ledger_lines) + "\n")

    (out / "grid.csv").write_text(to_csv(results), encoding="utf-8")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(SUMMARY_COLUMNS)
    for res in results:
        w.writerow([res["summary"][c] for c in SUMMARY_COLUMNS])
    (out / "summary.csv").write_text(buf.getvalue(), encoding="utf-8")
    grid_rows = [["Decode ID", "Test", "Finding", "Result"]] + [
        [res["decode_id"], g["test"], g["finding"], g["result"]] for res in results for g in res["grid"]]
    evidence = [["Decode ID", "Rule", "Hit", "Source verified", "Family", "Source", "Cipher",
                 "Value", "Computation"]] + [
        [res["decode_id"], r["rule_id"], r["hit"], r["source_verified"], r["family"], r["label"],
         r["cipher"] or "", r["value"] if r["value"] is not None else "", r["computation"]]
        for res in results for r in res["records"] if r["hit"]]
    xlsx.write(out / "decodes.xlsx", [
        ("Summary", [SUMMARY_COLUMNS] + [[res["summary"][c] for c in SUMMARY_COLUMNS] for res in results]),
        ("Grid", grid_rows),
        ("Evidence", evidence),
    ])
    for name in ("grid.csv", "summary.csv", "decodes.xlsx"):
        events.append(("view", out / name))
    return events

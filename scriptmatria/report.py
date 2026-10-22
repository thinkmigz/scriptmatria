"""Decode report (rulebook §9–§10): canonical JSON, Markdown, Excel-ready CSV and
the comparison ledger, all built from the same evidence records so they
reconcile exactly. Decode content is deterministic; the only volatile field
(created_at_utc) lives in freeze_ledger.jsonl.
"""

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__, astro, dates, gematria, inputs, phrases, primes, rules, validator, xlsx
from .rules import INVALID, NO_HIT, QC, QS, RULE_CONFLICT, SN, UNVERIFIED

STATUS_LABEL = {QS: "✓ Qualified (structural)", QC: "✓ Qualified (calendar)", SN: "◆ Symbolic note",
                NO_HIT: "No hit", INVALID: "✗ Invalid", UNVERIFIED: "Unverified", RULE_CONFLICT: "⚠ Rule conflict"}
RULE_ORDER = ["M-PRIME", "M-REVPRIME", "PIGR-A", "PIGR-B", "OPP-TYPEA", "SELF-TYPEA", "BIRTH-SPAN-EXACT",
              "DN-EXACT", "DAY-GEM", "PLANET-GEM", "JERSEY-EXACT", "KW-EXACT"]
GRID_COLUMNS = ["Rule", "LHS", "RHS", "Derivation", "Status", "Source"]


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _overlays(req: inputs.DecodeRequest) -> dict:
    out = {}
    if "moon" in req.overlays:
        if req.event_start_local:
            out["moon"] = astro.moon_phase(req.event_date, req.timezone, req.event_start_local)
        else:
            out["moon"] = {"status": UNVERIFIED, "reason": "event_start_local is required for the lunar phase"}
    if "zodiac" in req.overlays:
        out["zodiac"] = {"event_sun_sign": astro.zodiac_sign(req.event_date),
                         "birth_sun_sign": astro.zodiac_sign(req.birth_date) if req.birth_date else None,
                         "treatment": "NOTE only"}
    return out


def _grid(records: list[dict]) -> list[dict]:
    """Every hit and every non-comparison gets its own row; misses are summarized per rule."""
    rows = []
    for rid in RULE_ORDER:
        recs = [r for r in records if r["rule_id"] == rid]
        if not recs:
            continue
        for r in recs:
            if r["status"] != NO_HIT:
                rows.append({"Rule": rid, "LHS": r["left_source"], "RHS": r["right_source"],
                             "Derivation": r["computation"], "Status": r["status"], "Source": r["source_id"]})
        misses = [r for r in recs if r["status"] == NO_HIT]
        if misses and len(misses) == len(recs) and len(misses) == 1:
            r = misses[0]
            rows.append({"Rule": rid, "LHS": r["left_source"], "RHS": r["right_source"],
                         "Derivation": r["computation"], "Status": NO_HIT, "Source": r["source_id"]})
        elif misses:
            rows.append({"Rule": rid, "LHS": misses[0]["left_source"], "RHS": f"{len(misses)} other value(s)",
                         "Derivation": "no exact match", "Status": NO_HIT, "Source": "ledger"})
    return rows


def _gematria_table(req: inputs.DecodeRequest, phrase_reg: dict) -> list[dict]:
    rows = []
    if phrase_reg.get("league") == req.league and req.phrase_registry_version == phrase_reg.get("phrase_registry_version"):
        for side, tid in (("team", req.team_id), ("opponent", req.opponent_id)):
            for p in phrases.team_phrases(phrase_reg, tid):
                kind = "/".join((p.kind, *p.aliases))
                rows.append({"subject": f"{side} {tid}", "phrase": p.text, "kind": kind, **gematria.all_values(p.text)})
    for kind, word in (("weekday", dates.weekday(req.event_date)), ("planet", dates.ruling_planet(req.event_date))):
        rows.append({"subject": "calendar", "phrase": word, "kind": kind, **gematria.all_values(word)})
    return rows


def _stat_standing(stat_code: str) -> str:
    return inputs.STAT_CODES.get(stat_code, "unregistered")


def _status(records: list[dict], stat_code: str) -> str:
    problems = []
    if _stat_standing(stat_code) != "approved":
        problems.append(f"{_stat_standing(stat_code)} stat")
    for status, label in ((RULE_CONFLICT, "rule conflict"), (INVALID, "invalid sources"),
                          (UNVERIFIED, "unverified inputs")):
        n = sum(1 for r in records if r["status"] == status)
        if n:
            problems.append(f"{n} {label}")
    return "Complete" if not problems else "Partial: " + ", ".join(problems)


def _note(req: inputs.DecodeRequest, records: list[dict], cls: dict) -> str:
    def names(status):
        seen = []
        for r in records:
            if r["status"] == status:
                label = r["rule_id"] if r["rule_id"] in ("M-PRIME", "M-REVPRIME") else f"{r['rule_id']} ({r['right_source']})"
                if label not in seen:
                    seen.append(label)
        return seen
    standing = _stat_standing(req.stat_code)
    parts = [f"{req.player_name}: next {req.stat_code} #{req.milestone}"
             + ("" if standing == "approved" else f" ({standing} stat, outside the approved pilot)")]
    q = names(QS) + names(QC)
    parts.append(f"qualified alignments: {', '.join(q)}" if q else "no qualified alignments")
    s = names(SN)
    if s:
        parts.append(f"symbolic notes: {', '.join(s)}")
    parts.append(f"Triple Prime Sync {cls['triple_prime_sync'].replace('_', ' ').lower()}")
    return "; ".join(parts) + ". Descriptive only; not an outcome pick."


def decode(req: inputs.DecodeRequest, registry: dict, phrase_reg: dict) -> dict:
    records = rules.evaluate(req, registry, phrase_reg)
    cls = validator.classify(records)
    m = req.milestone
    snapshot = req.to_dict()
    start_utc = (datetime.combine(req.event_date, req.event_start_local, ZoneInfo(req.timezone))
                 .astimezone(timezone.utc).isoformat() if req.event_start_local else None)
    spans = dates.birthday_spans(req.birth_date, req.event_date) if req.birth_date else None
    result = {
        "decode_id": req.decode_id,
        "mode": registry["mode"],
        "versions": {
            "engine_version": __version__,
            "rulebook_version": registry["rulebook_version"],
            "rule_registry_version": registry["registry_version"],
            "phrase_registry_version": phrase_reg.get("phrase_registry_version"),
            "input_schema_version": inputs.INPUT_SCHEMA_VERSION,
        },
        "seal": {
            "input_sha256": _sha(snapshot),
            "rule_registry_sha256": _sha(registry),
            "phrase_registry_sha256": _sha(phrase_reg),
            "event_id": req.event_id,
            "event_start_utc": start_utc,
        },
        "input": snapshot,
        "milestone_card": {
            "current_count": req.current_count, "target_count": m, "milestone_id": req.milestone_id,
            "M-INDEX": primes.prime_index(m), "reverse_digits": primes.reverse_digits(m),
        },
        "date_card": {**dates.date_numerology(req.event_date), "weekday": dates.weekday(req.event_date),
                      "ruling_planet": dates.ruling_planet(req.event_date)},
        "birthday_card": ({k: (UNVERIFIED if v is None else v) for k, v in spans.items()}
                          | {"birth_mmdd": req.birth_date.strftime("%m/%d")}) if spans else UNVERIFIED,
        "gematria_table": _gematria_table(req, phrase_reg),
        "grid": _grid(records),
        "classification": cls,
        "overlays": _overlays(req),
        "decode_status": _status(records, req.stat_code),
        "ledger_summary": validator.ledger(records),
        "records": records,
    }
    result["ritual_note"] = _note(req, records, cls)
    result["summary"] = summary_row(result)
    return result


SUMMARY_COLUMNS = [
    "Decode ID", "Event ID", "Event date", "League", "Player ID", "Player", "Team", "Opponent", "Stat",
    "Current", "Target", "Count as of", "Prime index", "Reverse prime", "PIGR-A", "PIGR-B", "Opponent Type A",
    "Self Type A", "Birthday match", "Date match", "Weekday / planet", "Jersey", "Keywords", "Moon", "Zodiac",
    "Prime Cluster", "Triple Prime", "Attempted", "Qualified", "Symbolic", "Invalid", "Unverified",
    "Decode status", "Rule registry",
]


def _lane(records: list[dict], rid: str) -> str:
    rs = [r for r in records if r["rule_id"] == rid]
    if not rs:
        return "—"
    hits = [r for r in rs if r["status"] in (QS, QC, SN)]
    if hits:
        return "; ".join(r["right_source"] for r in hits)
    for s in (RULE_CONFLICT, INVALID, UNVERIFIED):
        if all(r["status"] in (s, NO_HIT) for r in rs) and any(r["status"] == s for r in rs):
            return s
    return "No"


def summary_row(res: dict) -> dict:
    inp, recs, cls, ov = res["input"], res["records"], res["classification"], res["overlays"]
    c = cls["counts"]
    moon = ov.get("moon")
    return {
        "Decode ID": res["decode_id"], "Event ID": inp["event_id"], "Event date": inp["event_date_local"],
        "League": inp["league"], "Player ID": inp["player_id"], "Player": inp["player_name"],
        "Team": inp["team_id"], "Opponent": inp["opponent_id"], "Stat": f"{inp['stat_code']} ({inp['stat_scope']}, {_stat_standing(inp['stat_code'])})",
        "Current": inp["current_count"], "Target": inp["target_count"], "Count as of": inp["current_count_as_of"],
        "Prime index": res["milestone_card"]["M-INDEX"] or "Not prime",
        "Reverse prime": _lane(recs, "M-REVPRIME"), "PIGR-A": _lane(recs, "PIGR-A"), "PIGR-B": _lane(recs, "PIGR-B"),
        "Opponent Type A": _lane(recs, "OPP-TYPEA"), "Self Type A": _lane(recs, "SELF-TYPEA"),
        "Birthday match": _lane(recs, "BIRTH-SPAN-EXACT"), "Date match": _lane(recs, "DN-EXACT"),
        "Weekday / planet": f"{res['date_card']['weekday']} / {res['date_card']['ruling_planet']}"
                            + "".join(f"; {r['right_source']}" for r in recs
                                      if r["rule_id"] in ("DAY-GEM", "PLANET-GEM") and r["status"] == QC),
        "Jersey": _lane(recs, "JERSEY-EXACT"),
        "Keywords": _lane(recs, "KW-EXACT") if "keywords" in inp["overlays"] else "off",
        "Moon": (moon.get("phase") or moon.get("status")) if moon else "off",
        "Zodiac": ov["zodiac"]["event_sun_sign"] if "zodiac" in ov else "off",
        "Prime Cluster": cls["prime_cluster"] + (f" ({cls['prime_cluster_flag']})" if cls["prime_cluster_flag"] else ""),
        "Triple Prime": cls["triple_prime_sync"],
        "Attempted": c["attempted"], "Qualified": c["qualified_structural"] + c["qualified_calendar"],
        "Symbolic": c["symbolic_notes"], "Invalid": c["invalid"], "Unverified": c["unverified"],
        "Decode status": res["decode_status"], "Rule registry": res["versions"]["rule_registry_version"],
    }


def _md_table(headers: list[str], rows: list[list]) -> list[str]:
    cell = lambda v: str(v).replace("|", "/")  # noqa: E731
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(cell(v) for v in row) + " |" for row in rows)]


def to_markdown(res: dict) -> str:
    inp, cls, v, seal = res["input"], res["classification"], res["versions"], res["seal"]
    frozen = res.get("frozen", {})
    lines = [f"# Zilla 3.0 decode — {res['decode_id']}", "",
             f"**{res['mode']}** · {res['decode_status']}"
             + (f" · version {frozen['version']}" if frozen else "")
             + (f" (amends `{frozen['amends']}`)" if frozen.get("amends") else ""), ""]

    lines += ["## 1. Input summary", ""]
    lines += _md_table(["Field", "Value", "Source"], [
        ["Event", f"{inp['event_id']} · {inp['event_date_local']} · {inp['timezone']}"
                  + (f" · start {inp['event_start_local']}" if inp["event_start_local"] else ""), "snapshot"],
        ["Matchup", f"{inp['team_id']} vs {inp['opponent_id']} ({inp['league']})", "snapshot"],
        ["Player", f"{inp['player_name']} ({inp['player_id']})", "snapshot"],
        ["Stat", f"{inp['stat_code']} ({_stat_standing(inp['stat_code'])}) · {inp['stat_scope']} · "
                 f"{inp['current_count']} → {inp['target_count']}",
         f"{inp['current_count_source']} (as of {inp['current_count_as_of']})"],
        ["Birth date", inp["birth_date"] or UNVERIFIED, inp["birth_date_source"] or "—"],
        ["Jersey", inp["jersey"] if inp["jersey"] is not None else UNVERIFIED, inp["jersey_source"] or "—"],
        ["Overlays", ", ".join(inp["overlays"]) or "none requested", "snapshot"],
        ["Attestation", inp["operator_attestation"], "operator"],
    ])

    mc, dc = res["milestone_card"], res["date_card"]
    lines += ["", "## 2. Date and birthday card", ""]
    lines += _md_table(["DN1", "DN2", "DN3", "DN4", "DN5", "DOY", "Days left", "Weekday / ruler"],
                       [[dc["DN1"], dc["DN2"], dc["DN3"], dc["DN4"], dc["DN5"], dc["DOY"], dc["DAYS_LEFT"],
                         f"{dc['weekday']} / {dc['ruling_planet']}"]])
    lines.append("")
    bc = res["birthday_card"]
    if isinstance(bc, dict):
        lines += _md_table(["Lifetime days", "Age (y m d)", "Since birthday", "Until birthday", "Weeks", "Birth MM/DD"],
                           [[bc["total_days"], f"{bc['age_years']} {bc['ymd_months']} {bc['ymd_days']}",
                             bc["days_since_birthday"], bc["days_until_birthday"], bc["total_weeks"], bc["birth_mmdd"]]])
    else:
        lines.append("Birthday card: UNVERIFIED (birth date not supplied)")
    lines += ["", f"Milestone {mc['current_count']} → **{mc['target_count']}** · M-INDEX "
              f"{mc['M-INDEX'] if mc['M-INDEX'] else 'n/a (not prime)'} · reverse_digits {mc['reverse_digits']}", ""]

    lines += ["## 3. Gematria table", ""]
    lines += _md_table(["Subject", "Phrase", "Kind", "EO", "FR", "RO", "RR", "CH"],
                       [[g["subject"], g["phrase"], g["kind"], g["EO"], g["FR"], g["RO"], g["RR"], g["CH"]]
                        for g in res["gematria_table"]])

    lines += ["", "## 4. Milestone relationship grid", ""]
    lines += _md_table(GRID_COLUMNS, [[r["Rule"], r["LHS"], r["RHS"], r["Derivation"], STATUS_LABEL[r["Status"]],
                                       r["Source"]] for r in res["grid"]])

    lines += ["", "## 5. Prime cluster and Triple Prime", "",
              f"- Prime observations: {cls['prime_observations']} from {', '.join(cls['prime_families']) or 'none'}",
              f"- Prime Cluster: **{cls['prime_cluster']}**"
              + (f" — {cls['prime_cluster_flag']}" if cls["prime_cluster_flag"] else ""),
              f"- Triple Prime Sync: **{cls['triple_prime_sync']}** — {cls['triple_prime_reason']}"]
    deps = [d for d in cls["dependency_groups"] if d["dependent"]]
    if deps:
        lines += ["- Dependent restatements (one number, not independent evidence):"]
        lines += [f"  - **{d['number']}**: {', '.join(d['hits'])}" for d in deps]

    lines += ["", "## 6. Symbolic overlay", ""]
    notes = [r for r in res["records"] if r["status"] == SN]
    lines += [f"- {r['rule_id']}: {r['computation']}" for r in notes] or ["- No symbolic notes."]
    ov = res["overlays"]
    if "moon" in ov:
        moon = ov["moon"]
        lines.append(f"- Moon (NOTE): {moon['phase']} · age {moon['moon_age_days']} d at {moon['measured_at']}"
                     + (f" · exact {moon['principal_phase_utc']}" if moon["principal_phase_utc"] else "")
                     if "phase" in moon else f"- Moon: UNVERIFIED — {moon['reason']}")
    if "zodiac" in ov:
        z = ov["zodiac"]
        lines.append(f"- Zodiac (NOTE): event in {z['event_sun_sign']} season"
                     + (f"; born {z['birth_sun_sign']}" if z["birth_sun_sign"] else ""))

    c = cls["counts"]
    lines += ["", "## 7. Audit block", ""]
    lines += _md_table(["Attempted", "Qualified structural", "Qualified calendar", "Symbolic", "No hit",
                        "Invalid", "Unverified", "Rule conflict"],
                       [[c["attempted"], c["qualified_structural"], c["qualified_calendar"], c["symbolic_notes"],
                         c["no_hit"], c["invalid"], c["unverified"], c["rule_conflict"]]])
    lines += ["", f"Versions: engine {v['engine_version']} · rulebook {v['rulebook_version']} · rules "
              f"{v['rule_registry_version']} · phrases {v['phrase_registry_version']} · input schema "
              f"{v['input_schema_version']}",
              f"Hashes: input `{seal['input_sha256'][:16]}` · rules `{seal['rule_registry_sha256'][:16]}` · "
              f"phrases `{seal['phrase_registry_sha256'][:16]}`",
              f"Event start (UTC): {seal['event_start_utc'] or 'not supplied'}"]
    off = [o for o in inputs.OVERLAYS if o not in inp["overlays"]]
    if off:
        lines.append(f"Overlays not requested: {', '.join(off)}")

    lines += ["", "## 8. Ritual note", "", res["ritual_note"], ""]
    return "\n".join(lines)


def grid_csv(res: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["Decode ID", *GRID_COLUMNS])
    for r in res["grid"]:
        w.writerow([res["decode_id"], *(r[c] for c in GRID_COLUMNS)])
    return buf.getvalue()


def ledger_jsonl(res: dict) -> str:
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in res["records"])


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
    """Seal each decode. A sealed report is never overwritten: identical content is
    left alone and changed content becomes a linked revision (<id>.vN)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    events: list[tuple[str, Path]] = []
    now = datetime.now(timezone.utc)
    seals = []
    for res in results:
        existing = versions(out, res["decode_id"])
        if existing:
            prior = json.loads(existing[-1].read_text(encoding="utf-8"))
            prior_version = prior.pop("frozen", {}).get("version", len(existing))
            if prior == res:
                events.append((f"unchanged (sealed v{prior_version})", existing[-1]))
                continue
            version, amends = prior_version + 1, existing[-1].name
            base = f"{_safe(res['decode_id'])}.v{version}"
        else:
            version, amends, base = 1, None, _safe(res["decode_id"])
        frozen = {**res, "frozen": {"version": version, "amends": amends}}
        text = _dump(frozen)
        (out / f"{base}.json").write_text(text, encoding="utf-8")
        (out / f"{base}.md").write_text(to_markdown(frozen), encoding="utf-8")
        (out / f"{base}.csv").write_text(grid_csv(frozen), encoding="utf-8")
        (out / f"{base}.ledger.jsonl").write_text(ledger_jsonl(frozen), encoding="utf-8")
        events.append((f"sealed v{version}" + (f" (amends {amends})" if amends else ""), out / f"{base}.json"))
        start = res["seal"]["event_start_utc"]
        seals.append({
            "decode_id": res["decode_id"], "version": version, "file": f"{base}.json", "amends": amends,
            **{k: res["seal"][k] for k in ("input_sha256", "rule_registry_sha256", "phrase_registry_sha256")},
            "decode_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "event_start_utc": start,
            "created_at_utc": now.isoformat(timespec="seconds"),
            "sealed_before_event_start": (now < datetime.fromisoformat(start)) if start else None,
        })
    if seals:
        with (out / "freeze_ledger.jsonl").open("a", encoding="utf-8") as f:
            f.writelines(json.dumps(s, sort_keys=True) + "\n" for s in seals)

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(SUMMARY_COLUMNS)
    for res in results:
        w.writerow([res["summary"][c] for c in SUMMARY_COLUMNS])
    (out / "summary.csv").write_text(buf.getvalue(), encoding="utf-8")
    xlsx.write(out / "decodes.xlsx", [
        ("Summary", [SUMMARY_COLUMNS] + [[res["summary"][c] for c in SUMMARY_COLUMNS] for res in results]),
        ("Relationships", [["Decode ID", *GRID_COLUMNS]] + [[res["decode_id"], *(r[c] for c in GRID_COLUMNS)]
                                                            for res in results for r in res["grid"]]),
        ("Evidence", [["Decode ID", "Rule", "Status", "Family", "LHS", "RHS", "Cipher", "Value", "Computation"]] + [
            [res["decode_id"], r["rule_id"], r["status"], r["family"], r["left_source"], r["right_source"],
             r["cipher"] or "", r["value"], r["computation"]]
            for res in results for r in res["records"] if r["status"] != NO_HIT]),
    ])
    events += [("view", out / "summary.csv"), ("view", out / "decodes.xlsx")]
    return events

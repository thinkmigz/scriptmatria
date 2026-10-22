"""Post-event grading (rulebook §10). Grades go to an append-only ledger and never
modify a sealed decode. A stat that cannot be reliably graded is UNRESOLVED."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .report import versions

OUTCOMES = ("achieved", "not_achieved", "unresolved")


class GradeError(ValueError):
    pass


def grade(out_dir: str | Path, decode_id: str, outcome: str, actual: int | None = None,
          note: str | None = None, correction: bool = False) -> dict:
    if outcome not in OUTCOMES:
        raise GradeError(f"outcome must be one of {', '.join(OUTCOMES)}")
    out = Path(out_dir)
    sealed = versions(out, decode_id)
    if not sealed:
        raise GradeError(f"no sealed decode '{decode_id}' in {out}")
    latest = sealed[-1]
    ledger = out / "outcomes.jsonl"
    prior = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
             if line.strip()] if ledger.exists() else []
    if any(p["decode_id"] == decode_id for p in prior) and not correction:
        raise GradeError(f"'{decode_id}' is already graded; pass --correction to record a correction")
    entry = {
        "decode_id": decode_id,
        "graded_file": latest.name,
        "decode_sha256": hashlib.sha256(latest.read_bytes()).hexdigest(),
        "outcome": outcome.upper(),
        "actual_value": actual,
        "note": note,
        "correction": correction,
        "graded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry

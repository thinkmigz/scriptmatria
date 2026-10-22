"""Step 9/10: record outcomes after the event. Grades go to an append-only ledger
and never modify a frozen decode."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .report import versions


class GradeError(ValueError):
    pass


def grade(out_dir: str | Path, decode_id: str, achieved: bool, actual: int | None = None,
          note: str | None = None, correction: bool = False) -> dict:
    out = Path(out_dir)
    frozen = versions(out, decode_id)
    if not frozen:
        raise GradeError(f"no frozen decode '{decode_id}' in {out}")
    latest = frozen[-1]
    ledger = out / "outcomes.jsonl"
    prior = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
             if line.strip()] if ledger.exists() else []
    if any(p["decode_id"] == decode_id for p in prior) and not correction:
        raise GradeError(f"'{decode_id}' is already graded; pass --correction to record a correction")
    entry = {
        "decode_id": decode_id,
        "graded_file": latest.name,
        "report_sha256": hashlib.sha256(latest.read_bytes()).hexdigest(),
        "achieved": achieved,
        "actual_value": actual,
        "note": note,
        "correction": correction,
        "graded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry

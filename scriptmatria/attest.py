"""Operator sign-off for adapter drafts (rulebook §3). Turns a draft into an
attested input snapshot only after checking it was not altered since it was
fetched, and records who signed it and when."""

import json
from datetime import datetime, timezone
from pathlib import Path

from . import inputs
from .adapters.mlb_statsapi import content_hash


class AttestError(ValueError):
    pass


def attest(draft_path: str | Path, by: str, out_path: str | Path, *, allow_edits: bool = False,
           now: datetime | None = None) -> dict:
    by = (by or "").strip()
    if not by:
        raise AttestError("--by is required: name the person signing the snapshot")
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    if not draft.get("draft"):
        raise AttestError(f"{draft_path} is not an adapter draft")
    out = Path(out_path)
    if out.exists():
        raise AttestError(f"{out} already exists; attested snapshots are never overwritten")

    body = {"decodes": draft["decodes"], "players": draft.get("players", [])}
    edited = content_hash(body) != draft["content_sha256"]
    if edited and not allow_edits:
        raise AttestError("draft was modified after it was fetched; re-fetch, or attest with --allow-edits "
                          "to record the edit")
    signed_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    adapter = f"{draft['adapter']['id']}@{draft['adapter']['version']}"
    statement = (f"{by}; reviewed {adapter} draft {draft['content_sha256'][:12]} fetched "
                 f"{draft['fetched_at_utc']}; attested {signed_at}"
                 + ("; OPERATOR EDITED THE DRAFT" if edited else ""))
    decodes = [{**d, "operator_attestation": statement} for d in draft["decodes"]]
    for d in decodes:  # every row must pass the input lock before anything is written
        inputs.parse_request(d)

    record = {
        "attestation": {"by": by, "signed_at_utc": signed_at, "adapter": adapter,
                        "draft_sha256": draft["content_sha256"], "fetched_at_utc": draft["fetched_at_utc"],
                        "operator_edited": edited, "selection": draft.get("selection")},
        "decodes": decodes,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record

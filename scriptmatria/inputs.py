"""Load decode requests from local JSON or CSV files.

Missing data is never inferred: a field that is not supplied stays None and the
rules that need it report "Unverified".
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ENTITIES = ("opponent", "team", "player", "event")


class InputError(ValueError):
    pass


@dataclass(frozen=True)
class Phrase:
    entity: str
    phrase: str


@dataclass(frozen=True)
class SuppliedValue:
    entity: str
    label: str
    value: int


@dataclass(frozen=True)
class DecodeRequest:
    id: str
    player: str
    milestone: int
    stat_category: str | None = None
    current: int | None = None
    birthday: date | None = None
    jersey: int | None = None
    event_date: date | None = None
    team: str | None = None
    opponent: str | None = None
    phrases: tuple[Phrase, ...] = field(default_factory=tuple)
    values: tuple[SuppliedValue, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "player": self.player,
            "milestone": self.milestone,
            "stat_category": self.stat_category,
            "current": self.current,
            "birthday": self.birthday.isoformat() if self.birthday else None,
            "jersey": self.jersey,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "team": self.team,
            "opponent": self.opponent,
            "phrases": [{"entity": p.entity, "phrase": p.phrase} for p in self.phrases],
            "values": [{"entity": v.entity, "label": v.label, "value": v.value} for v in self.values],
        }


def _date(raw, name, errors):
    if raw in (None, ""):
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        errors.append(f"{name}: '{raw}' is not an ISO date (YYYY-MM-DD)")
        return None


def _int(raw, name, errors, required=False):
    if raw in (None, ""):
        if required:
            errors.append(f"{name}: required")
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        errors.append(f"{name}: '{raw}' is not a whole number")
        return None
    if n < 0:
        errors.append(f"{name}: must not be negative")
    return n


def _entity(raw, where, errors):
    if raw not in ENTITIES:
        errors.append(f"{where}: entity '{raw}' must be one of {', '.join(ENTITIES)}")
    return raw


def parse_request(raw: dict) -> DecodeRequest:
    errors: list[str] = []
    rid = str(raw.get("id") or "").strip()
    player = str(raw.get("player") or "").strip()
    if not rid:
        errors.append("id: required")
    if not player:
        errors.append("player: required")
    milestone = _int(raw.get("milestone"), "milestone", errors, required=True)
    if milestone == 0:
        errors.append("milestone: must be positive")

    phrases = []
    for i, p in enumerate(raw.get("phrases") or []):
        text = str(p.get("phrase") or "").strip()
        if not text:
            errors.append(f"phrases[{i}]: phrase is empty")
        phrases.append(Phrase(_entity(p.get("entity"), f"phrases[{i}]", errors), text))

    values = []
    for i, v in enumerate(raw.get("values") or []):
        label = str(v.get("label") or "").strip()
        if not label:
            errors.append(f"values[{i}]: label is required (where did this number come from?)")
        n = _int(v.get("value"), f"values[{i}].value", errors, required=True)
        values.append(SuppliedValue(_entity(v.get("entity"), f"values[{i}]", errors), label, n or 0))

    req = DecodeRequest(
        id=rid,
        player=player,
        milestone=milestone or 0,
        stat_category=raw.get("stat_category") or None,
        current=_int(raw.get("current"), "current", errors),
        birthday=_date(raw.get("birthday"), "birthday", errors),
        jersey=_int(raw.get("jersey"), "jersey", errors),
        event_date=_date(raw.get("event_date"), "event_date", errors),
        team=raw.get("team") or None,
        opponent=raw.get("opponent") or None,
        phrases=tuple(phrases),
        values=tuple(values),
    )
    if req.birthday and req.event_date and req.event_date < req.birthday:
        errors.append("event_date: precedes birthday")
    if errors:
        raise InputError(f"decode '{rid or '?'}': " + "; ".join(errors))
    return req


def _csv_row(row: dict) -> dict:
    """CSV columns mirror the JSON keys. `phrases` is 'entity:phrase|entity:phrase',
    `values` is 'entity:label=value|...'."""
    out = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
    phrases = []
    for item in filter(None, (out.pop("phrases", "") or "").split("|")):
        entity, _, text = item.partition(":")
        phrases.append({"entity": entity.strip(), "phrase": text.strip()})
    values = []
    for item in filter(None, (out.pop("values", "") or "").split("|")):
        entity, _, rest = item.partition(":")
        label, _, num = rest.rpartition("=")
        values.append({"entity": entity.strip(), "label": label.strip(), "value": num.strip()})
    out["phrases"], out["values"] = phrases, values
    return out


def load(path: str | Path) -> list[DecodeRequest]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            raws = [_csv_row(r) for r in csv.DictReader(f)]
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        raws = data["decodes"] if isinstance(data, dict) and "decodes" in data else data
        if isinstance(raws, dict):
            raws = [raws]
    requests = [parse_request(r) for r in raws]
    ids = [r.id for r in requests]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise InputError(f"duplicate decode ids: {', '.join(dupes)}")
    return requests

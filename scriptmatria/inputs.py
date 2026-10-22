"""PlayerMilestoneInput v0.1: load and validate operator-entered decode snapshots
from local JSON or CSV (rulebook §3).

Missing optional data is never inferred: it stays None and the affected lanes
report UNVERIFIED. Contradictory data fails the input lock.
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

INPUT_SCHEMA_VERSION = "0.1"
STAT_SCOPES_IMPLEMENTED = ("career",)
STAT_CODES = {"HR": "approved", "H": "trial", "RBI": "trial"}  # mirrors registry pilot_stats
APPROVED_ADAPTERS = ("mlb-statsapi@0.1.0",)  # mirrors registry approved_adapters
OVERLAYS = ("moon", "zodiac", "keywords")
REQUIRED = ("event_id", "event_date_local", "timezone", "league", "player_id", "player_name",
            "team_id", "opponent_id", "stat_code", "stat_scope", "current_count",
            "current_count_as_of", "current_count_source", "phrase_registry_version",
            "operator_attestation")


class InputError(ValueError):
    pass


@dataclass(frozen=True)
class RequestedPhrase:
    team_id: str
    phrase: str


@dataclass(frozen=True)
class DecodeRequest:
    event_id: str
    event_date: date
    timezone: str
    league: str
    player_id: str
    player_name: str
    team_id: str
    opponent_id: str
    stat_code: str
    stat_scope: str
    current_count: int
    current_count_as_of: str
    current_count_source: str
    phrase_registry_version: str
    operator_attestation: str
    birth_date: date | None = None
    birth_date_source: str | None = None
    jersey: int | None = None
    jersey_source: str | None = None
    jersey_effective_date: date | None = None
    event_start_local: time | None = None
    adapter: str | None = None
    overlays: tuple[str, ...] = ()
    requested_phrases: tuple[RequestedPhrase, ...] = field(default_factory=tuple)

    @property
    def milestone(self) -> int:
        return self.current_count + 1

    @property
    def decode_id(self) -> str:
        return f"{self.event_id}_{self.player_id}_{self.stat_code}"

    @property
    def milestone_id(self) -> str:
        return f"{self.stat_code}:{self.stat_scope}:{self.milestone}"

    def to_dict(self) -> dict:
        iso = lambda d: d.isoformat() if d else None  # noqa: E731
        return {
            "input_schema_version": INPUT_SCHEMA_VERSION,
            "event_id": self.event_id,
            "event_date_local": iso(self.event_date),
            "timezone": self.timezone,
            "league": self.league,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "team_id": self.team_id,
            "opponent_id": self.opponent_id,
            "stat_code": self.stat_code,
            "stat_scope": self.stat_scope,
            "current_count": self.current_count,
            "current_count_as_of": self.current_count_as_of,
            "current_count_source": self.current_count_source,
            "target_count": self.milestone,
            "phrase_registry_version": self.phrase_registry_version,
            "operator_attestation": self.operator_attestation,
            "birth_date": iso(self.birth_date),
            "birth_date_source": self.birth_date_source,
            "jersey": self.jersey,
            "jersey_source": self.jersey_source,
            "jersey_effective_date": iso(self.jersey_effective_date),
            "event_start_local": self.event_start_local.strftime("%H:%M") if self.event_start_local else None,
            "adapter": self.adapter,
            "overlays": list(self.overlays),
            "requested_phrases": [{"team_id": p.team_id, "phrase": p.phrase} for p in self.requested_phrases],
        }


def _text(raw, name, errors, required=False):
    v = raw.get(name)
    v = str(v).strip() if v not in (None, "") else None
    if required and not v:
        errors.append(f"{name}: required")
    return v


def _date(raw, name, errors, required=False):
    v = raw.get(name)
    if v in (None, ""):
        if required:
            errors.append(f"{name}: required")
        return None
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        errors.append(f"{name}: '{v}' is not an ISO date (YYYY-MM-DD)")
        return None


def _int(raw, name, errors, required=False):
    v = raw.get(name)
    if v in (None, ""):
        if required:
            errors.append(f"{name}: required")
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        errors.append(f"{name}: '{v}' is not a whole number")
        return None
    if n < 0:
        errors.append(f"{name}: must not be negative")
    return n


def _as_of(raw, errors) -> tuple[str | None, date | None]:
    v = _text(raw, "current_count_as_of", errors, required=True)
    if not v:
        return None, None
    try:
        return v, datetime.fromisoformat(v).date()
    except ValueError:
        errors.append(f"current_count_as_of: '{v}' is not an ISO date or timestamp")
        return None, None


def parse_request(raw: dict) -> DecodeRequest:
    errors: list[str] = []
    t = {k: _text(raw, k, errors, required=True) for k in
         ("event_id", "timezone", "league", "player_id", "player_name", "team_id", "opponent_id",
          "stat_code", "stat_scope", "current_count_source", "phrase_registry_version",
          "operator_attestation")}
    event_date = _date(raw, "event_date_local", errors, required=True)
    current = _int(raw, "current_count", errors, required=True)
    as_of_text, as_of_date = _as_of(raw, errors)

    if t["timezone"]:
        try:
            ZoneInfo(t["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            errors.append(f"timezone: '{t['timezone']}' is not an IANA timezone (e.g. America/New_York)")
    if t["stat_scope"] and t["stat_scope"] not in STAT_SCOPES_IMPLEMENTED:
        errors.append(f"stat_scope: '{t['stat_scope']}' is not implemented in v0.1 "
                      f"(supported: {', '.join(STAT_SCOPES_IMPLEMENTED)})")
    if t["stat_code"] and t["stat_code"] not in STAT_CODES:
        errors.append(f"stat_code: '{t['stat_code']}' is not registered (allowed: {', '.join(STAT_CODES)})")
    adapter = _text(raw, "adapter", errors)
    if adapter and adapter not in APPROVED_ADAPTERS:
        errors.append(f"adapter: '{adapter}' is not approved (approved: {', '.join(APPROVED_ADAPTERS)})")
    if t["team_id"] and t["team_id"] == t["opponent_id"]:
        errors.append("opponent_id: must differ from team_id")

    start = None
    if raw.get("event_start_local") not in (None, ""):
        try:
            start = time.fromisoformat(str(raw["event_start_local"]))
        except ValueError:
            errors.append(f"event_start_local: '{raw['event_start_local']}' is not a 24-hour time (HH:MM)")

    overlays = raw.get("overlays") or []
    if isinstance(overlays, str):
        overlays = [o for o in overlays.split("|") if o]
    for o in overlays:
        if o not in OVERLAYS:
            errors.append(f"overlays: '{o}' must be one of {', '.join(OVERLAYS)}")

    requested = []
    for i, p in enumerate(raw.get("requested_phrases") or []):
        tid, text = str(p.get("team_id") or "").strip(), str(p.get("phrase") or "").strip()
        if not tid or not text:
            errors.append(f"requested_phrases[{i}]: team_id and phrase are required")
        requested.append(RequestedPhrase(tid, text))

    birth = _date(raw, "birth_date", errors)
    jersey_eff = _date(raw, "jersey_effective_date", errors)
    # Contradictions fail the input lock rather than being silently resolved.
    if event_date:
        if birth and birth > event_date:
            errors.append("birth_date: after the event date")
        if as_of_date and as_of_date > event_date:
            errors.append("current_count_as_of: after the event date (a pre-event count is required)")
        if jersey_eff and jersey_eff > event_date:
            errors.append("jersey_effective_date: after the event date (jersey not in effect for this event)")

    jersey = _int(raw, "jersey", errors)
    if errors:
        raise InputError(f"decode '{t.get('event_id') or '?'}_{t.get('player_id') or '?'}': " + "; ".join(errors))
    return DecodeRequest(
        event_id=t["event_id"], event_date=event_date, timezone=t["timezone"], league=t["league"],
        player_id=t["player_id"], player_name=t["player_name"], team_id=t["team_id"],
        opponent_id=t["opponent_id"], stat_code=t["stat_code"], stat_scope=t["stat_scope"],
        current_count=current, current_count_as_of=as_of_text,
        current_count_source=t["current_count_source"],
        phrase_registry_version=t["phrase_registry_version"],
        operator_attestation=t["operator_attestation"],
        birth_date=birth, birth_date_source=_text(raw, "birth_date_source", errors),
        jersey=jersey, jersey_source=_text(raw, "jersey_source", errors),
        jersey_effective_date=jersey_eff, event_start_local=start, adapter=adapter,
        overlays=tuple(sorted(set(overlays))), requested_phrases=tuple(requested),
    )


def _csv_row(row: dict) -> dict:
    """CSV columns mirror the JSON keys. `overlays` is 'moon|zodiac',
    `requested_phrases` is 'TEAM_ID:phrase|TEAM_ID:phrase'."""
    out = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
    phrases = []
    for item in filter(None, (out.pop("requested_phrases", "") or "").split("|")):
        tid, _, text = item.partition(":")
        phrases.append({"team_id": tid.strip(), "phrase": text.strip()})
    out["requested_phrases"] = phrases
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
    ids = [r.decode_id for r in requests]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise InputError(f"duplicate decodes (event_id + player_id + stat_code): {', '.join(dupes)}")
    return requests

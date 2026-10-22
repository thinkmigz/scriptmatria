"""Rule engine. Each rule is a fixed comparison between the milestone M and the
source values of a decode. Every comparison is recorded, hit or not, so the
audit can show how many checks produced each match.
"""

import json
from dataclasses import dataclass
from importlib import resources

from . import dates, gematria, primes
from .inputs import DecodeRequest

GEMATRIA_FAMILY = {e: f"{e}_gematria" for e in ("opponent", "team", "player", "event")}
_UNSET = object()


REGISTRY_FILE = "rules_v2.json"


def load_registry(name: str = REGISTRY_FILE) -> dict:
    return json.loads(resources.files("scriptmatria.registry").joinpath(name).read_text("utf-8"))


@dataclass(frozen=True)
class Source:
    source_id: str
    family: str
    label: str
    value: int
    match_rule: str  # rule that compares this value directly with the milestone
    cipher: str | None = None
    phrase: str | None = None
    verified: bool = True  # False for supplied numbers not yet tied to a phrase and cipher


def build_sources(req: DecodeRequest) -> tuple[list[Source], dict[str, str]]:
    """All numbers a decode may compare against, plus why any group is unverified."""
    sources: list[Source] = []
    unverified: dict[str, str] = {}

    for p in req.phrases:
        rule = "TYPEA" if p.entity == "opponent" else "GEM-SELF"
        for code, v in gematria.all_values(p.phrase).items():
            sources.append(Source(f"{p.entity}:{p.phrase}:{code}", GEMATRIA_FAMILY[p.entity],
                                  f"{p.entity} '{p.phrase}' ({code})", v, rule, code, p.phrase))
    for sv in req.values:
        rule = "TYPEA" if sv.entity == "opponent" else "GEM-SELF"
        sources.append(Source(f"{sv.entity}:supplied:{sv.label}", GEMATRIA_FAMILY[sv.entity],
                              f"{sv.label} [{sv.entity}, supplied]", sv.value, rule, "supplied",
                              verified=False))
    if not any(s.family == "opponent_gematria" for s in sources):
        unverified["opponent_gematria"] = "no opponent phrases or values supplied"

    if req.jersey is not None:
        sources.append(Source("jersey", "jersey", "jersey", req.jersey, "JERSEY"))
    else:
        unverified["jersey"] = "jersey not supplied"

    if req.birthday and req.event_date:
        for key, v in dates.birthday_spans(req.birthday, req.event_date).items():
            sources.append(Source(f"birthday:{key}", "birthday", f"birthday {key}", v, "BDAY"))
    else:
        unverified["birthday"] = "birthday not supplied" if not req.birthday else "event date not supplied"

    if req.event_date:
        day = req.event_date.isoformat()
        for key, v in dates.date_numerology(req.event_date).items():
            sources.append(Source(f"calendar:{key}", "calendar", f"{day} {key}", v, "DN"))
        for kind, rule, word in (("weekday", "DAY-GEM", dates.weekday(req.event_date)),
                                 ("planet", "PLANET-GEM", dates.ruling_planet(req.event_date))):
            for code, v in gematria.all_values(word).items():
                sources.append(Source(f"calendar:{kind}:{word}:{code}", "calendar",
                                      f"{kind} '{word}' ({code})", v, rule, code, word))
    else:
        unverified["calendar"] = "event date not supplied"

    return sources, unverified


class _Recorder:
    def __init__(self, registry: dict, milestone: int):
        self.rules = registry["rules"]
        self.milestone = milestone
        self.records: list[dict] = []

    def add(self, rule_id: str, hit: bool, computation: str, source: Source | None = None,
            family: str | None = None, value=_UNSET):
        rule = self.rules[rule_id]
        self.records.append({
            "rule_id": rule_id,
            "rule_version": rule["version"],
            "hit": hit,
            "family": family or (source.family if source else rule["family"]),
            "source_id": source.source_id if source else "milestone",
            "label": source.label if source else f"milestone {self.milestone}",
            "cipher": source.cipher if source else None,
            "phrase": source.phrase if source else None,
            "source_verified": source.verified if source else True,
            "value": value if value is not _UNSET else (source.value if source else self.milestone),
            "milestone": self.milestone,
            "computation": computation,
            "evidence_class": rule["evidence_class"],
            "prime_related": rule["prime_related"],
        })


def evaluate(req: DecodeRequest, registry: dict) -> tuple[list[dict], dict[str, str]]:
    m = req.milestone
    sources, unverified = build_sources(req)
    rec = _Recorder(registry, m)

    # Milestone arithmetic
    idx_m = primes.prime_index(m)
    rec.add("PRIME-M", idx_m is not None,
            f"{m} is the {_ordinal(idx_m)} prime" if idx_m else f"{m} is not prime")
    rev = primes.reverse_digits(m)
    if rev == m:
        rec.add("REVPRIME-M", False, f"{m} reversed is itself; no separate reverse value", value=rev)
    else:
        rec.add("REVPRIME-M", primes.is_prime(rev),
                f"{m} → {rev}, {'prime' if primes.is_prime(rev) else 'not prime'}", value=rev)

    # PIGR bridges: one comparison per source value, A and B judged independently.
    target_b = primes.nth_prime(m)
    for s in sources:
        if idx_m is not None:
            ok = s.value == idx_m
            rec.add("PIGR-A", ok, f"index of {m} = {idx_m}; {s.label} = {s.value}"
                    + ("" if ok else f" ≠ {idx_m}"), s)
        ok = s.value == target_b
        if ok:
            comp = f"{s.value} is the {_ordinal(m)} prime"
        elif primes.is_prime(s.value):
            comp = f"{s.value} is the {_ordinal(primes.prime_index(s.value))} prime, not the {_ordinal(m)}"
        else:
            comp = f"{s.value} is not prime"
        rec.add("PIGR-B", ok, comp, s)
    if idx_m is None:
        rec.add("PIGR-A", False, f"{m} is not prime; PIGR-A not applicable", family="source")

    # Direct equality syncs
    for s in sources:
        ok = s.value == m
        rec.add(s.match_rule, ok, f"{s.label} = {s.value}" + (f" = milestone {m}" if ok else f" ≠ {m}"), s)

    # Symbolic tags: kept separate, never counted as structural evidence.
    sym = {n: name for name, nums in registry["symbolic_sets"].items() for n in nums}
    for s in [None, *sources]:
        v = s.value if s else m
        label = s.label if s else "milestone"
        rec.add("SYM", v in sym,
                f"{label} = {v}, a {sym[v]} number" if v in sym else f"{label} = {v}, not in a symbolic set",
                s, family="symbolic", value=v)

    return rec.records, unverified


def _ordinal(n: int | None) -> str:
    if n is None:
        return "?"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

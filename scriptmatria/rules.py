"""Relationship engine (rulebook §4–§5). Every eligible comparison between the
milestone M and a source value is recorded with an evidence lineage and a status,
whether it hits or not. Inputs that are missing, outside the phrase registry or in
conflict produce UNVERIFIED, INVALID or RULE_CONFLICT records instead of guesses.
"""

import json
from dataclasses import dataclass
from importlib import resources

from . import dates, gematria, phrases, primes
from .inputs import DecodeRequest

REGISTRY_FILE = "rules_v3.json"

QS, QC, SN = "QUALIFIED_STRUCTURAL", "QUALIFIED_CALENDAR", "SYMBOLIC_NOTE"
NO_HIT, INVALID, UNVERIFIED, RULE_CONFLICT = "NO_HIT", "INVALID", "UNVERIFIED", "RULE_CONFLICT"
HIT_STATUS = {"structural": QS, "calendar": QC, "symbolic": SN}
COMPARED = (QS, QC, SN, NO_HIT)


def load_registry(name: str = REGISTRY_FILE) -> dict:
    return json.loads(resources.files("scriptmatria.registry").joinpath(name).read_text("utf-8"))


@dataclass(frozen=True)
class Source:
    source_id: str
    family: str
    label: str
    value: int
    match_rule: str  # rule comparing this value directly with M
    cipher: str | None = None
    phrase: str | None = None
    aliases: tuple[str, ...] = ()


class _Ledger:
    def __init__(self, req: DecodeRequest, registry: dict):
        self.req, self.rules, self.records = req, registry["rules"], []

    def add(self, rule_id: str, status: str, computation: str, *, source: Source | None = None,
            family: str | None = None, right: str | None = None, value=None,
            operation: str | None = None, numeric: dict | None = None):
        rule = self.rules[rule_id]
        m = self.req.milestone
        self.records.append({
            "event_id": self.req.event_id,
            "player_id": self.req.player_id,
            "milestone_id": self.req.milestone_id,
            "rule_id": rule_id,
            "rule_version": rule["version"],
            "status": status,
            "class": rule["class"],
            "prime_related": rule["prime_related"],
            "family": family or (source.family if source else rule["family"]),
            "left_source": f"milestone M={m}",
            "right_source": right or (source.label if source else f"milestone M={m}"),
            "operation": operation or rule["operation"],
            "numeric_values": numeric or {"M": m, **({"G": source.value} if source else {})},
            "computation": computation,
            "source_id": source.source_id if source else (family or "milestone"),
            "phrase": source.phrase if source else None,
            "cipher": source.cipher if source else None,
            "aliases": list(source.aliases) if source else [],
            "value": value if value is not None else (source.value if source else m),
        })


def _gematria_sources(req: DecodeRequest, phrase_reg: dict, led: _Ledger) -> list[Source]:
    out: list[Source] = []
    lanes = (("team", req.team_id, "team_gematria", "SELF-TYPEA"),
             ("opponent", req.opponent_id, "opponent_gematria", "OPP-TYPEA"))
    version = phrase_reg.get("phrase_registry_version")
    if phrase_reg.get("league") != req.league or version is None:
        for _, tid, fam, rule in lanes:
            led.add(rule, UNVERIFIED, f"no approved phrase registry for league {req.league}",
                    family=fam, right=f"{tid} phrases")
        return out
    if req.phrase_registry_version != version:
        for _, tid, fam, rule in lanes:
            led.add(rule, RULE_CONFLICT,
                    f"snapshot cites phrase registry {req.phrase_registry_version}; loaded registry is {version}",
                    family=fam, right=f"{tid} phrases")
        return out
    for side, tid, fam, rule in lanes:
        team_phrases = phrases.team_phrases(phrase_reg, tid)
        if not team_phrases:
            led.add(rule, UNVERIFIED, f"no authorized {side} phrase: {tid} is not in the phrase registry",
                    family=fam, right=f"{tid} phrases")
        for p in team_phrases:
            for code, v in gematria.all_values(p.text).items():
                out.append(Source(f"{side}:{tid}:{p.kind}:{code}", fam, f"{side} '{p.text}' ({code})", v,
                                  rule, code, p.text, p.aliases))

    allowed = {req.team_id, req.opponent_id}
    for rp in req.requested_phrases:
        fam = "opponent_gematria" if rp.team_id == req.opponent_id else "team_gematria"
        rule = "OPP-TYPEA" if rp.team_id == req.opponent_id else "SELF-TYPEA"
        if rp.team_id not in allowed:
            led.add(rule, INVALID, f"'{rp.phrase}' belongs to {rp.team_id}, which is not in this event",
                    family=fam, right=f"requested phrase '{rp.phrase}'")
        elif gematria.normalize(rp.phrase) not in phrases.all_phrase_texts(phrase_reg, rp.team_id):
            led.add(rule, INVALID, f"'{rp.phrase}' is not an approved phrase for {rp.team_id}",
                    family=fam, right=f"requested phrase '{rp.phrase}'")
    return out


def build_sources(req: DecodeRequest, phrase_reg: dict, led: _Ledger) -> list[Source]:
    sources = _gematria_sources(req, phrase_reg, led)

    if req.jersey is not None:
        sources.append(Source("jersey", "jersey", f"jersey #{req.jersey}", req.jersey, "JERSEY-EXACT"))
    else:
        led.add("JERSEY-EXACT", UNVERIFIED, "jersey not supplied", family="jersey", right="jersey")

    if req.birth_date:
        for key, v in dates.birthday_spans(req.birth_date, req.event_date).items():
            if v is None:
                led.add("BIRTH-SPAN-EXACT", UNVERIFIED, f"{key}: Feb 29 birthday observance is pending",
                        family="birthday", right=f"birthday {key}")
            else:
                sources.append(Source(f"birthday:{key}", "birthday", f"birthday {key}", v, "BIRTH-SPAN-EXACT"))
    else:
        led.add("BIRTH-SPAN-EXACT", UNVERIFIED, "birth date not supplied", family="birthday",
                right="birthday spans")

    day = req.event_date.isoformat()
    for key, v in dates.date_numerology(req.event_date).items():
        sources.append(Source(f"calendar:{key}", "calendar", f"{day} {key}", v, "DN-EXACT"))
    for kind, rule, word in (("weekday", "DAY-GEM", dates.weekday(req.event_date)),
                             ("planet", "PLANET-GEM", dates.ruling_planet(req.event_date))):
        for code, v in gematria.all_values(word).items():
            sources.append(Source(f"calendar:{kind}:{code}", "calendar", f"{kind} '{word}' ({code})", v,
                                  rule, code, word))
    return sources


def evaluate(req: DecodeRequest, registry: dict, phrase_reg: dict) -> list[dict]:
    led = _Ledger(req, registry)
    m = req.milestone
    sources = build_sources(req, phrase_reg, led)

    # Milestone properties
    idx_m = primes.prime_index(m)
    led.add("M-PRIME", QS if idx_m else NO_HIT,
            f"{m} is the {ordinal(idx_m)} prime" if idx_m else f"{m} is not prime")
    rev = primes.reverse_digits(m)
    rev_prime = primes.is_prime(rev)
    led.add("M-REVPRIME", QS if rev_prime else NO_HIT,
            f"reverse_digits({m}) = {rev}, {'prime' if rev_prime else 'not prime'}",
            value=rev, numeric={"M": m, "reverse_digits(M)": rev})

    # PIGR bridges over every eligible source value; A and B judged independently.
    target_b = primes.nth_prime(m)
    for s in sources:
        if idx_m is not None:
            ok = s.value == idx_m
            led.add("PIGR-A", QS if ok else NO_HIT,
                    f"prime_index({m}) = {idx_m}; {s.label} = {s.value}" + ("" if ok else f" ≠ {idx_m}"),
                    source=s, numeric={"M": m, "prime_index(M)": idx_m, "G": s.value})
        ok = s.value == target_b
        if ok:
            comp = f"{s.label} = {s.value}, the {ordinal(m)} prime"
        elif primes.is_prime(s.value):
            comp = f"{s.label} = {s.value}, the {ordinal(primes.prime_index(s.value))} prime, not the {ordinal(m)}"
        else:
            comp = f"{s.label} = {s.value}, not prime"
        led.add("PIGR-B", QS if ok else NO_HIT, comp, source=s,
                numeric={"M": m, "G": s.value, "nth_prime(M)": target_b})
    if idx_m is None:
        led.add("PIGR-A", NO_HIT, f"{m} is not prime; PIGR-A not applicable", family="source")

    # Direct equality
    for s in sources:
        ok = s.value == m
        status = HIT_STATUS[registry["rules"][s.match_rule]["class"]] if ok else NO_HIT
        led.add(s.match_rule, status, f"{s.label} = {s.value}" + (" = M" if ok else f" ≠ {m}"), source=s)

    # Keyword overlay (opt-in): symbolic notes only.
    if "keywords" in req.overlays:
        kw = {n: name for name, nums in registry["symbolic_sets"].items() for n in nums}
        for s in [None, *sources]:
            v = s.value if s else m
            label = s.label if s else f"milestone M={m}"
            led.add("KW-EXACT", SN if v in kw else NO_HIT,
                    f"{label} = {v}, {kw[v]} code" if v in kw else f"{label} = {v}, not a keyword",
                    source=s, family="symbolic", value=v, numeric={"value": v})
    return led.records


def ordinal(n: int | None) -> str:
    if n is None:
        return "?"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

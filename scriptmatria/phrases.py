"""Approved phrase registry: the only source of gematria phrases. A registry is
frozen before any comparison is made (rulebook §8)."""

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from . import gematria


@dataclass(frozen=True)
class Phrase:
    team_id: str
    kind: str  # city | nickname | full
    text: str
    aliases: tuple[str, ...] = ()  # other kinds that normalize to the same letters


def load(path: str | Path | None = None, league: str = "MLB") -> dict:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    name = f"phrases_{league.lower()}.json"
    files = resources.files("scriptmatria.registry")
    if not files.joinpath(name).is_file():
        return {"registry": "phrases", "league": league, "phrase_registry_version": None, "teams": {}}
    return json.loads(files.joinpath(name).read_text("utf-8"))


def team_phrases(registry: dict, team_id: str) -> list[Phrase]:
    """City, nickname and city+nickname for one team, deduplicated by normalized letters."""
    team = registry["teams"].get(team_id)
    if team is None:
        return []
    city, nick = team.get("city"), team.get("nickname")
    raw = [("city", city), ("nickname", nick), ("full", " ".join(x for x in (city, nick) if x))]
    out: list[Phrase] = []
    for kind, text in raw:
        if not text:
            continue
        key = gematria.normalize(text)
        same = next((p for p in out if gematria.normalize(p.text) == key), None)
        if same:
            out[out.index(same)] = Phrase(same.team_id, same.kind, same.text, same.aliases + (kind,))
        else:
            out.append(Phrase(team_id, kind, text))
    return out


def all_phrase_texts(registry: dict, team_id: str) -> set[str]:
    return {gematria.normalize(p.text) for p in team_phrases(registry, team_id)}

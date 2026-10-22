"""MLB Stats API adapter (statsapi.mlb.com): an approved, versioned data adapter
under rulebook §2. It never decodes. It writes a DRAFT snapshot in which every
fetched value carries the exact URL it came from and when it was fetched; an
operator must review and attest the draft before it can be decoded.

Stat definitions (v0.1): career = regular-season career totals (gameType R) as
the API reports them; postseason games are not included.
"""

import hashlib
import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone

ADAPTER_ID = "mlb-statsapi"
ADAPTER_VERSION = "0.1.0"
BASE = "https://statsapi.mlb.com/api/v1"

# Phrase-registry team ID -> MLB Stats API team ID.
TEAM_IDS = {
    "ARI": 109, "ATH": 133, "ATL": 144, "BAL": 110, "BOS": 111, "CHC": 112, "CWS": 145, "CIN": 113,
    "CLE": 114, "COL": 115, "DET": 116, "HOU": 117, "KC": 118, "LAA": 108, "LAD": 119, "MIA": 146,
    "MIL": 158, "MIN": 142, "NYM": 121, "NYY": 147, "PHI": 143, "PIT": 134, "SD": 135, "SF": 137,
    "SEA": 136, "STL": 138, "TB": 139, "TEX": 140, "TOR": 141, "WSH": 120,
}
# Our stat codes -> MLB Stats API hitting fields.
STAT_FIELDS = {"HR": "homeRuns", "H": "hits", "RBI": "rbi"}

GetJson = Callable[[str], dict]


class AdapterError(RuntimeError):
    pass


def _url(path: str, **params) -> str:
    query = urllib.parse.urlencode(params, safe="(),[]=")
    return f"{BASE}{path}" + (f"?{query}" if query else "")


def http_get_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": f"scriptmatria/{ADAPTER_ID}-{ADAPTER_VERSION}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # network, HTTP or JSON errors all stop the fetch
        raise AdapterError(f"GET {url} failed: {e}") from e


class Client:
    """Thin read-only client. `get_json` is injectable so tests use recorded responses."""

    def __init__(self, get_json: GetJson = http_get_json):
        self.get_json = get_json

    def active_roster(self, team: str, on: str) -> tuple[list[dict], str]:
        url = _url(f"/teams/{TEAM_IDS[team]}/roster", rosterType="active", date=on)
        data = self.get_json(url)
        return [{"id": e["person"]["id"], "name": e["person"]["fullName"], "jersey": e.get("jerseyNumber")}
                for e in data.get("roster", [])], url

    def season_hr_leaders(self, team: str, season: int, limit: int = 15) -> tuple[list[dict], str]:
        url = _url("/stats", stats="season", group="hitting", season=season, gameType="R",
                   teamId=TEAM_IDS[team], sortStat="homeRuns", order="desc", limit=limit, playerPool="ALL")
        data = self.get_json(url)
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        return [{"id": s["player"]["id"], "name": s["player"]["fullName"],
                 "season_hr": s["stat"].get("homeRuns", 0)} for s in splits], url

    def person(self, person_id: int) -> tuple[dict, str]:
        url = _url(f"/people/{person_id}", hydrate="stats(group=[hitting],type=[career])")
        data = self.get_json(url)
        people = data.get("people") or []
        if not people:
            raise AdapterError(f"no person {person_id} in response from {url}")
        p = people[0]
        career = {}
        for block in p.get("stats", []):
            if block.get("type", {}).get("displayName") == "career" and \
                    block.get("group", {}).get("displayName") == "hitting":
                splits = block.get("splits") or [{}]
                career = splits[0].get("stat", {})
        return {"id": p["id"], "name": p["fullName"], "birth_date": p.get("birthDate"),
                "primary_number": p.get("primaryNumber"), "career": career}, url


def _slug(name: str) -> str:
    parts = "".join(c if c.isalnum() or c == " " else " " for c in name.lower()).split()
    return "-".join(parts[-1:] + parts[:-1]) if parts else "player"


def build_draft(client: Client, *, event_id: str, event_date: str, timezone_name: str, start_local: str,
                home: str, away: str, stats: list[str], top_hr: int, season: int,
                phrase_registry_version: str, overlays: list[str], now: datetime | None = None) -> dict:
    """Pick each team's top-N season HR hitters who are on the active roster for the event
    date, and build one unattested decode snapshot per player per stat."""
    for team in (home, away):
        if team not in TEAM_IDS:
            raise AdapterError(f"unknown team id {team}")
    for s in stats:
        if s not in STAT_FIELDS:
            raise AdapterError(f"stat {s} has no Stats API field (supported: {', '.join(STAT_FIELDS)})")
    fetched_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    calls: list[str] = []
    decodes, players = [], []
    for team, opponent in ((away, home), (home, away)):
        roster, roster_url = client.active_roster(team, event_date)
        leaders, leaders_url = client.season_hr_leaders(team, season)
        calls += [roster_url, leaders_url]
        on_roster = {p["id"]: p for p in roster}
        chosen = [p for p in leaders if p["id"] in on_roster][:top_hr]
        if len(chosen) < top_hr:
            raise AdapterError(f"{team}: only {len(chosen)} season HR leaders are on the active roster")
        for leader in chosen:
            person, person_url = client.person(leader["id"])
            calls.append(person_url)
            jersey = on_roster[leader["id"]]["jersey"] or person["primary_number"]
            players.append({"mlbam_id": person["id"], "name": person["name"], "team_id": team,
                            "season": season, "season_hr": leader["season_hr"],
                            "birth_date": person["birth_date"], "jersey": jersey,
                            "career": {s: person["career"].get(STAT_FIELDS[s]) for s in stats},
                            "sources": {"roster": roster_url, "leaders": leaders_url, "person": person_url}})
            for s in stats:
                value = person["career"].get(STAT_FIELDS[s])
                if value is None:
                    raise AdapterError(f"{person['name']}: career {STAT_FIELDS[s]} missing in {person_url}")
                decodes.append({
                    "event_id": event_id, "event_date_local": event_date, "timezone": timezone_name,
                    "event_start_local": start_local, "league": "MLB",
                    "player_id": f"{_slug(person['name'])}-{person['id']}", "player_name": person["name"],
                    "team_id": team, "opponent_id": opponent, "stat_code": s, "stat_scope": "career",
                    "current_count": int(value), "current_count_as_of": fetched_at,
                    "current_count_source": f"{ADAPTER_ID} {ADAPTER_VERSION}: {person_url} "
                                            f"(career {STAT_FIELDS[s]}, regular season)",
                    "birth_date": person["birth_date"],
                    "birth_date_source": f"{ADAPTER_ID} {ADAPTER_VERSION}: {person_url}",
                    "jersey": int(jersey) if jersey not in (None, "") else None,
                    "jersey_source": f"{ADAPTER_ID} {ADAPTER_VERSION}: {roster_url}",
                    "phrase_registry_version": phrase_registry_version,
                    "operator_attestation": "",
                    "adapter": f"{ADAPTER_ID}@{ADAPTER_VERSION}",
                    "overlays": overlays,
                })
    body = {"decodes": decodes, "players": players}
    return {
        "draft": True,
        "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION, "base_url": BASE},
        "fetched_at_utc": fetched_at,
        "selection": {"rule": f"top {top_hr} {season} regular-season HR hitters per team on the active roster "
                              f"for {event_date}", "stats": stats},
        "api_calls": calls,
        "content_sha256": content_hash(body),
        **body,
    }


def content_hash(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

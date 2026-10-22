# scriptmatria

The **Zilla 3.0** player-milestone decoding engine. It is deterministic, auditable and **TAG-ONLY**.

You give it one athlete, one cumulative career stat, one event and one opponent. It runs every comparison allowed by a versioned rule registry, in a fixed order, and records every comparison with a status, hit or miss. Then it seals a report that can be replayed byte-for-byte.

- **Authority:** [ZILLA_3_RULEBOOK.md](ZILLA_3_RULEBOOK.md) (v0.2, merged draft). Its registry is [`rules_v3.json`](scriptmatria/registry/rules_v3.json), and the approved phrases are in [`phrases_mlb.json`](scriptmatria/registry/phrases_mlb.json).
- **Input contract:** [`input.schema.json`](input.schema.json) (PlayerMilestoneInput v0.1).
- **Legacy sources:** [`legacy_source_manifest.md`](legacy_source_manifest.md). The existing Zilla installation is not touched by this project.

> Alignments are mathematical observations, not predictions. No rule here has demonstrated predictive value. Rarity controls live in the separate research lab, and scoring is deferred until prospective evidence justifies it.

## Install

```bash
python3 -m pip install -e ".[test]"   # Python 3.11+, no runtime dependencies
```

## Use

```bash
scriptmatria decode examples/mlb_pilot.json --print            # seal reports into reports/
scriptmatria research control examples/mlb_pilot.json          # rarity control, research/ only
scriptmatria grade MLB-2026-10-21-FIXTURE-PA_FICTIONAL-A --outcome achieved --actual 23
scriptmatria gematria "Mercury"
```

**Files written per decode** (`reports/<event_id>_<player_id>_<stat_code>.*`):

| File | Contents |
| --- | --- |
| `.json` | the canonical decode: input snapshot, versions, seal hashes, cards, gematria table, grid, classification, every comparison |
| `.md` | the readable report, in the rulebook §9 order: input summary, date/birthday card, gematria table, relationship grid, TRIPLE PRIME (when found), symbolic overlay, audit block, ritual note |
| `.csv` | the Excel-ready relationship grid |
| `.ledger.jsonl` | the comparison ledger, one evidence record per comparison |
| `.vN.*` | a linked revision when a corrected snapshot is decoded; earlier versions are never overwritten |

**Files written per run:**

| File | Contents |
| --- | --- |
| `freeze_ledger.jsonl` | an append-only seal log with hashes, `created_at_utc`, `event_start_utc` and `sealed_before_event_start` |
| `outcomes.jsonl` | an append-only log of grades: ACHIEVED, NOT_ACHIEVED or UNRESOLVED |
| `summary.csv` | one summary row per decode |
| `decodes.xlsx` | Summary, Relationships and Evidence sheets |

## Statuses

| Status | Meaning |
| --- | --- |
| `QUALIFIED_STRUCTURAL` | exact hit of a structural rule (M-PRIME, M-REVPRIME, PIGR-A/B, OPP-TYPEA, SELF-TYPEA) |
| `QUALIFIED_CALENDAR` | exact hit of DN-EXACT, DAY-GEM, PLANET-GEM or BIRTH-SPAN-EXACT |
| `SYMBOLIC_NOTE` | JERSEY-EXACT, or KW-EXACT (keywords, opt-in); never structural evidence |
| `NO_HIT` | compared, no match |
| `INVALID` | a phrase outside the approved registry or outside this event |
| `UNVERIFIED` | an input is missing, or a rule is pending (for example a Feb 29 birthday in a non-leap year) |
| `RULE_CONFLICT` | the snapshot cites a different phrase-registry version; the match is withheld |

**TRIPLE PRIME** is shown when a decode has 3 or more qualified prime relationships, with each relationship listed. With fewer, nothing is shown.

## Pilot (MLB career HR, fictional athlete)

`examples/mlb_pilot.json` describes this pilot:
- Fictional Player A, NYY vs BOS
- event 2026-10-21 at 19:05 ET
- career HR 22 → 23
- born 2000-06-01, jersey #23
- overlays: keywords, moon and zodiac

| Rule | Derivation | Status |
| --- | --- | --- |
| M-PRIME | 23 is the 9th prime | Qualified (structural) |
| M-REVPRIME | reverse_digits(23) = 32, not prime | No hit |
| PLANET-GEM | planet 'Mercury' (CH) = 23 = M | Qualified (calendar) |
| JERSEY-EXACT | jersey #23 = 23 = M | Symbolic note |
| KW-EXACT | DN2 = 41 and Mercury (RR) = 41, Skull and Bones code | Symbolic note |

**Birthday card:** 9,638 days; age 26y 4m 20d; 142 days since and 223 until the birthday.
**Date card:** DN 77/41/14/57/12, day 294, 71 days left, Wednesday / Mercury.
**Moon:** Waxing Gibbous, age 11.3 days at first pitch.
**Dependencies:** the 23s (prime milestone, jersey, Mercury CH) are listed as one dependent number, not three confirmations.

The roadmap's math fixture is in `tests/fixtures/memphis_pilot.json`. There, "Memphis" EO = 83 is the 23rd prime, so PIGR-B qualifies and PIGR-A does not. Run it with `--phrases tests/fixtures/phrases_fixture.json`.

## Module map (Phase 1 deliverables)

| Deliverable | Module |
| --- | --- |
| `zilla_math.py` | `gematria.py`, `primes.py` (cached sieve), `dates.py`, `astro.py` |
| `relationship_engine.py` | `rules.py` (+ `phrases.py`) |
| `signal_validator.py` | `validator.py` |
| `decode_report.py` | `report.py`, `xlsx.py`, `grading.py` |
| research lab | `control.py` |

## Tests

```bash
python3 -m pytest
```

The suite covers the rulebook §12 acceptance gates and all the roadmap Phase 6 fixtures:
- Memphis PIGR-B, a no-match player, missing birthday, duplicate alias, conflicting dates and non-leap Feb 29
- a source outside the event, no authorized opponent phrase, PIGR-C invalid, a registry conflict and a corrected-snapshot revision
- CSV/JSON/MD reconciliation to the ledger, byte-identical replay, and a lock that fails if the rulebook, registry and schema disagree

## Roadmap

- **Next:** the team-record adapter for game decodes like Hawks–Magic. It covers record transitions on both result paths, holds, regular-season scope and reciprocal head-to-head dedupe; rulebook §13 lists the open items.
- **Later:** historical replay and counterfactual research, then automation and messaging (Telegram auth fail-closed, with no recalculation by a language model).

## Stat codes

`HR` is the approved pilot stat. `H` and `RBI` are **trial** stats: they decode normally but are labeled `trial` in the summary, the ritual note and the decode status. Any other `stat_code` is rejected.

## World Series 2026 Game 1 (Rays @ Brewers, 2026-10-23)

`examples/ws2026_g1_template.csv` holds 6 players × 3 stats (HR, H, RBI). Event, time, teams and overlays are prefilled. The operator fills in `current_count`, `current_count_as_of`, `current_count_source`, `birth_date`, `jersey` and `operator_attestation`, plus the names of the open player slots. Then run:

```bash
scriptmatria decode examples/ws2026_g1_template.csv --out reports/ws2026_g1
```

## Fetching player data (MLB Stats API adapter)

The source policy is **manual or an approved adapter with operator sign-off**. The approved adapter is `mlb-statsapi@0.1.0`, which reads `statsapi.mlb.com` (no API key needed).

```bash
# 1. Draft: top 3 regular-season HR hitters per team on the active roster, career HR/H/RBI,
#    birthdays and jerseys. Every value records its exact URL and fetch time.
scriptmatria fetch mlb --event-id MLB-2026-10-23-TB-MIL --date 2026-10-23 --start 19:00 \
  --timezone America/Chicago --home MIL --away TB --top-hr 3 --stats HR,H,RBI \
  --out drafts/ws2026_g1.draft.json

# 2. Review the printed table and the draft, then sign it. Unsigned drafts cannot be decoded.
scriptmatria attest drafts/ws2026_g1.draft.json --by "Your Name" --out inputs/ws2026_g1.json

# 3. Decode and seal.
scriptmatria decode inputs/ws2026_g1.json --out reports/ws2026_g1
```

- **Stat definition:** career totals are regular-season career totals as the API reports them; postseason games are not included.
- **Edited drafts:** a draft edited after fetching is refused unless you attest with `--allow-edits`, and that edit is written into the attestation.
- **Reports:** each decode is `<event_id>_<player_id>_<stat_code>`, so one player can have HR, H and RBI decodes for the same game.
- **Cloud sessions:** the environment's network policy must allow `statsapi.mlb.com`. Running on your own computer, for example in Cowork, needs nothing extra.

## Stat scopes: career vs combined

- `career`: regular-season career totals, the MLB official career line. World Series games don't change it.
- `combined` (**trial**): career regular season **plus** career postseason, as of before the event.
  - The snapshot must record `regular_season_count` and `postseason_count`, and they must add up to `current_count`.
  - The total changes after every postseason game, so each game needs a fresh snapshot, attested before that game's first pitch.

Combined decode IDs end in `-combined`, for example `MLB-2026-10-23-TB-MIL_turang-brice-668930_HR-combined`. The MLB Stats API adapter only drafts `career` snapshots; combined snapshots are entered manually and attested.

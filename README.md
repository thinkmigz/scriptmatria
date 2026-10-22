# scriptmatria

The Zilla 3.0 decoding engine. It is lite, deterministic and **TAG-ONLY**.

You give it an athlete, a game date and a stat milestone. It runs every athlete through the same calculations, in the same order, under the same versioned rules, and returns an auditable ritual decode:
- every match with its formula, source and rule
- every miss
- a Triple Prime Sync status
- a control test
- an Excel sheet

**[ZILLA_3_RULEBOOK.md](ZILLA_3_RULEBOOK.md) is the authority** on what counts as a valid match. The registry it describes is [`scriptmatria/registry/rules_v2.json`](scriptmatria/registry/rules_v2.json).

> Alignments are mathematical observations, not predictions. No rule here has demonstrated predictive value; that belongs to a separate research process (Phase 2+).

## Install

```bash
python3 -m pip install -e ".[test]"   # Python 3.11+, no runtime dependencies
```

## Use

```bash
scriptmatria decode examples/mlb_career_hr.json --out decodes --print   # first reference case
scriptmatria decode examples/sample_decodes.csv
scriptmatria gematria "Mercury"
scriptmatria grade mlb-fictional-player-a-hr23 --achieved yes --actual 23
```

`decode` writes these files to `decodes/`:

| File | What it is |
| --- | --- |
| `<id>.md` | Decode grid, decode status, finding, dependent and pending hits, comparison ledger |
| `<id>.json` | Full audit: inputs and `input_sha256`, registry version, every comparison, classification, control test |
| `<id>.vN.json/.md` | An amendment, written when inputs or rules change. Earlier versions are never overwritten. |
| `freeze_ledger.jsonl` | Append-only log of every freeze, with timestamp and hashes |
| `outcomes.jsonl` | Append-only grades from `scriptmatria grade`. These never touch a decode. |
| `summary.csv`, `grid.csv`, `decodes.xlsx` | Spreadsheet views of the run. The xlsx has three sheets: Summary, Grid and Evidence. |

Identical inputs and the same rule version always give byte-identical reports.

## The 10-step workflow

1. **Input lock:** inputs are validated and hashed. Missing data is never inferred.
2. **Number generation:**
   - birthday spans
   - date card: DN1–DN5, DOY, days left, weekday and ruling planet
   - five-cipher gematria (EO, FR, RO, RR, CH)
   - primes
3. **Relationship detection:** prime and reverse prime, PIGR-A and PIGR-B (independent), Type A, jersey, birthday, DN, and weekday and planet gematria.
4. **Ritual overlay:**
   - Skull & Bones and Jesuit keyword lanes
   - moon phase (Meeus true phases, timezone- and time-aware)
   - zodiac season tag
5. **Validation:**
   - Bare supplied numbers are *source pending* and don't count.
   - Restated numbers are flagged as dependent.
   - Triple Prime Sync needs 3 families on 3 numbers.
6. **Control test:** the same sources are decoded against milestones M ± 10. The result is descriptive rarity.
7. **Output:** grid, summary row and decode status.
8. **Freeze:** reports are written once. Changes become amendments.
9. **Grade:** outcomes go to a separate append-only ledger.
10. **Learn:** the research engine is not part of this tool.

## Reference case: MLB career home runs

`examples/mlb_career_hr.json` describes Fictional Player A:
- born 2000-06-01, wears jersey #23
- playing on 2026-10-21
- going for career HR #23
- the opponent gematria, 83, is supplied without its phrase

| Test | Finding | Result |
| --- | --- | --- |
| Prime milestone | 23 is the 9th prime | ✓ Exact |
| PIGR-B | 83 is the 23rd prime (needs its phrase and cipher) | Source pending |
| Jersey | jersey = 23 = milestone 23 | ✓ Exact |
| Weekday | Wednesday · ruled by Mercury | Tag |
| Weekday & planet gematria | planet 'Mercury' (CH) = 23 = milestone 23 | ✓ Exact |
| Symbolic codes | DN2 = 41 and Mercury (RR) = 41, Skull and Bones numbers | ✓ Exact |
| Triple Prime Sync | 1 verified prime hit from 1 family | Not qualified |

The decode status is **Partial, source verification required**. The three hits on 23 (prime milestone, jersey and Mercury CH) are listed as dependent: they are one number, not three confirmations.

## Input

JSON is either `{"decodes": [...]}` or a list. CSV uses the same column names, written as `phrases` = `entity:phrase|...` and `values` = `entity:label=value|...`.

```json
{
  "id": "mlb-fictional-player-a-hr23",
  "player": "Fictional Player A",
  "stat_category": "career HR",
  "milestone_type": "cumulative",
  "current": 22,
  "milestone": 23,
  "birthday": "2000-06-01",
  "jersey": 23,
  "event_date": "2026-10-21",
  "timezone": "America/New_York",
  "event_time": "19:05",
  "opponent": "Hypothetical Opponent X",
  "phrases": [{"entity": "opponent", "phrase": "Hypothetical Opponent X"}]
}
```

The rulebook (§2) gives the full field contract. Use `phrases` for opponent names whenever you can. Bare `values` stay *source pending*.

## Tests

```bash
python3 -m pytest
```

The suite contains the Phase 1 readiness checks (rulebook §10). These cover the math reference cases, independent PIGR, leap-year birthdays, duplicate handling, Triple Prime Sync qualification, byte-identical reproducibility, and a lock that fails if the rulebook and registry disagree.

## Roadmap

- **Phase 1** (this repo): rulebook, math engine, relationship detector, signal validator, decode report.
- **Phase 2:** historical replay and counterfactual testing.
- **Phase 3:** automation, dashboards and Telegram.

Predictive scoring is deferred until prospective evidence justifies it.

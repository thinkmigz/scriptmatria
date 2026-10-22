# Zilla 3.0 Master Decoding Rulebook

**Version:** v0.2 — merged draft · **Rule registry:** v3.5.0 (`scriptmatria/registry/rules_v3.json`) · **Mode:** TAG-ONLY
**Primary track:** individual athlete statistical milestones · **Pilot:** MLB career home runs

> **Governance.** This is the player-milestone successor contract. It merges `ZILLA_3_MASTER_RULEBOOK_v0.1_DRAFT.md` (2026-10-21) with the §13 decisions approved on 2026-10-22, and replaces the repo's earlier v2 rulebook.
>
> It does **not** amend the legacy `ZillaGPT_INPUT_CONTRACT.locked.md`, `ZillaGPT_OUTPUT_CONTRACT.locked.md` or `ZillaGPT_SCORING_POLICY.locked.md`. Legacy NBA team-outcome decoding stays under those files until it is deliberately migrated through its own adapter.
>
> The code implements this document and the tests enforce it. If code and rulebook disagree, the code is wrong. Items still marked *pending* fail closed.

## 1. Mission and definitions

**Mission.** Produce deterministic, reproducible, source-traceable displays of numerical and symbolic alignments involving an athlete's **next specified statistical milestone**.

**A successful decode** meets all of these conditions:
- the arithmetic is correct
- every relationship uses authorized inputs and rules
- every qualifying and non-qualifying attempt is recorded
- duplicates are identified
- the pre-event snapshot is preserved

Producing many matches, picking an outcome after the fact, or claiming that alignments predict the milestone is **not** a successful decode. Numerical exactness is distinct from predictive evidence. The October 9 audit measured 49.4% Zilla board accuracy over 866 selections.

**In scope (v0.1):**
- one player and one **cumulative career** counter per decode
- the target, `target_count = current_count + 1`; current totals are never inferred
- event date, player, current count, birthday, jersey, team and opponent
- the approved phrase set, primes, calendar fields and opt-in symbolic overlays
- outputs: an Excel-ready grid, the full evidence ledger and a narrative note
- explicit missing/unverified states instead of invented facts

**Out of scope until separately specified:**
- picks, sides, totals, parlays, confidence tiers and weights
- per-game threshold props
- live scraping or implicit data sources (only approved, versioned adapters are allowed; see §2)
- opportunistic phrases, 35-cipher sweeps, ad hoc reductions and concat ladders
- historical rewrites
- any predictive claim

## 2. Source hierarchy

1. The sealed **input snapshot** for the player and event: entered manually, or drafted by an **approved adapter** and attested by an operator.
2. The **rule registry** (`rules_v3.json`) and the math implementations, at explicit versions.
3. The **approved phrase registry** (`phrases_mlb.json`).
4. The **symbolic code registry** (§6).
5. Experimental rules, only when expressly opted in and labeled. None are enabled in v0.1.
6. Historical documents stay archival and are never silently merged.

Conflicting rules fail closed: the engine emits `RULE_CONFLICT`, shows the alternatives and withholds the match. For example, a snapshot that cites a different phrase-registry version gets `RULE_CONFLICT` on both gematria lanes. No language model or commentary layer may choose a rule.

## 3. Input contract — `PlayerMilestoneInput v0.1` (`input.schema.json`)

**Required for a base decode:**
- `event_id`, `event_date_local`, `timezone` (IANA), `league`
- `player_id`, `player_name`, `team_id`, `opponent_id`
- `stat_code`, `stat_scope` (`career` or `combined`; see **Stat scopes** below)
- `current_count`, `current_count_as_of`, `current_count_source`
- `phrase_registry_version`, `operator_attestation`

**Required to activate an overlay or lane:**

| Field(s) | Activates |
| --- | --- |
| `birth_date` (+ `birth_date_source`) | birthday spans |
| `jersey` (+ `jersey_source`, `jersey_effective_date`) | jersey |
| `event_start_local` + `timezone` | moon |
| `overlays: ["keywords"]` | keyword codes |

Overlays are **off unless requested** (`moon`, `zodiac`, `keywords`). A missing lane is reported `UNVERIFIED` and is never guessed.

**Input-lock failures:** contradictory inputs fail the lock instead of being resolved silently. These are:
- a count dated after the event
- a birth date after the event
- a jersey whose effective date is after the event
- the team equal to the opponent
- an unimplemented scope
- an invalid timezone, time or overlay

**Source policy (decided 2026-10-22):** manual or approved adapter with operator sign-off.
- **Approved adapters:** `mlb-statsapi@0.1.0`, which reads `statsapi.mlb.com`.
- **Drafts only:** an adapter never decodes. It writes a **draft** in which every value carries its exact URL and `fetched_at_utc`, plus a content hash.
- **Sign-off:** `scriptmatria attest` checks the hash and records who signed the draft and when. Only an attested snapshot passes the input lock, because `operator_attestation` is required.
- **No silent edits:** a draft edited after fetching is refused unless the operator attests with `--allow-edits`, and that edit is written into the attestation.
- **Stat definition:** for `mlb-statsapi`, career totals are **regular-season** career totals; postseason games are not included.

**Stat scopes:** career (approved), combined (trial).
- `career` is the regular-season career total, the MLB official career line. Postseason games do not change it.
- `combined` is the career regular-season total **plus** the career postseason total (all rounds and years), as of before the event.
  - The snapshot records both parts, `regular_season_count` and `postseason_count`, and they must sum to `current_count`, or the input lock fails.
  - It changes after every postseason game, so **every game needs a fresh, attested snapshot**.
- A combined decode's ID ends in `-combined`, and its status reads `Partial: trial scope`.

**Pilot stats:** HR (approved), H (trial), RBI (trial). Any other `stat_code` fails the input lock. A trial-stat decode is labeled in the input summary, the summary row and the ritual note, and its decode status reads `Partial: trial stat`.

## 4. Canonical mathematics (`zilla_math.py`)

**Gematria — five canonical ciphers.** Text is reduced to letters only and is case-insensitive. Digits, spaces and punctuation count as zero.

| Code | Cipher | Values |
| --- | --- | --- |
| EO | English Ordinal | a=1 … z=26 |
| FR | Full Reduction | EO digit-reduced (k=2, s=1, v=4) |
| RO | Reverse Ordinal | a=26 … z=1 |
| RR | Reverse Reduction | RO digit-reduced (a=8) |
| CH | Chaldean | a1 b2 c3 d4 e5 f8 g3 h5 i1 j1 k2 l3 m4 n5 o7 p8 q1 r2 s3 t4 u6 v6 w6 x5 y1 z7 |

No other cipher is authorized.

**Primes:**
- `is_prime(n)` holds for integers n ≥ 2 with exactly two divisors.
- `prime_index(p)` is the 1-based position of a prime, or null. For example, `prime_index(23) = 9`.
- `nth_prime(k)` returns the kth prime. For example, `nth_prime(23) = 83`.
- `reverse_digits(n)` reverses base-10 digits, and leading zeros drop (100 → 1). It is **not** the Reverse Ordinal cipher.

**Birthday spans** (birth date → local event date):

| Span | Definition |
| --- | --- |
| `total_days` | lifetime days |
| `age_years`, `ymd_months`, `ymd_days` | exact calendar arithmetic |
| `days_since_birthday`, `days_until_birthday` | an event-day birthday gives 0 for both |
| `total_weeks` | `total_days // 7` |
| Birth MM/DD | stored literally |

**Feb 29 (decided: pending, fail closed).** In a non-leap year, any span whose value depends on the observed date is `UNVERIFIED`. Lifetime days and weeks always compute.

**Calendar codes.** In the formulas, m is the month, d the day and Y the 4-digit year. Examples use Oct 21, 2026.

| Code | Formula | Oct 21, 2026 |
| --- | --- | --- |
| DN1 | m + d + century + 2-digit year | **77** |
| DN2 | m + d + each digit of Y | **41** |
| DN3 | every digit of m, d and Y | **14** |
| DN4 | m + d + 2-digit year | **57** |
| DN5 | every digit of m, d and 2-digit year | **12** |
| DOY | calendar day of year | **294** |
| DAYS_LEFT | days_in_year − DOY (the event day is excluded) | **71** |

**Weekday rulers:** Sun→Sun, Mon→Moon, Tue→Mars, Wed→Mercury, Thu→Jupiter, Fri→Venus, Sat→Saturn. The weekday and planet names are each run through all five ciphers:
- Wednesday: 100 / 37 / 143 / 44 / 34
- Mercury: 103 / 40 / 86 / 41 / 23
- Monday: 72 / 27 / 90 / 27 / 22
- Moon: 57 / 21 / 51 / 15 / 23

**Astronomy (NOTE only, opt-in):**
- **Moon:** Meeus, *Astronomical Algorithms* ch. 49, true phases with ΔT = 69 s. It requires the event start time and timezone.
- **Zodiac:** a fixed tropical sun-sign table (Aries 3/21 … Pisces 2/19).

## 5. Relationship vocabulary

All comparisons are exact integer equality. A phrase's raw gematria G is used **as-is**, never digit-summed or re-transformed.

| Rule ID | Version | Qualifies when | Class | Prime-related |
| --- | --- | --- | --- | --- |
| M-PRIME | 1.0 | `is_prime(M)` | structural | yes |
| M-REVPRIME | 2.0 | `is_prime(reverse_digits(M))` (palindromes included) | structural | yes |
| M-INDEX | 1.0 | `prime_index(M)` exists: an annotation on the milestone card, not evidence | annotation | no |
| OPP-TYPEA | 1.0 | authorized opponent raw G = M | structural | no |
| SELF-TYPEA | 1.0 | authorized own-team raw G = M (source identity preserved) | structural | no |
| PIGR-A | 1.0 | `is_prime(M)` and `prime_index(M) = G` | structural | yes |
| PIGR-B | 1.0 | `is_prime(G)` and `prime_index(G) = M` | structural | yes |
| JERSEY-EXACT | 2.0 | effective jersey J = M | symbolic | no |
| DN-EXACT | 2.0 | a named DN1–DN5, DOY or DAYS_LEFT field = M | calendar | no |
| DAY-GEM | 1.0 | a cipher value of the weekday name = M | calendar | no |
| PLANET-GEM | 1.0 | a cipher value of the ruling planet = M | calendar | no |
| BIRTH-SPAN-EXACT | 2.0 | a named birthday span = M | calendar | no |
| KW-EXACT | 1.0 | M or any eligible value is in a registered keyword set (opt-in) | symbolic | no |

**What every PIGR hit records:** the phrase, subject (team or opponent), cipher, raw G, M and direction.
- PIGR-A and PIGR-B are evaluated independently, so one value is never labeled as both.
- **PIGR-C** (digit-summing G to create a bridge) is **invalid**.

**PIGR source scope (decided).** PIGR is checked against every eligible source value: phrase gematria, jersey, birthday spans, calendar codes, and weekday and planet gematria. Each hit names its source family. *This is broader than the draft's phrase-only wording. It follows the practice in the Hawks–Magic reconstruction, for example 43 → 14 = DN3 and 353 → 71 = days left.*

**Weekday and planet gematria (decided).** These are calendar rules (`DAY-GEM`, `PLANET-GEM`) that can match M. *This differs from the draft's NOTE-only treatment, by user decision.*

**Experimental bridges** are **OFF**: concat, SACB/EACB, power-chain, square/Fibonacci and mirrors. They need separate registered specifications. Turning them off does not repeal their legacy use.

## 6. Keyword and astronomical layer

The registered keyword codes for v0.1 are:
- **Skull and Bones:** 149, 41, 76, 322
- **Jesuit:** 144, 153, 72

Each keyword note records the matched number, where it came from and the category. For example, DN2 = 41 matching 41 is a `DN → KW` echo. It is not a milestone alignment and not an independent prime source.

Moon, zodiac, jersey and keywords are NOTE-level only. Open-ended searches for "famous number" meanings are forbidden.

## 7. Validation, independence and Triple Prime

Every comparison carries this evidence lineage: `event_id | player_id | milestone_id | rule_id | left_source | right_source | operation | numeric_values | family | rule_version | status`.

Each comparison has exactly one status:

| Status | Meaning |
| --- | --- |
| `QUALIFIED_STRUCTURAL` | an exact hit of a structural rule |
| `QUALIFIED_CALENDAR` | an exact hit of a calendar or biographical rule |
| `SYMBOLIC_NOTE` | an exact hit of a symbolic rule; never structural evidence |
| `NO_HIT` | compared, with no match |
| `INVALID` | not allowed: a phrase outside the registry or the event |
| `UNVERIFIED` | input missing or rule pending |
| `RULE_CONFLICT` | rule versions disagree; the match is withheld |

**Validation rules:**
- **Checks:** type and range, source eligibility, the phrase whitelist, effective dates, exact results and the rule version.
- **Duplicates:** the same number restated under several labels is grouped as **dependent**, for example prime 23 = jersey 23 = Mercury CH 23. One number is one observation.
- **Duplicate phrases:** two phrases that normalize to the same letters are computed once, with their aliases kept. Athletics is both nickname and full name.
- **Counts:** reported separately as attempted, qualified (structural and calendar), symbolic, no-hit, invalid, unverified and rule conflict.

**TRIPLE PRIME:** a decode with **3 or more qualified prime relationships** (M-PRIME, M-REVPRIME, PIGR-A or PIGR-B) shows **TRIPLE PRIME** with each relationship listed. With fewer than 3, nothing is shown. There is no separate independence rule. "Same number under several labels" is listed in the audit block as information only.

## 8. Comparison universe and anti-cherry-pick protection

The following are frozen before any comparison: the phrase list (city, nickname and city+nickname from the registry), the five ciphers, the milestone and the date fields.
- Every attempted comparison is saved, including `NO_HIT`.
- A late nickname, alternate spelling or extra cipher can never join a run invisibly. Operator-requested phrases outside the registry are recorded as `INVALID`.

Rarity controls belong to the **research lab only**: `scriptmatria research control`. That command decodes the same sources against milestones M ± 10. The results are never part of a sealed decode.

## 9. Output contract (`decode_report.py`)

Each decode emits, in order:
1. an input summary with sources and gaps
2. a date and birthday card with labeled units
3. a gematria table for the authorized phrases
4. a relationship grid: rule, LHS, RHS, derivation, status and source
5. TRIPLE PRIME, when found
6. the symbolic overlay
7. an audit block: counts, versions, hashes and overlays not requested
8. a one-sentence descriptive ritual note, never a pick

**Exports:** `<event_id>_<player_id>_<stat_code>.json` (canonical), `.md`, `.csv` (the grid) and `.ledger.jsonl` (every comparison). Each run also writes `summary.csv` and `decodes.xlsx`, which has Summary, Relationships and Evidence sheets. The CSV, JSON and Markdown reconcile exactly to the ledger.

## 10. Sealing and post-event grading

**Seal:**
- Each decode carries the SHA-256 of the normalized input snapshot, the rule registry and the phrase registry.
- `freeze_ledger.jsonl` adds the decode hash, `created_at_utc`, `event_start_utc` and `sealed_before_event_start`.
- Reports are never overwritten: identical content is left alone, and changed content becomes a linked revision (`<id>.vN`, which records `amends`).

**Grade:** `scriptmatria grade <id> --outcome achieved|not_achieved|unresolved` appends to `outcomes.jsonl`.
- A grade never touches a decode, and a second grade requires `--correction`.
- A stat that can't be reliably graded is `UNRESOLVED`, for example during a doubleheader stat correction.
- Grade against a stable `event_id`, and exclude or flag the compromised periods noted in the October 9 audit.

## 11. Versioning and change management

The output carries `engine_version`, `rulebook_version`, `rule_registry_version`, `phrase_registry_version` and `input_schema_version`.

**Change types:** keep these three separate:
- a **math bug fix**, which changes values
- a **classification rule change**, which changes qualifying hits
- a **research experiment**, which changes hypotheses

**Every change requires:**
- a new registry version, with the old file kept unchanged (`rules_v1.json` and `rules_v2.json` remain as history)
- a matching edit to this rulebook
- regression tests

Old decodes keep the versions they were sealed under.

## 12. Acceptance gates for v0.1 → v1.0

| Gate | Enforced by |
| --- | --- |
| All five ciphers agree on reference phrases | `tests/test_gematria.py`, `test_report.py::test_pilot_reference_values` |
| Prime and PIGR-A/B pass, including negative and PIGR-C cases | `test_primes.py`, `test_engine.py` |
| Birthday spans pass leap years, exact birthdays and year ends | `test_dates.py`, `test_engine.py::test_fixture_nonleap_feb29` |
| Every qualified hit traces to input, phrase, cipher, formula and version | `test_engine.py::test_only_registered_rules_and_ciphers` |
| Identical lineage never counts as independent | `test_engine.py::test_dependent_restatements_grouped` |
| Every comparison is recorded and reproduces identically | `test_report.py::test_seal_and_replay_are_identical` |
| Missing or contradictory data gives explicit statuses | `test_inputs.py`, `test_engine.py` fixtures |
| Sealing and revision history pass change detection | `test_report.py::test_corrected_snapshot_creates_linked_revision` |
| CSV, JSON and Markdown reconcile to the ledger | `test_report.py::test_csv_json_markdown_reconcile_to_ledger` |
| A full single-player pilot gives the same result twice | `test_report.py::test_seal_and_replay_are_identical` |

**Roadmap Phase 6 fixtures** (`tests/test_engine.py`):
- Memphis PIGR-B
- no-match player
- missing birthday
- duplicate phrase alias
- conflicting dates
- non-leap Feb 29
- source outside the event
- no authorized opponent phrase
- PIGR-C invalid
- registry conflict
- corrected-snapshot revision

## 13. Approvals

| # | Item | Status |
| --- | --- | --- |
| 1 | Player-prop source policy | **Decided:** manual or approved adapter with operator sign-off (`mlb-statsapi@0.1.0`) |
| 2 | Pilot stat | **Decided:** MLB career HR (approved); career H and RBI as **trial** stats (2026-10-22, World Series test); `combined` (regular season + postseason) scope added as **trial** (2026-10-22) |
| 3 | Opponent phrase scope | **Decided:** city, nickname and city+nickname; no abbreviations |
| 4 | Leap-day birthdays / lunar time source | **Decided:** Feb 29 pending (fail closed); moon needs the event start time (Meeus ch. 49) |
| 5 | Triple Prime | **Decided:** shown when 3+ qualified prime relationships are found (2026-10-22) |
| 6 | Experimental bridges for research mode | **Pending:** all OFF |
| 7 | Labeling one number from several dependent sources | **Interim:** grouped as "dependent restatements"; one number is one observation |

**Default for anything undecided:** fail closed. Show it as pending, and never infer or score.

### Open items raised by the Hawks–Magic reconstruction (team-record adapter, not in v0.1)
- **Core ciphers:** that card treats EO/FR/RO/RR as core and Chaldean as supplemental; this rulebook keeps five canonical ciphers.
- **Jesuit set:** that card adds 54 to the Jesuit set; this rulebook's set is 144, 153, 72.
- **Keyword phrases:** that card uses phrase-gematria keywords such as "Masonry", "Society of Jesus" and "Skull and Bones". These need a registered keyword-phrase list.
- **Team-game mechanics:** record-state transitions on both result paths, **holds** (unchanged counters), regular-season scope filters and reciprocal head-to-head deduplication need a separate team-record input contract.
- **Other overlays:** figure and anniversary spans, and moon sign, need their own registries and algorithms.

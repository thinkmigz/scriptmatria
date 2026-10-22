# Zilla 3.0 Master Decoding Rulebook

**Status:** LOCKED · **Registry:** v2.0.0 (`scriptmatria/registry/rules_v2.json`) · **Mode:** TAG-ONLY

This rulebook is the single authority on four things:
- what counts as a valid numerical match
- which transformations are allowed
- how relationships are classified
- what the decoder outputs

The code implements exactly this rulebook, and the test suite enforces it. If code and rulebook disagree, the code is wrong.

**Central formula:** Verified Data → Exact Calculations → Qualified Relationships → Independent Evidence → Auditable Decode

---

## 1. Principles

1. **Same path for everyone.** Every athlete goes through the same calculations, in the same order, under the same rule version.
2. **No improvisation.** A number is compared only through a rule listed in §4. Finding an interesting number never creates a new rule.
3. **Calculation validity is not predictive validity.** An exact alignment is a mathematical observation. No rule here has demonstrated predictive value; the October 9 audit measured 49.4% Zilla board accuracy over 866 selections.
4. **Every hit is traceable.** Each match records its rule ID, rule version, source, phrase, cipher, inputs and computation.
5. **Misses are recorded too.** The decode logs every comparison it attempted, including no-hits, so the size of the search is always visible.
6. **History is immutable.** Frozen decodes are never edited. Corrections become amendments, and outcomes are kept in a separate ledger.

## 2. Inputs (workflow step 1: input lock)

| Field | Required | Notes |
| --- | --- | --- |
| `id`, `player`, `milestone` | yes | `milestone` is the next stat value M (a positive whole number). |
| `milestone_type` | recommended | `cumulative` means a running count reaching a new value, like career HR #23. `threshold` means a single-game line, like 20+ points. |
| `current`, `stat_category` | recommended | For example, 22 and "career HR". |
| `birthday`, `event_date` | for birthday and calendar lanes | ISO `YYYY-MM-DD`. |
| `jersey` | for the jersey lane | |
| `timezone`, `event_time` | optional | IANA zone and local `HH:MM`. They set the moon-phase day and the moon age. |
| `phrases` | for gematria lanes | `{entity, phrase}`, where entity is `opponent`, `team`, `player` or `event`. Every phrase is computed in all 5 ciphers. |
| `values` | discouraged | A bare number with a label. It is **source pending** until it is replaced by its phrase (§5.1). |

The rules for inputs:
- Missing data is never inferred. Any lane whose input is missing is reported as **Unverified**.
- Inputs are canonicalized and hashed (`input_sha256`).

## 3. Number generation (workflow step 2)

### 3.1 Gematria: five canonical ciphers

Phrases are reduced to letters only and are case-insensitive. Digits, spaces and punctuation count as zero.

| Code | Cipher | Values |
| --- | --- | --- |
| EO | English Ordinal | a=1 … z=26 |
| FR | Full Reduction | EO reduced to one digit (k=2, s=1, v=4) |
| RO | Reverse Ordinal | a=26 … z=1 |
| RR | Reverse Reduction | RO reduced to one digit (a=8) |
| CH | Chaldean | a1 b2 c3 d4 e5 f8 g3 h5 i1 j1 k2 l3 m4 n5 o7 p8 q1 r2 s3 t4 u6 v6 w6 x5 y1 z7 |

No other cipher is authorized.

### 3.2 Primes
- `is_prime(n)` decides whether n is prime.
- `prime_index(n)` is the 1-based position of a prime: 2 is the 1st prime, 23 is the 9th, 83 is the 23rd.
- `nth_prime(i)` is the inverse of `prime_index`.
- `reverse(n)` reverses n's digits (23 → 32).

### 3.3 Birthday spans (birth date → event date)

| Span | Definition |
| --- | --- |
| `total_days` | lifetime days elapsed |
| `age_years`, `ymd_months`, `ymd_days` | exact calendar years, months and days, never negative |
| `days_since_birthday` | days since the most recent birthday |
| `days_until_birthday` | days until the next birthday |
| `total_weeks` | `total_days // 7` |

Feb 29 birthdays are observed on Feb 28 in non-leap years. Each span is a separate anchor and is never substituted for another.

### 3.4 Calendar codes for the event date
In the formulas below, m is the month, d is the day, and Y is the 4-digit year. The examples use Oct 21, 2026.

| Code | Formula | Oct 21, 2026 |
| --- | --- | --- |
| DN1 | m + d + century + 2-digit year | 10+21+20+26 = **77** |
| DN2 | m + d + each digit of Y | 10+21+2+0+2+6 = **41** |
| DN3 | every digit of m, d and Y | 1+0+2+1+2+0+2+6 = **14** |
| DN4 | m + d + 2-digit year | 10+21+26 = **57** |
| DN5 | every digit of m, d and 2-digit year | 1+0+2+1+2+6 = **12** |
| DOY | day of the year | **294** |
| DAYS_LEFT | days remaining after the date | **71** |
| Weekday / ruler | Sun→Sun, Mon→Moon, Tue→Mars, Wed→Mercury, Thu→Jupiter, Fri→Venus, Sat→Saturn | Wednesday / Mercury |

The weekday name and the ruling-planet name are each run through all 5 ciphers. Monday is 72 / 27 / 90 / 27 / 22 and Moon is 57 / 21 / 51 / 15 / 23 (EO / FR / RO / RR / CH).

### 3.5 Astronomical tags (descriptive only, never matched against M)
- **Moon phase:** true phase instants come from Meeus, *Astronomical Algorithms* (2nd ed., ch. 49), using ΔT = 69 s, which is accurate to about a minute.
  - The event day is named for a principal phase (New Moon, First Quarter, Full Moon or Last Quarter) when that instant falls within the calendar day in the event timezone.
  - Otherwise it takes the intermediate name that follows the most recent principal phase.
  - Moon age is measured at `event_time`, or at local noon if no time is given.
- **Zodiac:** a fixed tropical sun-sign table. Aries starts 3/21, Taurus 4/20, Gemini 5/21, Cancer 6/21, Leo 7/23, Virgo 8/23, Libra 9/23, Scorpio 10/23, Sagittarius 11/22, Capricorn 12/22, Aquarius 1/20 and Pisces 2/19. This is a season tag, and there is no zodiac match rule.

## 4. Relationship rules (workflow steps 3–4)

**Sources** are every number generated in §3, plus jersey and verified phrases. Each source belongs to exactly one **family**: `milestone`, `opponent_gematria`, `team_gematria`, `player_gematria`, `event_gematria`, `jersey`, `birthday` or `calendar`.

| Rule ID | Version | Qualifies when | Evidence class | Prime-related |
| --- | --- | --- | --- | --- |
| PRIME-M | 1.0 | M is prime | structural | yes |
| REVPRIME-M | 1.0 | reverse(M) is prime and reverse(M) ≠ M | structural | yes |
| PIGR-A | 1.0 | M is prime **and** prime_index(M) = G, for a source value G | structural | yes |
| PIGR-B | 1.0 | G is prime **and** prime_index(G) = M | structural | yes |
| TYPEA | 1.0 | opponent gematria G = M | structural | no |
| GEM-SELF | 1.0 | team, player or event gematria G = M (self-referential, reported separately) | structural | no |
| JERSEY | 1.0 | jersey = M | structural | no |
| BDAY | 1.0 | a birthday span (§3.3) = M | structural | no |
| DN | 2.0 | DN1–DN5, DOY or DAYS_LEFT = M | calendar | no |
| DAY-GEM | 1.0 | a cipher value of the weekday name = M | calendar | no |
| PLANET-GEM | 1.0 | a cipher value of the ruling planet = M | calendar | no |
| SYM | 1.0 | M or any source value is in a locked symbolic set (§4.1) | symbolic | no |

Two rules govern how PIGR is applied:
- PIGR-A and PIGR-B are evaluated **independently**. One value is never labeled as both.
- PIGR is checked against every source value. The family of the hit is the family of the source.

### 4.1 Locked symbolic sets
- **Skull and Bones:** 149, 41, 76, 322
- **Jesuit:** 144, 153, 72

Symbolic hits are reported in their own lane, for example DN2 = 41 as a "calendar-to-keyword echo". They **never** count as structural or prime evidence.

### 4.2 Forbidden
- PIGR-C digit-sum bridges
- mirror and concat bridges, and SACB/EACB, which are not in this registry
- extra ciphers
- any creative transformation during a decode (re-reducing, reversing a source value, combining sources)

## 5. Signal validation (workflow step 5)

### 5.1 Source verification
A hit counts only if its source is verified:
- **Verified sources:** computed phrases (with phrase and cipher recorded), jersey, birthday spans and calendar codes.
- **Source pending:** a bare supplied number, for example "opponent gematria 83" with no phrase.

Pending hits are shown as **Source pending** and listed separately. They do **not** count toward Prime Cluster, Triple Prime Sync or the control test, and they make the decode status **Partial, source verification required**.

### 5.2 Independence and duplicates
Verified structural hits are grouped by the number they restate.

- Any group with more than one hit is listed under **Dependent hits**. Those hits are descriptions of one number, not separate confirmations.
- Example: M = 23 gives PRIME-M (23 is prime), JERSEY (#23) and PLANET-GEM (Mercury CH = 23). That is one number restated three times.

### 5.3 Classification
- **Prime Cluster:** 3 or more verified prime-related hits.
- **Triple Prime Sync:** 3 or more verified prime-related hits from **at least 3 distinct families** on **at least 3 distinct numbers**.
  - Example that qualifies: M = 23 (milestone), jersey 9 (PIGR-A, jersey family) and DN1 = 83 (PIGR-B, calendar family).
  - Example that does not: three PIGR-A hits from one opponent phrase in three ciphers.

## 6. Control test (workflow step 6)
The same verified sources are decoded against every alternative milestone within M ± 10. Values must be at least 1, and M itself is excluded.

The report gives the actual number of verified structural hits, the control average, and how many alternatives have as many hits or more. This is **descriptive rarity**, not a probability that the milestone happens.

## 7. Decode output (workflow step 7)
Each decode produces:
- a Markdown grid (Test | Finding | Result), using the results ✓ Exact, No hit, Source pending, Unverified, Tag, ✓ Qualified / Not qualified, and Descriptive
- a one-line finding
- a JSON audit containing every comparison, the classification, the control test, the comparison ledger and `input_sha256`
- a one-row spreadsheet summary

**Decode status:**
- **Complete:** every lane has its inputs and every hit has a verified source.
- **Partial, inputs missing: …**
- **Partial, source verification required**

Each run also writes `grid.csv`, `summary.csv` and `decodes.xlsx`, which has three sheets: Summary, Grid and Evidence.

## 8. Freeze, amend, grade (workflow steps 8–10)
- **Freeze:** a decode is written once.
  - Rerunning identical inputs leaves it untouched.
  - Changed inputs or rules produce `<id>.vN.json`, which records `amends`.
  - Every freeze is appended to `freeze_ledger.jsonl` with a UTC timestamp and SHA-256 hashes.
- **Grade:** `scriptmatria grade <id> --achieved yes|no` appends to `outcomes.jsonl` and never modifies a decode. A second grade requires `--correction`.
- **Learn:** whether any alignment is associated with outcomes is a question for a separate research engine, using clean pre-event decodes and matched baselines. It is not part of this tool.

## 9. Change control
Any change to a formula, rule or set requires all of the following:
1. A new registry version. The old registry file is kept unchanged.
2. A matching edit to this rulebook.
3. Reference tests for the new behavior.
4. A note in `changes_from_v1` (or its successor) in the registry.

Old decodes keep the registry version they were produced under, so a new rule never re-scores history.

## 10. Phase 1 readiness

| Test | Passing condition | Enforced by |
| --- | --- | --- |
| Mathematical accuracy | all reference cases pass | `tests/test_gematria.py`, `test_primes.py`, `test_dates.py`, `test_astro.py`, `test_reference_mlb.py` |
| PIGR | A and B calculated independently | `test_decode.py::test_pigr_a_and_b_are_never_both_labeled_for_one_value` |
| Birthday intervals | correct across leap years and anniversaries | `test_dates.py` |
| Duplicate handling | one relationship cannot inflate the signal count | `test_decode.py::test_same_family_does_not_make_triple_sync`, `test_dependent_hits_flagged` |
| Triple Prime Sync | only qualified configurations get the tag | `test_decode.py::test_triple_prime_sync_requires_three_families`, `test_pending_sources_never_qualify_triple_sync` |
| Reproducibility | same inputs and rule version produce identical outputs | `test_decode.py::test_output_is_byte_identical_across_runs` |
| Transparency | every displayed match has an auditable source | `test_decode.py::test_ledger_counts_every_comparison`, `test_rulebook.py` |

**First reference category:** MLB career home runs (`examples/mlb_career_hr.json`, `tests/test_reference_mlb.py`).

## 11. Module map

| Phase 1 deliverable | Module |
| --- | --- |
| Master Decoding Rulebook | `ZILLA_3_RULEBOOK.md` + `scriptmatria/registry/rules_v2.json` |
| Canonical Math Engine (`zilla_math`) | `gematria.py`, `primes.py`, `dates.py`, `astro.py` |
| Relationship Detector (`relationship_engine`) | `rules.py` |
| Signal Validator (`signal_validator`) | `validator.py`, `control.py` |
| Full Decode Report (`decode_report`) | `report.py`, `xlsx.py`, `grading.py` |

## 12. Open items
- **Reconcile with legacy code:** check `gematria_engine_primes.py`, `date_numerology_final.py` and `team-registry.nba.json` against §3 and add their reference values as tests. The DN1–DN5 formulas in §3.4 follow the Zilla 3.0 date card, and the legacy file must be confirmed against it.
- **Authorized opponent phrases:** lock the phrase set per team (city, nickname, full name) so `values` can be retired in favor of `phrases`.

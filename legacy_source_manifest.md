# Legacy source manifest (roadmap Phase 0)

**Purpose:** identify the exact legacy files that scriptmatria's rules were reconciled against, so historical versions are never overwritten and every inherited value can be traced to its source.

**Status:** template. Fingerprints are filled in when each file is uploaded. None of these files are in this repository, and the legacy Zilla installation is not touched by this project.

| File | Role | Version / date | SHA-256 | Reconciled? |
| --- | --- | --- | --- | --- |
| `gematria_engine_primes.py` | five-cipher gematria + prime utilities | — | *pending upload* | No; cipher tables re-derived from definitions |
| `date_numerology_final.py` | DN1–DN5, DOY, days left, weekday/planet lookup, `get_duration_variations` | — | *pending upload* | Partly; DN1–DN5 match the rulebook draft; the leap-day defect is fixed independently |
| `team-registry.nba.json` | NBA team phrase registry (30 teams × 3 variants × 5 ciphers) | — | *pending upload* | No; NBA is out of v0.1 scope |
| `nba_full_decode.js` | legacy NBA scoring path (PIGR-A/B mislabel noted in the audit) | Feb 2026 | *pending upload* | Not inherited |
| `scoring-rubric.md` | v2.12.0 rubric: PIGR-A/B definitions, PIGR-C prohibition | Apr 2026 | *pending upload* | Definitions inherited; point weights not inherited |
| `ZillaGPT_INPUT_CONTRACT.locked.md` | legacy NBA team-slate input contract | locked | *pending upload* | Untouched; separate contract |
| `ZillaGPT_OUTPUT_CONTRACT.locked.md` | legacy output contract | locked | *pending upload* | Untouched |
| `ZillaGPT_SCORING_POLICY.locked.md` | TAG-ONLY default | locked | *pending upload* | TAG-ONLY inherited |
| `ZillaGPT_SCORING_TABLE.locked.md` | legacy scoring table | locked | *pending upload* | Not inherited |
| Full system audit 2026-10-09 | audit baseline (49.4% over 866 selections, data integrity findings) | 2026-10-09 | *pending upload* | Findings applied |

## Known problems recorded from the audit (do not import these periods unflagged)

- Historical pregame files were rewritten after games (hindsight contamination).
- Doubleheader matching inverted outcomes for 14 of 24 pairs.
- There are NHL overtime/shootout accounting errors (the pre-OTL window).
- Multiple scoring tables and engine versions conflict (v2.12 rubric vs v2.36 engine vs the Feb JS port).

## Before importing any real historical ledger

1. Verify an off-machine backup and perform a test restore.
2. Confirm restrictive access permissions (Supabase RLS, service-role keys server-side only).
3. Record the fingerprint of every imported file in the table above.

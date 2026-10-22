import argparse
import json
import sys
from pathlib import Path

from . import __version__, control, gematria, grading, inputs, phrases, report, rules


def _load(args):
    requests = inputs.load(args.file)
    registry = rules.load_registry()
    regs = {}
    for r in requests:
        if r.league not in regs:
            regs[r.league] = phrases.load(args.phrases, r.league)
    return requests, registry, regs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="scriptmatria", description="Zilla 3.0 TAG-ONLY player-milestone decoder.")
    ap.add_argument("--version", action="version", version=f"scriptmatria {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decode", help="decode snapshots from a local JSON or CSV file and seal the reports")
    d.add_argument("file")
    d.add_argument("--out", default="reports", help="output directory (default: reports/)")
    d.add_argument("--phrases", help="phrase registry file (default: the built-in registry for the league)")
    d.add_argument("--print", action="store_true", help="also print each report to the terminal")

    rs = sub.add_parser("research", help="research lab tools (never part of a sealed decode)")
    rs.add_argument("tool", choices=["control"])
    rs.add_argument("file")
    rs.add_argument("--out", default="research", help="output directory (default: research/)")
    rs.add_argument("--phrases")

    f = sub.add_parser("fetch", help="draft snapshots from an approved adapter (must be attested before decoding)")
    f.add_argument("source", choices=["mlb"])
    f.add_argument("--event-id", required=True)
    f.add_argument("--date", required=True, help="event date, YYYY-MM-DD (local)")
    f.add_argument("--start", required=True, help="first pitch, HH:MM local")
    f.add_argument("--timezone", required=True, help="IANA zone of the venue, e.g. America/Chicago")
    f.add_argument("--home", required=True, help="home team ID (phrase registry), e.g. MIL")
    f.add_argument("--away", required=True, help="away team ID, e.g. TB")
    f.add_argument("--stats", default="HR,H,RBI", help="comma-separated stat codes (default HR,H,RBI)")
    f.add_argument("--top-hr", type=int, default=3, help="season HR leaders per team on the active roster")
    f.add_argument("--season", type=int, help="season for the HR leader list (default: event year)")
    f.add_argument("--overlays", default="keywords,moon,zodiac")
    f.add_argument("--out", required=True, help="draft file to write, e.g. drafts/ws2026_g1.draft.json")

    a = sub.add_parser("attest", help="operator sign-off: turn an adapter draft into a decodable snapshot")
    a.add_argument("draft")
    a.add_argument("--by", required=True, help="name of the person signing")
    a.add_argument("--out", required=True, help="attested snapshot file to write (never overwritten)")
    a.add_argument("--allow-edits", action="store_true", help="accept a draft edited after fetching (recorded)")

    g = sub.add_parser("gematria", help="show all five cipher values for a phrase")
    g.add_argument("phrase")

    gr = sub.add_parser("grade", help="record the outcome after the event (never edits the decode)")
    gr.add_argument("decode_id", help="<event_id>_<player_id>_<stat_code>")
    gr.add_argument("--outcome", choices=grading.OUTCOMES, required=True)
    gr.add_argument("--actual", type=int, help="actual stat value after the event")
    gr.add_argument("--note")
    gr.add_argument("--correction", action="store_true", help="record a correction to an earlier grade")
    gr.add_argument("--out", default="reports", help="report directory (default: reports/)")

    args = ap.parse_args(argv)
    if args.cmd == "gematria":
        for code, (name, _) in gematria.CIPHERS.items():
            print(f"{code}  {name:<18} {gematria.value(args.phrase, code)}")
        return 0

    if args.cmd == "fetch":
        from .adapters import mlb_statsapi
        try:
            draft = mlb_statsapi.build_draft(
                mlb_statsapi.Client(), event_id=args.event_id, event_date=args.date, timezone_name=args.timezone,
                start_local=args.start, home=args.home, away=args.away,
                stats=[s.strip() for s in args.stats.split(",") if s.strip()], top_hr=args.top_hr,
                season=args.season or int(args.date[:4]),
                phrase_registry_version=phrases.load(league="MLB")["phrase_registry_version"],
                overlays=[o.strip() for o in args.overlays.split(",") if o.strip()])
        except mlb_statsapi.AdapterError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for p in draft["players"]:
            career = ", ".join(f"{k} {v}" for k, v in p["career"].items())
            print(f"{p['team_id']:<4} {p['name']:<24} #{p['jersey'] or '?':<3} born {p['birth_date']}  "
                  f"season HR {p['season_hr']}  career {career}")
        print(f"draft (NOT attested): {out}  sha {draft['content_sha256'][:12]}")
        print(f"review it, then: scriptmatria attest {out} --by \"<your name>\" --out <snapshot.json>")
        return 0

    if args.cmd == "attest":
        from .attest import AttestError, attest
        try:
            record = attest(args.draft, args.by, args.out, allow_edits=args.allow_edits)
        except (AttestError, inputs.InputError, OSError, ValueError, KeyError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"attested {len(record['decodes'])} snapshots by {record['attestation']['by']} -> {args.out}")
        return 0

    if args.cmd == "grade":
        try:
            entry = grading.grade(args.out, args.decode_id, args.outcome, args.actual, args.note, args.correction)
        except grading.GradeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"graded {entry['decode_id']} ({entry['graded_file']}): {entry['outcome']}")
        return 0

    try:
        requests, registry, regs = _load(args)
    except (inputs.InputError, OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.cmd == "research":
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for r in requests:
            path = out / f"{report._safe(r.decode_id)}.control.json"
            path.write_text(json.dumps(control.control_test(r, registry, regs[r.league]), indent=2,
                                       sort_keys=True) + "\n", encoding="utf-8")
            print(f"research/control             {path}")
        return 0

    results = [report.decode(r, registry, regs[r.league]) for r in requests]
    for status, path in report.write(results, args.out):
        print(f"{status:<28} {path}")
    if args.print:
        for res in results:
            print()
            print(report.to_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())

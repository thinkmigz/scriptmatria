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

    g = sub.add_parser("gematria", help="show all five cipher values for a phrase")
    g.add_argument("phrase")

    gr = sub.add_parser("grade", help="record the outcome after the event (never edits the decode)")
    gr.add_argument("decode_id", help="<event_id>_<player_id>")
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

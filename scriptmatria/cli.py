import argparse
import sys

from . import __version__, gematria, grading, inputs, report, rules


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="scriptmatria", description="Lite TAG-ONLY ritual decoder.")
    ap.add_argument("--version", action="version", version=f"scriptmatria {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decode", help="decode requests from a local JSON or CSV file and freeze the reports")
    d.add_argument("file")
    d.add_argument("--out", default="decodes", help="output directory (default: decodes/)")
    d.add_argument("--print", action="store_true", help="also print each grid to the terminal")

    g = sub.add_parser("gematria", help="show all five cipher values for a phrase")
    g.add_argument("phrase")

    gr = sub.add_parser("grade", help="record whether a decoded milestone happened (never edits the decode)")
    gr.add_argument("decode_id")
    gr.add_argument("--achieved", choices=["yes", "no"], required=True)
    gr.add_argument("--actual", type=int, help="actual stat value after the event")
    gr.add_argument("--note")
    gr.add_argument("--correction", action="store_true", help="record a correction to an earlier grade")
    gr.add_argument("--out", default="decodes", help="decode directory (default: decodes/)")

    args = ap.parse_args(argv)
    if args.cmd == "gematria":
        for code, (name, _) in gematria.CIPHERS.items():
            print(f"{code}  {name:<18} {gematria.value(args.phrase, code)}")
        return 0

    if args.cmd == "grade":
        try:
            entry = grading.grade(args.out, args.decode_id, args.achieved == "yes", args.actual,
                                  args.note, args.correction)
        except grading.GradeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"graded {entry['decode_id']} ({entry['graded_file']}): achieved={entry['achieved']}")
        return 0

    try:
        requests = inputs.load(args.file)
    except (inputs.InputError, OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    registry = rules.load_registry()
    results = [report.decode(r, registry) for r in requests]
    for status, path in report.write(results, args.out):
        print(f"{status:<28} {path}")
    if args.print:
        for res in results:
            print()
            print(report.to_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())

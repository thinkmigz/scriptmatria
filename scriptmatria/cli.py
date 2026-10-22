import argparse
import sys

from . import __version__, gematria, inputs, report, rules


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="scriptmatria", description="Lite TAG-ONLY ritual decoder.")
    ap.add_argument("--version", action="version", version=f"scriptmatria {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decode", help="decode requests from a local JSON or CSV file")
    d.add_argument("file")
    d.add_argument("--out", default="decodes", help="output directory (default: decodes/)")
    d.add_argument("--print", action="store_true", help="also print each grid to the terminal")

    g = sub.add_parser("gematria", help="show all five cipher values for a phrase")
    g.add_argument("phrase")

    args = ap.parse_args(argv)
    if args.cmd == "gematria":
        for code, (name, _) in gematria.CIPHERS.items():
            print(f"{code}  {name:<18} {gematria.value(args.phrase, code)}")
        return 0

    try:
        requests = inputs.load(args.file)
    except (inputs.InputError, OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    registry = rules.load_registry()
    results = [report.decode(r, registry) for r in requests]
    for path in report.write(results, args.out):
        print(path)
    if args.print:
        for res in results:
            print()
            print(report.to_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())

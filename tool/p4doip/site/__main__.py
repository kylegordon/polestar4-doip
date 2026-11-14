"""python -m p4doip.site build --root <tree> --out <dir>   |   python -m p4doip.site scan <dir> --patterns <file>"""
import argparse
import os
import sys

from . import gate
from .build import build
from .inputs import InputError, Inputs, tracked_files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m p4doip.site", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="render the public site from git-tracked files, then scan the output")
    b.add_argument("--root", default=".", help="repository checkout or git-archive export (default: .)")
    b.add_argument("--out", default="_site", help="output directory (default: _site)")
    b.add_argument("--manifest", help="tracked-file list, for a tree with no .git (git ls-tree -r --name-only HEAD)")
    b.add_argument("--commit", default=os.environ.get("GITHUB_SHA", ""), help="commit id for the footer")
    s = sub.add_parser("scan", help="fail if any file under DIR holds private content")
    s.add_argument("dir")
    s.add_argument("--patterns", default="scripts/patterns.txt", help="shared pattern file")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "build":
            inputs = Inputs(args.root, tracked_files(args.root, args.manifest))
            patterns = gate.load_patterns(inputs.read_input("scripts/patterns.txt"))
            pages = build(inputs, args.out, args.commit)
            for name in pages:
                print("%-18s %7d bytes" % (name, os.path.getsize(os.path.join(args.out, name))))
            target = args.out
        else:
            with open(args.patterns, encoding="utf-8") as f:
                patterns = gate.load_patterns(f.read())
            target = args.dir
    except (InputError, ValueError, OSError) as e:
        print("site: %s" % e, file=sys.stderr)
        return 2
    problems = gate.scan_dir(target, patterns)
    if problems:
        print("site: FAIL, private or exact-date content in the output (values not shown):", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    print("site: output scan OK (%s)" % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Privacy gate for the public site: clean text on the way in, scan every written file on the way out.

In: `clean()` reduces exact dates to month and year, drops times of day, then applies `privacy.mask`, so
free text from docs/ and catalogue/ cannot carry a session date or an identifier onto the site.

Out: `scan_dir()` fails the build if any written file
- matches a pattern in scripts/patterns.txt (the list prepublish-check.sh uses),
- holds a line that `privacy.mask` would change (VIN, email, phone, any 10+ digit run),
- holds an exact date or time of day,
- holds a VIN or other identifier as UTF-16 text or as hex-wrapped text (decoded with the same helpers
  `p4 strings` uses).
Findings name the file, line and kind, never the matched value: the CI log is public.
"""
import os
import re

from .. import privacy

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")

# 2026-11-14, 2026.11.14 (a release, maybe .2), 2026/11/14; optionally followed by a time of day.
DATE = re.compile(r"\b((?:19|20)\d{2})([-./])(0[1-9]|1[0-2])\2(0[1-9]|[12]\d|3[01])(?:\.\d+)?"
                  r"(?:[ T]([01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)?(?![\d])")
# 16:01, 16:01:30, 16:01-16:02 standing alone (DID references like 1A01:4209 have no word boundary).
TIME = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:\s*-\s*([01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)?\b")
_MONTH_NAMES = "|".join(MONTHS + tuple(m[:3] for m in MONTHS))
DAY_MONTH = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:%s)\b|\b(?:%s)\s+\d{1,2}(?:st|nd|rd|th)?\b(?!\s*\d{3})"
                       % (_MONTH_NAMES, _MONTH_NAMES), re.I)
HEX_TEXT = re.compile(r"(?:[0-9a-fA-F]{2}){8,}")
HIDDEN = ("[VIN hidden]", "[email hidden]", "[phone hidden]", "[number hidden]")


def reduce_dates(text: str) -> str:
    """Exact dates become 'November 2026'; times of day become 'a recorded time'."""
    text = DATE.sub(lambda m: "%s %s" % (MONTHS[int(m.group(3)) - 1], m.group(1)), text)
    return TIME.sub("a recorded time", text)


def clean(text: str) -> str:
    """Free text as the site may show it: dates reduced, then identifiers masked."""
    return privacy.mask(reduce_dates(text))


def load_patterns(text: str) -> list[re.Pattern]:
    """scripts/patterns.txt: one extended regex per line; # comments and blank lines ignored."""
    pats = [re.compile(line, re.I | re.M) for line in text.splitlines()
            if line.strip() and not line.startswith("#")]
    if not pats:
        raise ValueError("no patterns in the shared pattern file")
    return pats


def _decoded_variants(text: str) -> list[str]:
    """Text that may hide inside a line: UTF-16 (NULs between letters) and hex-wrapped text."""
    out = []
    if "\x00" in text:
        out.append(text.replace("\x00", ""))
    for m in HEX_TEXT.finditer(text):
        out.extend(privacy.readable_runs(m.group()))
    return out


def scan_text(text: str, patterns: list[re.Pattern]) -> list[tuple[int, str]]:
    """(line number, kind) for every problem in one file's text."""
    hits: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        for i, p in enumerate(patterns, 1):
            if p.search(line):
                hits.append((n, "matches shared pattern %d" % i))
        if privacy.mask(line) != line:
            hits.append((n, "privacy.mask would change it"))
        if DATE.search(line) or DAY_MONTH.search(line):
            hits.append((n, "exact date"))
        if TIME.search(line):
            hits.append((n, "time of day"))
        for v in _decoded_variants(line):
            if privacy.VIN_LIKE.search(v) or any(h in v for h in HIDDEN) or privacy.mask(v) != v:
                hits.append((n, "identifier in UTF-16 or hex-wrapped text"))
                break
    return hits


def read_output(path: str) -> str:
    """A written file as text; UTF-16 files (BOM or NUL lanes) are decoded so their text is scanned too."""
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or raw.count(b"\x00") * 4 > len(raw):
        for enc in ("utf-16-le", "utf-16-be"):
            text += "\n" + raw.decode(enc, errors="replace")
    return text


def scan_dir(out_dir: str, patterns: list[re.Pattern]) -> list[str]:
    """'path:line: kind' for every problem in every file under out_dir. Empty means the output may ship."""
    problems: list[str] = []
    files = 0
    for dirpath, _dirs, names in os.walk(out_dir):
        for name in sorted(names):
            path = os.path.join(dirpath, name)
            files += 1
            rel = os.path.relpath(path, out_dir)
            problems.extend("%s:%d: %s" % (rel, n, kind) for n, kind in scan_text(read_output(path), patterns))
    if files == 0:
        problems.append("%s: no files to scan" % out_dir)
    return problems

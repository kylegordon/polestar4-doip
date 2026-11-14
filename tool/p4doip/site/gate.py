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
import html
import os
import re

from .. import privacy

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")

# Boundaries are "not a letter or digit" rather than \b, so log_2026-11-14 and snap_16:01 are caught too.
_L = r"(?<![A-Za-z0-9])"
_R = r"(?![A-Za-z0-9])"
# 2026-11-14, 2026.11.14 (a release, maybe .2), 2026/11/14; optionally followed by a time of day.
DATE = re.compile(_L + r"((?:19|20)\d{2})([-./])(0[1-9]|1[0-2])\2(0[1-9]|[12]\d|3[01])(?:\.\d+)?"
                  r"(?:[ T_]([01]?\d|2[0-3])[:.]?[0-5]\d(?:[:.]?[0-5]\d)?Z?)?(?!\d)")
# 14/11/2026, 14.11.2026, 11-14-2026, 14/11/26: day and month first (either order). A 2-digit year only with
# slashes, so software versions like 4.2.11 are not dates.
DATE_DMY = re.compile(_L + r"(0?[1-9]|[12]\d|3[01])(?:([-./])(0?[1-9]|[12]\d|3[01])\2(?:19|20)\d{2}"
                      r"|/(0?[1-9]|[12]\d|3[01])/\d{2})(?![\d.])")
# 20261114: compact year-month-day.
DATE_COMPACT = re.compile(_L + r"(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?:T\d{4,6}Z?)?" + _R)
# 16:01, 16:01:30, 16:01-16:02 standing alone (DID references like 1A01:4209 have a letter or digit before).
TIME = re.compile(r"(?<![A-Za-z0-9:])([01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?"
                  r"(?:\s*-\s*([01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)?(?![A-Za-z0-9:])")
_MONTH_NAMES = "|".join(MONTHS + tuple(m[:3] for m in MONTHS) + ("Sept",))
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
DAY_MONTH = re.compile(r"%s%s(?:\s+of)?\s+(?:%s)\b|\b(?:%s)\.?\s+%s(?!\d)"
                       % (_L, _DAY, _MONTH_NAMES, _MONTH_NAMES, _DAY), re.I)
EXACT_DATES = (DATE, DATE_DMY, DATE_COMPACT, DAY_MONTH)
TAG = re.compile(r"<[^>]*>")
RUN_10 = re.compile(r"\d{10,}")
HEX_RUN_ANY = re.compile(r"[0-9a-fA-F]{16,}")
HIDDEN = ("[VIN hidden]", "[email hidden]", "[phone hidden]", "[number hidden]")


def reduce_dates(text: str) -> str:
    """Exact dates become 'November 2026'; times of day become 'a recorded time'."""
    text = DATE.sub(lambda m: "%s %s" % (MONTHS[int(m.group(3)) - 1], m.group(1)), text)
    text = DATE_COMPACT.sub(lambda m: "%s %s" % (MONTHS[int(m.group()[4:6]) - 1], m.group()[:4]), text)
    return TIME.sub("a recorded time", text)


def clean(text: str) -> str:
    """Free text as the site may show it: dates reduced, then identifiers masked."""
    return privacy.mask(reduce_dates(text))


def load_patterns(text: str) -> list[re.Pattern]:
    """scripts/patterns.txt: one extended regex per line; # comments and blank lines ignored."""
    if "\r" in text:
        raise ValueError("the shared pattern file has CR line endings; grep would match nothing with it")
    pats = [re.compile(line, re.I | re.M) for line in text.splitlines()
            if line.strip() and not line.startswith("#")]
    if not pats:
        raise ValueError("no patterns in the shared pattern file")
    return pats


def _decoded_variants(text: str) -> list[str]:
    """Text that may hide inside a line: UTF-16 (NULs between letters) and hex-wrapped text at either
    byte alignment."""
    out = []
    if "\x00" in text:
        out.append(text.replace("\x00", ""))
    for m in HEX_RUN_ANY.finditer(text):
        digits = m.group()
        for start in (0, 1):  # both byte alignments; each candidate trimmed to whole bytes
            cand = digits[start:]
            out.extend(privacy.readable_runs(cand[:len(cand) - len(cand) % 2]))
    return out


def text_views(text: str) -> list[str]:
    """What a reader sees: tags removed, entities decoded; once with whitespace collapsed and once with line
    breaks removed, so an identifier split by markup (YSM<b>..</b>, &#89;SM..) or a line break is whole again."""
    plain = html.unescape(TAG.sub("", text))
    return [re.sub(r"\s+", " ", plain), re.sub(r"\s*\n\s*", "", plain)]


def _view_problems(view: str, patterns: list[re.Pattern]) -> list[str]:
    """Checks for the joined views. privacy.mask is too wide here (it allows separators, so adjacent code
    spans such as '4222 000000' would join into a 'number'); unbroken digit runs, VINs, shared patterns and
    dates are checked instead."""
    kinds = ["matches shared pattern %d" % i for i, p in enumerate(patterns, 1) if p.search(view)]
    if privacy.VIN_LIKE.search(view) or RUN_10.search(view) or privacy.EMAIL.search(view):
        kinds.append("identifier")
    if any(rx.search(view) for rx in EXACT_DATES):
        kinds.append("exact date")
    return kinds


def _problems(line: str, patterns: list[re.Pattern]) -> list[str]:
    kinds = ["matches shared pattern %d" % i for i, p in enumerate(patterns, 1) if p.search(line)]
    if privacy.mask(line) != line:
        kinds.append("privacy.mask would change it")
    if any(rx.search(line) for rx in EXACT_DATES):
        kinds.append("exact date")
    if TIME.search(line):
        kinds.append("time of day")
    return kinds


def scan_text(text: str, patterns: list[re.Pattern]) -> list[tuple[int, str]]:
    """(line number, kind) for every problem in one file's text. Line 0 = found only in the joined text view."""
    hits: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        hits.extend((n, k) for k in _problems(line, patterns))
        for v in _decoded_variants(line):
            if any(h in v for h in HIDDEN) or privacy.VIN_LIKE.search(v) or _problems(v, patterns):
                hits.append((n, "identifier, path or date in UTF-16 or hex-wrapped text"))
                break
    if not hits:
        for view in text_views(text):
            hits.extend((0, k + " (in the text with markup removed)") for k in _view_problems(view, patterns))
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
    def walk_error(err: OSError) -> None:
        problems.append("%s: cannot read (%s)" % (err.filename, err.strerror))

    for dirpath, dirs, names in os.walk(out_dir, onerror=walk_error):
        for name in sorted(names + [d for d in dirs if os.path.islink(os.path.join(dirpath, d))]):
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                problems.append("%s: symlink in the output (not scanned through; the build makes none)"
                                % os.path.relpath(path, out_dir))
                continue
            files += 1
            rel = os.path.relpath(path, out_dir)
            problems.extend("%s:%d: %s" % (rel, n, kind) for n, kind in scan_text(read_output(path), patterns))
    if files == 0:
        problems.append("%s: no files to scan" % out_dir)
    return problems

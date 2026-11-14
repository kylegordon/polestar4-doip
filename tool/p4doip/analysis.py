"""Offline analysis helpers behind `p4 flips`, `p4 changes` and `p4 findvalue`.

Pure functions over snapshot dicts ({"MOD:DID": hex}) and watch-log lines; cli.py does the file lookup and printing.
Nothing here touches the car."""
import re

# DIDs that tick on their own: clocks and counters (DD00-DD02), the rolling logs (D200-D2FF) and 9007.
NOISE_DIDS = {0xDD00, 0xDD01, 0xDD02, 0x9007}
NOISE_RANGE = (0xD200, 0xD2FF)


def is_noise(key: str) -> bool:
    did = int(key.split(":")[1], 16)
    return did in NOISE_DIDS or NOISE_RANGE[0] <= did <= NOISE_RANGE[1]


def shorten(text: str, width: int | None) -> str:
    if width is None or width < 3 or len(text) <= width:
        return text
    return text[:width - 2] + ".."


def flips(snaps: list[dict], include_noise: bool = False, stats: dict | None = None) -> list[tuple[str, list[str]]]:
    """Keys whose value alternates over the snapshots: even positions all equal, odd positions all equal, and the
    two differ (A==C!=B, or A==C!=B==D with four). Keys missing from any snapshot are skipped.
    Returns (key, [value per snapshot]) sorted by key."""
    if len(snaps) < 3:
        raise ValueError("flips needs at least three snapshots")
    out = []
    if stats is not None:
        stats["skipped"] = len(set(snaps[0]).union(*snaps[1:]) - set(snaps[0]).intersection(*snaps[1:]))
    for key in sorted(set(snaps[0]).intersection(*snaps[1:])):
        vals = [s[key] for s in snaps]
        if len(set(vals[0::2])) == 1 and len(set(vals[1::2])) == 1 and vals[0] != vals[1]:
            if include_noise or not is_noise(key):
                out.append((key, vals))
    return out


CHANGE_LINE = re.compile(r"^(?:\d{4}-\d\d-\d\dT)?(\d\d:\d\d:\d\d)(?:Z|[+-]\d\d:\d\d)? (\S+) CHANGE (.+?) -> (.*?)(?:  \[(.*)\])?$")
HIDDEN_LINE = re.compile(r" (?:MUTED after|noisy|baseline-noise) ")
HMS = re.compile(r"^\d\d:\d\d:\d\d$")


def check_hms(text: str | None, what: str) -> str | None:
    if text is not None and not HMS.match(text):
        raise SystemExit("%s must be HH:MM:SS, got %r" % (what, text))
    return text


def _hex_bytes(text: str) -> bytes | None:
    try:
        return bytes.fromhex(text)
    except ValueError:
        return None


def byte_jitter(old: str, new: str) -> int | None:
    """Size of a change in counts: the smallest of the largest per-byte step and the BE and LE integer steps,
    so one count on one field and a carry (01ff -> 0200) both read as 1. None when the values are not same-length
    hex (a state change such as 'no response'): always significant."""
    a, b = _hex_bytes(old), _hex_bytes(new)
    if a is None or b is None or len(a) != len(b) or not a:
        return None
    return min(max(abs(x - y) for x, y in zip(a, b)),
               abs(int.from_bytes(a, "big") - int.from_bytes(b, "big")),
               abs(int.from_bytes(a, "little") - int.from_bytes(b, "little")))


def changes(lines, since: str | None = None, until: str | None = None, keys: set[str] | None = None,
            significant: int | None = None, stats: dict | None = None) -> list[tuple[str, str, str, str, str]]:
    """(time, key, old, new, decode) for each CHANGE line, filtered by clock time (HH:MM:SS, no date or midnight
    handling), key, and change size (kept only when larger than `significant` counts). `stats`, if given, gets
    counts of lines not shown: hidden (MUTED/noisy/baseline-noise), unparsed (CHANGE-like but malformed) and
    jitter (dropped by `significant`)."""
    out = []
    st = stats if stats is not None else {}
    for k in ("hidden", "unparsed", "jitter"):
        st.setdefault(k, 0)
    for line in lines:
        m = CHANGE_LINE.match(line.rstrip("\n"))
        if not m:
            if HIDDEN_LINE.search(line):
                st["hidden"] += 1
            elif " CHANGE " in line:
                st["unparsed"] += 1
            continue
        t, key, old, new, dec = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5) or ""
        if (since and t < since) or (until and t > until) or (keys and key not in keys):
            continue
        if significant is not None:
            size = byte_jitter(old, new)
            if size is not None and size <= significant:
                st["jitter"] += 1
                continue
        out.append((t, key, old, new, dec))
    return out


# (label, scale, offset): decoded = raw * scale + offset. The usual automotive packings.
TRANSFORMS = [
    ("raw", 1, 0), ("raw*2", 2, 0), ("raw*10", 10, 0), ("raw*100", 100, 0),
    ("raw/2", 0.5, 0), ("raw/10", 0.1, 0), ("raw/100", 0.01, 0),
    ("raw-40", 1, -40), ("raw+40", 1, 40),
    ("raw/2-40", 0.5, -40), ("raw/2+40", 0.5, 40), ("raw*2-40", 2, -40), ("raw*2+40", 2, 40),
    ("raw/10-273.15 (Kelvin*10)", 0.1, -273.15),
]
WIDTHS = (1, 2, 4)


def decodings(data: bytes, target: float, tol: float = 0.5):
    """Every (offset, width, endian, transform label, decoded value) in `data` whose decoded value is within
    tolerance of `target`. The tolerance is half the transform's step, capped at `tol`."""
    for width in WIDTHS:
        for order in ("be",) if width == 1 else ("be", "le"):
            for off in range(len(data) - width + 1):
                raw = int.from_bytes(data[off:off + width], "big" if order == "be" else "little")
                for label, scale, add in TRANSFORMS:
                    val = raw * scale + add
                    if abs(val - target) <= min(abs(scale) / 2, tol) + 1e-9:
                        yield off, width, order, label, val


def _fmt(x: float) -> str:
    return ("%.4f" % x).rstrip("0").rstrip(".")


def findvalue(a: dict, x: float, b: dict | None = None, y: float | None = None, tol: float = 0.5):
    """Positions where a value decodes to x in `a` (and, with `b`, to y in `b` at the same position under the same
    encoding). Returns (key, "u16be raw/10 @2", decoded_a, decoded_b or None) sorted by key then position."""
    out = []
    for key in sorted(a):
        da = _hex_bytes(a[key])
        if not da:
            continue
        hits_a = {(o, w, e, lab): v for o, w, e, lab, v in decodings(da, x, tol)}
        if b is None:
            out += [(key, _where(*h), v, None) for h, v in hits_a.items()]
            continue
        db = _hex_bytes(b.get(key, ""))
        if not db or y is None:
            continue
        hits_b = {(o, w, e, lab): v for o, w, e, lab, v in decodings(db, y, tol)}
        out += [(key, _where(*h), v, hits_b[h]) for h, v in hits_a.items() if h in hits_b]
    return out


def _where(off: int, width: int, order: str, label: str) -> str:
    return "u%d%s %s @%d" % (width * 8, "" if width == 1 else order, label, off)


def fmt_hit(hit) -> str:
    key, where, va, vb = hit
    vals = _fmt(va) if vb is None else "%s -> %s" % (_fmt(va), _fmt(vb))
    return "%s  %s  %s" % (key, where, vals)

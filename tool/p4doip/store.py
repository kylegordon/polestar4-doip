"""Where results live: runs/<YYYY-MM-DD>/ under the project root, one JSON object per line."""
import datetime
import glob
import json
import os
import re
import sys

from .client import blocked_reason, caution_reason, is_transient


def root() -> str:
    return os.environ.get("P4_ROOT", os.getcwd())


def run_dir(date: str | None = None) -> str:
    d = os.path.join(root(), "runs", date or datetime.date.today().isoformat())
    os.makedirs(d, exist_ok=True)
    return d


def now() -> str:
    """Wall-clock time for screen and log lines."""
    return datetime.datetime.now().strftime("%H:%M:%S")


def stamp() -> str:
    """Full local timestamp with UTC offset, for records."""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


REPAIR_MARKER = b'{"_p4_repaired": true}'


def append_jsonl(path: str, obj: dict) -> None:
    """Append one record. If a crash left the file without a trailing newline, close the line and write a
    repair marker first: the half-written record stays a broken (tolerated) line instead of swallowing the
    next record, and read_jsonl knows the break was produced by this function, not by random corruption."""
    line = json.dumps(obj, sort_keys=True).encode() + b"\n"
    with open(path, "a+b") as f:
        if f.tell():
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                f.write(b"\n" + REPAIR_MARKER + b"\n")
        f.write(line)


def read_jsonl(path: str) -> list[dict]:
    """Every JSON object in a JSONL file, in order.

    A crash can leave one truncated line. It is tolerated (with a warning) when it is the last line or when
    it is immediately followed by append_jsonl's repair marker; any other malformed line is still an error,
    so real damage is not hidden."""
    with open(path) as f:
        lines = f.readlines()
    out = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            following = lines[i + 1].strip() if i + 1 < len(lines) else ""
            tail_empty = all(not rest.strip() for rest in lines[i + 1:])
            if tail_empty or following == REPAIR_MARKER.decode():
                print("warning: %s line %d: ignoring a truncated record (%s)" % (path, i + 1, e),
                      file=sys.stderr, flush=True)
                continue
            raise ValueError("%s line %d is not JSON: %s" % (path, i + 1, e)) from e
        if obj.get("_p4_repaired"):
            continue
        out.append(obj)
    return out


def scan_path(target: int, date: str | None = None) -> str:
    return os.path.join(run_dir(date), "scan-%04X.jsonl" % target)


# "hazard": the module (or gateway) stopped answering right after this DID in a paced scan; it outranks
# everything so that no later answer makes a scan read it again.
RANK = {"hazard": 3, "ok": 2, "nrc": 1, "nack": 1, "timeout": 0}


def retryable(rec: dict) -> bool:
    """True when the record is a transient refusal (or was marked so) and must be asked again next run."""
    if rec.get("retryable"):
        return True
    code = rec.get("code")
    if rec.get("status") != "nrc" or code is None:
        return False
    try:
        return is_transient(int(code, 16) if isinstance(code, str) else int(code))
    except (TypeError, ValueError):
        return False


def _timestamp(rec: dict):
    t = rec.get("t")
    if not isinstance(t, str):
        return None
    try:
        return datetime.datetime.fromisoformat(t)
    except ValueError:
        return None


def _recent(rec: dict, days: float, now: datetime.datetime) -> bool:
    t = _timestamp(rec)
    if t is None:
        return False
    if t.tzinfo is None:
        t = t.astimezone()  # legacy records without an offset: interpret as local time
    return (now - t).total_seconds() <= days * 86400


def done_dids(scans: dict[int, dict], rescan: bool = False, skip_silent_after: float | None = None,
              now: datetime.datetime | None = None) -> set[int]:
    """DIDs a scan may skip: hazards forever; OK and definitive NRCs unless --rescan; and, with
    --skip-silent-after, timeouts recorded within that many days. Transient NRCs are never settled."""
    done = {d for d, r in scans.items() if r["status"] == "hazard"}
    if rescan:
        return done
    now = now or datetime.datetime.now().astimezone()
    for d, r in scans.items():
        if r["status"] in ("ok", "nrc") and not retryable(r):
            done.add(d)
        elif r["status"] == "timeout" and skip_silent_after and _recent(r, skip_silent_after, now):
            done.add(d)
    return done


_SCANS_CACHE: dict[tuple[str, int, str | None], tuple[list[tuple[str, float]], dict[int, dict]]] = {}


def load_scans(target: int, day: str | None = None) -> dict[int, dict]:
    """Best recorded result per DID for a module, across every run day (or just one day with `day`).

    A DID that has ever answered OK stays OK (later refusals or timeouts are the car's state, not
    the DID going away); a timeout never replaces a definite answer. Among equals the latest wins.
    Cached against the scan files' mtimes (new appends invalidate): do not mutate the returned dict.
    """
    files = [(p, os.stat(p).st_mtime) for p in sorted(glob.glob(os.path.join(root(), "runs", day or "*", "scan-%04X.jsonl" % target)))]
    key = (root(), target, day)
    hit = _SCANS_CACHE.get(key)
    if hit is not None and files == hit[0]:
        return hit[1]
    out: dict[int, dict] = {}
    for path, _ in files:
        for rec in read_jsonl(path):
            if "did" not in rec:
                continue  # run header
            did = int(rec["did"], 16)
            if did not in out or RANK[rec["status"]] >= RANK[out[did]["status"]]:
                out[did] = rec
            elif retryable(out[did]) and rec["status"] == "nrc" and not retryable(rec):
                out[did] = rec  # a definitive refusal replaces an older transient one
    _SCANS_CACHE[key] = (files, out)
    return out


def known_ok(target: int, allow_caution: bool = False) -> list[int]:
    """DIDs that answered OK on this module, minus blocked reads (an old or hand-made record must not revive
    one) and, unless allowed, caution reads."""
    return sorted(d for d, r in load_scans(target).items()
                  if r["status"] == "ok" and not blocked_reason(target, d)
                  and (allow_caution or not caution_reason(target, d)))


LEGACY = re.compile(r"^([0-9A-F]{4}) ([0-9A-F]{4}) (OK ([0-9a-f]*)|NRC ([0-9A-F]{2})|NACK ([0-9A-F]{2})|no response)\s*$")


def parse_legacy_line(line: str) -> dict | None:
    """'1601 2B24 OK 00010000' / '... NRC 31' / '... NACK 03' / '... no response' from 2026-11-10 reads."""
    m = LEGACY.match(line.strip())
    if not m:
        return None
    rec = {"tgt": m.group(1), "did": m.group(2)}
    if m.group(3).startswith("OK"):
        rec.update(status="ok", data=m.group(4))
    elif m.group(5):
        rec.update(status="nrc", code=m.group(5))
    elif m.group(6):
        rec.update(status="nack", code=m.group(6))
    else:
        rec.update(status="timeout")
    return rec


def import_legacy(paths: list[str], date: str) -> dict[str, int]:
    """Convert legacy sweep text files into runs/<date>/scan-<TGT>.jsonl. Returns counts per module."""
    counts: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()
    for path in paths:
        with open(path) as f:
            for line in f:
                rec = parse_legacy_line(line)
                if rec is None or (rec["tgt"], rec["did"]) in seen:
                    continue
                seen.add((rec["tgt"], rec["did"]))
                rec.update(t=date, src=os.path.basename(path))
                append_jsonl(scan_path(int(rec["tgt"], 16), date), rec)
                counts[rec["tgt"]] = counts.get(rec["tgt"], 0) + 1
    return counts

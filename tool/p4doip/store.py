"""Where results live: runs/<YYYY-MM-DD>/ under the project root, one JSON object per line."""
import datetime
import glob
import json
import os
import re

from .client import blocked_reason


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


def append_jsonl(path: str, obj: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")


def read_jsonl(path: str) -> list[dict]:
    out = []
    with open(path) as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError("%s line %d is not JSON: %s" % (path, n, e)) from e
    return out


def scan_path(target: int, date: str | None = None) -> str:
    return os.path.join(run_dir(date), "scan-%04X.jsonl" % target)


RANK = {"ok": 2, "nrc": 1, "nack": 1, "timeout": 0}


def load_scans(target: int) -> dict[int, dict]:
    """Best recorded result per DID for a module, across every run day.

    A DID that has ever answered OK stays OK (later refusals or timeouts are the car's state, not
    the DID going away); a timeout never replaces a definite answer. Among equals the latest wins.
    """
    out: dict[int, dict] = {}
    for path in sorted(glob.glob(os.path.join(root(), "runs", "*", "scan-%04X.jsonl" % target))):
        for rec in read_jsonl(path):
            if "did" not in rec:
                continue  # run header
            did = int(rec["did"], 16)
            if did not in out or RANK[rec["status"]] >= RANK[out[did]["status"]]:
                out[did] = rec
    return out


def known_ok(target: int) -> list[int]:
    """DIDs that answered OK on this module, minus blocked reads (an old or hand-made record must not revive one)."""
    return sorted(d for d, r in load_scans(target).items() if r["status"] == "ok" and not blocked_reason(target, d))


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

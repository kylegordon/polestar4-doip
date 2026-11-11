"""p4 — read-only DoIP discovery tools for the Polestar 4. See README.md."""
import argparse
import glob
import json
import os
import sys
import time

from . import decode, store
from .client import NACK_UNKNOWN_TARGET, ActivationRefused, ConnectionLost, DoIP, blocked_reason

IDENTITY_DIDS = [0xF186, 0xF187, 0xF188, 0xF189, 0xF18A, 0xF18B, 0xF18C, 0xF191, 0xF192, 0xF193, 0xF194,
                 0xF195, 0xF197, 0xF199, 0xF19D, 0xF120, 0xF121, 0xF125, 0xF12A, 0xF12B, 0xF12E,
                 0xF1A0, 0xF1A1, 0xF1A5, 0xF1AA, 0xF1AB, 0xF1AE, 0xDD00, 0xDD01, 0xDD02, 0xDD0A, 0xD134]
# Ordered by where answers clustered on 2026-11-10 (8,192 DIDs, ~6 min at ~24/s). Those reads were
# not exhaustive, so an empty result here does not mean an empty module.
DEFAULT_RANGES = ("D900-DAFF,DD00-DDFF,ED00-EDFF,F100-F1FF,FD00-FEFF,D000-D2FF,E100-E5FF,EE00-EFFF,"
                  "4000-4AFF,2B00-2BFF,3000-30FF,9000-90FF,9800-98FF")
USAGE_MODE_DID = 0xDD0A  # answers on every module seen so far; recorded so results from different car states can be told apart


VIN_DID = 0xF190


def stored_value(did: int, payload: bytes) -> str:
    """Hex of a DID value as written to runs/ and logs. The VIN (F190) is recorded as zeros of the same length."""
    return "00" * len(payload) if did == VIN_DID else payload.hex()


def hexint(s: str) -> int:
    return int(s, 16)


def parse_ranges(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        lo, hi = int(a, 16), int(b or a, 16)
        if lo > hi or hi > 0xFFFF:
            raise SystemExit("bad range %r" % part)
        out += range(lo, hi + 1)
    return out


def catalogue_modules() -> dict[int, str]:
    path = os.path.join(store.root(), "catalogue", "modules.yaml")
    if not os.path.exists(path):
        return {}
    import yaml
    with open(path) as f:
        return {int(m["addr"], 16): "%s (%s)" % (m.get("label", "?"), m.get("status", "?")) for m in yaml.safe_load(f)}


def targets(args) -> list[int]:
    """Module addresses from the command line; 'all' means every module in catalogue/modules.yaml."""
    out: list[int] = []
    for t in args.targets:
        out += sorted(catalogue_modules()) if t.lower() == "all" else [int(t, 16)]
    if not out:
        raise SystemExit("no modules given (and catalogue/modules.yaml is empty)")
    return out


def connect(args, forever: bool = False) -> DoIP:
    """Connect, retrying while the gateway refuses us (it allows one tester at a time)."""
    c = DoIP(args.host, args.port)
    attempt = 0
    while True:
        try:
            return c.connect()
        except (ConnectionLost, ActivationRefused) as e:
            attempt += 1
            if not forever and attempt > args.retries:
                raise SystemExit("cannot connect to %s: %s (is another diagnostic tool or another p4 still connected?)" % (args.host, e))
            print("%s connect failed (%s); retrying in %gs" % (store.now(), e, args.retry_wait), file=sys.stderr, flush=True)
            time.sleep(args.retry_wait)


class Link:
    """A connection that reconnects and repeats the request if the gateway drops it."""

    def __init__(self, args):
        self.args = args
        self.c = connect(args)

    def do(self, method: str, *a, **kw):
        for _ in range(3):
            try:
                return getattr(self.c, method)(*a, **kw)
            except ConnectionLost as e:
                print("%s connection lost (%s); reconnecting" % (store.now(), e), file=sys.stderr, flush=True)
                self.c = connect(self.args)
        raise SystemExit("the connection keeps dropping; giving up. Results so far are saved.")

    def close(self):
        self.c.close()


def printable(b: bytes) -> str:
    t = b.rstrip(b"\x00 ")
    return t.decode("ascii") if t and all(32 <= c < 127 for c in t) else ""


def explain_nack(code: int, target: int) -> str:
    if code == NACK_UNKNOWN_TARGET:
        return "gateway NACK 03 for %04X: module address does not exist" % target
    return "gateway NACK %02X for %04X: not 'unknown address' — routing lost or module unreachable/asleep" % (code, target)


# -- commands -------------------------------------------------------------
def cmd_discover(args):
    """Physical TesterPresent to every address: finds modules the 1FFF broadcast misses."""
    out = os.path.join(store.run_dir(), "discover.jsonl")
    link = Link(args)
    store.append_jsonl(out, {"run": store.stamp(), "start": "%04X" % args.start, "end": "%04X" % args.end})
    present, silent = [], []
    odd_nacks: dict[int, int] = {}
    for addr in range(args.start, args.end + 1):
        r = link.do("tester_present", addr, args.timeout)
        if r.status in ("ok", "nrc"):
            present.append(addr)
        elif r.status == "timeout":
            silent.append(addr)
        elif r.code != NACK_UNKNOWN_TARGET:
            odd_nacks[r.code] = odd_nacks.get(r.code, 0) + 1
        if not (r.status == "nack" and r.code == NACK_UNKNOWN_TARGET):
            store.append_jsonl(out, {"t": store.stamp(), "tgt": "%04X" % addr, "status": r.status,
                                     "code": None if r.code is None else "%02X" % r.code})
    link.close()
    known = catalogue_modules()
    print("answering: %d  silent (no NACK, no answer): %d" % (len(present), len(silent)))
    for addr in present:
        print("  %04X %s" % (addr, known.get(addr, "** not in catalogue/modules.yaml **")))
    for addr in silent:
        print("  %04X silent %s" % (addr, known.get(addr, "")))
    for code, n in sorted(odd_nacks.items()):
        print("WARNING: %d addresses got gateway NACK %02X (not 'unknown address'); this census is not reliable" % (n, code))
    missing = sorted(a for a in known if args.start <= a <= args.end and a not in present)
    if missing:
        print("in catalogue but not answering: " + " ".join("%04X" % a for a in missing))


def cmd_identify(args):
    link = Link(args)
    for tgt in targets(args):
        res = {}
        for did in IDENTITY_DIDS:
            r = link.do("read_did", tgt, did)
            if r.status == "ok":
                res["%04X" % did] = r.payload.hex()
                print("%04X %04X %s %s" % (tgt, did, r.payload.hex(), printable(r.payload)))
        if not res:
            print("%04X: no identity DIDs answered (nothing written)" % tgt)
            continue
        with open(os.path.join(store.run_dir(), "identify-%04X.json" % tgt), "w") as f:
            json.dump(res, f, indent=1, sort_keys=True)
    link.close()


def cmd_scan(args):
    """Try a list of DIDs on one module. DIDs with a definite answer (OK or NRC) in any earlier run are skipped."""
    if args.like is not None:
        dids = store.known_ok(args.like)
        if not dids:
            raise SystemExit("no recorded OK DIDs for %04X to copy" % args.like)
    else:
        dids = parse_ranges(args.ranges)
    done = set() if args.rescan else {d for d, r in store.load_scans(args.target).items() if r["status"] in ("ok", "nrc")}
    todo = [d for d in dids if d not in done]
    for d in [d for d in todo if blocked_reason(args.target, d)]:
        print("skipping %s" % blocked_reason(args.target, d), file=sys.stderr, flush=True)
        todo.remove(d)
    path = store.scan_path(args.target)
    print("%04X: %d DIDs to try (%d already answered in earlier runs) -> %s" % (args.target, len(todo), len(dids) - len(todo), path),
          file=sys.stderr, flush=True)
    if not todo:
        return
    link = Link(args)
    mode = link.do("read_did", args.target, USAGE_MODE_DID)
    if mode.status == "nack":
        raise SystemExit(explain_nack(mode.code, args.target))
    store.append_jsonl(path, {"run": store.stamp(), "usage_mode": mode.payload.hex() if mode.status == "ok" else mode.text()})
    ok = 0
    held: list[dict] = []  # timeouts not yet proven to come from a live module

    def module_alive() -> bool:
        return link.do("tester_present", args.target).status in ("ok", "nrc")

    def settle_held(at_did: int):
        if not held:
            return
        if module_alive():
            for rec in held:
                store.append_jsonl(path, rec)
            held.clear()
        else:
            raise SystemExit("%04X stopped answering near DID %04X; the last %d timeouts were not recorded. Re-run to resume."
                             % (args.target, at_did, len(held)))

    start = time.monotonic()
    for i, did in enumerate(todo, 1):
        r = link.do("read_did", args.target, did, args.timeout)
        rec = {"t": store.stamp(), "tgt": "%04X" % args.target, "did": "%04X" % did, "status": r.status}
        if r.status == "nack":
            raise SystemExit(explain_nack(r.code, args.target))
        if r.status == "timeout":
            held.append(rec)
            if len(held) >= 5:
                settle_held(did)
        else:
            for h in held:  # an answer proves the module was alive, so the timeouts before it are real
                store.append_jsonl(path, h)
            held.clear()
            if r.status == "ok":
                # F190 is the VIN: record that it answers, not its value (runs/ may be shared).
                rec["data"] = stored_value(did, r.payload)
                ok += 1
                print("%04X %04X OK %s" % (args.target, did, rec["data"]), flush=True)
            else:
                rec["code"] = "%02X" % r.code
            store.append_jsonl(path, rec)
        if i % 500 == 0:
            rate = i / (time.monotonic() - start)
            print("  %d/%d, %d OK, %.0f/s, ~%.0f min left" % (i, len(todo), ok, rate, (len(todo) - i) / rate / 60),
                  file=sys.stderr, flush=True)
    settle_held(todo[-1])
    link.close()
    print("%04X: %d new OK; %d known OK in total" % (args.target, ok, len(store.known_ok(args.target))))


def cmd_dtc(args):
    """Stored DTCs (19 02 FF) and supported DTCs (19 0A): what a module monitors hints at what it is."""
    link = Link(args)
    for tgt in targets(args):
        for name, req in (("stored", b"\x19\x02\xff"), ("supported", b"\x19\x0a")):
            r = link.do("request", tgt, req, 3.0)
            rec = {"t": store.stamp(), "kind": name, "status": r.status}
            if r.status == "ok":
                body = r.data[3:]
                recs = [body[i:i + 4] for i in range(0, len(body) - 3, 4)]
                print("%04X %s: %d DTCs" % (tgt, name, len(recs)))
                for d in recs:
                    print("  %s status %02X" % (d[:3].hex().upper(), d[3]))
                rec["raw"] = r.data.hex()
            else:
                print("%04X %s: %s" % (tgt, name, r.text()))
                rec["code"] = None if r.code is None else "%02X" % r.code
            store.append_jsonl(os.path.join(store.run_dir(), "dtc-%04X.jsonl" % tgt), rec)
    link.close()


def cmd_snapshot(args):
    """Read every known-OK DID of the given modules once and save it under a name."""
    link = Link(args)
    snap = {}
    for tgt in targets(args):
        dids = store.known_ok(tgt)
        if not dids:
            print("%04X: no known OK DIDs (run scan first)" % tgt, file=sys.stderr)
        for did in dids:
            r = link.do("read_did", tgt, did)
            snap["%04X:%04X" % (tgt, did)] = stored_value(did, r.payload) if r.status == "ok" else r.text()
    link.close()
    if not snap:
        raise SystemExit("nothing to snapshot")
    path = os.path.join(store.run_dir(), "snap-%s.json" % args.name)
    with open(path, "w") as f:
        json.dump({"t": store.stamp(), "values": snap}, f, indent=1, sort_keys=True)
    print("%d values -> %s" % (len(snap), path))


def diff_snapshots(a: dict, b: dict) -> list[tuple[str, str | None, str | None]]:
    keys = sorted(set(a) | set(b))
    return [(k, a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)]


def find_snapshot(name: str) -> str:
    if os.path.exists(name):
        return name
    found = sorted(glob.glob(os.path.join(store.root(), "runs", "*", "snap-%s.json" % name)))
    if not found:
        raise SystemExit("no snapshot named %r in runs/*/" % name)
    return found[-1]  # the most recent day


def cmd_diff(args):
    def load(name):
        with open(find_snapshot(name)) as f:
            return json.load(f)["values"]
    sigs = decode.index(decode.load()) if args.labels else {}
    changes = diff_snapshots(load(args.a), load(args.b))
    for key, old, new in changes:
        tgt, did = (int(x, 16) for x in key.split(":"))
        label = "  [%s]" % ", ".join(s["name"] for s in sigs[(tgt, did)]) if (tgt, did) in sigs else ""
        print("%s %s -> %s%s" % (key, old, new, label))
    print("%d changed" % len(changes))


def parse_watch_specs(specs: list[str]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for spec in specs:
        tgt_s, _, dids_s = spec.partition(":")
        tgt = int(tgt_s, 16)
        dids = [int(d, 16) for d in dids_s.split(",")] if dids_s else store.known_ok(tgt)
        if not dids:
            raise SystemExit("%04X: no known OK DIDs; give %04X:DID,DID or run scan first" % (tgt, tgt))
        for d in [d for d in dids if blocked_reason(tgt, d)]:
            print("skipping %s" % blocked_reason(tgt, d), file=sys.stderr, flush=True)
            dids.remove(d)
        pairs += [(tgt, d) for d in dids]
    if not pairs:
        raise SystemExit("nothing left to watch")
    return pairs


def cmd_watch(args):
    """Poll DIDs and print only changes.

    For the first --baseline seconds leave the car alone: anything that changes then is background
    noise and is hidden from the screen for the rest of the run (still logged). After the baseline
    nothing is hidden automatically, unless --mute N is given (N changes within 10 s).
    """
    pairs = [p for p in parse_watch_specs(args.specs) if "%04X:%04X" % p not in args.hide and "%04X" % p[1] not in args.hide]
    sigs = decode.index(decode.load())
    log = os.path.join(store.run_dir(), "watch-%s.log" % (args.name or time.strftime("%H%M%S")))
    last: dict[tuple[int, int], str] = {}
    hist: dict[tuple[int, int], list[float]] = {}
    noisy: set[tuple[int, int]] = set()

    def emit(line, show=True):
        line = "%s %s" % (store.now(), line)
        with open(log, "a") as f:
            f.write(line + "\n")
        if show:
            print(line, flush=True)

    c = None
    passes = 0
    started = None
    baseline_done = args.baseline <= 0
    while args.passes is None or passes < args.passes:
        try:
            if c is None:
                c = connect(args, forever=True)
                emit("connected: %d reads per pass -> %s" % (len(pairs), log))
                if started is None:
                    started = time.monotonic()
                    if not baseline_done:
                        emit("baseline: leave the car alone for %gs" % args.baseline)
            for key in pairs:
                r = c.read_did(*key)
                val = stored_value(key[1], r.payload) if r.status == "ok" else r.text()
                if not baseline_done and time.monotonic() - started >= args.baseline:
                    baseline_done = True
                    emit("baseline over: %d noisy values hidden. Go." % len(noisy))
                if val == last.get(key):
                    continue
                name = "%04X:%04X" % key
                extra = "  [%s]" % decode.describe(sigs[key], r.payload) if r.status == "ok" and key in sigs else ""
                if key not in last:
                    emit("%s %s%s" % (name, val, extra), show=args.show_first)
                elif key in noisy:
                    emit("%s noisy %s -> %s" % (name, last[key], val), show=False)
                elif not baseline_done:
                    if r.status == "ok":
                        noisy.add(key)
                    emit("%s baseline-noise %s -> %s" % (name, last[key], val), show=False)
                else:
                    now = time.monotonic()
                    if r.status == "ok":
                        hist[key] = [t for t in hist.get(key, []) if now - t < 10] + [now]
                    if args.mute and len(hist.get(key, [])) > args.mute:
                        noisy.add(key)
                        emit("%s MUTED after %s -> %s (changing more than %d times in 10s; still logged)" % (name, last[key], val, args.mute))
                    else:
                        emit("%s CHANGE %s -> %s%s" % (name, last[key], val, extra))
                last[key] = val
            passes += 1
            time.sleep(args.interval)
        except ConnectionLost as e:
            emit("ERROR connection lost: %s; reconnecting" % e)
            c = None
    if c:
        c.close()


def cmd_mark(args):
    text = " ".join(args.text)
    os.makedirs(os.path.join(store.root(), "local"), exist_ok=True)
    with open(os.path.join(store.root(), "local", "session-log.md"), "a") as f:
        f.write("- %s %s\n" % (store.now(), text))
    store.append_jsonl(os.path.join(store.run_dir(), "marks.jsonl"), {"t": store.stamp(), "mark": text})
    print("- %s %s" % (store.now(), text))


def cmd_known(args):
    for tgt in targets(args):
        scans = store.load_scans(tgt)
        ok = [d for d, r in sorted(scans.items()) if r["status"] == "ok"]
        refused = sorted(d for d, r in scans.items() if r["status"] == "nrc" and r.get("code") != "31")
        print("%04X: %d tried, %d OK, %d refused (exist, but not readable in this state)" % (tgt, len(scans), len(ok), len(refused)))
        if args.list:
            for d in ok:
                print("  %04X %s" % (d, scans[d].get("data", "")))
            for d in refused:
                print("  %04X NRC %s" % (d, scans[d]["code"]))


def cmd_import_legacy(args):
    paths = sorted(glob.glob(os.path.join(store.root(), "local", "reads", "*sweep*.txt"))
                   + glob.glob(os.path.join(store.root(), "local", "reads", "unknown-*.txt"))
                   + glob.glob(os.path.join(store.root(), "local", "reads", "*-probe.txt")))
    existing = glob.glob(os.path.join(store.root(), "runs", args.date, "scan-*.jsonl"))
    if existing:
        raise SystemExit("runs/%s already has scan files; delete them to re-import" % args.date)
    for tgt, n in sorted(store.import_legacy(paths, args.date).items()):
        print("%s: %d DIDs" % (tgt, n))


def cmd_signals(args):
    sigs = decode.load()
    for s in sigs:
        print("%-9s %s %-28s %s %s" % (s["module"], s["did"], s["id"], s["confidence"], s["name"]))
    print("%d signals" % len(sigs))


def main(argv=None):
    p = argparse.ArgumentParser(prog="p4", description=__doc__)
    p.add_argument("--host", default=os.environ.get("P4_HOST", "169.254.19.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("P4_PORT", "13400")))
    p.add_argument("--retries", type=int, default=3, help="connection attempts before giving up")
    p.add_argument("--retry-wait", type=float, default=5.0, help="seconds between connection attempts")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("discover", help="find module addresses")
    s.add_argument("--start", type=hexint, default=0x1000)
    s.add_argument("--end", type=hexint, default=0x1FFE)
    s.add_argument("--timeout", type=float, default=0.3)
    s.set_defaults(fn=cmd_discover)

    s = sub.add_parser("identify", help="read part numbers / serials")
    s.add_argument("targets", nargs="+", help="module addresses, or 'all'")
    s.set_defaults(fn=cmd_identify)

    s = sub.add_parser("scan", help="find which DIDs a module answers")
    s.add_argument("target", type=hexint)
    s.add_argument("--ranges", default=DEFAULT_RANGES)
    s.add_argument("--like", type=hexint, help="try the DIDs that answered on this other module")
    s.add_argument("--timeout", type=float, default=0.5)
    s.add_argument("--rescan", action="store_true", help="try DIDs again even if an earlier run answered them")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("dtc", help="read stored and supported DTCs")
    s.add_argument("targets", nargs="+", help="module addresses, or 'all'")
    s.set_defaults(fn=cmd_dtc)

    s = sub.add_parser("snapshot", help="save all known DIDs of some modules")
    s.add_argument("name")
    s.add_argument("targets", nargs="+", help="module addresses, or 'all'")
    s.set_defaults(fn=cmd_snapshot)

    s = sub.add_parser("diff", help="compare two snapshots (names or file paths)")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--no-labels", dest="labels", action="store_false")
    s.set_defaults(fn=cmd_diff)

    s = sub.add_parser("watch", help="poll and print changes")
    s.add_argument("specs", nargs="+", help="1601 (all known DIDs) or 1601:E37B,2B1A")
    s.add_argument("--interval", type=float, default=0.0, help="pause between passes, seconds")
    s.add_argument("--baseline", type=float, default=20.0, help="seconds of 'car left alone' used to hide background noise (0 = none)")
    s.add_argument("--mute", type=int, default=0, help="also hide a value after this many changes in 10s (0 = never)")
    s.add_argument("--hide", default="", type=lambda v: set(v.upper().split(",")) if v else set())
    s.add_argument("--show-first", action="store_true", help="print initial values too")
    s.add_argument("--name", help="log file suffix")
    s.add_argument("--passes", type=int, help="stop after N passes (default: run until stopped)")
    s.set_defaults(fn=cmd_watch)

    s = sub.add_parser("mark", help="add a timestamped line to local/session-log.md and runs/<date>/marks.jsonl")
    s.add_argument("text", nargs="+")
    s.set_defaults(fn=cmd_mark)

    s = sub.add_parser("known", help="what has been scanned on a module")
    s.add_argument("targets", nargs="+", help="module addresses, or 'all'")
    s.add_argument("--list", action="store_true")
    s.set_defaults(fn=cmd_known)

    s = sub.add_parser("import-legacy", help="convert local/reads/*sweep*.txt from 2026-11-10 into runs/")
    s.add_argument("--date", default="2026-11-10")
    s.set_defaults(fn=cmd_import_legacy)

    s = sub.add_parser("signals", help="list and validate catalogue/signals.yaml")
    s.set_defaults(fn=cmd_signals)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()

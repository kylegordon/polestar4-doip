"""p4 — read-only DoIP discovery tools for the Polestar 4. See README.md."""
import argparse
import csv
import datetime
import glob
import json
import os
import re
import signal
import struct
import sys
import time

import yaml

from . import __version__, analysis, decode, hazards, store
from .client import (NACK_UNKNOWN_TARGET, ActivationRefused, BlockedRead, CautionedRead, ConnectionLost, DoIP,
                     Result, blocked_reason, caution_reason, is_transient, nrc_name)
from .privacy import MASKED_DIDS, readable_runs, readable_text, stored_value

IDENTITY_DIDS = [0xF180, 0xF181, 0xF182, 0xF183, 0xF184, 0xF186, 0xF187, 0xF188, 0xF189, 0xF18A, 0xF18B,
                 0xF18C, 0xF18E, 0xF18F, 0xF191, 0xF192, 0xF193, 0xF194, 0xF195, 0xF196, 0xF197, 0xF198,
                 0xF199, 0xF19D,
                 0xF120, 0xF121, 0xF125, 0xF12A, 0xF12B, 0xF12E,
                 0xF1A0, 0xF1A1, 0xF1A5, 0xF1AA, 0xF1AB, 0xF1AE,
                 0xE103, 0xD0B5, 0xDD00, 0xDD01, 0xDD02, 0xDD0A, 0xD134]
# F182/F183/F18E/F18F are probes: defined by ISO 14229-1:2020 but not yet seen answering on this car
# (docs/did-identity.md). E103 (traceability) and D0B5 are identification-adjacent; see catalogue/dids.yaml.
# F190 (VIN) is deliberately not probed: it is masked and carries no identification value. It can still be
# read with `./p4 read MODULE:F190` (recorded as zeros). IDENTITY_SKIP documents the exclusion for the tests.
IDENTITY_SKIP = {0xF190}
# Ordered by where answers clustered on 2026-11-10 (8,192 DIDs, ~6 min at ~24/s). Those reads were
# not exhaustive, so an empty result here does not mean an empty module.
DEFAULT_RANGES = ("D900-DAFF,DD00-DDFF,ED00-EDFF,F100-F1FF,FD00-FEFF,D000-D2FF,E100-E5FF,EE00-EFFF,"
                  "4000-4AFF,2B00-2BFF,3000-30FF,9000-90FF,9800-98FF")
GATEWAY = 0x1001
USAGE_MODE_DID = 0xDD0A  # answers on every module seen so far; recorded so results from different car states can be told apart


# Masked DIDs and stored_value live in privacy.py; re-exported above so callers keep one import.


def hexint(s: str) -> int:
    return int(s, 16)


def add_json(parser) -> None:
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")


def parse_ranges(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if not part.strip():
            continue  # empty spec (a watch-only sweep slot) means no DIDs; stray commas are tolerated
        a, _, b = part.partition("-")
        try:
            lo, hi = int(a, 16), int(b or a, 16)
        except ValueError:
            raise SystemExit("bad range %r: expected a hex DID or LO-HI, e.g. E37B or E300-E4FF" % part)
        if lo > hi or hi > 0xFFFF:
            raise SystemExit("bad range %r: LO must be <= HI and both <= FFFF" % part)
        out += range(lo, hi + 1)
    return out


def parse_dids_file(path: str) -> list[int]:
    """DIDs from a text file: one or more per line, spaces or commas, `#` comments, ranges allowed."""
    try:
        with open(path) as f:
            text = f.read()
    except OSError as e:
        raise SystemExit("cannot read %s: %s" % (path, e))
    tokens = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].replace(",", " ")
        tokens += line.split()
    if not tokens:
        raise SystemExit("%s: no DIDs found" % path)
    out: list[int] = []
    for tok in tokens:
        if "-" in tok:
            out += parse_ranges(tok)
        else:
            try:
                out.append(int(tok, 16))
            except ValueError:
                raise SystemExit("%s: bad DID %r" % (path, tok))
    seen: set[int] = set()
    uniq: list[int] = []
    for d in out:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


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
    c = DoIP(args.host, args.port, allow_caution=getattr(args, "allow_caution", False))
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
                res["%04X" % did] = stored_value(did, r.payload)
                print("%04X %04X %s %s" % (tgt, did, res["%04X" % did],
                                           "" if did in MASKED_DIDS else printable(r.payload)))
        if not res:
            print("%04X: no identity DIDs answered (nothing written)" % tgt)
            continue
        with open(os.path.join(store.run_dir(), "identify-%04X.json" % tgt), "w") as f:
            json.dump(res, f, indent=1, sort_keys=True)
    link.close()


def cmd_whois(args):
    """One-shot profile of a module: usage mode, every identity DID that answers, DTC counts and the closest
    cousins in docs/did-map.csv. Masked DIDs (VIN, serials) are shown as zeros with no text."""
    tgt = args.target
    link = Link(args)
    tp = link.do("tester_present", tgt)
    if tp.status == "nack":
        raise SystemExit(explain_nack(tp.code, tgt))
    mode = link.do("read_did", tgt, USAGE_MODE_DID)
    names = decode.load_dids()
    doc = {"module": "%04X" % tgt,
           "usage_mode": mode.payload.hex() if mode.status == "ok" else mode.text(), "identity": [], "dtc": {},
           "similar": []}
    say = (lambda *a, **k: None) if getattr(args, "json", False) else print
    say("%04X: usage mode %s" % (tgt, doc["usage_mode"]))
    for did in IDENTITY_DIDS:
        r = link.do("read_did", tgt, did)
        if r.status != "ok":
            continue
        text = "" if did in MASKED_DIDS else printable(r.payload)
        doc["identity"].append({"did": "%04X" % did, "name": names.get(did, {}).get("name", "?"),
                                "data": stored_value(did, r.payload), "text": text})
        say("  %04X %-40s %s%s" % (did, doc["identity"][-1]["name"], doc["identity"][-1]["data"],
                                   "  " + text if text else ""))
    for kind, req in (("stored", b"\x19\x02\xff"), ("supported", b"\x19\x0a")):
        r = link.do("request", tgt, req, 3.0)
        if r.status == "ok":
            n = len(dtc_records(r.data))
            doc["dtc"][kind] = {"count": n}
            say("  %s DTCs: %d" % (kind, n))
        else:
            doc["dtc"][kind] = {"error": r.text()}
            say("  %s DTCs: %s" % (kind, r.text()))
    map_path = os.path.join(store.root(), "docs", "did-map.csv")
    rows = load_didmap().get("%04X" % tgt, []) if os.path.exists(map_path) else []
    if any(status == "ok" for _, status, _ in rows):
        for score, m, shared, only in similar_scores(tgt)[:3]:
            doc["similar"].append({"module": m, "score": round(score, 4), "shared": shared, "only_here": only})
            say("  similar: %s  %.2f  %d shared, %d only-here" % (m, score, shared, only))
    else:
        say("  not in did-map yet: run ./p4 scan %04X to fingerprint it" % tgt)
    link.close()
    if getattr(args, "json", False):
        print(json.dumps(doc, indent=1, sort_keys=True))


ADAPT_AFTER = 20        # consecutive silent DIDs before --adaptive-timeout shortens the read timeout
ADAPT_PROBE_EVERY = 50  # while shortened, every Nth DID still gets the full timeout as a probe


class AdaptiveTimeout:
    """Opt-in scan speed-up for long silent ranges (--adaptive-timeout).

    After ADAPT_AFTER consecutive timeouts the per-DID timeout drops to 40% of --timeout (at least 0.2 s);
    every ADAPT_PROBE_EVERYth DID scanned in that state still gets the full timeout, so a slow-but-alive
    module is not misrecorded as silent. Any non-timeout answer restores the full timeout. Nothing is
    recorded differently: timeouts are held and settled exactly as before."""

    def __init__(self, full: float):
        self.full = full
        self.short = max(0.2, full * 0.4)
        self.silent = 0    # consecutive timeouts so far
        self.probed = 0    # DIDs attempted at the short timeout since that state began

    def next(self) -> float:
        """Timeout for the next read."""
        if self.silent < ADAPT_AFTER:
            return self.full
        self.probed += 1
        return self.full if self.probed % ADAPT_PROBE_EVERY == 0 else self.short

    def seen(self, status: str) -> None:
        if status == "timeout":
            self.silent += 1
        else:  # ok, NRC, NACK: the module answered, so start over at the full timeout
            self.silent = self.probed = 0


RETRY_ATTEMPTS = 3


def read_with_retry(link: "Link", target: int, did: int, timeout: float) -> "Result":
    """Read one DID, retrying a transient NRC (busy / sequence error) a couple of times before recording it."""
    r = link.do("read_did", target, did, timeout)
    tries = 1
    while r.status == "nrc" and is_transient(r.code) and tries < RETRY_ATTEMPTS:
        time.sleep(0.2 * tries)
        r = link.do("read_did", target, did, timeout)
        tries += 1
    return r


def scan_core(args, target: int, dids: list[int], paced: float | None, timeout: float) -> int:
    """The scan proper, shared by cmd_scan and cmd_sweep: skip DIDs already answered in any earlier run (and
    blocked ones, recorded hazards and, with --skip-silent-after, recently silent ones), then read the rest
    into runs/<date>/scan-<TGT>.jsonl. Transient NRCs are retried in-process and never settle a DID."""
    scans = store.load_scans(target)
    hazards = {d for d, r in scans.items() if r["status"] == "hazard"}  # never read again, even with --rescan
    done = store.done_dids(scans, rescan=getattr(args, "rescan", False),
                           skip_silent_after=getattr(args, "skip_silent_after", None))
    for d in sorted(hazards & set(dids)):
        print("skipping %04X: recorded as a hazard (%s)" % (d, scans[d].get("why", "")), file=sys.stderr, flush=True)
    todo = [d for d in dids if d not in done]
    for d in [d for d in todo if blocked_reason(target, d)]:
        print("skipping %s" % blocked_reason(target, d), file=sys.stderr, flush=True)
        todo.remove(d)
    path = store.scan_path(target)
    print("%04X: %d DIDs to try (%d already answered in earlier runs) -> %s" % (target, len(todo), len(dids) - len(todo), path),
          file=sys.stderr, flush=True)
    if not todo:
        return 0
    if paced is not None:
        args.allow_caution = True  # careful mode is the designed way to test a caution DID one at a time
    elif not getattr(args, "allow_caution", False):
        for d in [d for d in todo if caution_reason(target, d)]:
            print("skipping %s (use --allow-caution or a paced scan to try it)" % caution_reason(target, d),
                  file=sys.stderr, flush=True)
            todo.remove(d)
    if not todo:
        return 0
    names = decode.load_dids() if getattr(args, "names", False) else {}
    link = Link(args)
    mode = link.do("read_did", target, USAGE_MODE_DID)
    if mode.status == "nack":
        raise SystemExit(explain_nack(mode.code, target))
    store.append_jsonl(path, {"v": 2, "tool": __version__, "commit": os.environ.get("P4_COMMIT", ""),
                              "run": store.stamp(), "usage_mode": mode.payload.hex() if mode.status == "ok" else mode.text(),
                              "timeout": timeout, "skip_silent_after": getattr(args, "skip_silent_after", None),
                              "paced": paced, "rescan": bool(getattr(args, "rescan", False)),
                              "adaptive_timeout": bool(getattr(args, "adaptive_timeout", False))})
    if paced is not None:
        return paced_scan(args, target, link, todo, path, paced, timeout)
    adapt = AdaptiveTimeout(timeout) if getattr(args, "adaptive_timeout", False) else None
    ok = 0
    held: list[dict] = []  # timeouts not yet proven to come from a live module

    def module_alive() -> bool:
        return link.do("tester_present", target).status in ("ok", "nrc")

    def settle_held(at_did: int):
        if not held:
            return
        if module_alive():
            for rec in held:
                store.append_jsonl(path, rec)
            held.clear()
        else:
            raise SystemExit("%04X stopped answering near DID %04X; the last %d timeouts were not recorded. Re-run to resume."
                             % (target, at_did, len(held)))

    start = time.monotonic()
    for i, did in enumerate(todo, 1):
        tmo = adapt.next() if adapt else timeout
        r = read_with_retry(link, target, did, tmo)
        rec: dict = {"t": store.stamp(), "tgt": "%04X" % target, "did": "%04X" % did, "status": r.status}
        if adapt:
            adapt.seen(r.status)
        if r.status == "nack":
            raise SystemExit(explain_nack(r.code or 0, target))
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
                print("%04X %04X OK %s%s" % (target, did, rec["data"],
                                             "  " + names[did].get("name", "") if did in names else ""), flush=True)
            else:
                rec["code"] = "%02X" % (r.code or 0)
                if is_transient(r.code):
                    rec["retryable"] = True
            store.append_jsonl(path, rec)
        if i % 500 == 0:
            rate = i / (time.monotonic() - start)
            print("  %d/%d, %d OK, %.0f/s, ~%.0f min left" % (i, len(todo), ok, rate, (len(todo) - i) / rate / 60),
                  file=sys.stderr, flush=True)
    settle_held(todo[-1])
    link.close()
    print("%04X: %d new OK; %d known OK in total" % (target, ok, len(store.known_ok(target))))
    return ok


def cmd_scan(args):
    """Try a list of DIDs on one module. DIDs with a definite answer (OK or NRC) in any earlier run are skipped."""
    if args.adaptive_timeout and args.paced is not None:
        raise SystemExit("--adaptive-timeout only applies to the normal scan; paced scans never adapt")
    if args.dids_file and args.like is not None:
        raise SystemExit("give --dids-file or --like, not both")
    if args.dids_file:
        dids = parse_dids_file(args.dids_file)
    elif args.like is not None:
        dids = store.known_ok(args.like, getattr(args, "allow_caution", False))
        if not dids:
            raise SystemExit("no recorded OK DIDs for %04X to copy" % args.like)
    else:
        dids = parse_ranges(args.ranges)
    scan_core(args, args.target, dids, args.paced, args.timeout)


def paced_scan(args, target: int, link: "Link", todo: list[int], path: str, paced: float, timeout: float) -> int:
    """Careful scan for modules that may fall over (1301:EE13 knocked the Mobileye ECU off for a minute).

    Per DID: read it once (never repeated, even if the connection drops), wait `paced` seconds, then check that the
    module and the gateway both answer TesterPresent. Only then is the result recorded and the next DID read. At the
    first refusal, drop or silence the DID is recorded as a hazard (scan never reads it again), the module's recovery
    is timed, and the scan stops.
    """
    if paced < 0:
        raise SystemExit("--paced must be 0 or more seconds")
    names = decode.load_dids() if getattr(args, "names", False) else {}
    c = link.c
    gateway = c.gateway or GATEWAY

    def answers(t: int) -> bool:
        for _ in range(3):  # a single lost reply must not mark an innocent DID
            try:
                if c.tester_present(t).status in ("ok", "nrc"):
                    return True
            except ConnectionLost:
                return False
        return False

    def fresh_answers(t: int) -> bool:
        """TesterPresent on a new connection (the old one may be gone); any failure counts as no answer."""
        try:
            with DoIP(args.host, args.port).connect() as d:
                return d.tester_present(t).status in ("ok", "nrc")
        except (ConnectionLost, ActivationRefused, OSError):
            return False

    def hazard(did: int, why: str):
        store.append_jsonl(path, {"t": store.stamp(), "tgt": "%04X" % target, "did": "%04X" % did, "status": "hazard", "why": why})
        print("%s %04X %04X HAZARD: %s; recorded, scan will never read it again" % (store.now(), target, did, why), flush=True)
        print('  propose a catalogue entry: - {module: "%04X", did: "%04X", action: caution, why: "%s"}'
              % (target, did, why.replace('"', "'")), file=sys.stderr, flush=True)
        c.close()
        t0 = time.monotonic()
        while time.monotonic() - t0 < args.recover:
            time.sleep(args.recover_poll)
            if fresh_answers(target) and fresh_answers(gateway):
                raise SystemExit("%04X answered again %.0f s after DID %04X. Stopped; add it to catalogue/hazards.yaml before going on."
                                 % (target, time.monotonic() - t0, did))
        raise SystemExit("%04X still silent %.0f s after DID %04X. Stopped; add it to catalogue/hazards.yaml."
                         % (target, args.recover, did))

    if not (answers(target) and answers(gateway)):
        raise SystemExit("%04X or the gateway does not answer TesterPresent before the first read; nothing read" % target)
    def stop_on_term(*_):
        raise KeyboardInterrupt  # docker stop sends SIGTERM: let the handler below record the unchecked DID
    signal.signal(signal.SIGTERM, stop_on_term)
    ok = 0
    for i, did in enumerate(todo, 1):
        sent, problem = False, None
        try:
            try:
                sent = True
                r = c.read_did(target, did, timeout)
            except ConnectionLost as e:
                problem = "the connection dropped on the read (%s)" % e
            if problem is None and r.status == "nack":
                problem = "gateway refused the read (NACK %02X)" % r.code
            if problem is None:
                time.sleep(paced)  # a knockout may land a moment after the answer: check after the pause
                module_ok = answers(target)
                gateway_ok = module_ok and answers(gateway)
        except KeyboardInterrupt:
            if not sent:
                raise SystemExit("interrupted before reading %04X %04X; nothing recorded for it" % (target, did))
            # Read but never checked: treat it as a hazard rather than read it again next time.
            store.append_jsonl(path, {"t": store.stamp(), "tgt": "%04X" % target, "did": "%04X" % did, "status": "hazard",
                                      "why": "scan interrupted between the read and the module check; check by hand"})
            raise SystemExit("interrupted after reading %04X %04X; recorded as a hazard (unchecked)" % (target, did))
        if problem is not None:
            hazard(did, problem)
        if not module_ok:
            hazard(did, "no TesterPresent answer from %04X after the read" % target)
        if not gateway_ok:
            hazard(did, "no TesterPresent answer from the gateway after the read")
        rec = {"t": store.stamp(), "tgt": "%04X" % target, "did": "%04X" % did, "status": r.status}
        if r.status == "ok":
            rec["data"] = stored_value(did, r.payload)
            ok += 1
            print("%04X %04X OK %s%s" % (target, did, rec["data"],
                                         "  " + names[did].get("name", "") if did in names else ""), flush=True)
        elif r.status == "nrc":
            rec["code"] = "%02X" % r.code
            if is_transient(r.code):
                rec["retryable"] = True
        store.append_jsonl(path, rec)
        if i % 25 == 0:
            print("  %d/%d paced, %d OK" % (i, len(todo), ok), file=sys.stderr, flush=True)
    link.close()
    print("%04X: %d new OK; %d known OK in total" % (target, ok, len(store.known_ok(target))))
    return ok


# -- unattended sweep -----------------------------------------------------
def write_progress(path: str, current: str, total: int, remaining: list[str], watch_secs: float, parked: bool) -> None:
    """sweep.progress.json for the status site (web/gen.py reads it). Written atomically after every slot."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"current": current, "since": time.time(), "total": total, "remaining": remaining,
                   "gated": [], "parked": parked, "watch_secs": watch_secs, "tool": __version__},
                  f, indent=1, sort_keys=True)
    os.replace(tmp, path)


SLOT_KEYS = {"module", "ranges", "paced", "watch", "watch_secs", "rescan", "adaptive_timeout", "timeout"}


def plan_slots(path: str, allow_caution: bool = False) -> tuple[list[dict], bool]:
    """(slots, parked) from a sweep plan file: a YAML list of slots, or a mapping {slots: [...], parked: bool}.

    Slot keys: module (hex address), ranges (default DEFAULT_RANGES; empty = no scan, watch-only),
    paced (careful-mode seconds), watch (comma-separated DIDs), watch_secs (watch length, default 240),
    rescan / adaptive_timeout / timeout (per-slot overrides of the command-line flags).
    All slots are validated before the first one runs, so a bad plan costs no car time."""
    import yaml
    try:
        with open(path) as f:
            doc = yaml.safe_load(f)
    except OSError as e:
        raise SystemExit("cannot read plan %s: %s" % (path, e))
    if isinstance(doc, dict):
        allowed = {"slots", "parked", "gated"}
        unknown = set(doc) - allowed
        if unknown:
            raise SystemExit("plan %s: unknown top-level key(s): %s" % (path, ", ".join(sorted(unknown))))
        raw, parked = doc.get("slots"), bool(doc.get("parked", False))
    else:
        raw, parked = doc, False
    if not isinstance(raw, list) or not raw:
        raise SystemExit("plan %s: no slots found (expected a list of slots or {slots: [...], parked: bool})" % path)
    slots = []
    for n, s in enumerate(raw, 1):
        if not isinstance(s, dict) or "module" not in s:
            raise SystemExit("plan slot %d: needs at least a module" % n)
        unknown = set(s) - SLOT_KEYS
        if unknown:
            raise SystemExit("plan slot %d: unknown key(s): %s (allowed: %s)"
                             % (n, ", ".join(sorted(unknown)), ", ".join(sorted(SLOT_KEYS))))
        try:
            tgt = int(str(s["module"]), 16)
        except ValueError:
            raise SystemExit("plan slot %d: module %r is not a hex address" % (n, s["module"]))
        spec = s.get("ranges")
        if spec is None:
            spec = DEFAULT_RANGES
        if isinstance(spec, list):
            spec = ",".join(str(x) for x in spec)
        try:
            dids = parse_ranges(str(spec))
        except SystemExit as e:
            raise SystemExit("plan slot %d: bad ranges %r (%s)" % (n, spec, e))
        watch = s.get("watch")
        if isinstance(watch, list):
            watch = ",".join(str(x) for x in watch)
        watch_dids: list[int] = []
        if watch:
            try:
                watch_dids = [int(d, 16) for d in str(watch).split(",")]
            except ValueError:
                raise SystemExit("plan slot %d: bad watch DIDs %r" % (n, watch))
            for d in list(watch_dids):
                why = blocked_reason(tgt, d)
                if why:
                    print("skipping %s" % why, file=sys.stderr, flush=True)
                    watch_dids.remove(d)
                elif caution_reason(tgt, d) and not allow_caution:
                    print("skipping %s (use --allow-caution)" % caution_reason(tgt, d), file=sys.stderr, flush=True)
                    watch_dids.remove(d)
        try:
            watch_secs = float(s.get("watch_secs", 240))
            paced = None if s.get("paced") is None else float(s["paced"])
            slot_timeout = float(s["timeout"]) if s.get("timeout") is not None else None
        except (TypeError, ValueError):
            raise SystemExit("plan slot %d: paced, watch_secs and timeout must be numbers" % n)
        slots.append({"tgt": tgt, "dids": dids, "paced": paced, "watch_dids": watch_dids, "watch_secs": watch_secs,
                      "rescan": bool(s.get("rescan", False)), "adaptive_timeout": bool(s.get("adaptive_timeout", False)),
                      "timeout": slot_timeout,
                      "str": "%04X:%s" % (tgt, spec) if spec not in ("", DEFAULT_RANGES) else "%04X" % tgt})
    return slots, parked


SCAN_RATE = 24.0  # DIDs/s measured on this car (README); ETAs are labelled estimates


def plan_eta(slot: dict, skip_silent_after: float | None) -> tuple[int, int, float]:
    """(to_try, skipped, rough minutes) for a slot, without touching the car."""
    scans = store.load_scans(slot["tgt"])
    done = store.done_dids(scans, rescan=slot["rescan"], skip_silent_after=skip_silent_after)
    todo = [d for d in slot["dids"] if d not in done]
    todo = [d for d in todo if not blocked_reason(slot["tgt"], d)]
    if slot["paced"] is None:
        todo = [d for d in todo if not caution_reason(slot["tgt"], d)]
    secs = len(todo) / SCAN_RATE
    if slot["watch_dids"]:
        secs += slot["watch_secs"]
    return len(todo), len(slot["dids"]) - len(todo), secs / 60.0


def sweep_watch(args, target: int, dids: list[int], secs: float, should_stop=None) -> None:
    """Bounded watch after a sweep slot: poll the slot's DIDs for `secs` seconds, logging changes to
    runs/<date>/watch-sweep-<TGT>.log in cmd_watch's format (baseline 0, nothing muted)."""
    log = os.path.join(store.run_dir(), "watch-sweep-%04X.log" % target)
    pairs = [(target, d) for d in dids]
    sigs = decode.index(decode.load())
    emit = WatchLog(log)
    last: dict[tuple[int, int], str] = {}
    raw: dict[tuple[int, int], bytes] = {}
    c = None
    end = time.monotonic() + secs
    while time.monotonic() < end and not (should_stop and should_stop()):
        try:
            if c is None:
                c = connect(args, forever=True)
                emit("connected: %d reads per pass -> %s" % (len(pairs), log))
            for key in pairs:
                if time.monotonic() >= end or (should_stop and should_stop()):
                    break
                r = c.read_did(*key)
                if r.status == "ok":
                    raw[key] = r.payload
                val = stored_value(key[1], r.payload) if r.status == "ok" else r.text()
                if val == last.get(key):
                    continue
                name = "%04X:%04X" % key
                extra = ("  [%s]" % decode.describe(sigs[key], r.payload, sibling_context(raw, key[0]))
                         if r.status == "ok" and key in sigs else "")
                if key in last:
                    emit("%s CHANGE %s -> %s%s" % (name, last[key], val, extra))
                else:
                    emit("%s %s%s" % (name, val, extra), show=False)  # first values stay off the screen, like cmd_watch
                last[key] = val
        except ConnectionLost as e:
            emit("ERROR connection lost: %s; reconnecting" % e)
            c = None
    if c:
        c.close()


def cmd_sweep(args):
    """Run a scan plan unattended: scan slots in order, watch the slot's DIDs afterwards when the plan lists
    any, write runs/<date>/sweep.progress.json after every slot for the status site. --max-minutes and SIGTERM
    stop between slots; a hazard or gateway refusal (any SystemExit from a scan) stops everything and is
    written to the progress file so the status site does not show a stale slot as running."""
    slots, parked = plan_slots(args.plan, getattr(args, "allow_caution", False))
    if args.dry_run:
        total = 0.0
        print("plan %s: %d slots (dry run; nothing is connected or written)" % (args.plan, len(slots)))
        for slot in slots:
            todo, skipped, minutes = plan_eta(slot, args.skip_silent_after)
            total += minutes
            print("  %-14s %5d to try, %5d already settled, ~%5.1f min%s"
                  % (slot["str"], todo, skipped, minutes, " + watch" if slot["watch_dids"] else ""))
        print("  estimated total: ~%.1f min (%.0f DIDs/s)" % (total, SCAN_RATE))
        return
    prog = os.path.join(store.run_dir(), "sweep.progress.json")
    log = os.path.join(store.run_dir(), "sweep.log")

    def note(text):
        with open(log, "a") as f:
            f.write("%s %s\n" % (store.now(), text))

    print("plan %s: %d slots; progress -> %s" % (args.plan, len(slots), prog), file=sys.stderr, flush=True)
    stop = {"now": False}

    def stop_after_slot(*_):
        stop["now"] = True  # only checked between slots (and inside a sweep watch)
        print("%s SIGTERM: will stop after the current slot" % store.now(), file=sys.stderr, flush=True)

    start = time.monotonic()
    i = 0
    try:
        for i, slot in enumerate(slots):
            signal.signal(signal.SIGTERM, stop_after_slot)  # a paced slot replaces this with its own, on purpose
            write_progress(prog, slot["str"], len(slots), [s["str"] for s in slots[i:]],
                           slot["watch_secs"] if slot["watch_dids"] else 0, parked)
            if stop["now"]:
                print("SIGTERM: stopping before %s; %d slots left" % (slot["str"], len(slots) - i), flush=True)
                write_progress(prog, "stopped (SIGTERM)", len(slots), [s["str"] for s in slots[i:]], 0, parked)
                return
            if args.max_minutes is not None and time.monotonic() - start >= args.max_minutes * 60:
                print("--max-minutes %g reached; stopping before %s; %d slots left"
                      % (args.max_minutes, slot["str"], len(slots) - i), flush=True)
                write_progress(prog, "stopped (--max-minutes)", len(slots), [s["str"] for s in slots[i:]], 0, parked)
                return
            slot_args = argparse.Namespace(**vars(args))
            slot_args.rescan = slot["rescan"]
            slot_args.adaptive_timeout = slot["adaptive_timeout"]
            if slot["paced"] is not None and slot["adaptive_timeout"]:
                raise SystemExit("plan slot %r: paced and adaptive_timeout cannot be combined" % slot["str"])
            if slot["timeout"] is not None:
                slot_args.timeout = slot["timeout"]
            note("scan %s: start" % slot["str"])
            ok = scan_core(slot_args, slot["tgt"], slot["dids"], slot["paced"], slot_args.timeout)
            note("scan %s: %d new OK" % (slot["str"], ok))
            if slot["watch_dids"]:
                sweep_watch(slot_args, slot["tgt"], slot["watch_dids"], slot["watch_secs"],
                            should_stop=lambda: stop["now"])
    except KeyboardInterrupt:
        write_progress(prog, "stopped (interrupted)", len(slots), [s["str"] for s in slots[i:]], 0, parked)
        note("stopped (interrupted) at %s" % slots[i]["str"])
        raise SystemExit("sweep interrupted; progress saved")
    except SystemExit as e:
        write_progress(prog, "failed: %s" % e, len(slots), [s["str"] for s in slots[i:]], 0, parked)
        note("failed: %s" % e)
        raise
    write_progress(prog, "done", len(slots), [], 0, parked)
    note("done: %d slots" % len(slots))
    print("sweep: %d slots done" % len(slots))


DTC_STATUS_BITS = [(0x01, "testFailed"), (0x02, "testFailedThisOperationCycle"), (0x04, "pendingDTC"),
                   (0x08, "confirmedDTC"), (0x10, "testNotCompletedSinceLastClear"),
                   (0x20, "testFailedSinceLastClear"), (0x40, "testNotCompletedThisOperationCycle"),
                   (0x80, "warningIndicatorRequested")]


def dtc_status(byte: int) -> str:
    return ", ".join(name for mask, name in DTC_STATUS_BITS if byte & mask) or "none"


def dtc_records(data: bytes) -> list[bytes]:
    """4-byte records (3-byte DTC + status) from a 59 xx response, past the service/sub-function/availability byte."""
    body = data[3:]
    return [body[i:i + 4] for i in range(0, len(body) - 3, 4)]


def cmd_dtc(args):
    """Stored (19 02 FF) and supported (19 0A) DTCs, optionally a freeze frame (19 04); names from
    catalogue/dtc.yaml. What a module monitors hints at what it is."""
    names = decode.load_dtcs() if getattr(args, "names", False) else {}
    freeze = None
    if args.freeze:
        try:
            freeze = bytes.fromhex(args.freeze)
        except ValueError:
            raise SystemExit("--freeze needs a 3-byte hex DTC, e.g. D12345")
        if len(freeze) != 3:
            raise SystemExit("--freeze needs exactly 3 bytes (6 hex digits), e.g. D12345")
    link = Link(args)
    out = []
    for tgt in targets(args):
        jobs = ([("freeze", b"\x19\x04" + freeze + b"\xff")] if freeze
                else [("stored", b"\x19\x02\xff"), ("supported", b"\x19\x0a")])
        for kind, req in jobs:
            r = link.do("request", tgt, req, 3.0)
            rec = {"t": store.stamp(), "kind": kind, "status": r.status}
            if r.status == "ok":
                recs = dtc_records(r.data)
                rec["raw"] = r.data.hex()
                if kind != "freeze":
                    rec["dtcs"] = [{"dtc": d[:3].hex().upper(), "status": "%02X" % d[3]} for d in recs]
                if not getattr(args, "json", False):
                    print("%04X %s: %d DTCs" % (tgt, kind, len(recs)) if kind != "freeze"
                          else "%04X freeze %s: %s" % (tgt, args.freeze.upper(), r.data.hex()))
                    for d in recs:
                        label = names.get(int.from_bytes(d[:3], "big"), {}).get("name", "")
                        print("  %s status %02X (%s)%s" % (d[:3].hex().upper(), d[3], dtc_status(d[3]),
                                                          "  " + label if label else ""))
            else:
                if not getattr(args, "json", False):
                    print("%04X %s: %s" % (tgt, kind, r.text()))
                rec["code"] = None if r.code is None else "%02X" % r.code
            store.append_jsonl(os.path.join(store.run_dir(), "dtc-%04X.jsonl" % tgt), rec)
            out.append(rec)
    link.close()
    if getattr(args, "json", False):
        print(json.dumps(out, indent=1, sort_keys=True))


def cmd_snapshot(args):
    """Read every known-OK DID of the given modules once and save it under a name."""
    link = Link(args)
    snap = {}
    for tgt in targets(args):
        dids = store.known_ok(tgt, getattr(args, "allow_caution", False))
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
    if getattr(args, "json", False):
        out = []
        for key, old, new in changes:
            tgt, did = (int(x, 16) for x in key.split(":"))
            out.append({"key": key, "old": old, "new": new,
                        "signals": [s["name"] for s in sigs[(tgt, did)]] if (tgt, did) in sigs else []})
        print(json.dumps(out, indent=1, sort_keys=True))
        return
    for key, old, new in changes:
        tgt, did = (int(x, 16) for x in key.split(":"))
        label = "  [%s]" % ", ".join(s["name"] for s in sigs[(tgt, did)]) if (tgt, did) in sigs else ""
        print("%s %s -> %s%s" % (key, old, new, label))
    print("%d changed" % len(changes))


def load_snapshot_values(name: str) -> dict:
    with open(find_snapshot(name)) as f:
        return json.load(f)["values"]


def label_for(key: str, sigs: dict, dids: dict) -> str:
    tgt, did = (int(x, 16) for x in key.split(":"))
    names = [s["name"] for s in sigs.get((tgt, did), [])]
    if not names and did in dids and dids[did].get("name"):
        names = [dids[did]["name"]]
    return "  [%s]" % ", ".join(names) if names else ""


def cmd_flips(args):
    """Values equal in A and C but different in B: changed with an action and changed back."""
    names = [args.a, args.b, args.c] + (args.snap_d or [])
    stats: dict = {}
    out = analysis.flips([load_snapshot_values(n) for n in names], include_noise=args.all, stats=stats)
    sigs, dids = decode.index(decode.load()), decode.load_dids()
    for key, vals in out:
        print("%s %s%s" % (key, " ".join(analysis.shorten(v, args.short) for v in vals[:2]), label_for(key, sigs, dids)))
    print("%d flipped over %d snapshots" % (len(out), len(names)))
    if stats["skipped"]:
        print("%d keys skipped (not in every snapshot)" % stats["skipped"], file=sys.stderr)


def find_watch_log(name: str) -> str:
    if os.path.exists(name):
        return name
    found = sorted(glob.glob(os.path.join(store.root(), "runs", "*", name)))
    if not found:
        raise SystemExit("no watch log %r (a path, or a file name inside runs/*/)" % name)
    return found[-1]


def cmd_changes(args):
    """Compact 'time key new-value' list from a watch log's CHANGE lines."""
    keys = {k.strip().upper() for k in args.keys.split(",") if k.strip()} if args.keys else None
    since, until = analysis.check_hms(args.since, "--since"), analysis.check_hms(args.until, "--until")
    if since and until and since > until:
        raise SystemExit("--since is after --until (times are clock times; ranges across midnight are not supported)")
    stats: dict = {}
    with open(find_watch_log(args.log)) as f:
        rows = analysis.changes(f, since, until, keys, args.significant, stats)
    for t, key, _old, new, _dec in rows:
        print("%s %s %s" % (t, key, analysis.shorten(new, args.width)))
    print("%d changes" % len(rows))
    for n, text in ((stats["hidden"], "muted/noisy lines in the log are not shown"),
                    (stats["unparsed"], "CHANGE lines not understood"),
                    (stats["jitter"], "dropped by --significant (this includes 1-step flag/enum changes)")):
        if n:
            print("%d %s" % (n, text), file=sys.stderr)


def cmd_findvalue(args):
    """Positions in a snapshot (or two) that decode to a value under the usual encodings."""
    pair = args.b is not None
    if pair and (args.from_ is None or args.to is None):
        raise SystemExit("two snapshots need --from X --to Y")
    if not pair and args.value is None:
        raise SystemExit("one snapshot needs --value X (or give a second snapshot with --from/--to)")
    if pair and args.value is not None:
        raise SystemExit("--value is for a single snapshot; use --from/--to with two")
    a = load_snapshot_values(args.a)
    if pair:
        hits = analysis.findvalue(a, args.from_, load_snapshot_values(args.b), args.to, args.tol)
    else:
        hits = analysis.findvalue(a, args.value, tol=args.tol)
    sigs, dids = decode.index(decode.load()), decode.load_dids()
    for hit in hits:
        print(analysis.fmt_hit(hit) + label_for(hit[0], sigs, dids))
    print("%d hits" % len(hits))


def parse_watch_specs(specs: list[str], allow_caution: bool = False) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for spec in specs:
        tgt_s, _, dids_s = spec.partition(":")
        if ":" in dids_s:
            raise SystemExit("one module per watch spec: %r. Use e.g. 1631:D003 1637:D003" % spec)
        try:
            tgt = int(tgt_s, 16)
            dids = [int(d, 16) for d in dids_s.split(",")] if dids_s else store.known_ok(tgt, allow_caution)
        except ValueError:
            raise SystemExit("bad watch spec %r: expected MODULE[:DID,DID] in hex (e.g. 1631:D003)" % spec)
        if not dids:
            raise SystemExit("%04X: no known OK DIDs; give %04X:DID,DID or run scan first" % (tgt, tgt))
        for d in list(dids):
            why = blocked_reason(tgt, d)
            if why:
                print("skipping %s" % why, file=sys.stderr, flush=True)
                dids.remove(d)
            elif caution_reason(tgt, d) and not allow_caution:
                print("skipping %s (use --allow-caution to watch it)" % caution_reason(tgt, d),
                      file=sys.stderr, flush=True)
                dids.remove(d)
        pairs += [(tgt, d) for d in dids]
    if not pairs:
        raise SystemExit("nothing left to watch")
    return pairs


def sibling_context(raw: dict[tuple[int, int], bytes], tgt: int) -> dict[int, bytes]:
    """DID -> payload for one module, for decodes whose count lives in a sibling DID."""
    return {did: payload for (t, did), payload in raw.items() if t == tgt}


class WatchLog:
    """cmd_watch's emit: timestamped lines appended to a watch log and shown on screen unless quiet."""

    def __init__(self, path: str):
        self.path = path

    def __call__(self, line: str, show: bool = True) -> None:
        line = "%s %s" % (store.stamp(), line)  # ISO date+offset: no midnight guesswork in correlate/web
        with open(self.path, "a") as f:
            f.write(line + "\n")
        if show:
            print(line, flush=True)


def cmd_watch(args):
    """Poll DIDs and print only changes.

    For the first --baseline seconds leave the car alone: anything that changes then is background
    noise and is hidden from the screen for the rest of the run (still logged). After the baseline
    nothing is hidden automatically, unless --mute N is given (N changes within 10 s).
    """
    pairs = [p for p in parse_watch_specs(args.specs, getattr(args, "allow_caution", False)) if "%04X:%04X" % p not in args.hide and "%04X" % p[1] not in args.hide]
    sigs = decode.index(decode.load())
    log = os.path.join(store.run_dir(), "watch-%s.log" % (args.name or time.strftime("%H%M%S")))
    last: dict[tuple[int, int], str] = {}
    raw: dict[tuple[int, int], bytes] = {}
    hist: dict[tuple[int, int], list[float]] = {}
    noisy: set[tuple[int, int]] = set()
    emit = WatchLog(log)
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
                if r.status == "ok":
                    raw[key] = r.payload
                val = stored_value(key[1], r.payload) if r.status == "ok" else r.text()
                if not baseline_done and time.monotonic() - started >= args.baseline:
                    baseline_done = True
                    emit("baseline over: %d noisy values hidden. Go." % len(noisy))
                if val == last.get(key):
                    continue
                name = "%04X:%04X" % key
                extra = ("  [%s]" % decode.describe(sigs[key], r.payload, sibling_context(raw, key[0]))
                         if r.status == "ok" and key in sigs else "")
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
            if args.keepalive and args.interval > args.keepalive:
                end = time.monotonic() + args.interval
                while time.monotonic() < end and c is not None:
                    time.sleep(min(args.keepalive, end - time.monotonic()))
                    if time.monotonic() < end:
                        try:
                            c.tester_present(pairs[0][0])
                        except ConnectionLost as e:
                            emit("ERROR connection lost during keepalive: %s; reconnecting" % e)
                            c = None
            else:
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
    names = decode.load_dids() if getattr(args, "names", False) else {}
    doc = {}
    for tgt in targets(args):
        scans = store.load_scans(tgt)
        ok = [d for d, r in sorted(scans.items()) if r["status"] == "ok"]
        refused = sorted(d for d, r in scans.items()
                         if r["status"] == "nrc" and r.get("code") != "31" and not store.retryable(r))
        retry = sorted(d for d, r in scans.items() if store.retryable(r))
        hazards_ = sorted(d for d, r in scans.items() if r["status"] == "hazard")
        if getattr(args, "json", False):
            doc["%04X" % tgt] = {
                "tried": len(scans),
                "ok": [{"did": "%04X" % d, "data": scans[d].get("data", ""),
                        "name": names.get(d, {}).get("name", "")} for d in ok],
                "refused": [{"did": "%04X" % d, "code": scans[d]["code"],
                             "nrc": nrc_name(int(scans[d]["code"], 16))} for d in refused],
                "retryable": [{"did": "%04X" % d, "code": scans[d]["code"]} for d in retry],
                "hazards": [{"did": "%04X" % d, "why": scans[d].get("why", "")} for d in hazards_],
            }
            continue
        print("%04X: %d tried, %d OK, %d refused (exist, but not readable in this state)" % (tgt, len(scans), len(ok), len(refused)))
        if args.list:
            for d in ok:
                print("  %04X %s%s" % (d, scans[d].get("data", ""),
                                       "  " + names[d].get("name", "") if d in names else ""))
            for d in refused:
                print("  %04X NRC %s (%s)%s" % (d, scans[d]["code"], nrc_name(int(scans[d]["code"], 16)),
                                                "  " + names[d].get("name", "") if d in names else ""))
        for d in retry:
            print("  %04X NRC %s (%s) transient; the next scan asks again" % (d, scans[d]["code"], nrc_name(int(scans[d]["code"], 16))))
        for d in hazards_:
            print("  %04X HAZARD (scan never reads it): %s" % (d, scans[d].get("why", "")))
    if getattr(args, "json", False):
        print(json.dumps(doc, indent=1, sort_keys=True))


def cmd_hazards(args):
    """Reads that are blocked or cautioned, and why. Offline; reads catalogue/hazards.yaml."""
    hs = hazards.entries()
    if getattr(args, "json", False):
        print(json.dumps([{"module": "%04X" % h.module, "did": "%04X" % h.did, "action": h.action,
                           "why": h.why, "evidence": h.evidence, "severity": h.severity, "source": h.source}
                          for h in hs], indent=1, sort_keys=True))
        return
    for h in hs:
        print("%-7s %04X:%04X %-8s %s" % (h.action, h.module, h.did, h.severity, h.why))
        if h.evidence:
            print("        evidence: %s" % h.evidence)
    nblock = sum(1 for h in hs if h.action == "block")
    print("%d hazards: %d block, %d caution" % (len(hs), nblock, len(hs) - nblock))
    if not os.path.exists(hazards.catalogue_path()):
        print("note: %s is missing; only the built-in block applies" % hazards.catalogue_path(), file=sys.stderr)


def cmd_did(args):
    """Look up a DID by hex value or text: the registry name, matching signals, and the modules that answer."""
    reg = decode.load_dids()
    sigs = decode.load()
    q = args.name.strip()
    hex_q = bool(re.fullmatch(r"[0-9a-fA-F]{1,4}", q))
    reg_rows = []
    sig_rows = []
    modules: list[str] = []
    if hex_q:
        d = int(q, 16)
        if d in reg:
            reg_rows = [(d, reg[d])]
        sig_rows = [s for s in sigs if int(s["did"], 16) == d]
        if os.path.exists(os.path.join(store.root(), "docs", "did-map.csv")):
            modules = sorted({m for m, rows in load_didmap().items()
                              for did, status, _ in rows if int(did, 16) == d and status == "ok"})
    else:
        reg_rows = sorted((d, e) for d, e in reg.items() if q.lower() in str(e.get("name", "")).lower())
        sig_rows = [s for s in sigs if q.lower() in s["id"].lower() or q.lower() in s["name"].lower()]
    if not (reg_rows or sig_rows or modules):
        raise SystemExit("no DID or signal matches %r (searched catalogue/dids.yaml, catalogue/signals.yaml%s)"
                         % (q, " and docs/did-map.csv" if hex_q else ""))
    if getattr(args, "json", False):
        print(json.dumps({"registry": [{"did": "%04X" % d, **e} for d, e in reg_rows],
                          "signals": sig_rows, "modules": modules}, indent=1, sort_keys=True))
        return
    for d, e in reg_rows:
        print("%04X  %-44s %s%s" % (d, e.get("name", "?"), e.get("family", ""), " masked" if e.get("masked") else ""))
        if e.get("note"):
            print("      %s" % e["note"])
    for sig in sig_rows:
        print("%s:%s  %-26s %s [%s]" % (sig["module"], sig["did"], sig["id"], sig["name"], sig["confidence"]))
    if modules:
        print("answers on: %s" % " ".join(modules))


def cmd_read(args):
    """Read one ID (MODULE:DID[,DID]) with the same guard as every other command; masked values print as zeros."""
    tgt_s, sep, dids_s = args.spec.partition(":")
    if not sep:
        raise SystemExit("read needs MODULE:DID[,DID], e.g. 1601:E37B")
    try:
        tgt = int(tgt_s, 16)
        dids = [int(d, 16) for d in dids_s.split(",") if d.strip()]
    except ValueError:
        raise SystemExit("bad read spec %r: expected hex MODULE:DID[,DID]" % args.spec)
    if not dids:
        raise SystemExit("read needs at least one DID")
    if args.repeat < 1:
        raise SystemExit("--repeat must be 1 or more")
    if args.multi and len(dids) == 1:
        raise SystemExit("--multi needs at least two DIDs")
    lengths: dict[int, int] = {}
    if args.multi:
        path = os.path.join(store.root(), "docs", "did-map.csv")
        if os.path.exists(path):
            for did_s, status, n in load_didmap().get("%04X" % tgt, []):
                if status == "ok" and n:
                    lengths[int(did_s, 16)] = n
    link = Link(args)
    out = []
    try:
        for n in range(args.repeat):
            if args.multi:
                try:
                    r = link.do("read_dids", tgt, dids, 1.0)
                except (BlockedRead, CautionedRead) as e:
                    raise SystemExit(str(e))
                if r.status != "ok":
                    out.append({"module": "%04X" % tgt, "dids": ["%04X" % d for d in dids],
                                "status": r.status, "code": None if r.code is None else "%02X" % r.code})
                    if not getattr(args, "json", False):
                        print("%04X multi %s: %s" % (tgt, ",".join("%04X" % d for d in dids), r.text()))
                else:
                    body = r.data[1:]  # after 62
                    split, pos = [], 0
                    for did in dids:
                        ln = lengths.get(did)
                        if ln is None or body[pos:pos + 2] != struct.pack(">H", did) or len(body) < pos + 2 + ln:
                            split = None
                            break
                        split.append((did, body[pos + 2:pos + 2 + ln]))
                        pos += 2 + ln
                    if split is None:
                        out.append({"module": "%04X" % tgt, "dids": ["%04X" % d for d in dids],
                                    "status": "ok", "raw": r.data.hex(), "split": False})
                        if not getattr(args, "json", False):
                            print("%04X multi: raw %s (no split: lengths unknown in docs/did-map.csv)"
                                  % (tgt, r.data.hex()))
                    else:
                        for did, payload in split:
                            rec = {"module": "%04X" % tgt, "did": "%04X" % did, "status": "ok",
                                   "data": stored_value(did, payload), "multi": True}
                            rec["text"] = "" if did in MASKED_DIDS else printable(payload)
                            out.append(rec)
                            if not getattr(args, "json", False):
                                print("%04X %04X OK %s%s" % (tgt, did, rec["data"],
                                                              "  " + rec["text"] if rec["text"] else ""))
            else:
                for did in dids:
                    try:
                        r = link.do("read_did", tgt, did)
                    except (BlockedRead, CautionedRead) as e:
                        raise SystemExit(str(e))
                    rec = {"module": "%04X" % tgt, "did": "%04X" % did, "status": r.status}
                    if r.status == "ok":
                        rec["data"] = stored_value(did, r.payload)
                        rec["text"] = "" if did in MASKED_DIDS else printable(r.payload)
                    elif r.code is not None:
                        rec["code"] = "%02X" % r.code
                        rec["nrc"] = nrc_name(r.code) if r.status == "nrc" else ""
                    out.append(rec)
                    if not getattr(args, "json", False):
                        shown = "OK " + rec.get("data", "") if r.status == "ok" else r.text()
                        print("%04X %04X %s%s" % (tgt, did, shown, "  " + rec["text"] if rec.get("text") else ""))
            if args.interval and n + 1 < args.repeat:
                time.sleep(args.interval)
    finally:
        link.close()
    if getattr(args, "json", False):
        print(json.dumps(out, indent=1, sort_keys=True))


def cmd_import_legacy(args):
    paths = sorted(glob.glob(os.path.join(store.root(), "local", "reads", "*sweep*.txt"))
                   + glob.glob(os.path.join(store.root(), "local", "reads", "unknown-*.txt"))
                   + glob.glob(os.path.join(store.root(), "local", "reads", "*-probe.txt")))
    existing = glob.glob(os.path.join(store.root(), "runs", args.date, "scan-*.jsonl"))
    if existing:
        raise SystemExit("runs/%s already has scan files; delete them to re-import" % args.date)
    for tgt, n in sorted(store.import_legacy(paths, args.date).items()):
        print("%s: %d DIDs" % (tgt, n))


def cmd_didmap(args):
    """Regenerate docs/did-map.csv from runs/: every DID that answered OK plus DIDs that exist but refuse
    with NRC 22/33 — the same rows scripts/export-did-map.sh writes. Values are never exported.
    --check exits 1 when the file on disk is stale (used by scripts/prepublish-check.sh)."""
    files = sorted(glob.glob(os.path.join(store.root(), "runs", "*", "scan-*.jsonl")))
    if not files:
        raise SystemExit("no runs/*/scan-*.jsonl here; nothing to export")
    best: dict[tuple[str, str], tuple[int, dict]] = {}
    for path in files:
        for rec in store.read_jsonl(path):
            if "did" not in rec:
                continue  # run header
            rank = {"ok": 2, "nrc": 1}.get(rec["status"], 0)
            if store.retryable(rec):
                rank = 0  # a transient refusal is not a map fact
            key = (rec["tgt"], rec["did"])
            if key not in best or rank >= best[key][0]:
                best[key] = (rank, rec)
    rows = ["module,did,status,length_bytes,nrc"]
    for (tgt, did), (_, rec) in sorted(best.items()):
        if store.retryable(rec):
            continue  # a transient refusal is not a DID fact
        if rec["status"] == "ok":
            rows.append("%s,%s,ok,%d," % (tgt, did, len(rec.get("data", "")) // 2))
        elif rec["status"] == "nrc" and rec.get("code") in ("22", "33"):
            rows.append("%s,%s,nrc,,%s" % (tgt, did, rec["code"]))
    text = "\n".join(rows) + "\n"
    out = os.path.join(store.root(), "docs", "did-map.csv")
    if args.check:
        stale = not os.path.exists(out)
        if not stale:
            with open(out) as f:
                stale = f.read() != text
        if stale:
            raise SystemExit(1)
        print("docs/did-map.csv is up to date (%d DIDs)" % (len(rows) - 1))
        return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, out)
    print("%s: %d DIDs" % (out, len(rows) - 1))


# -- offline analysis ----------------------------------------------------------
# Text extraction and masking live in privacy.py (shared with web/); readable_text is imported above.


def cmd_strings(args):
    """Readable text in every answered DID of the given modules, identifiers masked.

    Masked DIDs (VIN, serials: recorded as zeros) are left out; other identity DIDs (part numbers etc.)
    are searched like any DID, relying on the masking."""
    names = decode.load_dids() if getattr(args, "names", False) else {}
    rows = []
    for tgt in targets(args):
        for did, rec in sorted(store.load_scans(tgt).items()):
            if rec["status"] != "ok" or did in MASKED_DIDS:
                continue
            raw = rec.get("data", "")
            text = readable_text(raw) or " | ".join(readable_runs(raw))
            if text:
                rows.append({"module": "%04X" % tgt, "did": "%04X" % did, "text": text,
                             "name": names.get(did, {}).get("name", "")})
                if not getattr(args, "json", False):
                    print("%04X:%04X %s%s" % (tgt, did, text,
                                              "  [" + names[did]["name"] + "]" if did in names else ""))
    if getattr(args, "json", False):
        print(json.dumps(rows, indent=1, sort_keys=True))


# Watch lines that record a value change: CHANGE, and the hidden kinds (MUTED, noisy, baseline-noise).
# New logs start with a full ISO timestamp; old ones (and hand-written test logs) with HH:MM:SS. Both parse.
WATCH_LINE = re.compile(r"^(?:\d{4}-\d\d-\d\dT)?\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d)? (\S+) "
                        r"(CHANGE|MUTED after|noisy|baseline-noise) (.*)$")
CLOCK = re.compile(r"^(?:(\d{4}-\d\d-\d\d)T)?(\d\d):(\d\d):(\d\d)(?:[+-]\d\d:\d\d)? ")


def watch_changes(path: str, day: datetime.date):
    """(changes, first, last) of a watch log: changes are (local time, text) for every line that records a
    value change; first/last are the log's time span. Log lines carry only the clock time, so the date
    comes from the run directory and rolls over when the clock goes backwards by more than 12 h."""
    out = []
    first = prev = None
    with open(path) as f:
        for line in f:
            m = CLOCK.match(line)
            if not m:
                continue
            clock = datetime.time(int(m.group(2)), int(m.group(3)), int(m.group(4)))
            if m.group(1):  # new log: the date is in the line, so no rollover heuristic
                t = datetime.datetime.combine(datetime.date.fromisoformat(m.group(1)), clock)
            else:
                t = datetime.datetime.combine(day, clock)
                while prev is not None and t < prev - datetime.timedelta(hours=12):
                    t += datetime.timedelta(days=1)
            first = first or t
            prev = t
            c = WATCH_LINE.match(line.rstrip("\n"))
            if c:
                kind = "" if c.group(2) == "CHANGE" else c.group(2).split()[0] + " "
                out.append((t, "%s %s%s" % (c.group(1), kind, c.group(3))))
    return out, first, prev


def cmd_correlate(args):
    """For each mark of a run day, the watch changes from --before s before it to --after s after it.
    Reads watch logs from that day and the day before (a watch started before midnight logs there)."""
    try:
        day = datetime.date.fromisoformat(args.date)
    except ValueError:
        raise SystemExit("date must be YYYY-MM-DD, got %r" % args.date)
    if any(os.path.basename(n) != n for n in args.logs):
        raise SystemExit("log names are file names inside runs/<date>/, not paths")
    d = os.path.join(store.root(), "runs", day.isoformat())
    marks_path = os.path.join(d, "marks.jsonl")
    if not os.path.exists(marks_path):
        raise SystemExit("no marks for %s (%s)" % (args.date, marks_path))
    if args.logs:
        logs = [(day, os.path.join(d, n)) for n in args.logs]
    else:
        prev_day = day - datetime.timedelta(days=1)
        logs = [(dd, p) for dd in (prev_day, day)
                for p in sorted(glob.glob(os.path.join(store.root(), "runs", dd.isoformat(), "watch-*.log")))]
    if not logs:
        raise SystemExit("no watch logs in %s" % d)
    changes, spans = [], []
    for dd, p in logs:
        ch, first, last = watch_changes(p, dd)
        changes += [(t, os.path.basename(p), text) for t, text in ch]
        if first:
            spans.append((first, last))
    changes.sort()
    lo, hi = datetime.timedelta(seconds=args.before), datetime.timedelta(seconds=args.after)
    for mark in store.read_jsonl(marks_path):
        mt = datetime.datetime.fromisoformat(mark["t"]).astimezone().replace(tzinfo=None)
        near = [(t, log, text) for t, log, text in changes if mt - lo <= t <= mt + hi]
        covered = any(a <= mt <= b for a, b in spans)
        print("== %s %s (%d changes%s)" % (mt.strftime("%H:%M:%S"), mark["mark"], len(near),
                                          "" if covered else "; no watch log covers this time"))
        for t, log, text in near:
            print("  %+4ds %s  (%s)" % ((t - mt).total_seconds(), text, log))


def load_didmap() -> dict[str, list[tuple[str, str, int]]]:
    """docs/did-map.csv rows per module: (did, status, length_bytes)."""
    path = os.path.join(store.root(), "docs", "did-map.csv")
    if not os.path.exists(path):
        raise SystemExit("no docs/did-map.csv here; run ./p4 didmap (or scripts/export-did-map.sh) first")
    out: dict[str, list[tuple[str, str, int]]] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            out.setdefault(row["module"], []).append((row["did"], row["status"], int(row["length_bytes"] or 0)))
    return out


def did_pairs(rows: list[tuple[str, str, int]], refused: bool) -> set[tuple]:
    """A module's fingerprint: (did, length) for answered rows, plus (did, "refused") for exists-but-refused
    rows when refused is set (an NRC 31 set is a family fingerprint too: rear-only DIDs refuse on front doors)."""
    return {(d, n if s == "ok" else "r") for d, s, n in rows if s == "ok" or (refused and s == "nrc")}


def similar_scores(target: int, refused: bool = False) -> list[tuple[float, str, int, int]]:
    """(score, module, shared, only-here) for every other module whose fingerprint pairs in
    docs/did-map.csv overlap the target's, best first: Jaccard over the pairs. Shared by cmd_similar and whois."""
    ok = {m: did_pairs(rows, refused) for m, rows in load_didmap().items()}
    tgt = "%04X" % target
    here = ok.get(tgt, set())
    if not here:
        raise SystemExit("%04X: no answered DIDs in docs/did-map.csv" % target)
    scored = []
    for m, pairs in sorted(ok.items()):
        if m == tgt:
            continue
        if not pairs:
            print("%s: no answered DIDs in docs/did-map.csv; skipped" % m, file=sys.stderr)
            continue
        scored.append((len(here & pairs) / len(here | pairs), m, len(here & pairs), len(here - pairs)))
    return sorted(scored, key=lambda s: (-s[0], s[1]))


def cmd_similar(args):
    """Rank modules by fingerprint overlap with the target (Jaccard over docs/did-map.csv), or with
    --families print the clusters of modules that pair above --threshold: which modules belong together."""
    if args.families:
        mods = sorted(load_didmap())
        pairs = {m: did_pairs(rows, args.refused) for m, rows in load_didmap().items()}
        root_of = {m: m for m in mods}

        def find(m):
            while root_of[m] != m:
                root_of[m] = root_of[root_of[m]]
                m = root_of[m]
            return m

        for i, a in enumerate(mods):
            for b in mods[i + 1:]:
                if pairs[a] and pairs[b] and len(pairs[a] & pairs[b]) / len(pairs[a] | pairs[b]) >= args.threshold:
                    root_of[find(b)] = find(a)
        groups: dict[str, list[str]] = {}
        for m in mods:
            groups.setdefault(find(m), []).append(m)
        families = sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: (-len(g), g[0]))
        standalone = len(mods) - sum(len(g) for g in families)
        if getattr(args, "json", False):
            print(json.dumps({"families": families, "standalone": standalone}, indent=1, sort_keys=True))
            return
        for g in families:
            print("family (%d): %s" % (len(g), " ".join(g)))
        print("%d families of 2+; %d modules standalone" % (len(families), standalone))
        return
    if args.target is None:
        raise SystemExit("give a module address, or --families")
    rows = similar_scores(args.target, args.refused)[:args.top]
    if getattr(args, "json", False):
        print(json.dumps([{"module": m, "score": round(score, 4), "shared": shared, "only_here": only}
                          for score, m, shared, only in rows], indent=1, sort_keys=True))
        return
    for score, m, shared, only in rows:
        print("%s  %.2f  %d shared, %d only-here" % (m, score, shared, only))


def merge_did_ranges(dids: list[int], gap: int) -> list[tuple[int, int]]:
    """[lo, hi] runs of DIDs, merged while the space between neighbours is <= gap skipped DIDs."""
    runs: list[list[int]] = []
    for d in sorted(dids):
        if runs and d - runs[-1][1] <= gap + 1:
            runs[-1][1] = d
        else:
            runs.append([d, d])
    return [(a, b) for a, b in runs]


def ranges_spec(runs: list[tuple[int, int]]) -> str:
    return ",".join("%04X" % a if a == b else "%04X-%04X" % (a, b) for a, b in runs)


def cmd_ranges(args):
    """Suggested --ranges specs from docs/did-map.csv: where a module's answered DIDs cluster, or (with --all)
    the union of DIDs answered by 3+ modules. A hint for planning faster sweeps, not a replacement for
    DEFAULT_RANGES."""
    if args.gap < 0:
        raise SystemExit("--gap must be 0 or more")
    if args.all and args.module is not None:
        raise SystemExit("give --module or --all, not both")
    ok = {m: sorted(int(d, 16) for d, s, _ in rows if s == "ok") for m, rows in load_didmap().items()}
    if args.all:
        counts: dict[int, int] = {}
        for dids in ok.values():
            for d in dids:
                counts[d] = counts.get(d, 0) + 1
        union = {d for d, n in counts.items() if n >= args.min_modules}
        covered = sum(len(set(dids) & union) for dids in ok.values())
        runs = merge_did_ranges(union, args.gap)
        if getattr(args, "json", False):
            print(json.dumps({"min_modules": args.min_modules, "ranges": ranges_spec(runs),
                              "covered": covered, "answered": sum(map(len, ok.values()))}, indent=1, sort_keys=True))
            return
        print("all: %d ranges cover %d of %d answered (DIDs on >= %d modules)"
              % (len(runs), covered, sum(map(len, ok.values())), args.min_modules))
        print("  " + ranges_spec(runs))
        return
    doc = []
    for m in (["%04X" % args.module] if args.module is not None else sorted(ok)):
        dids = ok.get(m, [])
        if not dids:
            print("%s: no answered DIDs in docs/did-map.csv" % m, file=sys.stderr)
            continue
        runs = merge_did_ranges(dids, args.gap)
        default_covered = len(set(dids) & set(parse_ranges(DEFAULT_RANGES)))
        doc.append({"module": m, "ranges": ranges_spec(runs), "count": len(runs),
                    "answered": len(dids), "default_covered": default_covered})
        if not getattr(args, "json", False):
            print("%s: %d ranges cover %d of %d answered; DEFAULT_RANGES cover %d of them"
                  % (m, len(runs), len(dids), len(dids), default_covered))
            print("  " + ranges_spec(runs))
    if getattr(args, "json", False):
        print(json.dumps(doc, indent=1, sort_keys=True))


def run_days(pattern: str) -> list[str]:
    """Run days that hold a file matching pattern (e.g. 'scan-1601.jsonl'), earliest first."""
    return sorted({os.path.basename(os.path.dirname(p))
                   for p in glob.glob(os.path.join(store.root(), "runs", "*", pattern))})


def two_days(days: list[str], what: str, hint: str, a: str | None, b: str | None) -> tuple[str, str]:
    """The two days to diff: the given ones, or the earliest and latest recorded."""
    for d in (a, b):
        if d and d not in days:
            raise SystemExit("no runs/%s/%s (days that have one: %s)" % (d, what, ", ".join(days) or "none"))
    if not days:
        raise SystemExit("no runs/*/%s here; %s" % (what, hint))
    if len(days) < 2:
        raise SystemExit("only one run day has %s (%s); nothing to diff" % (what, days[0]))
    return a or days[0], b or days[-1]


def cmd_scandiff(args):
    """Which DIDs of one module changed status between two run days (default: earliest vs latest). Needs runs/."""
    what = "scan-%04X.jsonl" % args.target
    day_a, day_b = two_days(run_days(what), what, "run ./p4 scan first", args.day_a, args.day_b)
    was, now = store.load_scans(args.target, day_a), store.load_scans(args.target, day_b)

    def nrc_desc(rec: dict) -> str:
        return "NRC %s (%s)" % (rec.get("code") or "??", nrc_name(int(str(rec.get("code") or "0"), 16)))

    groups: dict[str, list[str]] = {k: [] for k in ("newly answered OK", "refused -> OK", "was OK now refused",
                                                    "was OK now silent", "newly refused")}
    for d in sorted(set(was) | set(now)):
        s0 = was[d]["status"] if d in was else None
        s1 = now[d]["status"] if d in now else None
        if s1 == "ok" and s0 != "ok":  # a first sight, a refusal or a silence turning into an answer
            groups["refused -> OK" if s0 == "nrc" else "newly answered OK"].append("%04X" % d)
        elif s0 == "ok" and s1 == "nrc":
            groups["was OK now refused"].append("%04X %s" % (d, nrc_desc(now[d])))
        elif s0 == "ok" and s1 == "timeout":
            groups["was OK now silent"].append("%04X" % d)
        elif s1 == "nrc" and s0 not in ("nrc", "ok"):
            groups["newly refused"].append("%04X %s" % (d, nrc_desc(now[d])))
        # anything else (same status both days, or absent on one day = not recorded then) stays quiet
    if getattr(args, "json", False):
        print(json.dumps({"day_a": day_a, "day_b": day_b, "groups": groups}, indent=1, sort_keys=True))
        return
    for name, lines in groups.items():
        if lines:
            print("%s:" % name)
            for line in lines:
                print("  " + line)
    parts = ["%d %s" % (len(v), k) for k, v in groups.items() if v]
    print("%s -> %s: %d changed%s" % (day_a, day_b, sum(len(v) for v in groups.values()),
                                      " (%s)" % ", ".join(parts) if parts else ""))


def stored_dtcs(target: int, day: str) -> list[bytes] | None:
    """The day's last stored-DTC answer as 4-byte records (3-byte DTC + status), or None if none was recorded."""
    path = os.path.join(store.root(), "runs", day, "dtc-%04X.jsonl" % target)
    raw = None
    if os.path.exists(path):
        for rec in store.read_jsonl(path):
            if rec.get("kind") == "stored" and rec.get("status") == "ok" and rec.get("raw"):
                raw = rec["raw"]  # the day's last answer wins
    if raw is None:
        return None
    body = bytes.fromhex(raw)[3:]  # like cmd_dtc: drop 59 02 FF, split into 4-byte records
    return [body[i:i + 4] for i in range(0, len(body) - 3, 4)]


def cmd_dtcdiff(args):
    """Which stored DTCs appeared or cleared per module between two run days (default: earliest vs latest). Needs runs/."""
    day_a, day_b = two_days(run_days("dtc-*.jsonl"), "dtc-*.jsonl", "run ./p4 dtc first", args.day_a, args.day_b)
    tgts = targets(args) if args.targets else sorted({int(os.path.basename(p)[4:8], 16)
                                                      for p in glob.glob(os.path.join(store.root(), "runs", "*", "dtc-*.jsonl"))})
    doc = []
    for tgt in tgts:
        a, b = stored_dtcs(tgt, day_a), stored_dtcs(tgt, day_b)
        if a is None or b is None:
            print("%04X: no stored-DTC answer recorded on %s; skipped" % (tgt, day_a if a is None else day_b), file=sys.stderr)
            continue
        new, gone = sorted(set(b) - set(a)), sorted(set(a) - set(b))
        doc.append({"module": "%04X" % tgt,
                    "new": [{"dtc": d[:3].hex().upper(), "status": "%02X" % d[3]} for d in new],
                    "gone": [{"dtc": d[:3].hex().upper(), "status": "%02X" % d[3]} for d in gone],
                    "unchanged": len(set(a) & set(b))})
        if getattr(args, "json", False):
            continue
        print("%04X %s -> %s: %d new, %d gone, %d unchanged" % (tgt, day_a, day_b, len(new), len(gone), len(set(a) & set(b))))
        for label, dtcs in (("new   ", new), ("gone  ", gone)):
            for d in dtcs:
                print("  %sDTC %s status %02X" % (label, d[:3].hex().upper(), d[3]))
    if getattr(args, "json", False):
        print(json.dumps({"day_a": day_a, "day_b": day_b, "modules": doc}, indent=1, sort_keys=True))


def cmd_signals(args):
    sigs = decode.load()
    if getattr(args, "json", False):
        print(json.dumps(sigs, indent=1, sort_keys=True))
        return
    for s in sigs:
        print("%-9s %s %-28s %s %s" % (s["module"], s["did"], s["id"], s["confidence"], s["name"]))
    print("%d signals" % len(sigs))


# -- coverage, self-check, export, report ------------------------------------
def cmd_runs(args):
    """List run days with counts and size (offline)."""
    base = os.path.join(store.root(), "runs")
    days = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))) if os.path.isdir(base) else []
    rows = []
    for day in days:
        d = os.path.join(base, day)
        files = os.listdir(d)
        row = {"day": day,
               "scans": len([f for f in files if f.startswith("scan-")]),
               "dtc": len([f for f in files if f.startswith("dtc-")]),
               "watches": len([f for f in files if f.startswith("watch-")]),
               "snapshots": len([f for f in files if f.startswith("snap-")]),
               "marks": os.path.exists(os.path.join(d, "marks.jsonl")),
               "bytes": sum(os.path.getsize(os.path.join(d, f)) for f in files),
               "last": max((os.path.getmtime(os.path.join(d, f)) for f in files), default=None)}
        rows.append(row)
    if getattr(args, "json", False):
        print(json.dumps(rows, indent=1, sort_keys=True))
        return
    for r in rows:
        print("%s  scan %2d  dtc %2d  watch %2d  snap %2d  marks %s  %5.1f MB"
              % (r["day"], r["scans"], r["dtc"], r["watches"], r["snapshots"], "yes" if r["marks"] else "no",
                 (r["bytes"] or 0) / 1e6))
    print("%d run days" % len(rows))


def cmd_tree(args):
    """DID coverage per module: one character per 0x1000 block (0x0000-0xFFFF) of answered DIDs (offline)."""
    bars = " .:-=+*#%@"
    mods = [args.module] if args.module is not None else sorted(catalogue_modules())
    rows = []
    for tgt in mods:
        scans = store.load_scans(tgt)
        ok = [d for d, r in scans.items() if r["status"] == "ok"]
        blocks = [0] * 16
        for d in ok:
            blocks[d >> 12] += 1
        bar = "".join(bars[min(9, n)] for n in blocks)
        rows.append({"module": "%04X" % tgt, "ok": len(ok), "tried": len(scans), "bar": bar})
        if not getattr(args, "json", False):
            print("%04X %s  %4d ok / %4d tried" % (tgt, bar, len(ok), len(scans)))
    if getattr(args, "json", False):
        print(json.dumps(rows, indent=1, sort_keys=True))
        return
    print("blocks 0x0000..0xFFFF, one char per 0x1000; legend '%s' (0..9+)" % bars)


def cmd_doctor(args):
    """Self-check: catalogue files, hazards, did-map, run directories and (unless --offline) the gateway."""
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    root = store.root()
    add("P4_ROOT writable", os.access(root, os.W_OK), root)
    cat = os.path.join(root, "catalogue")
    for fname in ("modules.yaml", "signals.yaml", "dids.yaml"):
        path = os.path.join(cat, fname)
        try:
            if not os.path.exists(path):
                raise OSError("missing")
            with open(path) as f:
                yaml.safe_load(f)
            add("catalogue/%s" % fname, True)
        except Exception as e:  # noqa: BLE001 - a self-check reports, it does not crash
            add("catalogue/%s" % fname, False, str(e))
    try:
        n = len(decode.load())
        add("signals decode", True, "%d loaded" % n)
    except Exception as e:  # noqa: BLE001
        add("signals decode", False, str(e))
    try:
        add("hazards", True, "%d entries" % len(hazards.entries()))
    except Exception as e:  # noqa: BLE001
        add("hazards", False, str(e))
    try:
        n = len(decode.load_dtcs())
        add("dtc registry", True, "%d named" % n)
    except Exception as e:  # noqa: BLE001
        add("dtc registry", False, str(e))
    didmap = os.path.join(root, "docs", "did-map.csv")
    add("docs/did-map.csv", os.path.exists(didmap),
        "present" if os.path.exists(didmap) else "missing; run ./p4 didmap")
    runs = os.path.join(root, "runs")
    add("runs/", True, runs if os.path.isdir(runs) else "none yet (created at the first scan)")
    if not args.offline:
        c = DoIP(args.host, args.port, allow_caution=getattr(args, "allow_caution", False))
        try:
            c.connect()
            add("gateway routing activation", True, "%s:%d" % (args.host, args.port))
            gw = c.tester_present(GATEWAY, 1.0)
            add("gateway TesterPresent", gw.status in ("ok", "nrc"), gw.text())
            mods = sorted(a for a in catalogue_modules() if a != GATEWAY)
            if mods:
                m = c.tester_present(mods[0], 1.0)
                # informational: a catalogue module can be asleep or absent at this moment
                add("%04X TesterPresent (informational)" % mods[0], True, m.text())
        except (ConnectionLost, ActivationRefused) as e:
            add("gateway reachable", False, str(e))
        finally:
            c.close()
    if getattr(args, "json", False):
        print(json.dumps(checks, indent=1, sort_keys=True))
    else:
        for c in checks:
            print("%-4s %-34s %s" % ("OK" if c["ok"] else "FAIL", c["check"], c["detail"]))
    failed = [c for c in checks if not c["ok"]]
    if failed:
        raise SystemExit("%d check(s) failed" % len(failed))


def cmd_export(args):
    """Export recorded DID facts as JSON or CSV (offline). Values for masked DIDs are always zeros."""
    names = decode.load_dids()
    sigs = decode.load()
    sig_by: dict[tuple[int, int], list[dict]] = {}
    for sig in sigs:
        for mod in sig["module"].split(","):
            sig_by.setdefault((int(mod, 16), int(sig["did"], 16)), []).append(sig)
    mods = [args.module] if args.module is not None else sorted(catalogue_modules())
    rows = []
    for tgt in mods:
        for did, rec in sorted(store.load_scans(tgt).items()):
            if rec["status"] == "timeout" and not args.all:
                continue
            if store.retryable(rec):
                continue
            row = {"module": "%04X" % tgt, "did": "%04X" % did, "status": rec["status"],
                   "name": names.get(did, {}).get("name", ""),
                   "signals": [s["id"] for s in sig_by.get((tgt, did), [])]}
            if rec["status"] == "ok":
                data = rec.get("data", "")
                row["data"] = "00" * (len(data) // 2) if did in MASKED_DIDS else data
                row["length_bytes"] = len(data) // 2
            elif rec["status"] == "nrc":
                row["code"] = rec.get("code", "")
            elif rec["status"] == "hazard":
                row["why"] = rec.get("why", "")
            rows.append(row)
    if args.format == "json":
        text = json.dumps(rows, indent=1, sort_keys=True) + "\n"
    else:
        import csv as _csv
        import io
        buf = io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["module", "did", "status", "length_bytes", "data", "nrc", "name", "signals", "why"])
        for r in rows:
            w.writerow([r["module"], r["did"], r["status"], r.get("length_bytes", ""), r.get("data", ""),
                        r.get("code", ""), r["name"], " ".join(r["signals"]), r.get("why", "")])
        text = buf.getvalue()
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print("%d rows -> %s" % (len(rows), args.out))
    else:
        print(text, end="")


def cmd_report(args):
    """Markdown summary of one run day: scans, DTCs, watches and marks (offline)."""
    day = args.date or datetime.date.today().isoformat()
    d = os.path.join(store.root(), "runs", day)
    if not os.path.isdir(d):
        raise SystemExit("no runs/%s" % day)
    scans: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(d, "scan-*.jsonl"))):
        tgt = os.path.basename(path)[5:9]
        recs = [r for r in store.read_jsonl(path) if "did" in r]
        counts = {}
        for r in recs:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        scans[tgt] = counts
    dtcs = {}
    for path in sorted(glob.glob(os.path.join(d, "dtc-*.jsonl"))):
        tgt = os.path.basename(path)[4:8]
        stored = None
        for r in store.read_jsonl(path):
            if r.get("kind") == "stored" and r.get("status") == "ok":
                stored = len(dtc_records(bytes.fromhex(r["raw"])))
        if stored is not None:
            dtcs[tgt] = stored
    watches = {}
    for path in sorted(glob.glob(os.path.join(d, "watch-*.log"))):
        changes, first, last = watch_changes(path, datetime.date.fromisoformat(day))
        watches[os.path.basename(path)] = len(changes)
    marks = store.read_jsonl(os.path.join(d, "marks.jsonl")) if os.path.exists(os.path.join(d, "marks.jsonl")) else []
    lines = ["# Run %s" % day, "", "## Scans", ""]
    if scans:
        lines += ["| Module | OK | refused | silent | hazards |", "|---|---|---|---|---|"]
        for tgt, c in sorted(scans.items()):
            lines.append("| %s | %d | %d | %d | %d |" % (tgt, c.get("ok", 0), c.get("nrc", 0),
                                                         c.get("timeout", 0), c.get("hazard", 0)))
    else:
        lines.append("_none_")
    lines += ["", "## Stored DTCs", ""]
    lines += ["- %s: %d" % (t, n) for t, n in sorted(dtcs.items())] or ["_none_"]
    lines += ["", "## Watches", ""]
    lines += ["- %s: %d changes" % (n, c) for n, c in sorted(watches.items())] or ["_none_"]
    lines += ["", "## Marks", ""]
    lines += ["- %s %s" % (m.get("t", ""), m.get("mark", "")) for m in marks] or ["_none_"]
    text = "\n".join(lines) + "\n"
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print("%s -> %s" % (day, args.out))
    else:
        print(text, end="")


def main(argv=None):
    # allow_abbrev=False: `--ho X` must not stand in for `--host X` (the ./p4 wrapper only knows the full names).
    p = argparse.ArgumentParser(prog="p4", description=__doc__, allow_abbrev=False)
    p.add_argument("--host", default=os.environ.get("P4_HOST", "169.254.19.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("P4_PORT", "13400")))
    p.add_argument("--retries", type=int, default=3, help="connection attempts before giving up")
    p.add_argument("--retry-wait", type=float, default=5.0, help="seconds between connection attempts")
    p.add_argument("--allow-caution", action="store_true",
                   help="allow reads marked caution in catalogue/hazards.yaml (refused by default; a paced scan allows them)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("discover", help="find module addresses")
    s.add_argument("--start", type=hexint, default=0x1000)
    s.add_argument("--end", type=hexint, default=0x1FFE)
    s.add_argument("--timeout", type=float, default=0.3)
    s.set_defaults(fn=cmd_discover)

    s = sub.add_parser("identify", help="read part numbers / serials")
    s.add_argument("targets", nargs="+", help="module addresses, or 'all'")
    s.set_defaults(fn=cmd_identify)

    s = sub.add_parser("whois", help="one-shot profile of a module: usage mode, identity DIDs, DTCs, closest cousins")
    s.add_argument("target", type=hexint)
    add_json(s)
    s.set_defaults(fn=cmd_whois)

    s = sub.add_parser("scan", help="find which DIDs a module answers")
    s.add_argument("target", type=hexint)
    s.add_argument("--ranges", default=DEFAULT_RANGES)
    s.add_argument("--like", type=hexint, help="try the DIDs that answered on this other module")
    s.add_argument("--dids-file", metavar="FILE", help="read DIDs from a file (hex, spaces/commas, # comments, ranges)")
    s.add_argument("--names", action="store_true", help="append catalogue/dids.yaml names to OK lines")
    s.add_argument("--timeout", type=float, default=0.5)
    s.add_argument("--rescan", action="store_true", help="try DIDs again even if an earlier run answered them")
    s.add_argument("--skip-silent-after", type=float, default=None, metavar="DAYS",
                   help="also skip DIDs that were silent within this many days (default: retry every timeout)")
    s.add_argument("--paced", type=float, default=None, metavar="SECONDS",
                   help="careful mode: read one DID, wait this long, check the module and gateway still answer; "
                        "stop at the first refusal, drop or silence and record that DID as a hazard")
    s.add_argument("--adaptive-timeout", action="store_true",
                   help="after 20 DIDs with no answer in a row, drop the per-DID timeout to 40%% (min 0.2 s); "
                        "every 50th DID still gets the full timeout as a probe, and any answer restores it. "
                        "Only for the normal scan, never --paced")
    s.add_argument("--recover", type=float, default=300.0, help="paced mode: seconds to wait for a silent module to come back")
    s.add_argument("--recover-poll", type=float, default=5.0, help="paced mode: seconds between checks while waiting")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("sweep", help="run a scan plan unattended: slots from a YAML file, watch after each, progress for the web")
    s.add_argument("--plan", required=True,
                   help="YAML file: a list of slots {module, ranges?, paced?, watch?, watch_secs?} "
                        "(or {slots: [...], parked: bool}); ranges defaults to the scan defaults, empty = no scan")
    s.add_argument("--timeout", type=float, default=0.5)
    s.add_argument("--rescan", action="store_true", help="try DIDs again even if an earlier run answered them")
    s.add_argument("--adaptive-timeout", action="store_true",
                   help="speed up long silent ranges (as ./p4 scan --adaptive-timeout)")
    s.add_argument("--skip-silent-after", type=float, default=None, metavar="DAYS",
                   help="also skip DIDs silent within this many days (default: retry every timeout)")
    s.add_argument("--dry-run", action="store_true", help="validate the plan and print ETAs; do not connect or write")
    s.add_argument("--max-minutes", type=float, default=None, help="stop between slots after this many minutes (default: no budget)")
    s.add_argument("--recover", type=float, default=300.0, help="paced slots: seconds to wait for a silent module to come back")
    s.add_argument("--recover-poll", type=float, default=5.0, help="paced slots: seconds between checks while waiting")
    s.set_defaults(fn=cmd_sweep)

    s = sub.add_parser("dtc", help="read stored and supported DTCs")
    s.add_argument("targets", nargs="+", help="module addresses, or 'all'")
    s.add_argument("--names", action="store_true", help="label codes from catalogue/dtc.yaml")
    s.add_argument("--freeze", metavar="DTC", help="also/only read the freeze frame for this 3-byte DTC (19 04)")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(fn=cmd_dtc)

    s = sub.add_parser("snapshot", help="save all known DIDs of some modules")
    s.add_argument("name")
    s.add_argument("targets", nargs="+", help="module addresses, or 'all'")
    s.set_defaults(fn=cmd_snapshot)

    s = sub.add_parser("diff", help="compare two snapshots (names or file paths)")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--no-labels", dest="labels", action="store_false")
    add_json(s)
    s.set_defaults(fn=cmd_diff)

    s = sub.add_parser("watch", help="poll and print changes")
    s.add_argument("specs", nargs="+", help="1601 (all known DIDs) or 1601:E37B,2B1A")
    s.add_argument("--interval", type=float, default=0.0, help="pause between passes, seconds")
    s.add_argument("--keepalive", type=float, default=0.0, metavar="SECS",
                   help="during a long --interval, send TesterPresent this often so the gateway keeps the session (0 = never)")
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
    s.add_argument("--names", action="store_true", help="append catalogue/dids.yaml names")
    add_json(s)
    s.set_defaults(fn=cmd_known)

    s = sub.add_parser("didmap", help="regenerate docs/did-map.csv from runs/ (offline)")
    s.add_argument("--check", action="store_true", help="exit 1 if docs/did-map.csv is stale instead of writing it")
    s.set_defaults(fn=cmd_didmap)

    s = sub.add_parser("hazards", help="reads that are blocked or cautioned, and why (offline)")
    add_json(s)
    s.set_defaults(fn=cmd_hazards)

    s = sub.add_parser("runs", help="run days: scans, DTCs, watches, size (offline)")
    add_json(s)
    s.set_defaults(fn=cmd_runs)

    s = sub.add_parser("tree", help="DID coverage per module as a 0x1000-block bar (offline)")
    s.add_argument("--module", type=hexint, help="one module (default: every catalogue module)")
    add_json(s)
    s.set_defaults(fn=cmd_tree)

    s = sub.add_parser("doctor", help="self-check catalogue, hazards, did-map and (unless --offline) the gateway")
    s.add_argument("--offline", action="store_true", help="skip the car/gateway checks")
    add_json(s)
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("export", help="export recorded DID facts as JSON or CSV (offline)")
    s.add_argument("--format", choices=("json", "csv"), default="json")
    s.add_argument("--module", type=hexint, help="one module (default: every catalogue module)")
    s.add_argument("--out", metavar="FILE", help="write here instead of stdout")
    s.add_argument("--all", action="store_true", help="include timeout rows too")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("report", help="markdown summary of one run day (offline)")
    s.add_argument("date", nargs="?", metavar="YYYY-MM-DD", help="run day (default: today)")
    s.add_argument("--out", metavar="FILE", help="write here instead of stdout")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("did", help="look up a DID by hex value or catalogue name (offline)")
    s.add_argument("name", help="hex DID (e.g. E37B) or part of a name (e.g. speed)")
    add_json(s)
    s.set_defaults(fn=cmd_did)

    s = sub.add_parser("read", help="read MODULE:DID[,DID] once (or --repeat) with the usual guard")
    s.add_argument("spec", help="MODULE:DID[,DID], e.g. 1601:E37B or 1601:E37B,2B15")
    s.add_argument("--repeat", type=int, default=1, metavar="N", help="read the set N times (default 1)")
    s.add_argument("--interval", type=float, default=0.0, help="seconds between repeats")
    s.add_argument("--multi", action="store_true",
                   help="experimental: one 0x22 with several DIDs (split needs docs/did-map.csv lengths)")
    add_json(s)
    s.set_defaults(fn=cmd_read)

    s = sub.add_parser("import-legacy", help="convert local/reads/*sweep*.txt from 2026-11-10 into runs/")
    s.add_argument("--date", default="2026-11-10")
    s.set_defaults(fn=cmd_import_legacy)

    s = sub.add_parser("strings", help="readable text in answered DIDs, identifiers masked (offline)")
    s.add_argument("targets", nargs="+", help="module addresses, or 'all'")
    s.add_argument("--names", action="store_true", help="append catalogue/dids.yaml names")
    add_json(s)
    s.set_defaults(fn=cmd_strings)

    s = sub.add_parser("correlate", help="watch CHANGE lines near each mark of a run day (offline)")
    s.add_argument("date", help="run day, YYYY-MM-DD")
    s.add_argument("logs", nargs="*", help="watch log file names in that day (default: all watch-*.log)")
    s.add_argument("--before", type=float, default=2.0, help="seconds before a mark to include")
    s.add_argument("--after", type=float, default=15.0, help="seconds after a mark to include")
    s.set_defaults(fn=cmd_correlate)

    s = sub.add_parser("similar", help="modules whose answered DIDs look most like a target's (offline)")
    s.add_argument("target", type=hexint, nargs="?", help="module to match (not needed with --families)")
    s.add_argument("--top", type=int, default=8, help="how many matches to list")
    s.add_argument("--families", action="store_true", help="print the clusters of look-alike modules instead")
    s.add_argument("--threshold", type=float, default=0.8, metavar="SCORE",
                   help="--families: minimum Jaccard score to put two modules in one family (default 0.8)")
    s.add_argument("--refused", action="store_true",
                   help="also score the exists-but-refused DID sets (NRC 31 sets are family fingerprints too)")
    add_json(s)
    s.set_defaults(fn=cmd_similar)

    s = sub.add_parser("scandiff", help="which DIDs changed status between two run days (offline)")
    s.add_argument("target", type=hexint)
    s.add_argument("--day-a", metavar="YYYY-MM-DD", help="first day (default: earliest with a scan file)")
    s.add_argument("--day-b", metavar="YYYY-MM-DD", help="second day (default: latest with a scan file)")
    add_json(s)
    s.set_defaults(fn=cmd_scandiff)

    s = sub.add_parser("dtcdiff", help="which stored DTCs appeared or cleared between two run days (offline)")
    s.add_argument("targets", nargs="*", help="module addresses, or 'all' (default: every module with dtc files)")
    s.add_argument("--day-a", metavar="YYYY-MM-DD", help="first day (default: earliest with a dtc file)")
    s.add_argument("--day-b", metavar="YYYY-MM-DD", help="second day (default: latest with a dtc file)")
    add_json(s)
    s.set_defaults(fn=cmd_dtcdiff)

    s = sub.add_parser("ranges", help="suggested --ranges specs from answered DIDs (offline)")
    s.add_argument("--module", type=hexint, help="one module (default: every module in docs/did-map.csv)")
    s.add_argument("--all", action="store_true", help="one union spec: DIDs answered by --min-modules modules or more")
    s.add_argument("--min-modules", type=int, default=3, metavar="N", help="--all: how many modules must answer a DID (default 3)")
    s.add_argument("--gap", type=lambda v: int(v, 0), default=0x40, metavar="N",
                   help="max space between consecutive DIDs in one range, e.g. 0x40")
    add_json(s)
    s.set_defaults(fn=cmd_ranges)

    s = sub.add_parser("flips", help="values equal in snapshots A and C but different in B: changed and changed back (offline)")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("c")
    s.add_argument("--snap-d", action="append", metavar="SNAP", help="further snapshot(s) to confirm A==C!=B==D (repeatable)")
    s.add_argument("--all", action="store_true", help="include clocks and counters (DD00-DD02, D200-D2FF, 9007)")
    s.add_argument("--short", type=int, metavar="N", help="truncate values to N characters")
    s.set_defaults(fn=cmd_flips)

    s = sub.add_parser("changes", help="compact 'time key new-value' list from a watch log's CHANGE lines (offline)")
    s.add_argument("log", help="watch log path, or file name inside runs/*/")
    s.add_argument("--since", metavar="HH:MM:SS")
    s.add_argument("--until", metavar="HH:MM:SS")
    s.add_argument("--keys", metavar="MOD:DID,...", help="only these keys")
    s.add_argument("--width", type=int, metavar="N", help="truncate values to N characters")
    s.add_argument("--significant", type=int, metavar="N",
                   help="drop same-length hex changes of N counts or fewer (per byte or as a whole number)")
    s.set_defaults(fn=cmd_changes)

    s = sub.add_parser("findvalue", help="positions that decode to X in snapshot A and Y in B, or X in one snapshot (offline)")
    s.add_argument("a")
    s.add_argument("b", nargs="?")
    s.add_argument("--from", dest="from_", type=float, metavar="X", help="decoded value in A")
    s.add_argument("--to", type=float, metavar="Y", help="decoded value in B")
    s.add_argument("--value", type=float, metavar="X", help="single-snapshot mode: positions equal to X")
    s.add_argument("--tol", type=float, default=0.5, help="largest decoded error accepted (default 0.5, capped at half a step)")
    s.set_defaults(fn=cmd_findvalue)

    s = sub.add_parser("signals", help="list and validate catalogue/signals.yaml")
    add_json(s)
    s.set_defaults(fn=cmd_signals)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()

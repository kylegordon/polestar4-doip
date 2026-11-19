"""Static pages from /srv plus /live.json: values and history from the newest watch log."""
import datetime
import glob
import json
import os
import re
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

W = os.environ.get("P4_WEB_W", "/w")
SRV = os.environ.get("P4_WEB_OUT", "/srv")
HOST = os.environ.get("P4_WEB_HOST", "127.0.0.1")  # localhost by default: the pages hold car data
PORT = int(os.environ.get("P4_WEB_PORT", "8088"))
HIST = 600  # points kept per DID
LINE = re.compile(r"(?:\d{4}-\d\d-\d\dT)?(\d\d:\d\d:\d\d)(?:[+-]\d\d:\d\d)? ([0-9A-F]{4}:[0-9A-F]{4}) (.*)")
EXTRA = re.compile(r"\[([^\]=]+)=([^\]]*)\]")
NUM = re.compile(r"-?\d+(?:\.\d+)?")

lock = threading.Lock()
state = {"file": None, "pos": 0, "keys": {}, "events": []}
MATRIX = re.compile(r"^(?:\d{4}-\d\d-\d\dT)?(\d\d:\d\d:\d\d)(?:[+-]\d\d:\d\d)? (1BB[34]):7022 (.*)$")
MATRIX_HEX = re.compile(r"[0-9a-f]{64}")
NO_DATA = "ff" * 32  # drawn grey: the lamp did not answer (NRC, timeout) on that read
SPEED = re.compile(r"^(?:\d{4}-\d\d-\d\dT)?(\d\d:\d\d:\d\d)(?:[+-]\d\d:\d\d)? (1631:D003|1601:E36E) (.*)$")
SPEED_SCALE = {"1631:D003": 0.0140625, "1601:E36E": 1 / 256}  # km/h per count (catalogue vehicle_speed, vddm_speed)


def speed_value(key, rest):
    """km/h from a watch line's new value, or None if the read failed."""
    new = rest.rsplit("-> ", 1)[1] if "-> " in rest else rest
    m = re.match(r"[0-9a-f]{4}\b", new)
    return round(int(m.group(), 16) * SPEED_SCALE[key], 1) if m else None
matrix_lock = threading.Lock()
matrix_cache = {}  # path -> ((mtime, size), frames)


def matrix_value(rest):
    """New value of a watch line (plain, CHANGE, noisy, baseline-noise, MUTED after ... -> new); NO_DATA if not hex."""
    new = rest.rsplit("-> ", 1)[1] if "-> " in rest else rest
    m = MATRIX_HEX.match(new)
    return m.group() if m else NO_DATA


def matrix_logs():
    """Every watch log with headlamp matrix readings: [{name, frames: [[HH:MM:SS, lamp, 32-byte hex]], speed: [[HH:MM:SS, km/h]]}].

    Speed comes from 1631:D003, or 1601:E36E in logs that do not have D003. Oldest log first."""
    out = []
    for p in sorted(glob.glob(W + "/runs/*/watch-*.log")):
        try:
            st = os.stat(p)
            mt = (st.st_mtime, st.st_size)
            if p not in matrix_cache or matrix_cache[p][0] != mt:
                frames, speeds = [], {"1631:D003": [], "1601:E36E": []}
                with open(p, errors="replace") as f:
                    for ln in f:
                        ln = ln.rstrip("\n")
                        m = MATRIX.match(ln)
                        if m:
                            frames.append([m.group(1), m.group(2), matrix_value(m.group(3))])
                            continue
                        m = SPEED.match(ln)
                        if m:
                            speeds[m.group(2)].append([m.group(1), speed_value(m.group(2), m.group(3))])
                matrix_cache[p] = (mt, frames, speeds["1631:D003"] or speeds["1601:E36E"])
        except OSError:
            continue
        if matrix_cache[p][1]:
            out.append({"name": "%s/%s" % (p.split("/")[-2], os.path.basename(p)), "frames": matrix_cache[p][1], "speed": matrix_cache[p][2]})
    return out


CHARGE_LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d)?) 1635:(4801|4802|497C|489C|EE83|DA31) (.*)$")
CHARGE_GAP = 900  # s between readings that starts a new charge session
CHARGE_LOG = re.compile(r"watch-(?:.*-)?charge(?:-.*)?\.log$")  # charge watches, not chargelid/discharge
CHARGE_HEX = {"4801": 4, "4802": 4, "497C": 4, "489C": 8, "EE83": 112, "DA31": 440}  # full-length values only
charge_cache = {}  # path -> ((mtime, size), [[epoch, did, hex]])


def u16s(h, count):
    """Big-endian u16 words from hex, dropping 0xFFFF padding."""
    return [w for w in (int(h[i:i + 4], 16) for i in range(0, min(len(h), count * 4) - 3, 4)) if w != 0xFFFF]


def charge_point(cur):
    """One sample from the latest value of each DID (catalogue decodes: hv_soc, pack_current, pack_voltage,
    charge_power_limit_kw, pack_temperatures, cell_group_voltages)."""
    p = {}
    if "4801" in cur:
        p["soc"] = round(int(cur["4801"][:4], 16) * 0.002, 2)
    if "4802" in cur:
        p["amps"] = round(int(cur["4802"][:4], 16) * 0.1 - 1638.4, 1)
    if "497C" in cur:
        p["volts"] = round(int(cur["497C"][:4], 16) * 0.01, 1)
    if "amps" in p and "volts" in p:
        p["kw"] = round(-p["amps"] * p["volts"] / 1000, 1)  # + = into the pack
    if "489C" in cur:
        p["limit"] = round(int(cur["489C"][:8], 16) * 0.000001, 1)
    t = u16s(cur.get("EE83", ""), 28)
    if t:
        p["tmin"], p["tmax"] = round(min(t) * 0.01 - 50, 1), round(max(t) * 0.01 - 50, 1)
    c = u16s(cur.get("DA31", ""), 110)
    if c:
        p["cmin"], p["cmax"] = min(c) / 1000, max(c) / 1000
    return p


def charge_sessions():
    """Charge sessions from every charge watch log, newest first: [{start, end, points: [{t, soc, kw, ...}]}].

    Watch logs record changes only, so a point is emitted at every charge-DID line once a current (4802) has been seen,
    from the latest value of each DID; lines in the same second share one point."""
    reads = []
    for p in sorted(glob.glob(W + "/runs/*/watch-*charge*.log")):
        if not CHARGE_LOG.search(os.path.basename(p)):
            continue
        try:
            st = os.stat(p)
            mt = (st.st_mtime, st.st_size)
            if p not in charge_cache or charge_cache[p][0] != mt:
                rows = []
                with open(p, errors="replace") as f:
                    for ln in f:
                        m = CHARGE_LINE.match(ln.rstrip("\n"))
                        if not m:
                            continue
                        rest = m.group(3)
                        new = rest.rsplit("-> ", 1)[1] if "-> " in rest else rest
                        try:
                            ep = datetime.datetime.fromisoformat(m.group(1)).timestamp()  # honours the logged offset
                        except ValueError:
                            continue
                        h = re.match(r"[0-9a-f]+", new)
                        ok = h is not None and len(h.group()) >= CHARGE_HEX[m.group(2)]
                        rows.append([ep, m.group(2), h.group() if ok else None])  # None: failed or short read
                charge_cache[p] = (mt, rows)
        except OSError:
            continue
        reads += charge_cache[p][1]
    reads.sort(key=lambda r: r[0])
    sessions, cur, last = [], {}, None
    for ep, did, h in reads:
        if last is None or ep - last > CHARGE_GAP:
            sessions.append([])
            cur = {}
        last = ep
        if h is None:
            cur.pop(did, None)  # a failed read must not leave the old value in use; the next point shows the gap
        else:
            cur[did] = h
        if "4802" in cur:
            pt = charge_point(cur)
            pt["t"] = time.strftime("%H:%M:%S", time.localtime(ep))
            pt["e"] = ep
            if sessions[-1] and sessions[-1][-1]["e"] == ep:
                sessions[-1][-1] = pt
            else:
                sessions[-1].append(pt)
    out = []
    for s in sessions:
        if s:
            out.append({"start": time.strftime("%Y-%m-%d %H:%M", time.localtime(s[0]["e"])),
                        "end": time.strftime("%H:%M:%S", time.localtime(s[-1]["e"])), "points": s})
    return out[::-1]


def numeric(val, extra):
    if extra:
        first = extra.split(";", 1)[0].strip()  # the first signal's value only, not the next signal's id
        if first.startswith("not available"):
            return None
        m = NUM.search(first)
        if m:
            return float(m.group())
    if re.fullmatch(r"[0-9a-f]{1,8}", val or ""):
        return float(int(val, 16))
    return None


def update():
    logs = glob.glob(W + "/runs/*/watch-*.log")
    if not logs:
        return
    newest = max(logs, key=os.path.getmtime)
    if newest != state["file"]:
        state.update(file=newest, pos=0, keys={}, events=[])
    with open(newest) as f:
        f.seek(state["pos"])
        chunk = f.read()
        state["pos"] = f.tell()
    day = newest.split("/")[-2]
    for ln in chunk.splitlines():
        m = LINE.match(ln)
        if not m:
            if " connected" in ln or "ERROR" in ln or "baseline" in ln:
                state["events"] = (state["events"] + [ln])[-20:]
            continue
        t, key, rest = m.groups()
        parts = rest.split()
        kind = parts[0]
        if kind in ("CHANGE", "noisy", "baseline-noise", "MUTED") and "->" in parts:
            val = parts[parts.index("->") + 1]
        else:
            val = parts[0]
        ex = EXTRA.search(rest)
        name, dec = (ex.group(1), ex.group(2)) if ex else ("", "")
        k = state["keys"].setdefault(key, {"name": "", "hist": [], "changes": 0})
        if name:
            k["name"] = name
        k.update(value=val, decoded=dec, t=t, day=day)
        if kind in ("CHANGE", "noisy", "baseline-noise", "MUTED"):
            k["changes"] += 1
        n = numeric(val, dec)
        if n is not None:
            k["hist"] = (k["hist"] + [[t, n]])[-HIST:]


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SRV, **kw)

    def log_message(self, *a):
        pass

    def send_body(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/matrix.json"):
            with matrix_lock:  # its own lock: a cold parse of every log must not stall /live.json
                body = json.dumps({"logs": matrix_logs()}).encode()
            return self.send_body(body, "application/json")
        if self.path.split("?")[0] == "/charge.json":
            with matrix_lock:
                body = json.dumps({"sessions": charge_sessions()}).encode()
            return self.send_body(body, "application/json")
        if self.path.split("?")[0] in ("/matrix.html", "/charge.html"):
            try:
                with open(W + "/web" + self.path.split("?")[0], "rb") as f:
                    return self.send_body(f.read(), "text/html; charset=utf-8")
            except OSError:
                self.send_error(404)
                return
        if self.path.startswith("/live.json"):
            with lock:
                try:
                    update()
                except OSError:
                    pass
                f = state["file"]
                age = time.time() - os.path.getmtime(f) if f else None
                body = json.dumps({"file": os.path.basename(f) if f else None, "age": age,
                                   "events": state["events"], "keys": state["keys"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def serve(host: str = HOST, port: int = PORT) -> None:
    ThreadingHTTPServer((host, port), H).serve_forever()


if __name__ == "__main__":  # p4-web runs python /w/web/server.py; set P4_WEB_HOST=0.0.0.0 to reach it from other devices
    serve()

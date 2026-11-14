"""Static pages from /srv plus /live.json: values and history from the newest watch log."""
import glob
import json
import os
import re
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

W = "/w"
SRV = "/srv"
HIST = 600  # points kept per DID
LINE = re.compile(r"(\d\d:\d\d:\d\d) ([0-9A-F]{4}:[0-9A-F]{4}) (.*)")
EXTRA = re.compile(r"\[([^\]=]+)=([^\]]*)\]")
NUM = re.compile(r"-?\d+(?:\.\d+)?")

lock = threading.Lock()
state = {"file": None, "pos": 0, "keys": {}, "events": []}
MATRIX = re.compile(r"^(\d\d:\d\d:\d\d) (1BB[34]):7022 (.*)$")
MATRIX_HEX = re.compile(r"[0-9a-f]{64}")
NO_DATA = "ff" * 32  # drawn grey: the lamp did not answer (NRC, timeout) on that read
SPEED = re.compile(r"^(\d\d:\d\d:\d\d) (1631:D003|1601:E36E) (.*)$")
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


def numeric(val, extra):
    if extra:
        m = NUM.search(extra)
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
        if self.path.split("?")[0] == "/matrix.html":
            try:
                with open(W + "/web/matrix.html", "rb") as f:
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


if __name__ == "__main__":  # run as python /w/web/server.py in the p4-web container
    ThreadingHTTPServer(("", 8088), H).serve_forever()

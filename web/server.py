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

    def do_GET(self):
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


ThreadingHTTPServer(("", 8088), H).serve_forever()

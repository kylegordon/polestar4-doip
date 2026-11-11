"""Regenerate static status pages for the Polestar 4 DoIP work every 20 s.

Reads the project (mounted read-only at /w) and the scan log (/status/mapall.out); writes HTML to /srv.
"""
import glob
import html
import json
import os
import re
import time

import yaml

W = "/w"
OUT = "/srv"
SCANLOG = "/status/mapall.out"
CSS = """
:root{--bg:#fff;--fg:#1d2329;--mut:#66707a;--line:#dde2e6;--acc:#0b6bcb;--ok:#2e7d32;--warn:#b26a00;--card:#f6f8fa}
@media (prefers-color-scheme: dark){:root{--bg:#14181c;--fg:#e4e8ec;--mut:#98a2ad;--line:#2c333a;--acc:#5aa9ff;--ok:#7bc47f;--warn:#f0b35a;--card:#1b2026}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px}
a{color:var(--acc)}nav a{margin-right:14px}h1{font-size:20px}h2{font-size:16px;margin-top:24px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600}code,pre,.mono{font-family:ui-monospace,Menlo,monospace;font-size:12px}
pre{background:var(--card);padding:10px;overflow-x:auto;white-space:pre-wrap;word-break:break-all}
.card{background:var(--card);padding:10px 12px;border-radius:6px;margin:8px 0}.mut{color:var(--mut)}
.unknown{color:var(--warn);font-weight:600}.confirmed{color:var(--ok);font-weight:600}td.v{word-break:break-all;max-width:420px}
"""


def page(name, title, body, refresh=30):
    nav = '<nav><a href="index.html">Overview</a><a href="live.html">Live</a><a href="findings.html">Findings</a><a href="signals.html">Signals</a><a href="text.html">Text</a><a href="marks.html">Timeline</a><a href="logs.html">Watch logs</a></nav>'
    doc = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           '<meta http-equiv="refresh" content="%d"><title>%s</title><style>%s</style></head><body>%s<h1>%s</h1>%s'
           '<p class="mut">Generated %s; refreshes every %ds.</p></body></html>') % (
        refresh, html.escape(title), CSS, nav, html.escape(title), body, time.strftime("%H:%M:%S"), refresh)
    tmp = os.path.join(OUT, name + ".tmp")
    with open(tmp, "w") as f:
        f.write(doc)
    os.replace(tmp, os.path.join(OUT, name))


def e(s):
    return html.escape(str(s))


VIN = re.compile(r"(?:YSM|LPS|LRW|YV1)[A-HJ-NPR-Z0-9]{14}")  # Polestar/Volvo WMIs


def text_of(hexdata):
    """Printable ASCII in a DID value (padding 00/ff/20 stripped), or '' if it isn't mostly text."""
    try:
        raw = bytes.fromhex(hexdata)
    except ValueError:
        return ""
    raw = raw.strip(b"\x00\xff\x20")
    if len(raw) < 4:
        return ""
    printable = sum(1 for c in raw if 32 <= c < 127)
    if printable / len(raw) < 0.9:
        return ""
    s = "".join(chr(c) if 32 <= c < 127 else "." for c in raw)
    if not re.search(r"[A-Za-z0-9]{3}", s):
        return ""
    s = re.sub(r"89\d{16,18}", lambda m: m.group()[:6] + "… [SIM ICCID hidden]", s)
    s = re.sub(r"(?<!\d)\d{15,16}(?!\d)", "[15-16 digit id (IMEI?) hidden]", s)
    return VIN.sub(lambda m: "[VIN hidden]" if len(re.findall(r"[G-HJ-NPR-Z]", m.group())) >= 2 else m.group(), s)


def read_jsonl(path):
    out = []
    try:
        with open(path) as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def scans():
    """addr -> did -> (status, data, t), best answer wins, latest among equals."""
    rank = {"ok": 2, "nrc": 1, "nack": 1, "timeout": 0}
    res = {}
    for p in sorted(glob.glob(W + "/runs/*/scan-*.jsonl")):
        for r in read_jsonl(p):
            if "did" not in r:
                continue
            d = res.setdefault(r["tgt"].upper(), {})
            cur = d.get(r["did"])
            new = (r["status"], r.get("data", r.get("code", "")), r["t"])
            if cur is None or rank.get(new[0], 0) >= rank.get(cur[0], 0):
                d[r["did"]] = new
    return res


def watch_last():
    """addr:did -> (value, time, file) from the newest watch logs."""
    last = {}
    for p in sorted(glob.glob(W + "/runs/*/watch-*.log"), key=os.path.getmtime):
        day = p.split("/")[-2]
        try:
            lines = open(p).read().splitlines()
        except OSError:
            continue
        for ln in lines:
            m = re.match(r"(\d\d:\d\d:\d\d) ([0-9A-F]{4}:[0-9A-F]{4}) (.*)", ln)
            if not m:
                continue
            t, k, rest = m.groups()
            parts = rest.split()
            if parts[0] in ("CHANGE", "noisy", "baseline-noise") and "->" in parts:
                v = parts[parts.index("->") + 1]
            else:
                v = parts[0]
            last[k] = (v, "%s %s" % (day, t), os.path.basename(p))
    return last


def scan_status(catalogue=()):
    try:
        txt = open(SCANLOG).read().replace("\r", "\n")
    except OSError:
        return "<p class=mut>No scan log.</p>"
    mods = re.findall(r"^=== (\S+) (\S+)", txt, re.M)
    done = re.findall(r"^(\S+): (\d+) new OK; (\d+) known OK in total", txt, re.M)
    prog = re.findall(r"^\s+(\d+/\d+, \d+ OK, [\d.]+/s, ~\d+ min left)", txt, re.M)
    errs = len(re.findall(r"Error response|Traceback|connection lost", txt, re.I))
    cur = mods[-1] if mods else ("-", "")
    finished = "ALL DONE" in txt
    body = '<div class="card"><b>Full-car scan:</b> %s' % (
        "finished" if finished else "scanning <b>%s</b> (started %s) %s" % (e(cur[0]), e(cur[1]), e(prog[-1]) if prog else ""))
    body += ' &middot; %d modules done &middot; errors: %d</div>' % (len(done), errs)
    if done:
        info = {m["addr"].upper(): m for m in catalogue}
        body += "<table><tr><th>Module</th><th>Label</th><th>Role</th><th>New OK DIDs</th><th>Known OK total</th></tr>"
        body += "".join('<tr><td><a href="m-%s.html">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            a, a, e(info.get(a.upper(), {}).get("label", "")), e(info.get(a.upper(), {}).get("role", "")), n, k) for a, n, k in done)
        body += "</table>"
    return body


def main():
    os.makedirs(OUT, exist_ok=True)
    mods = yaml.safe_load(open(W + "/catalogue/modules.yaml")) or []
    sigs = yaml.safe_load(open(W + "/catalogue/signals.yaml")) or []
    sigs = sigs.get("signals", sigs) if isinstance(sigs, dict) else sigs
    signame = {}
    for s in sigs:
        addrs = s.get("module", s.get("modules", s.get("addr", "")))
        addrs = addrs if isinstance(addrs, list) else str(addrs).split(",")
        for a in addrs:
            signame["%s:%s" % (str(a).strip().upper(), str(s.get("did", "")).upper())] = s.get("name", "")
    sc = scans()
    wl = watch_last()

    rows = []
    for m in mods:
        a = m["addr"].upper()
        d = sc.get(a, {})
        ok = sum(1 for v in d.values() if v[0] == "ok")
        st = m.get("status", "")
        rows.append('<tr><td><a href="m-%s.html">%s</a></td><td>%s</td><td>%s</td><td class="%s">%s</td><td>%d / %d</td><td class=mut>%s</td></tr>' % (
            a, a, e(m.get("label", "")), e(m.get("role", "")), e(st), e(st), ok, len(d), e(m.get("note", ""))))
    body = scan_status(mods)
    body += "<h2>Modules</h2><p class=mut>OK DIDs / DIDs tried, across all scan runs. Unknown modules in amber.</p>"
    body += "<table><tr><th>Addr</th><th>Label</th><th>Role</th><th>Status</th><th>DIDs</th><th>Note</th></tr>%s</table>" % "".join(rows)
    page("index.html", "Polestar 4 DoIP: live status", body)

    texts = []
    for m in mods:
        a = m["addr"].upper()
        d = sc.get(a, {})
        r = []
        for did in sorted(d):
            st, data, t = d[did]
            if st != "ok" or did == "F190":
                continue
            k = "%s:%s" % (a, did)
            w = wl.get(k)
            txt = text_of(data)
            if txt:
                texts.append((a, m.get("label", ""), did, txt))
            r.append('<tr><td class=mono>%s</td><td>%s</td><td class="v mono">%s</td><td class=mono><b>%s</b></td><td class="v mono">%s</td><td class=mut>%s</td></tr>' % (
                did, e(signame.get(k, "")), e(data[:200]), e(txt), e(w[0][:200]) if w else "", e(w[1]) if w else ""))
        refused = sorted(x for x, v in d.items() if v[0] == "nrc" and v[1] in ("22", "33", "7F", "7E"))
        b = '<div class=card>%s &middot; %s &middot; status <span class="%s">%s</span><br>%s</div>' % (
            e(m.get("label", "")), e(m.get("role", "")), e(m.get("status", "")), e(m.get("status", "")), e(m.get("note", "")))
        try:
            notes = open(W + "/local/module-notes/%s.md" % a).read().strip()
            b += "".join("<p>%s</p>" % e(para) for para in notes.split("\n\n"))
        except OSError:
            pass
        b += "<table><tr><th>DID</th><th>Signal</th><th>Scan value</th><th>Text</th><th>Last watched value</th><th>Watched at</th></tr>%s</table>" % "".join(r)
        if refused:
            b += "<p class=mut>Exist but refused in that state: %s</p>" % e(", ".join(refused))
        page("m-%s.html" % a, "Module %s %s" % (a, m.get("label", "")), b)

    tr = "".join('<tr><td><a href="m-%s.html">%s</a></td><td>%s</td><td class=mono>%s</td><td class=mono><b>%s</b></td></tr>' % (
        a, a, e(lb), d, e(t)) for a, lb, d, t in texts)
    page("text.html", "Readable text found", "<p class=mut>DID values that decode as printable ASCII (VIN-like strings hidden).</p>"
         "<table><tr><th>Module</th><th>Label</th><th>DID</th><th>Text</th></tr>%s</table>" % tr)

    try:
        ref = open(W + "/local/references.md").read()
        i = ref.find("## Drive")
        ref = ref[i:] if i >= 0 else ref
    except OSError:
        ref = "(no findings file)"
    page("findings.html", "Findings (drives, 2026-11-11)", "<pre>%s</pre>" % e(ref))

    sr = "".join('<tr><td>%s</td><td class=mono>%s</td><td>%s</td><td>%s</td></tr>' % (
        e(s.get("module", s.get("modules", s.get("addr", "")))), e(s.get("did", "")), e(s.get("name", "")), e(s.get("confidence", "")))
        for s in sigs)
    page("signals.html", "Signal catalogue", "<table><tr><th>Module</th><th>DID</th><th>Name</th><th>Confidence</th></tr>%s</table>" % sr)

    mk = []
    for p in sorted(glob.glob(W + "/runs/*/marks.jsonl")):
        mk += read_jsonl(p)
    mr = "".join("<tr><td class=mono>%s</td><td>%s</td></tr>" % (e(x.get("t", "")), e(x.get("mark", ""))) for x in reversed(mk))
    page("marks.html", "Timeline (marks)", "<table><tr><th>Time</th><th>Mark</th></tr>%s</table>" % mr)

    logs = sorted(glob.glob(W + "/runs/*/watch-*.log"), key=os.path.getmtime, reverse=True)
    li = []
    for p in logs:
        name = "log-%s-%s.html" % (p.split("/")[-2], os.path.basename(p)[:-4])
        lines = [ln for ln in open(p).read().splitlines() if " CHANGE " in ln or "connected" in ln or "ERROR" in ln]
        page(name, os.path.basename(p), "<p class=mut>%d changes (newest first)</p><pre>%s</pre>" % (len(lines), e("\n".join(reversed(lines)))), refresh=60)
        li.append('<tr><td><a href="%s">%s</a></td><td>%s</td><td>%d</td></tr>' % (name, e(p.split("/")[-2]), e(os.path.basename(p)), len(lines)))
    page("logs.html", "Watch logs", "<table><tr><th>Day</th><th>Log</th><th>Changes</th></tr>%s</table>" % "".join(li))


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as ex:  # keep serving the last good pages
            print("gen failed:", repr(ex), flush=True)
        time.sleep(20)

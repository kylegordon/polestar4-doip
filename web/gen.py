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
.cells{display:grid;grid-template-columns:repeat(auto-fill,minmax(40px,1fr));gap:3px}
.cell{position:relative;height:60px;background:var(--card);border-radius:3px;overflow:hidden;font-size:11px;text-align:center;display:flex;flex-direction:column;justify-content:center}
.cell i{position:absolute;left:0;right:0;bottom:0;height:var(--h);background:var(--acc);opacity:.35}
.cell b,.cell span,.cell small{position:relative}.cell b{font-size:9px;font-weight:400;color:var(--mut)}.cell small{font-size:9px;color:var(--mut)}
.temps{display:flex;flex-wrap:wrap;gap:4px}.temps span{background:var(--card);padding:2px 6px;border-radius:3px;font-size:12px}
.unknown{color:var(--warn);font-weight:600}.confirmed{color:var(--ok);font-weight:600}td.v{word-break:break-all;max-width:420px}
"""


def page(name, title, body, refresh=30):
    nav = '<nav><a href="index.html">Overview</a><a href="live.html">Live</a><a href="battery.html">Battery</a><a href="findings.html">Findings</a><a href="signals.html">Signals</a><a href="research.html">Research</a><a href="text.html">Text</a><a href="marks.html">Timeline</a><a href="logs.html">Watch logs</a></nav>'
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


def latest_scan_results(n=4):
    """Automatic: the last few scan slots that found new DIDs, from the newest unattended.log (no manual upkeep)."""
    logs = sorted(glob.glob(W + "/runs/*/unattended.log"))
    if not logs:
        return ""
    hits, cur = [], None
    try:
        with open(logs[-1], errors="replace") as f:
            for line in f:
                m = re.match(r"^(\S+) (\d\d:\d\d):\d\d scan (\S+): start$", line.strip())
                if m:
                    cur = ("%s %s" % (m.group(1), m.group(2)), m.group(3))
                    continue
                m = re.match(r"^(\S+): (\d+) new OK", line.strip())
                if m and cur and m.group(1) == cur[1].split(":")[0]:
                    if int(m.group(2)) > 0:
                        hits.append("%s %s: %s new DIDs" % (cur[0], cur[1].replace(":X:", " full-range ").replace(":", " "), m.group(2)))
                    cur = None
    except OSError:
        return ""
    if not hits:
        return ""
    return "<p class=mut>Latest scan results (automatic):</p><ul>%s</ul>" % "".join("<li>%s</li>" % e(h) for h in hits[-n:][::-1])


def status_lines():
    """The first three lines of local/web-status.txt (latest status or discoveries), shown at the top of the overview."""
    try:
        with open(W + "/local/web-status.txt", errors="replace") as f:
            lines = [l.strip() for l in f if l.strip()][:3]
    except OSError:
        return ""
    return "<ul class=status>%s</ul>" % "".join("<li>%s</li>" % e(l) for l in lines) if lines else ""


def research():
    """Research reports (local/analysis/*.md, written by the Haiku agents) newest first, plus agents still running.
    Returns (rows, top) where top is a short list for the overview."""
    items = []
    for p in glob.glob(W + "/local/analysis/*.md"):
        txt = open(p, errors="replace").read()
        title = next((ln.lstrip("# ").strip() for ln in txt.splitlines() if ln.startswith("#")), os.path.basename(p))
        done = txt.rstrip().endswith("DONE")
        name = "r-%s.html" % os.path.basename(p)[:-3]
        page(name, title, "<p class=mut>%s</p><pre>%s</pre>" % (e(os.path.basename(p)), e(txt)), refresh=60)
        items.append((os.path.getmtime(p), name, title, "done" if done else "writing"))
    for b in glob.glob(W + "/local/unattended/investigate/brief-newdids-*.txt"):
        out = W + "/local/analysis/" + os.path.basename(b)[6:-4] + ".md"
        if not os.path.exists(out):
            items.append((os.path.getmtime(b), "", "Investigating " + os.path.basename(b)[6:-4], "running"))
    items.sort(reverse=True)
    fmt = lambda t: time.strftime("%m-%d %H:%M", time.localtime(t))
    rows = "".join('<tr><td class=mono>%s</td><td>%s</td><td>%s</td></tr>' % (
        fmt(t), ('<a href="%s">%s</a>' % (n, e(ti))) if n else e(ti), e(st)) for t, n, ti, st in items)
    top = "".join('<li>%s %s (%s)</li>' % (fmt(t), ('<a href="%s">%s</a>' % (n, e(ti))) if n else e(ti), e(st)) for t, n, ti, st in items[:3])
    return rows, top


RATE = 45.0  # DIDs per second in practice (most reads get a quick NRC 31; measured 2026-11-13)
DEFAULT_DIDS = 8192  # DIDs in the tool's default scan ranges


def slot_secs(slot, watch):
    """Rough seconds for one scan slot plus the watch that follows it (info-block slots run back to back)."""
    mod, _, rng = slot.partition(":")
    rng = rng[2:] if rng.startswith("X:") else rng  # phase-2 slot marker
    n = DEFAULT_DIDS
    if rng:
        try:
            n = sum(int(b or a, 16) - int(a, 16) + 1 for a, _, b in (part.partition("-") for part in rng.split(",")))
        except ValueError:
            n = DEFAULT_DIDS  # unexpected slot text: assume a full module
    if "F400" in rng:
        return n / RATE
    if slot.split(":")[1:2] == ["X"]:
        watch /= 3  # phase 2: a watch only after every third chunk
    return n / RATE + watch


def progress():
    """Current task, overall progress and rough ETAs from the unattended script's progress file."""
    files = sorted(glob.glob(W + "/runs/*/unattended.progress.json"))
    if not files:
        return ""
    try:
        p = json.load(open(files[-1]))
    except (OSError, ValueError):
        return ""
    if not isinstance(p, dict):
        return ""
    now = time.time()
    rem, gated, watch, parked = p.get("remaining", []), set(p.get("gated", [])), p.get("watch_secs", 240), p.get("parked", 0)
    # Same order as the scanner: parked = P-only (gated) slots first; driving = the rest first, P-only after.
    g = [x for x in rem if x.split(":")[0] in gated]
    o = [x for x in rem if x.split(":")[0] not in gated]
    rem = g + o if parked else o + g
    total = p.get("total", 0) or 1
    done = total - len(rem)
    mods, order = {}, []
    t = 0.0
    for sl in rem:
        m = sl.split(":")[0]
        t += slot_secs(sl, 0 if parked else watch)  # no watches while parked
        if m not in mods:
            order.append(m)
        mods[m] = (t, m in gated)
    hm = lambda secs: "%dh %02dm" % (secs // 3600, secs % 3600 // 60) if secs >= 3600 else "%d min" % max(1, round(secs / 60))
    age = now - p.get("since", now)
    out = '<div class=card><b>Now:</b> %s <span class=mut>(for %s)</span><br>' % (e(p.get("current", "")), hm(age))
    out += '<b>Scan queue:</b> %d of %d slots done (%d%%), %d left; roughly %s of car time to finish%s.</div>' % (
        done, total, 100 * done // total, len(rem), hm(t) if rem else "0 min",
        "" if parked else "; P-only modules wait until the car is parked in P")
    if order:
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            e(m), "in %s" % hm(mods[m][0]), "P only" if mods[m][1] else "any time") for m in order)
        out += "<details><summary>Module ETAs (cumulative, car connected)</summary><table><tr><th>Module</th><th>Done</th><th>When</th></tr>%s</table></details>" % rows
    return out


BATTERY_KEYS = ("1635:DA31", "1635:EE83", "1635:4907", "1635:4908", "1635:4801", "1635:497C", "1635:4802", "1635:DA17", "1635:DA18")


def latest_values(keys, wl):
    """key -> (hex, 'YYYY-MM-DD HH:MM:SS', source), the newest of the watch logs and the snapshots.

    Watch logs carry local time and snapshots UTC; they are compared as text, which is right while UK time = UTC
    (the winter months these runs cover)."""
    out = {k: wl[k] for k in keys if k in wl and hexval(wl[k][0]) is not None}
    for p in glob.glob(W + "/runs/*/snap-*.json"):
        try:
            with open(p) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict) or not isinstance(d.get("values"), dict):
            continue
        t = str(d.get("t", ""))[:19].replace("T", " ")
        for k in keys:
            v = d["values"].get(k)
            if isinstance(v, str) and hexval(v) is not None and (k not in out or t > out[k][1]):
                out[k] = (v, t, os.path.basename(p))
    return out


def age_minutes(when):
    """Minutes since a 'YYYY-MM-DD HH:MM:SS' local time, or None if it does not parse."""
    try:
        return (time.time() - time.mktime(time.strptime(when[:19], "%Y-%m-%d %H:%M:%S"))) / 60
    except (TypeError, ValueError, OverflowError):
        return None


def hexval(s):
    """The bytes of a hex string, or None for anything else (a watch log may hold 'nrc', '-' or a cut-off value)."""
    try:
        return bytes.fromhex(s)
    except (TypeError, ValueError):
        return None


def u16s(hexdata):
    b = bytes.fromhex(hexdata)
    return [int.from_bytes(b[i:i + 2], "big") for i in range(0, len(b) - 1, 2)]


def battery(wl):
    """Cell-group voltages (1635 DA31, 0xFFFF = unused slot) and pack temperatures (EE83, 0.01 C - 50) as a grid."""
    v = latest_values(BATTERY_KEYS, wl)
    if "1635:DA31" not in v:
        return "<p class=mut>No cell reading recorded yet (1635 DA31).</p>"
    raw, when, src = v["1635:DA31"]
    cells = [(i + 1, mv) for i, mv in enumerate(u16s(raw)) if mv != 0xFFFF]
    if not cells:
        return "<p class=mut>Latest DA31 reading has no valid cells (%s, %s).</p>" % (e(when), e(src))
    mvs = [mv for _, mv in cells]
    lo, hi, mean = min(mvs), max(mvs), sum(mvs) / len(mvs)
    span = max(hi - lo, 1)
    head = "<div class=card>%d cell groups &middot; min %d mV &middot; max %d mV &middot; mean %.1f mV &middot; spread <b>%d mV</b> &middot; sum %.2f V" % (
        len(cells), lo, hi, mean, hi - lo, sum(mvs) / 1000)
    extra = []
    for k, fmt, scale, add in (("1635:4801", "SoC %.1f %%", 0.002, 0), ("1635:497C", "pack %.2f V", 0.01, 0),
                               ("1635:4802", "current %.1f A", 0.1, -1638.4)):
        if k in v:
            extra.append(fmt % (int.from_bytes(hexval(v[k][0]), "big") * scale + add))
    head += "".join(" &middot; %s" % x for x in extra)
    head += "<br><span class=mut>Cells read %s (%s). Other values are the newest of each and may be from a different time.</span></div>" % (e(when), e(src))
    age = age_minutes(when)
    if age is None or age > 10:
        head = "<p class=unknown>Old reading: these cells were read %s, not live.</p>" % (
            "at an unknown time" if age is None else "%s ago" % ("%.0f min" % age if age < 120 else "%.1f h" % (age / 60) if age < 2880 else "%.0f days" % (age / 1440))) + head
    grid = "".join('<div class=cell title="cell %d: %d mV" style="--h:%d%%"><i></i><b>%d</b><span>%d</span><small>+%d</small></div>' % (
        n, mv, 15 + 85 * (mv - lo) // span, n, mv, mv - lo) for n, mv in cells)
    body = head + "<h2>Cell groups</h2><p class=mut>Each box: group number, voltage in mV, and mV above the lowest group. Bar height shows the same difference.</p><div class=cells>%s</div>" % grid
    if "1635:EE83" in v:
        traw, twhen, tsrc = v["1635:EE83"]
        temps = [x * 0.01 - 50 for x in u16s(traw) if x != 0xFFFF]
        if temps:
            body += "<h2>Pack temperatures</h2><div class=card>%d sensors &middot; min %.1f &deg;C &middot; max %.1f &deg;C<br><span class=mut>Read %s (%s)</span></div>" % (
                len(temps), min(temps), max(temps), e(twhen), e(tsrc))
            body += "<div class=temps>%s</div>" % "".join("<span>%.1f</span>" % t for t in temps)
    for k, label in (("1635:4907", "Highest cell"), ("1635:4908", "Lowest cell")):
        # only beside a cell grid read in the same minute, so the two cannot contradict each other
        if k in v and len(v[k][0]) >= 6 and v[k][1][:16] == when[:16]:
            b = hexval(v[k][0][:6])
            body += "<p>%s: group %d, %d mV <span class=mut>(%s)</span></p>" % (label, b[0] + 1, int.from_bytes(b[1:3], "big"), e(v[k][1]))
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
    try:
        rrows, rtop = research()
    except (OSError, ValueError, TypeError):  # a report or brief changed mid-read: skip this section this round
        rrows, rtop = "", ""
    page("research.html", "Research (Haiku agents)", "<table><tr><th>Time</th><th>Report</th><th>State</th></tr>%s</table>" % rrows)
    try:
        prog = progress()
    except (OSError, ValueError, TypeError, KeyError):
        prog = ""
    body = status_lines() + latest_scan_results() + prog + ("<h2>Research</h2><ul>%s</ul><p class=mut><a href=research.html>All reports</a></p>" % rtop if rtop else "") + scan_status(mods)
    body += "<h2>Modules</h2><p class=mut>OK DIDs / DIDs tried, across all scan runs. Unknown modules in amber.</p>"
    body += "<table><tr><th>Addr</th><th>Label</th><th>Role</th><th>Status</th><th>DIDs</th><th>Note</th></tr>%s</table>" % "".join(rows)
    page("index.html", "Polestar 4 DoIP: live status", body)
    try:
        page("battery.html", "Battery cells", battery(wl))
    except Exception as ex:  # a bad reading must not stop the other pages
        print("battery page failed:", repr(ex), flush=True)
        page("battery.html", "Battery cells", "<p class=mut>Could not draw the battery page: %s</p>" % e(ex))

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

"""Render the public site's pages from git-tracked files. See the package docstring and docs/site-design.md.

Every page links to the file it was built from on GitHub. Free text from the repository passes through
`gate.clean` before it is placed in a page; the finished output is scanned by `gate.scan_dir`.
"""
import os
import re
import shutil

import markdown
import yaml

from .. import decode, hazards
from ..render import TOKENS, e
from . import gate
from .inputs import Inputs

REPO_URL = "https://github.com/kylegordon/polestar4-doip"
SOURCE_URL = REPO_URL + "/blob/main/"
OWNER = "kylegordon"  # the owner's GitHub handle; the site names no one else
CAR = "one UK Polestar 4, customer software 4.2.11"

NAV = (("index.html", "Start here"), ("hazards.html", "Hazards"), ("signals.html", "Signals"),
       ("findings.html", "Findings"), ("contribute.html", "Contribute"), ("glossary.html", "Glossary"))

LABEL = {"C": "Confirmed", "P": "Provisional"}

SITE_CSS = TOKENS + """
:root{color-scheme:light dark;--bad:#b3261e}
@media (prefers-color-scheme: dark){:root{--bad:#ff8a80}}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0}
header,main,footer,.banner{max-width:980px;margin:0 auto;padding:0 16px}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 16px;padding-top:14px;padding-bottom:10px;border-bottom:1px solid var(--line)}
header .brand{font-weight:700;color:var(--fg);text-decoration:none;margin-right:8px}
nav{display:flex;flex-wrap:wrap;gap:4px 14px}nav a{color:var(--acc);text-decoration:none}nav a[aria-current]{color:var(--fg);font-weight:600}
.banner{color:var(--mut);font-size:14px;padding-top:8px;padding-bottom:8px}
main{padding-bottom:32px}
h1{font-size:26px;line-height:1.25;margin:16px 0 8px}h2{font-size:20px;margin-top:32px}h3{font-size:17px}
a{color:var(--acc)}
code,pre{font-family:ui-monospace,Menlo,monospace;font-size:14px}
pre{background:var(--card);padding:10px 12px;border-radius:6px;overflow-x:auto}
.mut{color:var(--mut)}
.card{background:var(--card);padding:12px 14px;border-radius:8px;margin:12px 0}
.warn{border:2px solid var(--bad);border-radius:8px;padding:12px 14px;margin:16px 0}
.warn h2{margin-top:0;color:var(--bad);font-size:18px}
.stats{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}.stats div{background:var(--card);border-radius:8px;padding:10px 14px;min-width:140px}
.stats b{display:block;font-size:24px}
.table{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:15px}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600}
.badge{display:inline-block;border-radius:4px;padding:0 6px;font-size:13px;font-weight:600;white-space:nowrap}
.badge.c{color:var(--ok);border:1px solid var(--ok)}.badge.p{color:var(--warn);border:1px solid var(--warn)}
.badge.u{color:var(--mut);border:1px dashed var(--mut)}
.badge.block{color:var(--bad);border:1px solid var(--bad)}.badge.caution{color:var(--warn);border:1px solid var(--warn)}
li.lead{list-style:none;margin-left:-1.2em;border-left:3px dashed var(--mut);padding-left:10px}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.filters input,.filters select{font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
.filters input{flex:1 1 220px}
ol.steps>li{margin-bottom:18px}.stop{color:var(--bad);font-weight:600}
dl dt{font-weight:700;margin-top:14px}dl dd{margin-left:0}
footer{border-top:1px solid var(--line);padding-top:12px;padding-bottom:24px;font-size:14px;color:var(--mut)}
@media (max-width:640px){
 table.cards thead{display:none}table.cards tr{display:block;border-bottom:1px solid var(--line);padding:6px 0}
 table.cards td{display:block;border:0;padding:2px 0}table.cards td[data-label]::before{content:attr(data-label) ": ";color:var(--mut)}
}
"""


def badge(conf: str) -> str:
    return '<span class="badge %s">%s</span>' % (conf.lower(), LABEL[conf])


def unconfirmed() -> str:
    return '<span class="badge u">Unconfirmed</span>'


def t(text: object) -> str:
    """Free text from the repository, cleaned (dates, identifiers) and escaped."""
    return e(gate.clean(str(text)))


def source_link(path: str) -> str:
    return '<a href="%s%s">%s</a>' % (SOURCE_URL, e(path), e(path))


class Site:
    def __init__(self, inputs: Inputs, out_dir: str, commit: str = ""):
        self.inputs = inputs
        self.out = out_dir
        # Short id only: 7 characters cannot form the 10-digit run privacy.mask hides.
        self.commit = commit if re.fullmatch(r"[0-9a-f]{7,40}", commit or "") else ""
        self.pages: list[str] = []
        self.modules = self._modules()
        self.signals = decode.load(inputs.input_path("catalogue/signals.yaml"))
        hazards.clear_cache()
        self.hazards = hazards.load(inputs.input_path("catalogue/hazards.yaml"))
        known = set(self.modules)
        for sig in self.signals:
            for addr in sig["module"].split(","):
                if addr.strip().upper() not in known:
                    raise ValueError("signal %s: module %s is not in catalogue/modules.yaml" % (sig["id"], addr))
        for h in self.hazards:
            if "%04X" % h.module not in known:
                raise ValueError("hazard %04X:%04X: module is not in catalogue/modules.yaml" % (h.module, h.did))

    def _modules(self) -> dict[str, dict]:
        doc = yaml.safe_load(self.inputs.read_input("catalogue/modules.yaml")) or []
        return {str(m["addr"]).upper(): m for m in doc}

    def write(self, name: str, title: str, body: str, sources: list[str]) -> None:
        nav = "".join('<a href="%s"%s>%s</a>' % (href, ' aria-current="page"' if href == name else "", label)
                      for href, label in NAV)
        src = ", ".join(source_link(p) for p in sources)
        built = " Built from commit <code>%s</code>." % self.commit[:7] if self.commit else ""
        doc = (
            '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s · Polestar 4 DoIP</title><style>%s</style></head><body>\n'
            '<header><a class="brand" href="index.html">Polestar 4 DoIP</a><nav>%s</nav></header>\n'
            '<p class="banner">Everything here comes from %s. Other markets and software versions may differ.</p>\n'
            '<main><h1>%s</h1>\n%s\n</main>\n'
            '<footer><p>This page is built from %s in the <a href="%s">project repository</a>.%s '
            'Read-only diagnostic reads only; read <a href="hazards.html">Hazards</a> before connecting anything. '
            'No cookies, analytics or third-party scripts. Maintained by %s on GitHub. MIT licence.</p></footer>\n'
            '</body></html>\n'
        ) % (e(title), SITE_CSS, nav, e(CAR), e(title), body, src, REPO_URL, built, e(OWNER))
        with open(os.path.join(self.out, name), "w", encoding="utf-8") as f:
            f.write(doc)
        self.pages.append(name)

    # -- pages ---------------------------------------------------------------------------------------------

    def counts(self) -> dict[str, int]:
        return {
            "signals": len(self.signals),
            "confirmed": sum(1 for s in self.signals if s["confidence"] == "C"),
            "provisional": sum(1 for s in self.signals if s["confidence"] == "P"),
            "modules": len(self.modules),
            "blocked": sum(1 for h in self.hazards if h.action == "block"),
            "caution": sum(1 for h in self.hazards if h.action == "caution"),
        }

    def hazard_box(self) -> str:
        blocks = ", ".join("<code>%04X:%04X</code>" % (h.module, h.did) for h in self.hazards if h.action == "block")
        return ('<div class="warn"><h2>Before you connect anything</h2><p>Some reads knock a module off the car\'s '
                'network. Never read %s. The project\'s tool refuses them, but other tools will not. '
                '<a href="hazards.html">Read the hazards and what to do if something goes wrong</a>.</p></div>' % blocks)

    def index(self) -> None:
        c = self.counts()
        body = """
<p>This project records what a Polestar 4 reports through its diagnostic (OBD) port when you only ask it
questions. Each car module answers numbered data items. We work out what they mean by watching values change
while doing something to the car: opening a door, pressing the brake, driving. Nothing is written to the car.</p>
<p>It is useful if you own a Polestar 4 and want to know what your car exposes, or if you want to check these
findings against your own car. You do not need to connect anything to read it.</p>
<div class="stats">
<div><b>%(signals)d</b>signals decoded</div>
<div><b>%(confirmed)d</b>Confirmed</div>
<div><b>%(provisional)d</b>Provisional</div>
<div><b>%(modules)d</b>modules answering</div>
<div><b>%(blocked)d + %(caution)d</b>hazards (never read + caution)</div>
</div>
%(box)s
<h2>Where to go next</h2>
<ul>
<li><a href="findings.html">Findings</a>: what each module is and what has been learned, including leads.</li>
<li><a href="signals.html">Signals</a>: every decoded value, searchable, with how sure we are.</li>
<li><a href="hazards.html">Hazards</a>: reads to avoid and how to recover if a module stops answering.</li>
<li><a href="contribute.html">Contribute</a>: compare with your car, report a correction, or run a scan.</li>
<li><a href="glossary.html">Glossary</a>: the terms used on this site in plain English.</li>
</ul>
<h2>How sure are we?</h2>
<ul>
<li>%(c)s the same change was seen at least twice, in both directions, with the action written down.</li>
<li>%(p)s seen once, or the meaning fits but has not been repeated.</li>
<li>%(u)s a lead: something moved once or at a plausible time. Not in the catalogue yet.</li>
</ul>
<p>All of this comes from one car. Your car may run different software and answer differently.</p>
""" % dict(c, box=self.hazard_box(), c=badge("C"), p=badge("P"), u=unconfirmed())
        self.write("index.html", "Start here", body, ["README.md", "catalogue/signals.yaml", "catalogue/modules.yaml"])

    @staticmethod
    def _recorded_in(h: hazards.Hazard) -> str:
        where = [] if h.source == "built-in" else ["catalogue/hazards.yaml"]
        if (h.module, h.did) in hazards.BUILTIN_BLOCKED:
            where.append("tool code")
        return " and ".join(where)

    def hazards_page(self) -> None:
        rows = []
        rules = []
        for h in self.hazards:
            rule = "Never read" if h.action == "block" else "Caution"
            mod = self.modules.get("%04X" % h.module, {})
            rows.append('<tr><td data-label="Read"><code>%04X:%04X</code></td><td data-label="Module">%s</td>'
                        '<td data-label="Rule"><span class="badge %s">%s</span></td><td data-label="What happened">%s</td>'
                        '<td data-label="Evidence">%s</td><td data-label="Recorded in">%s</td></tr>' % (
                            h.module, h.did, t(mod.get("role", "")), h.action, rule, t(h.why),
                            t(h.evidence) or '<span class="mut">none recorded</span>',
                            self._recorded_in(h)))
            rules.append("%04X:%04X %s" % (h.module, h.did, h.action))
        body = """
<p>A few reads have upset a module on this car: it stopped answering, and once a warning lamp blinked and the
car refused new diagnostic connections until the adaptor was unplugged. No lasting harm has been seen, but
these reads are best avoided. The project's tool refuses them before anything is sent.</p>
<h2>Two kinds of rule</h2>
<ul>
<li><span class="badge block">Never read</span> the read is refused, on that module and on any broadcast that would
reach it. Seen to knock a module off the network.</li>
<li><span class="badge caution">Caution</span> refused by default. The module stopped answering once after this read,
probably because it was still starting up. The tool only allows it with <code>--allow-caution</code> or a
careful (<code>--paced</code>) scan.</li>
</ul>
<div class="warn"><h2>If a module stops answering</h2>
<ol>
<li><b>Stop.</b> Press Ctrl-C, or run <code>docker stop p4-live</code> in another terminal.</li>
<li><b>Do not retry</b> the read that caused it, and do not start another scan.</li>
<li><b>Wait</b> a minute or two. Modules on this car have come back on their own within about a minute.</li>
<li>If the car still refuses diagnostic connections, <b>unplug the adaptor from the OBD port and plug it back
in</b>. Then check with a single harmless command before doing anything else.</li>
<li>Tell us in an issue what you read and what happened, so the rule can be added.</li>
</ol></div>
<h2>The list</h2>
<div class="table"><table class="cards"><thead><tr><th>Read</th><th>Module</th><th>Rule</th><th>What happened</th>
<th>Evidence</th><th>Recorded in</th></tr></thead><tbody>
%s
</tbody></table></div>
<p class="mut">Read = module address : data identifier, both in hexadecimal. A broadcast (functional address
<code>1FFF</code>) or a range sweep through one of these also reaches the module, so the tool refuses those too.
Entries recorded in the tool code as well hold even if the catalogue file is missing.</p>
<h2>The exact rules</h2>
<p>For anyone writing their own tool: one rule per line, <code>module:did action</code>.</p>
<pre>%s</pre>
""" % ("\n".join(rows), e("\n".join(rules)))
        self.write("hazards.html", "Hazards", body, ["catalogue/hazards.yaml", "tool/p4doip/hazards.py"])

    def signals_page(self) -> None:
        rows = []
        mods = sorted({m.strip().upper() for s in self.signals for m in s["module"].split(",")})
        for s in sorted(self.signals, key=lambda s: (s["module"], s["did"], s["id"])):
            addrs = [m.strip().upper() for m in s["module"].split(",")]
            labels = " / ".join(str(self.modules.get(a, {}).get("label", "?")) for a in addrs)
            rows.append(
                '<tr data-mod="%s" data-conf="%s"><td data-label="Signal">%s<br><code class="mut">%s</code></td>'
                '<td data-label="Module"><code>%s</code> <span class="mut">%s</span></td><td data-label="DID"><code>%s</code></td>'
                '<td data-label="Unit">%s</td><td data-label="How sure">%s</td></tr>' % (
                    e(",".join(addrs)), s["confidence"], t(s["name"]), e(s["id"]), e(", ".join(addrs)), t(labels),
                    e(str(s["did"]).upper()), t(str(s.get("unit", "")).strip()), badge(s["confidence"])))
        options = "".join('<option value="%s">%s %s</option>' % (m, m, t(self.modules.get(m, {}).get("label", "")))
                          for m in mods)
        body = """
<p>Every decoded signal in the catalogue: %d in all. Module and DID are hexadecimal addresses. Leads (things
that moved once) are not listed here; they are on the <a href="findings.html">Findings</a> page marked
%s.</p>
<div class="filters" role="search">
<input id="q" type="search" placeholder="Search name, id, module or DID" aria-label="Search signals">
<select id="conf" aria-label="How sure"><option value="">Any confidence</option><option value="C">Confirmed</option><option value="P">Provisional</option></select>
<select id="mod" aria-label="Module"><option value="">Any module</option>%s</select>
</div>
<p id="count" class="mut" aria-live="polite"></p>
<div class="table"><table class="cards" id="sigs"><thead><tr><th>Signal</th><th>Module</th><th>DID</th><th>Unit</th><th>How sure</th></tr></thead><tbody>
%s
</tbody></table></div>
<p class="mut">Encodings, scaling and real examples are in the catalogue file linked below.</p>
<script>
(function(){
var q=document.getElementById("q"),c=document.getElementById("conf"),m=document.getElementById("mod");
var rows=Array.prototype.slice.call(document.querySelectorAll("#sigs tbody tr")),out=document.getElementById("count");
function run(){var s=q.value.toLowerCase(),n=0;rows.forEach(function(r){
var ok=(!c.value||r.dataset.conf===c.value)&&(!m.value||r.dataset.mod.split(",").indexOf(m.value)>=0)&&(!s||r.textContent.toLowerCase().indexOf(s)>=0);
r.hidden=!ok;if(ok)n++;});out.textContent=n+" of "+rows.length+" signals shown";}
[q,c,m].forEach(function(el){el.addEventListener("input",run);});run();
})();
</script>
""" % (len(self.signals), unconfirmed(), options, "\n".join(rows))
        self.write("signals.html", "Signals", body, ["catalogue/signals.yaml", "catalogue/modules.yaml"])

    def _github_links(self, html_text: str, base: str) -> str:
        """Relative links in a rendered document point at the file on GitHub."""
        def fix(m: re.Match) -> str:
            href = m.group(1)
            if re.match(r"[a-z][a-z0-9+.-]*:|#|/", href, re.I):
                return m.group(0)
            path = os.path.normpath(os.path.join(base, href)).replace(os.sep, "/")
            return 'href="%s%s"' % (SOURCE_URL, path)
        return re.sub(r'href="([^"]*)"', fix, html_text)

    def findings_page(self) -> None:
        src = gate.clean(self.inputs.read_input("docs/findings.md"))
        src = re.sub(r"\A# .*\n", "", src)  # the page has its own title
        md = markdown.Markdown(extensions=["tables", "toc", "sane_lists"], extension_configs={"toc": {"toc_depth": "2"}})
        html_text = md.convert(src)
        html_text = self._github_links(html_text, "docs")
        def mark_lead(m: re.Match[str]) -> str:
            return '<li class="lead">%s%s <strong>%s' % (m.group(1) or "", unconfirmed(), m.group(2))
        html_text, leads = re.subn(r"<li>(\s*<p>)?\s*<strong>(Leads?\b)", mark_lead, html_text)
        if not leads:  # the page promises leads are marked; a format change must not drop the badges silently
            raise ValueError("docs/findings.md: no '**Leads**' list items found to mark as Unconfirmed")
        body = ('<p>What has been learned, module by module, in the project\'s own words. Paragraphs marked %s are '
                'leads: seen once or only plausible. Signal names in <code>code</code> are catalogue ids '
                '(<a href="signals.html">Signals</a>). Session dates are shown as month and year.</p>'
                '<details class="card"><summary>Contents</summary>%s</details>\n%s') % (unconfirmed(), getattr(md, "toc", ""), html_text)  # set by the toc extension
        self.write("findings.html", "Findings", body, ["docs/findings.md"])

    def contribute_page(self) -> None:
        body = """
<p>You can help without connecting anything. If you do want to scan your own car, be honest with yourself
about the prerequisites below; the guide assumes them.</p>
<h2>Without a scan</h2>
<ul>
<li><b>Compare with your car.</b> If a finding does not match what your car does, or your car has a feature
this one lacks, <a href="%(repo)s/issues/new?template=observation.yml">open an observation issue</a>. Say which
market your car is from and which software version it runs.</li>
<li><b>Report a mistake.</b> Wrong wording, a wrong label or a broken link:
<a href="%(repo)s/issues/new?template=correction.yml">open a correction issue</a>.</li>
</ul>
<h2>With a scan: what you need</h2>
<ul>
<li>A computer running <b>Linux</b>. The car-facing commands need Docker's host networking, which works on Linux.
On a Mac or Windows PC, Docker cannot reach the adaptor; only the offline commands work there.</li>
<li><b>Docker</b> installed and working for your user, and <b>git</b>.</li>
<li>Being comfortable in a <b>terminal</b>: typing commands, reading their output, stopping a command with Ctrl-C.</li>
<li>An OBD-to-Ethernet adaptor that supports DoIP, plugged into the car's OBD port and your computer.</li>
<li>The car parked, with a healthy 12 V battery. About an hour.</li>
</ul>
<p>The tool only sends read requests and refuses the reads on the <a href="hazards.html">Hazards</a> page.
Read-only is still not risk-free: you use it at your own risk.</p>
<h2>Steps</h2>
<ol class="steps">
<li><b>Read the <a href="hazards.html">Hazards</a> page</b>, including what to do if a module stops answering.</li>
<li><b>Get the code.</b><pre>git clone %(repo)s.git
cd polestar4-doip</pre></li>
<li><b>Run the offline tests.</b> No car needed.<pre>./p4 test</pre>
Expected: the first run builds a Docker image, then a summary line ending in <code>passed</code> (some
tests may be reported as skipped).
<br><span class="stop">Stop if</span> any test fails: open an issue with the output instead of going on.</li>
<li><b>Connect.</b> Plug the adaptor into the car and the computer, wake the car (open a door) and leave it in P.
Give the adaptor's network interface a link-local address (169.254.x.x; in NetworkManager, the IPv4 method
"Link-Local Only"). Then:<pre>./p4 doctor</pre>
Expected: one line per check, each starting <code>OK</code>, including the gateway.
<br><span class="stop">Stop if</span> the gateway check fails. Check the cable and the address; do not loop retries.</li>
<li><b>List the modules.</b><pre>./p4 discover</pre>
Expected: <code>answering: N</code> followed by one line per module address. This car has %(modules)d. A line
marked <code>not in catalogue/modules.yaml</code> is a module we have never seen: worth reporting.
<br><span class="stop">Stop if</span> it prints a warning about gateway refusals, or modules disappear between runs.</li>
<li><b>Scan one module.</b> Start with one that is well known, for example the climate module:
<pre>./p4 scan 1A11</pre>
Expected: progress for a few minutes, then a list of the data identifiers that answered.
<br><span class="stop">Stop if</span> a module stops answering, a warning lamp appears or the car goes to sleep.
Follow the recovery steps on the Hazards page and do not repeat the read.</li>
<li><b>Prepare what to send.</b> Share which identifiers answered and their lengths, never their values:
<pre>./p4 export --format csv | cut -d, -f1-4 &gt; my-scan.csv</pre>
That keeps four columns: module, DID, status and length. Open the file and check it before you share it.</li>
<li><b>Send it.</b> <a href="%(repo)s/issues/new?template=scan-results.yml">Open a scan results issue</a> and attach
<code>my-scan.csv</code> and the <code>./p4 discover</code> output, with your market and software version.</li>
</ol>
<div class="warn"><h2>Never share</h2>
<p>The <code>runs/</code> folder, packet captures, the output of <code>identify</code>, <code>whois</code> or
<code>strings</code>, or any value you have not checked. They can hold your car's VIN, serial numbers, SIM and
modem numbers, and its GPS position. If in doubt, leave it out and ask in the issue first.</p></div>
<p>Pull requests are welcome too. Read the repository's README and CHANGELOG first; every change runs the tests
and the privacy check.</p>
""" % {"repo": REPO_URL, "modules": len(self.modules)}
        self.write("contribute.html", "Contribute", body, ["README.md", ".github/ISSUE_TEMPLATE/scan-results.yml"])

    GLOSSARY = (
        ("OBD port", "The diagnostic socket under the dashboard. Workshops plug in here."),
        ("DoIP", "Diagnostics over Internet Protocol (ISO 13400): car diagnostics carried over Ethernet instead of "
                 "the older CAN-only cables. The Polestar 4 uses it through the OBD port."),
        ("Adaptor", "The cable or box that turns the OBD port into an Ethernet connection your computer can use."),
        ("Gateway", "The module that receives every diagnostic request and passes it on. On this car it is at "
                    "address 1001."),
        ("Module (ECU)", "One of the car's computers: battery, doors, headlamps and so on. Each has a four-digit "
                         "hexadecimal address, such as 1635 for the high-voltage battery."),
        ("UDS", "Unified Diagnostic Services (ISO 14229), the request language the modules speak."),
        ("DID", "Data identifier: a numbered item a module can report, such as 4801. ReadDataByIdentifier (service "
                "0x22) is the only kind of request used to read them here."),
        ("Signal", "The meaning decoded from some or all of a DID's bytes, such as state of charge in percent."),
        ("Hexadecimal", "Base-16 numbers using 0-9 and A-F. Addresses and DIDs are written this way."),
        ("Broadcast (functional address)", "Address 1FFF, which reaches every module at once. A hazardous read "
                                           "sent this way reaches the module it upsets too."),
        ("Scan", "Asking a module for a range of DIDs to see which ones answer."),
        ("Watch", "Asking for known DIDs again and again to see which values change."),
        ("Paced scan", "A careful scan: one read at a time, checking the module still answers after each."),
        ("Confirmed", "The same change seen at least twice, in both directions, with the action written down "
                      "(C in the catalogue)."),
        ("Provisional", "Anything less than Confirmed: seen once, or plausible (P in the catalogue)."),
        ("Unconfirmed (lead)", "An observation that is not in the catalogue yet: something moved once or at a "
                               "plausible time."),
        ("Never read (block)", "A read the tool always refuses, because it knocked a module off the network."),
        ("Caution", "A read the tool refuses unless you ask for it on purpose."),
        ("DTC", "Diagnostic trouble code: a fault a module has stored."),
        ("Link-local address", "An address in 169.254.x.x that a computer can use on a direct cable with no router; "
                               "the car's gateway uses one."),
        ("Masked", "Hidden on purpose. Values that identify a car (VIN, serial numbers) are never stored or shown."),
    )

    def glossary_page(self) -> None:
        items = "".join("<dt>%s</dt><dd>%s</dd>" % (e(term), e(text)) for term, text in self.GLOSSARY)
        self.write("glossary.html", "Glossary", "<p>Terms used on this site, in plain English.</p><dl>%s</dl>" % items,
                   ["tool/p4doip/site/build.py"])

    def build(self) -> list[str]:
        self.index()
        self.hazards_page()
        self.signals_page()
        self.findings_page()
        self.contribute_page()
        self.glossary_page()
        with open(os.path.join(self.out, ".nojekyll"), "w") as f:
            f.write("")
        return self.pages


def build(inputs: Inputs, out_dir: str, commit: str = "") -> list[str]:
    """Render every page into a fresh out_dir. Returns the page names.

    An existing out_dir is replaced only if it is empty or holds an earlier build (its .nojekyll marker), and
    never if it is the repository or one of its parents, so a mistyped --out cannot delete anything else.
    """
    out = os.path.realpath(out_dir)
    if os.path.commonpath([out, inputs.root]) == out:
        raise ValueError("%s contains the repository; choose another output directory" % out_dir)
    if os.path.isdir(out) and os.listdir(out):
        if not os.path.exists(os.path.join(out, ".nojekyll")):
            raise ValueError("%s is not empty and is not an earlier site build; refusing to replace it" % out_dir)
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    return Site(inputs, out_dir, commit).build()

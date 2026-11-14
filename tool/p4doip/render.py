"""Pure HTML helpers shared by the private status site (web/gen.py) and the public site builder (p4doip.site).

No filesystem, network or car access: everything here takes values and returns strings, so importing it can
never widen what either site reads.
"""
import html

# Colour tokens for light and dark themes (prefers-color-scheme). Both sites build their CSS on these.
TOKENS = """
:root{--bg:#fff;--fg:#1d2329;--mut:#66707a;--line:#dde2e6;--acc:#0b6bcb;--ok:#2e7d32;--warn:#b26a00;--card:#f6f8fa}
@media (prefers-color-scheme: dark){:root{--bg:#14181c;--fg:#e4e8ec;--mut:#98a2ad;--line:#2c333a;--acc:#5aa9ff;--ok:#7bc47f;--warn:#f0b35a;--card:#1b2026}}
"""

# The coverage bar drawn by coverage_bar(): any page that uses the bar must include this rule.
BAR_CSS = ".bar{background:var(--line);height:10px;border-radius:5px;min-width:120px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}\n"

# The private status site's stylesheet: the tokens plus its layout rules.
CSS = TOKENS + """body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px}
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
""" + BAR_CSS + """.unknown{color:var(--warn);font-weight:600}.confirmed{color:var(--ok);font-weight:600}td.v{word-break:break-all;max-width:420px}
"""

DID_SPACE = 0x10000  # every possible DID, 0000-FFFF


def e(s: object) -> str:
    """HTML-escape any value (quotes included)."""
    return html.escape(str(s))


def coverage_bar(tried: int, total: int = DID_SPACE) -> str:
    """A bar for how much of a module's DID space has been tried, and the percentage as text."""
    pct = 100.0 * min(max(tried, 0), total) / total if total else 0.0
    return '<div class=bar title="%d of %d DIDs tried"><i style="width:%.1f%%"></i></div><small class=mut>%.0f%%</small>' % (
        tried, total, pct, pct)

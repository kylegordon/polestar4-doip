"""The public site build: right content, every hazard shown, no private data or exact dates in the output."""
import csv
import os
import re
import shutil

import pytest
import yaml

pytest.importorskip("markdown", reason="markdown not installed: rebuild the image (./p4 build) or install tool/requirements.txt")

from p4doip import decode, hazards  # noqa: E402
from p4doip.site import build as site_build  # noqa: E402
from p4doip.site import gate  # noqa: E402
from p4doip.site.__main__ import main  # noqa: E402
from p4doip.site.inputs import Inputs  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# What the builder reads; a tree holding only these (plus poisoned private dirs) must build.
INPUTS = ["catalogue/signals.yaml", "catalogue/hazards.yaml", "catalogue/modules.yaml", "docs/coverage.csv", "docs/findings.md",
          "scripts/patterns.txt"]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("site") / "out"
    inputs = Inputs(REPO, frozenset(INPUTS))
    pages = site_build.build(inputs, str(out), commit="0123456789abcdef")
    return out, pages, inputs


def page(site, name):
    return (site[0] / name).read_text()


def test_builds_the_phase1_pages(site):
    assert site[1] == ["index.html", "modules.html", "hazards.html", "signals.html", "findings.html", "contribute.html",
                       "glossary.html"]


def test_reads_only_the_named_inputs(site):
    assert set(site[2].read_paths) <= set(INPUTS)


def test_every_hazard_is_on_the_hazards_page(site):
    text = page(site, "hazards.html")
    hazards.clear_cache()
    every = {(h.module, h.did) for h in hazards.load(os.path.join(REPO, "catalogue", "hazards.yaml"))}
    every |= set(hazards.BUILTIN_BLOCKED)
    assert every
    for module, did in every:
        assert "%04X:%04X" % (module, did) in text
    assert "tool code" in text and "Never read" in text and "Caution" in text
    for step in ("Stop.", "Do not retry", "Wait", "unplug the adaptor"):
        assert step in text


def test_signal_count_matches_the_catalogue(site):
    text = page(site, "signals.html")
    with open(os.path.join(REPO, "catalogue", "signals.yaml")) as f:
        n = len(yaml.safe_load(f))  # the raw file, not the loader the build uses
    assert n == len(decode.load(os.path.join(REPO, "catalogue", "signals.yaml")))
    assert text.count("<tr data-mod=") == n
    assert "Every decoded signal in the catalogue: %d in all." % n in text
    assert "Confirmed" in text and "Provisional" in text and 'class="badge u">Unconfirmed' in text


def test_output_has_month_and_year_only(site):
    for name in site[1]:
        text = page(site, name)
        assert not gate.DATE.search(text), name
        assert not gate.TIME.search(text), name
    assert "November 2026" in page(site, "findings.html")


def test_output_scan_is_clean(site):
    with open(os.path.join(REPO, "scripts", "patterns.txt")) as f:
        assert gate.scan_dir(str(site[0]), gate.load_patterns(f.read())) == []


def test_every_page_links_its_source_and_the_footer_is_there(site):
    for name in site[1]:
        text = page(site, name)
        assert site_build.SOURCE_URL in text, name
        assert "Built from commit <code>0123456</code>" in text  # 7 hex digits: never a 10-digit run
        assert "one UK Polestar 4, customer software 4.2.11" in text


def test_findings_leads_and_links(site):
    text = page(site, "findings.html")
    assert 'class="lead"' in text
    assert 'href="%scatalogue/signals.yaml"' % site_build.SOURCE_URL in text
    assert 'id="1301-mobileye-supervision-ecu"' in text
    assert 'href="#1001-gateway"' in text  # the contents list


def test_contribute_has_prerequisites_steps_and_stop_lines(site):
    text = page(site, "contribute.html")
    for must in ("Linux", "Docker", "terminal", "Without a scan", "Never share", "cut -d, -f1-4"):
        assert must in text
    assert text.count('class="stop">Stop if') >= 4


def test_poisoned_private_dirs_never_reach_the_output(tmp_path):
    root = tmp_path / "repo"
    for rel in INPUTS:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(REPO, rel), root / rel)
    for d in ("runs/2026-11-14", "local", "captures", "external"):
        (root / d).mkdir(parents=True)
        (root / d / "x.md").write_text("PRIVATECANARY\n")
    (root / "NEXT.md").write_text("PRIVATECANARY\n")
    inputs = Inputs(str(root), frozenset(INPUTS))
    out = tmp_path / "out"
    site_build.build(inputs, str(out))
    for name in os.listdir(out):
        assert "PRIVATECANARY" not in (out / name).read_text()
    assert not any(re.search(r"(^|/)(runs|local|captures|external)/|NEXT\.md", p) for p in inputs.read_paths)


def test_refuses_to_replace_a_directory_that_is_not_a_build(tmp_path):
    keep = tmp_path / "keep"
    keep.mkdir()
    (keep / "important.txt").write_text("x")
    inputs = Inputs(REPO, frozenset(INPUTS))
    with pytest.raises(ValueError, match="not an earlier site build"):
        site_build.build(inputs, str(keep))
    assert (keep / "important.txt").exists()
    with pytest.raises(ValueError, match="contains the repository"):
        site_build.build(inputs, REPO)


def test_rebuild_replaces_an_earlier_build(tmp_path):
    inputs = Inputs(REPO, frozenset(INPUTS))
    out = tmp_path / "out"
    site_build.build(inputs, str(out))
    (out / "stale.html").write_text("old")
    site_build.build(inputs, str(out))
    assert not (out / "stale.html").exists()


def test_cli_build_and_scan(tmp_path, capsys):
    manifest = tmp_path / "manifest"
    manifest.write_text("\n".join(INPUTS) + "\n")
    out = tmp_path / "out"
    assert main(["build", "--root", REPO, "--manifest", str(manifest), "--out", str(out), "--commit", "abc1234"]) == 0
    assert "output scan OK" in capsys.readouterr().out
    patterns = os.path.join(REPO, "scripts", "patterns.txt")
    assert main(["scan", str(out), "--patterns", patterns]) == 0
    (out / "planted.html").write_text("serial 1234" + "5678" + "9012\n")
    assert main(["scan", str(out), "--patterns", patterns]) == 1
    assert "planted.html:1:" in capsys.readouterr().err


def test_cli_missing_input_is_an_error(tmp_path, capsys):
    manifest = tmp_path / "manifest"
    manifest.write_text("catalogue/signals.yaml\n")  # patterns.txt not tracked: refused
    assert main(["build", "--root", REPO, "--manifest", str(manifest), "--out", str(tmp_path / "o")]) == 2
    assert "not tracked" in capsys.readouterr().err


def test_built_in_blocks_show_even_when_the_catalogue_omits_them(tmp_path):
    root = tmp_path / "repo"
    for rel in INPUTS:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(REPO, rel), root / rel)
    with open(root / "catalogue" / "hazards.yaml") as f:
        doc = yaml.safe_load(f)
    kept = [h for h in doc if h["module"] != "1301"]
    assert kept and len(kept) < len(doc)
    (root / "catalogue" / "hazards.yaml").write_text(yaml.safe_dump(kept))
    out = tmp_path / "out"
    site_build.build(Inputs(str(root), frozenset(INPUTS)), str(out))
    text = (out / "hazards.html").read_text()
    for module, did in hazards.BUILTIN_BLOCKED:
        row = re.search(r"<tr><td[^>]*><code>%04X:%04X</code>.*?</tr>" % (module, did), text)
        assert row and "tool code" in row.group(0) and "Never read" in row.group(0)
    for h in kept:
        assert "%s:%s" % (h["module"], h["did"]) in text


def test_unknown_module_fails_the_build(tmp_path):
    root = tmp_path / "repo"
    for rel in INPUTS:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(REPO, rel), root / rel)
    with open(root / "catalogue" / "modules.yaml") as f:
        mods = [m for m in yaml.safe_load(f) if m["addr"] != "1635"]
    (root / "catalogue" / "modules.yaml").write_text(yaml.safe_dump(mods))
    with pytest.raises(ValueError, match="1635"):
        site_build.build(Inputs(str(root), frozenset(INPUTS)), str(tmp_path / "out"))


def _coverage_rows():
    with open(os.path.join(REPO, "docs", "coverage.csv")) as f:
        return list(csv.DictReader(f))


def _catalogue_tried():
    """Tried DIDs on catalogued modules only: the page leaves out addresses modules.yaml does not name."""
    known = {str(m["addr"]).upper() for m in yaml.safe_load(open(os.path.join(REPO, "catalogue", "modules.yaml")))}
    return sum(int(r["dids_tried"]) for r in _coverage_rows() if r["module"] in known)


def test_coverage_csv_is_counts_only():
    with open(os.path.join(REPO, "docs", "coverage.csv")) as f:
        assert f.readline().strip() == "module,dids_tried,dids_answering,refused"
    rows = _coverage_rows()
    assert rows
    for r in rows:
        assert set(r) == {"module", "dids_tried", "dids_answering", "refused"}
        assert re.fullmatch(r"[0-9A-F]{4}", r["module"])
        assert all(re.fullmatch(r"[0-9]+", r[k]) for k in ("dids_tried", "dids_answering", "refused"))


def test_modules_page_shows_every_module_and_the_whole_car_share(site):
    text = page(site, "modules.html")
    with open(os.path.join(REPO, "catalogue", "modules.yaml")) as f:
        mods = yaml.safe_load(f)
    assert len(re.findall(r"<tr><td data-label=\"Module\">", text)) == len(mods)
    for m in mods:
        assert "<code>%s</code>" % str(m["addr"]).upper() in text
    tried = _catalogue_tried()
    space = 65536 * len(mods)
    assert "%d of %d data items tried" % (tried, space) in text
    assert "width:%.1f%%" % (100.0 * tried / space) in text
    assert "<title>Modules" in text and 'aria-current="page">Modules' in text


def test_start_here_has_the_whole_car_bar(site):
    text = page(site, "index.html")
    tried = _catalogue_tried()
    assert "%d of %d" % (tried, 65536 * len(yaml.safe_load(open(os.path.join(REPO, "catalogue", "modules.yaml"))))) in text
    assert "asked about" in text and 'href="modules.html"' in text


def test_module_signal_counts_match_the_catalogue(site):
    text = page(site, "modules.html")
    with open(os.path.join(REPO, "catalogue", "signals.yaml")) as f:
        sigs = yaml.safe_load(f)
    for m in yaml.safe_load(open(os.path.join(REPO, "catalogue", "modules.yaml"))):
        addr = str(m["addr"]).upper()
        want = {k: sum(1 for s in sigs if s["confidence"] == k and addr in [a.strip().upper() for a in s["module"].split(",")])
                for k in "CP"}
        row = re.search(r'<tr><td data-label="Module"><code>%s</code>.*?</tr>' % addr, text, re.S).group(0)
        assert re.search(r'data-label="Confirmed">%d<' % want["C"], row), addr
        assert re.search(r'data-label="Provisional">%d<' % want["P"], row), addr


def _tree(tmp_path, coverage=None):
    root = tmp_path / "repo"
    for rel in INPUTS:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(REPO, rel), root / rel)
    if coverage is not None:
        (root / "docs" / "coverage.csv").write_text(coverage)
    return root


@pytest.mark.parametrize("csv_text, msg", [
    ("module,dids_tried,dids_answering,refused,value\n1001,1,1,0,AB\n", "columns"),
    ("module,dids_tried,dids_answering,refused\n1001,1.5,1,0\n", "whole numbers"),
    ("module,dids_tried,dids_answering,refused\n1001,1,2,0\n", "inconsistent"),
    ("module,dids_tried,dids_answering,refused\n1001,70000,1,0\n", "inconsistent"),
    ("module,dids_tried,dids_answering,refused\n1001,1,1,0\n1001,1,1,0\n", "twice"),
])
def test_bad_coverage_csv_fails_the_build(tmp_path, csv_text, msg):
    root = _tree(tmp_path, csv_text)
    with pytest.raises(ValueError, match=msg):
        site_build.build(Inputs(str(root), frozenset(INPUTS)), str(tmp_path / "out"))


def test_module_without_a_coverage_row_shows_zero(tmp_path):
    root = _tree(tmp_path, "module,dids_tried,dids_answering,refused\n1001,10,5,1\n")
    out = tmp_path / "out"
    site_build.build(Inputs(str(root), frozenset(INPUTS)), str(out))
    assert "width:0.0%" in (out / "modules.html").read_text()


def test_uncatalogued_module_in_coverage_is_left_out(tmp_path):
    root = _tree(tmp_path, "module,dids_tried,dids_answering,refused\n1001,10,5,1\nFFFF,500,5,0\n")
    out = tmp_path / "out"
    site_build.build(Inputs(str(root), frozenset(INPUTS)), str(out))
    text = (out / "modules.html").read_text()
    assert "FFFF" not in text
    assert "10 of %d data items tried" % (65536 * len(yaml.safe_load(open(root / "catalogue" / "modules.yaml")))) in text

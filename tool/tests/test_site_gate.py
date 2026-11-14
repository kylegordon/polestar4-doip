"""The public site's privacy gate: dates reduced on the way in, identifiers caught on the way out."""
import os

import pytest

from p4doip.site import gate

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAKE_VIN = "YSM" + "4ZPAA0TF000000"  # split so this file never holds a whole VIN


@pytest.fixture(scope="module")
def patterns():
    with open(os.path.join(REPO, "scripts", "patterns.txt")) as f:
        return gate.load_patterns(f.read())


@pytest.mark.parametrize("raw,want", [
    ("seen 2026-11-14", "seen November 2026"),
    ("entry 2026.11.12 correction", "entry November 2026 correction"),
    ("release 2026.11.14.2 notes", "release November 2026 notes"),
    ("(2026-11-14 16:32, parked)", "(November 2026, parked)"),
    ("on 2026/01/05", "on January 2026"),
    ("changed at 16:01-16:02 on the drive", "changed at a recorded time on the drive"),
    ("at 09:15:30 exactly", "at a recorded time exactly"),
    ("snap_2026-11-14_16:01 x", "snap_November 2026 x"),
    ("t 2026-11-14T16:01Z", "t November 2026"),
    ("folder 20261114T160130", "folder November 2026"),
])
def test_reduce_dates(raw, want):
    assert gate.reduce_dates(raw) == want


@pytest.mark.parametrize("text", ["1A01:4209 and 1601:D928", "release 4.2.11", "1635:4801 SoC", "x 0.08 V",
                                  "December 2025", "ratio 3:1", "P417_4.2.11_x", "Nov 2026"])
def test_reduce_dates_leaves_did_references_and_versions(text):
    assert gate.reduce_dates(text) == text


def test_clean_masks_identifiers_after_dates():
    assert gate.clean("part 6608017285 on 2026-11-14") == "part [number hidden] on November 2026"
    assert FAKE_VIN not in gate.clean("vin " + FAKE_VIN)


def kinds(text, patterns):
    return {k for _n, k in gate.scan_text(text, patterns)}


def test_clean_page_passes(patterns):
    assert gate.scan_text("<p>1635:4801 state of charge, November 2026, release 4.2.11</p>\n", patterns) == []


@pytest.mark.parametrize("text", [
    "vin " + FAKE_VIN,                                                     # plain
    "vin " + "\x00".join(FAKE_VIN),                                        # UTF-16 text (NUL lanes)
    "hex " + FAKE_VIN.encode().hex(),                                      # hex-wrapped
    "hex " + FAKE_VIN.encode("utf-16-le").hex(),                           # hex of UTF-16LE
    "hex " + FAKE_VIN.encode("utf-16-be").hex(),                           # hex of UTF-16BE
])
def test_planted_vin_is_caught(patterns, text):
    hits = gate.scan_text("<p>ok</p>\n<p>" + text + "</p>\n", patterns)
    assert hits and all(n == 2 for n, _k in hits)


def test_twelve_digit_serial_is_caught(patterns):
    assert "privacy.mask would change it" in kinds("serial 1234" + "5678" + "9012", patterns)


def test_shared_pattern_is_caught(patterns):
    assert any(k.startswith("matches shared pattern") for k in kinds("x " + FAKE_VIN, patterns))
    assert any(k.startswith("matches shared pattern") for k in kinds("/ho" + "me/someone/x", patterns))


@pytest.mark.parametrize("text", ["on 2026-11-14", "on 14 November", "Nov 14th", "release 2026.11.12",
                                  "log_2026-11-14.md", "14/11/2026", "14.11.2026", "11-14-2026", "14/11/26",
                                  "20261114", "snap-20261114T160130", "November 14 2026", "Nov. 14",
                                  "on the 14th of November"])
def test_exact_date_is_caught(patterns, text):
    assert "exact date" in kinds(text, patterns)


def test_time_of_day_is_caught(patterns):
    assert "time of day" in kinds("at 16:32 parked", patterns)


def test_findings_never_show_the_value(patterns, tmp_path):
    (tmp_path / "p.html").write_text("vin %s\n" % FAKE_VIN)
    problems = gate.scan_dir(str(tmp_path), patterns)
    assert problems and not any(FAKE_VIN in p for p in problems)
    assert problems[0].startswith("p.html:1:")


def test_utf16_file_is_decoded_and_caught(patterns, tmp_path):
    (tmp_path / "x.txt").write_bytes(("vin %s\n" % FAKE_VIN).encode("utf-16"))
    assert gate.scan_dir(str(tmp_path), patterns)


def test_empty_output_is_a_failure(patterns, tmp_path):
    assert gate.scan_dir(str(tmp_path), patterns) == ["%s: no files to scan" % tmp_path]


def test_pattern_file_must_have_patterns():
    with pytest.raises(ValueError):
        gate.load_patterns("# only a comment\n\n")


@pytest.mark.parametrize("text", ["release 4.2.11", "P417_4.2.11_EU", "November 2026", "Nov 2026", "1A01:4209"])
def test_versions_and_months_are_not_dates(patterns, text):
    assert gate.scan_text(text, patterns) == []


@pytest.mark.parametrize("text", [
    "YSM" + "4ZPAA0<wbr>TF000000",                  # split by a tag
    "&#89;SM" + "4ZPAA0TF000000",                   # entity
    "1234<b>56789</b>012",                          # digits split by markup
    "YSM" + "4ZPAA0\nTF000000",                    # split across lines
])
def test_identifier_split_by_markup_is_caught(patterns, text):
    assert gate.scan_text("<p>" + text + "</p>\n", patterns)


def test_hex_of_a_path_or_date_is_caught(patterns):
    assert gate.scan_text("x " + ("/ho" + "me/someone").encode().hex(), patterns)
    assert gate.scan_text("x " + "on 2026-11-14 ok".encode().hex(), patterns)
    assert gate.scan_text("x a" + FAKE_VIN.encode("utf-16-le").hex(), patterns)  # odd alignment


def test_coordinates_are_caught(patterns):
    assert any(k.startswith("matches shared pattern") for k in kinds("at 55.8" + "642, -4.2518", patterns))


def test_symlink_in_output_is_a_failure(patterns, tmp_path):
    (tmp_path / "ok.html").write_text("fine\n")
    os.symlink(tmp_path / "ok.html", tmp_path / "link.html")
    assert any("symlink" in p for p in gate.scan_dir(str(tmp_path), patterns))


def test_crlf_pattern_file_is_refused():
    with pytest.raises(ValueError, match="CR"):
        gate.load_patterns("abc\r\ndef\r\n")


# A VIN whose hex has no long digit runs and whose UTF-16 hex does not start with a shared-pattern WMI:
# only the hex/UTF-16 decoding can catch these.
LETTER_VIN = "YSM" + "JZKLMNZJKLMNZJ"


@pytest.mark.parametrize("encoded", [LETTER_VIN.encode("utf-16-le").hex(), LETTER_VIN.encode("utf-16-be").hex(),
                                     "a" + LETTER_VIN.encode("utf-16-le").hex()])
def test_hex_utf16_vin_needs_the_decoder(patterns, encoded):
    hits = gate.scan_text("x " + encoded + "\n", patterns)
    assert (1, "identifier, path or date in UTF-16 or hex-wrapped text") in hits

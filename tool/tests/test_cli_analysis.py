import json

import pytest

from p4doip import analysis
from p4doip.cli import main


def snap(root, day, name, values):
    d = root / "runs" / day
    d.mkdir(parents=True, exist_ok=True)
    (d / ("snap-%s.json" % name)).write_text(json.dumps({"t": "x", "values": values}))


# -- flips ------------------------------------------------------------------
def test_flips_finds_changed_and_back_and_skips_clocks(root, capsys):
    base = {"1001:C003": "aa", "1001:DD00": "01", "1316:D237": "01", "1316:4801": "9051", "1317:1111": "ff"}
    snap(root, "2026-11-14", "a", base)
    snap(root, "2026-11-14", "b", {**base, "1001:C003": "bb", "1001:DD00": "02", "1316:D237": "02", "1317:1111": "00"})
    snap(root, "2026-11-14", "c", {**base, "1317:1111": "01"})
    main(["flips", "a", "b", "c"])
    out = capsys.readouterr().out
    assert "1001:C003 aa bb" in out
    assert "DD00" not in out and "D237" not in out  # clocks and rolling logs
    assert "1317:1111" not in out  # A != C
    assert "1316:4801" not in out  # never changed
    assert out.endswith("1 flipped over 3 snapshots\n")
    main(["flips", "a", "b", "c", "--all"])
    out = capsys.readouterr().out
    assert "DD00 01 02" in out and "D237 01 02" in out


def test_flips_confirms_with_a_fourth_snapshot_and_shortens(root, capsys):
    snap(root, "2026-11-14", "a", {"1001:C003": "a" * 20, "1001:C004": "01"})
    snap(root, "2026-11-14", "b", {"1001:C003": "b" * 20, "1001:C004": "02"})
    snap(root, "2026-11-14", "c", {"1001:C003": "a" * 20, "1001:C004": "01"})
    snap(root, "2026-11-14", "d", {"1001:C003": "b" * 20, "1001:C004": "03"})
    main(["flips", "a", "b", "c", "--snap-d", "d", "--short", "8"])
    out = capsys.readouterr().out
    assert "1001:C003 aaaaaa.. bbbbbb.." in out
    assert "C004" not in out  # B != D
    assert "1 flipped over 4 snapshots" in out


def test_flips_labels_known_dids(root, capsys):
    snap(root, "2026-11-14", "a", {"1635:4801": "9051"})
    snap(root, "2026-11-14", "b", {"1635:4801": "9035"})
    snap(root, "2026-11-14", "c", {"1635:4801": "9051"})
    main(["flips", "a", "b", "c"])
    assert "1635:4801 9051 9035  [" in capsys.readouterr().out


def test_flips_needs_snapshots_that_exist_and_three_of_them(root):
    with pytest.raises(SystemExit, match="no snapshot named"):
        main(["flips", "x", "y", "z"])
    with pytest.raises(ValueError):
        analysis.flips([{}, {}])


# -- changes ----------------------------------------------------------------
LOG = [
    "16:00:00 connected: 2 reads per pass -> x",
    "16:00:01 1614:D90F 00",
    "16:00:05 1316:4801 CHANGE 9051 -> 9050  [hv_soc=73.8%]",
    "2026-11-14T16:00:09+00:00 1316:4801 CHANGE 9050 -> 9035",
    "16:00:12 1317:D237 CHANGE 0a0b -> no response",
    "16:00:20 1317:C003 CHANGE 01ff -> 0200",
    "16:00:30 1317:C004 CHANGE 00112233445566 -> 00112233445577",
    "16:00:40 1317:C005 MUTED after 01 -> 02 (changing more than 5 times in 10s; still logged)",
]


@pytest.fixture
def watch_log(root):
    d = root / "runs" / "2026-11-14"
    d.mkdir(parents=True)
    (d / "watch-t.log").write_text("".join(l + "\n" for l in LOG))
    return d / "watch-t.log"


def test_changes_lists_change_lines_compactly(watch_log, capsys):
    main(["changes", str(watch_log)])
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "16:00:05 1316:4801 9050"
    assert "16:00:09 1316:4801 9035" in out  # ISO-stamped line
    assert not any("MUTED" in l or "D90F" in l for l in out)
    assert out[-1] == "5 changes"


def test_changes_filters_by_time_key_and_width(watch_log, capsys):
    main(["changes", "watch-t.log", "--since", "16:00:06", "--until", "16:00:20", "--keys", "1317:d237,1317:C003"])
    out = capsys.readouterr().out
    assert "16:00:12 1317:D237 no response" in out and "16:00:20 1317:C003 0200" in out
    assert "4801" not in out
    main(["changes", str(watch_log), "--keys", "1317:C004", "--width", "8"])
    assert "16:00:30 1317:C004 001122.." in capsys.readouterr().out


def test_changes_significant_drops_jitter_but_keeps_state_changes(watch_log, capsys):
    main(["changes", str(watch_log), "--significant", "1"])
    out = capsys.readouterr().out
    assert "9050" not in out  # one count
    assert "C003" not in out  # carry: one count
    assert "C004 00112233445577" in out  # 17 counts: kept
    assert "no response" in out and "9035" in out


def test_changes_rejects_bad_times_and_missing_logs(root, watch_log):
    with pytest.raises(SystemExit, match="HH:MM:SS"):
        main(["changes", str(watch_log), "--since", "4pm"])
    with pytest.raises(SystemExit, match="no watch log"):
        main(["changes", "nope.log"])


def test_byte_jitter():
    assert analysis.byte_jitter("01ff", "0200") == 1
    assert analysis.byte_jitter("00", "0a") == 10
    assert analysis.byte_jitter("00", "zz") is None
    assert analysis.byte_jitter("00", "0000") is None


# -- findvalue --------------------------------------------------------------
def test_findvalue_two_snapshots_across_encodings(root, capsys):
    # u16 BE raw/10: 0x02e2=738 -> 73.8, 0x02f6=758 -> 75.8; u8 raw-40 at offset 2: 0x3d=61 -> 21, 0x41=65 -> 25
    snap(root, "2026-11-14", "a", {"1635:4801": "02e23d", "1635:0001": "ffff"})
    snap(root, "2026-11-14", "b", {"1635:4801": "02f641", "1635:0001": "ffff"})
    main(["findvalue", "a", "b", "--from", "73.8", "--to", "75.8"])
    out = capsys.readouterr().out
    assert "1635:4801  u16be raw/10 @0  73.8 -> 75.8" in out
    assert "0001" not in out
    main(["findvalue", "a", "b", "--from", "21", "--to", "25"])
    assert "1635:4801  u8 raw-40 @2  21 -> 25" in capsys.readouterr().out


def test_findvalue_single_snapshot_and_little_endian_kelvin(root, capsys):
    # u16 LE 0x0b8d = 2957 -> 2957/10-273.15 = 22.55; also u8 raw*2 etc.
    snap(root, "2026-11-14", "a", {"1A01:42F2": "8d0b", "1A01:DD0A": "0d"})
    main(["findvalue", "a", "--value", "22.55", "--tol", "0.05"])
    out = capsys.readouterr().out
    assert "1A01:42F2  u16le raw/10-273.15 (Kelvin*10) @0  22.55" in out
    main(["findvalue", "a", "--value", "26"])
    assert "1A01:DD0A  u8 raw*2 @0  26" in capsys.readouterr().out


def test_findvalue_skips_non_hex_and_checks_arguments(root):
    snap(root, "2026-11-14", "a", {"1001:C003": "no response"})
    snap(root, "2026-11-14", "b", {"1001:C003": "01"})
    assert analysis.findvalue({"k:1": "no response"}, 1.0) == []
    with pytest.raises(SystemExit, match="--from"):
        main(["findvalue", "a", "b"])
    with pytest.raises(SystemExit, match="--value"):
        main(["findvalue", "a"])
    with pytest.raises(SystemExit, match="single snapshot"):
        main(["findvalue", "a", "b", "--from", "1", "--to", "2", "--value", "1"])


# -- review additions ---------------------------------------------------------
def test_findvalue_requires_same_encoding_in_both_and_accepts_zero(root, capsys):
    # A: u8 raw = 10; B: u8 raw = 20 (raw matches 10 and 20), but "raw*2" would need 5/10 at A/B: different encodings
    hits = analysis.findvalue({"k:1": "0a"}, 10, {"k:1": "05"}, 10)
    assert all(h[1] != "u8 raw @0" for h in hits)  # raw in B is 5, not 10
    assert analysis.findvalue({"k:1": "0a"}, 10, {"k:2": "0a"}, 10) == []  # key missing from B
    assert analysis.findvalue({"k:1": "0a"}, 10, {"k:1": "zz"}, 10) == []  # non-hex in B
    assert analysis.findvalue({"k:1": "00"}, 0.0)  # zero is a valid target
    snap(root, "2026-11-14", "a", {"1001:C003": "00"})
    snap(root, "2026-11-14", "b", {"1001:C003": "05"})
    main(["findvalue", "a", "b", "--from", "0", "--to", "5"])
    assert "1001:C003  u8 raw @0  0 -> 5" in capsys.readouterr().out


def test_findvalue_tolerance_is_capped_by_the_step(root):
    assert analysis.findvalue({"k:1": "02e2"}, 73.84, tol=0.5)  # raw/10: 73.8 is within 0.05 of 73.84
    assert not [h for h in analysis.findvalue({"k:1": "02e2"}, 74.0) if "raw/10 @0" in h[1] and "u16be" in h[1]]


def test_flips_skips_keys_missing_from_a_snapshot_and_drops_a_ne_c():
    a, b, c = {"1:1": "01", "1:2": "01"}, {"1:1": "02", "1:2": "02"}, {"1:2": "01"}
    assert analysis.flips([a, b, c]) == [("1:2", ["01", "02", "01"])]
    d = {"1:2": "05"}
    assert analysis.flips([{"1:2": "01"}, {"1:2": "02"}, {"1:2": "01"}, d]) == []  # B != D
    assert analysis.flips([{"1:2": "01"}, {"1:2": "02"}, {"1:2": "03"}, {"1:2": "02"}]) == []


def test_is_noise_bounds():
    noisy = ["1:D200", "1:D2FF", "1:9007", "1:DD02", "1:DD00"]
    assert all(analysis.is_noise(k) for k in noisy)
    assert not analysis.is_noise("1:D300") and not analysis.is_noise("1:D1FF")


def test_changes_time_bounds_are_inclusive_and_keys_tolerate_spaces(watch_log, capsys):
    main(["changes", str(watch_log), "--since", "16:00:05", "--until", "16:00:05", "--keys", " 1316:4801 ,"])
    assert capsys.readouterr().out == "16:00:05 1316:4801 9050\n1 changes\n"


def test_changes_uses_the_newest_day_for_a_bare_name(root, capsys):
    for day, new in (("2026-11-13", "01"), ("2026-11-14", "02")):
        d = root / "runs" / day
        d.mkdir(parents=True, exist_ok=True)
        (d / "watch-x.log").write_text("10:00:00 1:1 CHANGE 00 -> %s\n" % new)
    main(["changes", "watch-x.log"])
    assert "10:00:00 1:1 02" in capsys.readouterr().out


def test_changes_reports_what_it_hides(watch_log, capsys):
    watch_log.write_text(watch_log.read_text() + "16:00:50 1317:C005 noisy 02 -> 03\n16:00:55 x CHANGE broken\n")
    main(["changes", str(watch_log), "--significant", "1"])
    err = capsys.readouterr().err
    assert "2 muted/noisy lines" in err and "1 CHANGE lines not understood" in err and "dropped by --significant" in err
    with pytest.raises(SystemExit, match="after --until"):
        main(["changes", str(watch_log), "--since", "17:00:00", "--until", "16:00:00"])


def test_flips_reports_skipped_keys(root, capsys):
    snap(root, "2026-11-14", "a", {"1:1": "01", "1:2": "01"})
    snap(root, "2026-11-14", "b", {"1:1": "02"})
    snap(root, "2026-11-14", "c", {"1:1": "01", "1:2": "01"})
    main(["flips", "a", "b", "c"])
    assert "1 keys skipped" in capsys.readouterr().err

"""The battery page decodes (web/gen.py): pure arithmetic on recorded hex, checked against hand-made readings."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web"))
import gen  # noqa: E402


def wl(**vals):
    return {k.replace("_", ":"): (v, "2026-11-13 10:00:00", "watch-x.log") for k, v in vals.items()}


def test_u16s_is_big_endian_and_drops_a_trailing_byte():
    assert gen.u16s("0e100e11") == [3600, 3601]
    assert gen.u16s("0e10ff") == [3600]


def test_battery_skips_unused_slots_and_keeps_cell_numbers(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "W", str(tmp_path))
    out = gen.battery(wl(**{"1635_DA31": "0f480f4c" + "ffff" + "0f50", "1635_4801": "77a7"}))
    assert "3 cell groups" in out and "min 3.912 V" in out and "max 3.920 V" in out and "spread <b>8 mV</b>" in out
    assert 'title="cell 4: 3920 mV"' in out and "cell 3:" not in out
    assert "SoC 61.3 %" in out


def test_battery_without_cells_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "W", str(tmp_path))
    assert "No cell reading" in gen.battery({})
    assert "no valid cells" in gen.battery(wl(**{"1635_DA31": "ffffffff"}))
    assert "No cell reading" in gen.battery(wl(**{"1635_DA31": "nrc"}))  # not hex: ignored


def test_temperatures_and_extremes(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "W", str(tmp_path))
    out = gen.battery(wl(**{"1635_DA31": "0f480f50", "1635_EE83": "1644ffff", "1635_4907": "010f50"}))
    assert "1 sensors" in out and "7.0" in out
    assert "Highest cell: group 2, 3.920 V" in out


def test_a_newer_snapshot_wins_over_an_older_watch_value(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "W", str(tmp_path))
    d = tmp_path / "runs" / "2026-11-13"
    d.mkdir(parents=True)
    (d / "snap-a.json").write_text(json.dumps({"t": "2026-11-13T11:00:00+00:00", "values": {"1635:4801": "0001"}}))
    (d / "snap-b.json").write_text(json.dumps(["not", "a", "snapshot"]))
    got = gen.latest_values(["1635:4801"], wl(**{"1635_4801": "77a7"}))
    assert got["1635:4801"][0] == "0001"
    (d / "snap-a.json").write_text(json.dumps({"t": "2026-11-13T09:00:00+00:00", "values": {"1635:4801": "0001"}}))
    assert gen.latest_values(["1635:4801"], wl(**{"1635_4801": "77a7"}))["1635:4801"][0] == "77a7"


def test_old_cells_are_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "W", str(tmp_path))
    assert "Old reading" in gen.battery(wl(**{"1635_DA31": "0f480f50"}))  # 2026-11-13 10:00 is not live
    import time
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    assert "Old reading" not in gen.battery({"1635:DA31": ("0f480f50", now, "watch-x.log")})


def test_coverage_bar_shows_share_of_did_space():
    assert "width:50.0%" in gen.coverage_bar(0x8000)
    assert ">50%<" in gen.coverage_bar(0x8000)
    assert "width:100.0%" in gen.coverage_bar(0x10000)
    assert "width:0.0%" in gen.coverage_bar(0)


def test_coverage_bar_clamps_odd_counts():
    assert "width:100.0%" in gen.coverage_bar(70000)
    assert "width:0.0%" in gen.coverage_bar(-5)
    assert "width:0.0%" in gen.coverage_bar(3, total=0)


def test_watch_log_lines_hide_gps_and_tpms_values():
    gps = "2026-11-15T10:00:01+00:00 1011:FD50 CHANGE aabbccdd11223344 -> aabbccdd11223355"
    tpms = "10:00:02 1A01:281F 00aa11bb22cc33dd"
    other = "10:00:03 1631:D003 CHANGE 0000 -> 0640"
    assert "aabb" not in gen.hide_line(gps) and "hidden" in gen.hide_line(gps)
    assert "00aa" not in gen.hide_line(tpms)
    assert gen.hide_line(other) == other


def test_hide_line_does_not_depend_on_the_line_layout():
    for ln in ("1011:FD50 aabbccdd11223344", "x  y 1a01:281f 00aa11bb22cc33dd", "2026-11-15T10:00:01+00:00  1011:FD50 noisy 11 -> 22"):
        out = gen.hide_line(ln)
        assert "hidden" in out and "aabb" not in out and "00aa" not in out and "-> 22" not in out


def test_module_pages_hide_identity_gps_and_tpms_values(tmp_path, monkeypatch):
    w, out = tmp_path / "w", tmp_path / "srv"
    (w / "catalogue").mkdir(parents=True)
    (w / "catalogue" / "modules.yaml").write_text('- {addr: "1011", label: TEM}\n- {addr: "1A01", label: CEM}\n')
    (w / "catalogue" / "signals.yaml").write_text("[]\n")
    day = w / "runs" / "2026-11-15"
    day.mkdir(parents=True)
    vin_hex = "59534d" + "41" * 14  # a fake identity value: must never appear
    rec = '{"tgt": "%s", "did": "%s", "status": "ok", "data": "%s", "t": "2026-11-15T10:00:00+00:00"}\n'
    (day / "scan-1011.jsonl").write_text(rec % ("1011", "FD50", "aabbccdd11223344") + rec % ("1011", "F190", vin_hex)
                                          + rec % ("1011", "D001", "0102"))
    (day / "scan-1A01.jsonl").write_text(rec % ("1A01", "281F", "00aa11bb22cc33dd"))
    (day / "watch-drive.log").write_text("2026-11-15T10:00:01+00:00 1011:FD50 CHANGE aabbccdd11223344 -> aabbccdd11223355\n")
    monkeypatch.setattr(gen, "W", str(w))
    monkeypatch.setattr(gen, "OUT", str(out))
    monkeypatch.setattr(gen, "SCANLOG", str(tmp_path / "none.out"))
    gen.main()
    served = "".join(p.read_text() for p in out.glob("*.html"))
    for secret in ("aabbccdd", "00aa11bb22", vin_hex[:20]):
        assert secret not in served
    page = (out / "m-1011.html").read_text()
    assert "(hidden: private)" in page and "D001" in page

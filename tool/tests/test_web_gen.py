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

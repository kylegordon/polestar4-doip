"""Headlamp matrix frames for the status page (web/server.py matrix_logs), from watch logs in the recorded format."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web"))
import server  # noqa: E402

A = "11" * 32 + "ff" * 52
B = "22" * 32 + "ff" * 52


def test_matrix_logs_reads_new_values_and_skips_other_dids(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "W", str(tmp_path))
    server.matrix_cache.clear()
    day = tmp_path / "runs" / "2026-11-14"
    day.mkdir(parents=True)
    log = day / "watch-x.log"
    log.write_text("\n".join([
        "10:00:00 1BB3:7022 %s" % A,
        "10:00:01 1BB4:7022 CHANGE %s -> %s" % (A, B),
        "10:00:02 1BB5:7022 %s" % A,
        "10:00:03 1BB3:7023 %s" % A,
        "10:00:05 1BB3:7022 noisy %s -> %s" % (A, B),
        "10:00:06 1BB4:7022 CHANGE %s -> NRC 22" % B,
        "10:00:07 1BB4:7022 MUTED after %s -> %s (6 changes in 10s)" % (B, A),
        "10:00:02 1631:D003 0d44  [vehicle_speed=47.75625 km/h]",
        "10:00:09 1631:D003 CHANGE 0d44 -> no response",
        "2026-11-14T10:00:10+00:00 1BB3:7022 %s" % A,  # watch logs now carry an ISO date and offset
    ]) + "\n")
    (day / "watch-empty.log").write_text("10:00:00 1601:E36E 0000\n")
    got = server.matrix_logs()
    assert [g["name"] for g in got] == ["2026-11-14/watch-x.log"]
    assert got[0]["frames"] == [["10:00:00", "1BB3", "11" * 32], ["10:00:01", "1BB4", "22" * 32],
                                ["10:00:05", "1BB3", "22" * 32], ["10:00:06", "1BB4", "ff" * 32], ["10:00:07", "1BB4", "11" * 32],
                                ["10:00:10", "1BB3", "11" * 32]]
    assert got[0]["speed"] == [["10:00:02", 47.8], ["10:00:09", None]]
    with open(log, "a") as f:
        f.write("10:00:11 1BB3:7022 %s\n" % B)
    assert server.matrix_logs()[0]["frames"][-1] == ["10:00:11", "1BB3", "22" * 32]


def test_charge_sessions_decodes_points_and_splits_on_gaps(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "W", str(tmp_path))
    server.charge_cache.clear()
    day = tmp_path / "runs" / "2026-11-15"
    day.mkdir(parents=True)
    temps = "1d4c" + "1f40" * 27 + "ffff" * 2  # 25.0 C then 30.0 C x27, padding dropped
    cells = "0eb3" + "0ea6" * 109 + "ffff" * 20
    (day / "watch-unattended-charge-131200.log").write_text("\n".join([
        "2026-11-15T13:12:01+00:00 1635:4801 3455  [hv_soc=26.794%]",
        "2026-11-15T13:12:01+00:00 1635:497C 99ca  [pack_voltage=393.7 V]",
        "2026-11-15T13:12:01+00:00 1635:489C 0cd0a3c0  [charge_power_limit_kw=215.0 kW]",
        "2026-11-15T13:12:01+00:00 1635:EE83 %s" % temps,
        "2026-11-15T13:12:02+00:00 1635:4802 309b  [pack_current=-394.1 A]",
        "2026-11-15T13:12:02+00:00 1635:DA31 %s" % cells,  # same second: replaces the 4802 point
        "2026-11-15T13:12:03+00:00 1601:E36E 0000",  # other modules ignored
        "2026-11-15T13:40:08+00:00 1635:4802 CHANGE 397e -> 405f  [pack_current=9.5 A]",  # > 15 min later: new session
        "2026-11-15T13:40:09+00:00 1635:4802 CHANGE 405f -> no response",
    ]) + "\n")
    got = server.charge_sessions()
    assert len(got) == 2 and len(got[0]["points"]) == 1  # newest first
    assert len(got[1]["points"]) == 1  # 4802 and DA31 in the same second share one point
    p = got[1]["points"][0]
    assert p["soc"] == 26.79 and p["amps"] == -394.1 and p["volts"] == 393.7 and p["limit"] == 215.0
    assert p["kw"] == round(394.1 * 393.7 / 1000, 1)
    assert (p["tmin"], p["tmax"]) == (25.0, 30.0) and (p["cmin"], p["cmax"]) == (3.75, 3.763)
    assert got[1]["points"][0]["e"] == 1794748322.0  # 13:12:02 UTC, whatever the local zone
    assert got[0]["points"][0]["amps"] == 9.5


def test_charge_sessions_honours_offsets_and_reloads_appended_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "W", str(tmp_path))
    server.charge_cache.clear()
    day = tmp_path / "runs" / "2026-11-15"
    day.mkdir(parents=True)
    log = day / "watch-unattended-charge-1.log"
    log.write_text("2026-11-15T13:12:02+00:00 1635:4802 309b\n"
                   "13:12:03 1635:4802 309c\n")  # old undated format: skipped
    got = server.charge_sessions()
    assert [pt["e"] for pt in got[0]["points"]] == [1794748322.0]
    with open(log, "a") as f:
        f.write("2026-11-15T14:13:02+01:00 1635:4801 3455\n")  # = 13:13:02 UTC; steady current, new point anyway
    pts = server.charge_sessions()[0]["points"]
    assert [pt["e"] for pt in pts] == [1794748322.0, 1794748382.0]
    assert pts[1]["amps"] == -394.1 and pts[1]["soc"] == 26.79


def test_charge_sessions_drops_failed_reads_and_other_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "W", str(tmp_path))
    server.charge_cache.clear()
    day = tmp_path / "runs" / "2026-11-15"
    day.mkdir(parents=True)
    (day / "watch-unattended-charge-1.log").write_text("\n".join([
        "2026-11-15T13:12:01+00:00 1635:497C 99ca",
        "2026-11-15T13:12:02+00:00 1635:4802 309b",
        "2026-11-15T13:12:03+00:00 1635:497C CHANGE 99ca -> no response",  # failed: voltage must not linger
        "2026-11-15T13:12:04+00:00 1635:489C 0cd0",  # short: dropped
        "2026-11-15T13:12:05+00:00 1635:4802 CHANGE 309b -> 309c",
        "2026-13-15T13:12:06+00:00 1635:4802 309d",  # impossible date: skipped, endpoint still works
    ]) + "\n")
    (day / "watch-discharge-1.log").write_text("2026-11-15T13:12:10+00:00 1635:4802 4100\n")
    (day / "watch-chargelid-1.log").write_text("2026-11-15T13:12:10+00:00 1635:4802 4100\n")
    pts = server.charge_sessions()[0]["points"]
    assert [p["t"][-2:] for p in pts] == ["02", "03", "04", "05"]  # nothing from the discharge/chargelid logs at :10
    assert [p.get("volts") for p in pts] == [393.7, None, None, None]  # a failed read clears its DID at once
    assert all("limit" not in p for p in pts) and pts[-1]["amps"] == -394.0


def test_numeric_skips_not_available_and_reads_only_the_first_signal():
    assert server.numeric("ffff", "not available") is None
    assert server.numeric("7fff7fff", "not available; brake_pressure_1675_b=not available") is None
    assert server.numeric("7fff0165", "not available; brake_pressure_1675_b=357") is None
    assert server.numeric("015d7fff", "349; brake_pressure_1675_b=not available") == 349.0
    assert server.numeric("0f7a", "55.715625 km/h") == 55.715625
    assert server.numeric("42", "pressed") == 66.0

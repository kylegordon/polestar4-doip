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


def test_private_values_are_hidden_in_live_json(tmp_path, monkeypatch):
    day = tmp_path / "runs" / "2026-11-15"
    day.mkdir(parents=True)
    (day / "watch-drive.log").write_text(
        "2026-11-15T10:00:00+00:00 1011:FD50 aabbccdd11223344\n"
        "2026-11-15T10:00:01+00:00 1011:FD50 CHANGE aabbccdd11223344 -> aabbccdd11223355\n"
        "2026-11-15T10:00:02+00:00 1631:D003 0640\n")
    monkeypatch.setattr(server, "W", str(tmp_path))
    server.state.update(file=None, pos=0, keys={}, events=[])
    server.update()
    assert server.state["keys"]["1011:FD50"]["value"] == "(hidden: private)"
    assert server.state["keys"]["1011:FD50"]["hist"] == []
    assert server.state["keys"]["1631:D003"]["value"] == "0640"

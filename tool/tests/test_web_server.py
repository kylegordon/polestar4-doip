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
    ]) + "\n")
    (day / "watch-empty.log").write_text("10:00:00 1601:E36E 0000\n")
    got = server.matrix_logs()
    assert [g["name"] for g in got] == ["2026-11-14/watch-x.log"]
    assert got[0]["frames"] == [["10:00:00", "1BB3", "11" * 32], ["10:00:01", "1BB4", "22" * 32],
                                ["10:00:05", "1BB3", "22" * 32], ["10:00:06", "1BB4", "ff" * 32], ["10:00:07", "1BB4", "11" * 32]]
    with open(log, "a") as f:
        f.write("10:00:08 1BB3:7022 %s\n" % B)
    assert server.matrix_logs()[0]["frames"][-1] == ["10:00:08", "1BB3", "22" * 32]

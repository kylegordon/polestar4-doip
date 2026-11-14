"""The status site: progress wiring, scan/watch readers, masking and the server defaults."""
import importlib.util
import json
import os
import time

import pytest

from conftest import REPO


def load(path, name, env, monkeypatch, tmp_path):
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def web(tmp_path, monkeypatch):
    w = tmp_path / "w"
    (w / "runs" / "2026-01-01").mkdir(parents=True)
    out = tmp_path / "srv"
    gen = load("web/gen.py", "p4_gen_test",
               {"P4_WEB_W": w, "P4_WEB_OUT": out, "P4_WEB_SCANLOG": tmp_path / "scan.out"},
               monkeypatch, tmp_path)
    return gen, w, out


def test_progress_reads_sweep_progress(web):
    gen, w, _ = web
    (w / "runs" / "2026-01-01" / "sweep.progress.json").write_text(json.dumps({
        "current": "1601:E37B", "since": time.time() - 60, "total": 3,
        "remaining": ["1601:E37B", "1635", "1A01"], "gated": [], "parked": False, "watch_secs": 0}))
    out = gen.progress()
    assert "1601:E37B" in out and "Scan queue" in out and "0 of 3" in out


def test_scans_and_watch_last_read_new_formats(web):
    gen, w, _ = web
    d = w / "runs" / "2026-01-01"
    (d / "scan-1601.jsonl").write_text(
        json.dumps({"v": 2, "tool": "x"}) + "\n"
        + json.dumps({"tgt": "1601", "did": "E37B", "status": "ok", "data": "05", "t": "x"}) + "\n")
    (d / "watch-1.log").write_text(
        "2026-01-01T10:00:00+01:00 1601:E37B CHANGE 03 -> 05  [epb_state=moving]\n")
    sc = gen.scans()
    assert sc["1601"]["E37B"][0] == "ok" and sc["1601"]["E37B"][1] == "05"
    last = gen.watch_last()
    assert last["1601:E37B"][0] == "05" and "2026-01-01 10:00:00" in last["1601:E37B"][1]


def test_latest_scan_results_reads_sweep_log(web):
    gen, w, _ = web
    (w / "runs" / "2026-01-01" / "sweep.log").write_text(
        "10:00:00 scan 1601:E37B: start\n10:02:00 scan 1601:E37B: 4 new OK\n"
        "10:03:00 scan 1635: start\n10:04:00 scan 1635: 0 new OK\n")
    out = gen.latest_scan_results()
    assert "1601:E37B" in out and "4 new DIDs" in out and "1635" not in out


def test_web_text_masks_identifiers(web):
    gen, _, _ = web
    vin = "YSM" + "4ZPAA0TF000000"
    assert "VIN hidden" in gen.text_of(("SW " + vin).encode().hex())
    assert "example.com" not in gen.text_of(b"a.b@example.com".hex())
    assert "900123" not in gen.text_of((b"call +" + b"44 7700 900123").hex())


def test_server_is_importable_and_localhost_by_default(tmp_path, monkeypatch):
    out = tmp_path / "srv"
    out.mkdir()
    monkeypatch.setenv("P4_WEB_OUT", str(out))
    monkeypatch.delenv("P4_WEB_HOST", raising=False)
    srv = load("web/server.py", "p4_server_test", {}, monkeypatch, tmp_path)
    assert srv.HOST == "127.0.0.1" and srv.PORT == 8088
    m = srv.LINE.match("2026-01-01T10:00:00+01:00 1601:E37B CHANGE 03 -> 05")
    assert m and m.group(1) == "10:00:00" and m.group(2) == "1601:E37B"
    m = srv.LINE.match("10:00:00 1601:E37B CHANGE 03 -> 05")  # old logs still parse
    assert m and m.group(2) == "1601:E37B"


def test_container_files_exist():
    assert os.path.exists(os.path.join(REPO, "web", "Dockerfile"))
    assert os.path.exists(os.path.join(REPO, "web", "start.sh"))

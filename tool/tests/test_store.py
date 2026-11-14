import os

import pytest

from p4doip import store


def test_load_scans_cache_follows_appends(root):
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E37B", "status": "ok", "data": "03"})
    first = store.load_scans(0x1601)
    assert first[0xE37B]["data"] == "03"
    again = store.load_scans(0x1601)
    assert again is first  # served from cache: same dict, same files
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E36E", "status": "ok", "data": "0100"})
    updated = store.load_scans(0x1601)
    assert 0xE36E in updated and 0xE37B in updated  # the append invalidated the cache


def test_load_scans_cache_is_root_scoped(root, tmp_path, monkeypatch):
    store.load_scans(0x1601)
    other = tmp_path / "other-root"
    (other / "runs" / "2026-11-12").mkdir(parents=True)
    monkeypatch.setenv("P4_ROOT", str(other))
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E37B", "status": "ok", "data": "05"})
    assert store.load_scans(0x1601)[0xE37B]["data"] == "05"  # not the first root's cached (empty) result


def test_truncated_tail_is_tolerated_and_next_append_is_safe(root):
    p = store.scan_path(0x1601, "2026-11-12")
    store.append_jsonl(p, {"t": "2026-11-12T10:00:00+01:00", "tgt": "1601", "did": "E37B", "status": "ok", "data": "03"})
    with open(p, "a") as f:
        f.write('{"t": "2026-11-12T10:00:01+01:00", "tgt": "1601", "di')  # power loss mid-append
    store.append_jsonl(p, {"t": "2026-11-12T10:00:02+01:00", "tgt": "1601", "did": "E37A", "status": "nrc", "code": "31"})
    scans = store.load_scans(0x1601)
    assert scans[0xE37B]["status"] == "ok" and scans[0xE37A]["status"] == "nrc"


def test_middle_corruption_is_still_an_error(root):
    p = store.scan_path(0x1601, "2026-11-12")
    with open(p, "w") as f:
        f.write('{"did": "E001"}\nnot json\n{"did": "E002"}\n')
    with pytest.raises(ValueError, match="not JSON"):
        store.read_jsonl(p)


def test_done_never_settles_a_transient_nrc(root):
    scans = {
        0xE37B: {"status": "ok"},
        0xE37A: {"status": "nrc", "code": "31"},
        0xE379: {"status": "nrc", "code": "21"},
        0xE378: {"status": "nrc", "code": "21", "retryable": True},
        0xE377: {"status": "timeout", "t": "2026-11-12T10:00:00+01:00"},
    }
    done = store.done_dids(scans)
    assert 0xE37B in done and 0xE37A in done
    assert 0xE379 not in done and 0xE378 not in done
    assert 0xE377 not in done
    assert store.done_dids(scans, rescan=True) == set()


def test_skip_silent_after_only_skips_recent_timeouts(root):
    import datetime
    now = datetime.datetime(2026, 11, 14, 12, 0, 0).astimezone()
    scans = {
        0xE371: {"status": "timeout", "t": "2026-11-14T10:00:00+01:00"},  # 2 h ago
        0xE372: {"status": "timeout", "t": "2026-11-01T10:00:00+01:00"},  # 13 days ago
        0xE373: {"status": "timeout"},                                  # no timestamp: never skipped
    }
    assert store.done_dids(scans, skip_silent_after=2, now=now) == {0xE371}
    assert store.done_dids(scans, skip_silent_after=30, now=now) == {0xE371, 0xE372}

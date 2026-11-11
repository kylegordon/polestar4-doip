import json

import pytest

from p4doip import store
from p4doip.cli import diff_snapshots, main, parse_ranges


def scan_records(root, tgt):
    files = list(root.glob("runs/*/scan-%s.jsonl" % tgt))
    assert len(files) == 1
    return [r for r in store.read_jsonl(str(files[0])) if "did" in r]


def reads_seen(sim):
    return [uds.hex() for _, uds in sim.seen if uds.hex() != "22dd0a" and uds[0] == 0x22]


def test_parse_ranges():
    assert parse_ranges("E37A-E37C,2B24") == [0xE37A, 0xE37B, 0xE37C, 0x2B24]
    with pytest.raises(SystemExit):
        parse_ranges("2000-1000")


# -- scan -------------------------------------------------------------------
def test_scan_records_ok_and_nrc_and_car_state(p4, root):
    out = p4("scan", "1601", "--ranges", "E37A-E37C")
    assert "1601 E37B OK 03" in out
    recs = {r["did"]: r for r in scan_records(root, "1601")}
    assert recs["E37B"]["status"] == "ok" and recs["E37B"]["data"] == "03"
    assert recs["E37A"]["status"] == "nrc" and recs["E37A"]["code"] == "31"
    header = store.read_jsonl(str(next(root.glob("runs/*/scan-1601.jsonl"))))[0]
    assert "run" in header and "usage_mode" in header


def test_scan_never_stores_the_vin(p4, root, sim):
    sim.set(0x1601, 0xF190, "59534d" + "3458585858585858585858585858")  # split: no whole hex VIN in this file
    out = p4("scan", "1601", "--ranges", "F190")
    assert "59534d" not in out
    assert scan_records(root, "1601")[0]["data"] == "00" * 17


def test_scan_skips_dids_already_answered(p4, root, sim):
    p4("scan", "1601", "--ranges", "E37A-E37B")
    sim.seen.clear()
    p4("scan", "1601", "--ranges", "E37A-E37C")
    assert reads_seen(sim) == ["22e37c"]
    assert len(scan_records(root, "1601")) == 3


def test_scan_skips_dids_answered_on_an_earlier_day(p4, root, sim):
    store.append_jsonl(store.scan_path(0x1601, "2026-11-10"), {"tgt": "1601", "did": "E37A", "status": "nrc", "code": "31"})
    p4("scan", "1601", "--ranges", "E37A-E37B")
    assert reads_seen(sim) == ["22e37b"]
    sim.seen.clear()
    p4("scan", "1601", "--ranges", "E37A-E37B", "--rescan")
    assert reads_seen(sim) == ["22e37a", "22e37b"]


def test_scan_like_copies_sibling_dids(p4, root):
    p4("scan", "1316", "--ranges", "F18C,DD0A")
    out = p4("scan", "1317", "--like", "1316")
    assert "1317 F18C OK 02160045" in out
    assert {r["did"] for r in scan_records(root, "1317")} == {"F18C", "DD0A"}


def test_scan_of_missing_module_stops(p4):
    with pytest.raises(SystemExit, match="does not exist"):
        p4("scan", "16A1", "--ranges", "2B24")


def test_scan_other_nack_is_not_called_missing(p4, sim):
    sim.nack_code = 0x06
    with pytest.raises(SystemExit, match="unreachable"):
        p4("scan", "16A1", "--ranges", "2B24")


@pytest.mark.parametrize("ranges", ["E370-E37F", "E370-E372"])
def test_scan_of_dead_module_records_nothing_and_resumes(p4, root, sim, ranges):
    sim.silent.add(0x1601)
    with pytest.raises(SystemExit, match="stopped answering"):
        p4("scan", "1601", "--ranges", ranges, "--timeout", "0.05")
    assert scan_records(root, "1601") == []
    sim.silent.clear()
    p4("scan", "1601", "--ranges", ranges, "--timeout", "0.05")
    assert len(scan_records(root, "1601")) == len(parse_ranges(ranges))


def test_timeouts_from_a_live_module_are_recorded_but_retried_next_time(p4, root, sim):
    sim.ignore = {(0x1601, d) for d in range(0xE370, 0xE376)}
    p4("scan", "1601", "--ranges", "E370-E375", "--timeout", "0.05")
    assert [r["status"] for r in scan_records(root, "1601")] == ["timeout"] * 6
    sim.seen.clear()
    p4("scan", "1601", "--ranges", "E370-E375", "--timeout", "0.05")
    assert len(reads_seen(sim)) == 6


def test_scan_survives_the_gateway_dropping_the_connection(p4, root, sim):
    sim.drop_after = 2
    p4("scan", "1601", "--ranges", "E378-E37C")
    assert {r["did"] for r in scan_records(root, "1601")} == {"E378", "E379", "E37A", "E37B", "E37C"}


# -- stored results ------------------------------------------------------------
def test_a_later_timeout_or_refusal_does_not_demote_a_known_ok(root):
    store.append_jsonl(store.scan_path(0x1601, "2026-11-10"), {"tgt": "1601", "did": "E37B", "status": "ok", "data": "03"})
    store.append_jsonl(store.scan_path(0x1601, "2026-11-11"), {"tgt": "1601", "did": "E37B", "status": "timeout"})
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E37B", "status": "nrc", "code": "22"})
    assert store.known_ok(0x1601) == [0xE37B]
    store.append_jsonl(store.scan_path(0x1601, "2026-11-13"), {"tgt": "1601", "did": "E37B", "status": "ok", "data": "09"})
    assert store.load_scans(0x1601)[0xE37B]["data"] == "09"


def test_import_legacy(p4, root):
    reads = root / "local" / "reads"
    reads.mkdir(parents=True)
    reads.joinpath("x-sweep.txt").write_text(
        "routing activation 0e8010011000000000\n1601 2B24 OK 00010000\n1601 2B00 NRC 31\n"
        "16A1 2B24 NACK 03\n1601 2B01 no response\n1601 2B24 OK 00010000\ngarbage\n")
    out = p4("import-legacy")
    assert "1601: 3 DIDs" in out
    assert store.known_ok(0x1601) == [0x2B24]
    with pytest.raises(SystemExit, match="already has scan files"):
        p4("import-legacy")


# -- discover ----------------------------------------------------------------
def test_discover_finds_modules_the_broadcast_misses(p4):
    out = p4("discover", "--start", "1250", "--end", "1320", "--timeout", "0.1")
    assert "1251 HUD" in out
    assert "1316" in out and "1317" in out
    assert "answering: 3" in out


def test_discover_reports_silent_and_missing_within_range_only(p4, sim):
    sim.silent.add(0x1316)
    out = p4("discover", "--start", "1310", "--end", "1320", "--timeout", "0.1")
    assert "1316 silent" in out
    missing = next(line for line in out.splitlines() if line.startswith("in catalogue but not answering"))
    assert "1316" in missing and "1314" in missing and "1601" not in missing


def test_discover_warns_when_nacks_are_not_unknown_address(p4, sim):
    sim.nack_code = 0x02
    out = p4("discover", "--start", "1310", "--end", "1315", "--timeout", "0.1")
    assert "WARNING" in out and "NACK 02" in out


# -- snapshot / diff -----------------------------------------------------------
def test_snapshot_then_diff_shows_only_what_changed(p4, sim):
    p4("scan", "1601", "--ranges", "E37B,2B1A,2B20")
    p4("snapshot", "before", "1601")
    sim.set(0x1601, 0xE37B, "09")
    sim.set(0x1601, 0x2B1A, "00000400")
    p4("snapshot", "after", "1601")
    out = p4("diff", "before", "after")
    assert "1601:E37B 03 -> 09" in out and "Parking brake state" in out
    assert "1601:2B1A 00000100 -> 00000400" in out
    assert "2 changed" in out


def test_diff_finds_snapshots_from_other_days(p4, root):
    for day, val in (("2026-11-10", "03"), ("2026-11-11", "09")):
        d = root / "runs" / day
        d.mkdir(parents=True)
        (d / ("snap-%s.json" % day[-2:])).write_text(json.dumps({"values": {"1601:E37B": val}}))
    assert "1601:E37B 03 -> 09" in p4("diff", "10", "11")
    with pytest.raises(SystemExit, match="no snapshot"):
        p4("diff", "10", "nope")


def test_diff_snapshots_handles_missing_keys():
    assert diff_snapshots({"a": "1"}, {"a": "1", "b": "2"}) == [("b", None, "2")]


# -- watch -------------------------------------------------------------------
def test_watch_prints_changes_with_decoded_value(p4, sim, root):
    sim.script[(0x1601, 0xE37B)] = ["03", "05", "09"]
    out = p4("watch", "1601:E37B", "--passes", "3", "--name", "t", "--baseline", "0")
    assert "1601:E37B CHANGE 03 -> 05  [epb_state=moving]" in out
    assert "1601:E37B CHANGE 05 -> 09  [epb_state=released]" in out
    assert "1601:E37B 03" not in out.replace("CHANGE 03", "")  # first value is quiet by default
    assert "1601:E37B 03" in next(root.glob("runs/*/watch-t.log")).read_text()


def test_watch_never_hides_a_value_by_default(p4, sim):
    sim.script[(0x1601, 0xE37B)] = ["03", "05", "09", "05", "03", "05", "09", "05"]  # two quick apply/release cycles
    out = p4("watch", "1601:E37B", "--passes", "8", "--baseline", "0")
    assert out.count("CHANGE") == 7 and "MUTED" not in out


def test_watch_baseline_hides_only_values_that_move_on_their_own(p4, sim, root):
    sim.script[(0x1601, 0x2B20)] = ["%08x" % n for n in range(40)]          # drifts constantly
    sim.script[(0x1601, 0xE37B)] = ["03"] * 12 + ["09"]                      # changes once, after the baseline
    out = p4("watch", "1601:2B20,E37B", "--passes", "14", "--baseline", "0.3", "--interval", "0.05", "--name", "b")
    assert "baseline over: 1 noisy values hidden" in out
    assert "1601:E37B CHANGE 03 -> 09" in out
    assert "1601:2B20 CHANGE" not in out
    assert "1601:2B20 noisy" in next(root.glob("runs/*/watch-b.log")).read_text()


def test_watch_mute_option_logs_the_change_that_triggered_it(p4, sim, root):
    sim.script[(0x1601, 0x2B20)] = ["%08x" % n for n in range(8)]
    out = p4("watch", "1601:2B20", "--passes", "8", "--mute", "3", "--name", "m", "--baseline", "0")
    assert out.count("CHANGE") == 3
    assert "MUTED after 00000003 -> 00000004" in out
    assert "noisy" in next(root.glob("runs/*/watch-m.log")).read_text()


def test_watch_whole_module_uses_known_dids_and_hide(p4, sim):
    p4("scan", "1601", "--ranges", "E37B,2B15")
    sim.script[(0x1601, 0x2B15)] = ["00", "03"]
    sim.script[(0x1601, 0xE37B)] = ["03", "09"]
    out = p4("watch", "1601", "--passes", "2", "--hide", "1601:E37B", "--baseline", "0")
    assert "1601:2B15 CHANGE 00 -> 03" in out and "E37B" not in out


def test_watch_keeps_going_when_the_gateway_drops_it(p4, sim):
    sim.script[(0x1601, 0xE37B)] = ["03", "03", "09"]
    sim.drop_after = 1
    out = p4("watch", "1601:E37B", "--passes", "3", "--baseline", "0")
    assert "ERROR connection lost" in out and "1601:E37B CHANGE 03 -> 09" in out


def test_watch_without_known_dids_says_what_to_do(p4):
    with pytest.raises(SystemExit, match="run scan first"):
        p4("watch", "1635", "--passes", "1")


# -- identify / dtc / mark -----------------------------------------------------
def test_dtc_lists_stored_codes_and_records_refusals(p4, root):
    out = p4("dtc", "1601")
    assert "1601 stored: 1 DTCs" in out and "D12345 status 08" in out
    assert "1601 supported: NRC 12" in out
    recs = store.read_jsonl(str(next(root.glob("runs/*/dtc-1601.jsonl"))))
    assert [(r["kind"], r["status"]) for r in recs] == [("stored", "ok"), ("supported", "nrc")]


def test_identify_prints_answers_and_does_not_overwrite_with_nothing(p4, root, sim):
    out = p4("identify", "1316")
    assert "1316 F18C 02160038" in out
    path = next(root.glob("runs/*/identify-1316.json"))
    assert json.loads(path.read_text()) == {"DD0A": "0d", "F18C": "02160038"}
    sim.silent.add(0x1316)
    assert "nothing written" in p4("identify", "1316")
    assert json.loads(path.read_text()) == {"DD0A": "0d", "F18C": "02160038"}


def test_all_means_every_catalogue_module(p4, sim):
    p4("dtc", "all")
    asked = {t for t, uds in sim.seen if uds[0] == 0x19}
    assert {0x1601, 0x1316, 0x1A01, 0x1BB4} <= asked and len(asked) == 43


def test_mark_goes_to_session_log_and_run_dir(p4, root):
    p4("mark", "left", "front", "door")
    assert root.joinpath("local", "session-log.md").read_text().rstrip().endswith("left front door")
    rec = store.read_jsonl(str(next(root.glob("runs/*/marks.jsonl"))))[0]
    assert rec["mark"] == "left front door" and "T" in rec["t"]


def test_cannot_connect_is_a_clear_error(root, sim):
    sim.close()
    with pytest.raises(SystemExit, match="cannot connect"):
        main(["--host", "127.0.0.1", "--port", "1", "--retries", "1", "--retry-wait", "0", "identify", "1601"])


def test_refused_activation_is_a_clear_error(root, sim):
    sim.activation_code = 0x00
    with pytest.raises(SystemExit, match="cannot connect"):
        main(["--host", "127.0.0.1", "--port", str(sim.port), "--retries", "1", "--retry-wait", "0", "identify", "1601"])


def test_scan_skips_blocked_dids(p4, root, sim):
    sim.modules.setdefault(0x1301, {})
    sim.set(0x1301, 0xEE12, "01")
    sim.set(0x1301, 0xEE14, "02")
    p4("scan", "1301", "--ranges", "EE12-EE14")
    assert "22ee13" not in reads_seen(sim)
    assert {r["did"] for r in scan_records(root, "1301")} == {"EE12", "EE14"}


def test_scan_like_never_copies_a_blocked_did(p4, root, sim):
    sim.set(0x1635, 0xEE13, "00d46d97")
    sim.modules.setdefault(0x1301, {})
    sim.set(0x1301, 0xEE12, "01")
    p4("scan", "1635", "--ranges", "EE13")
    sim.seen.clear()
    p4("scan", "1301", "--like", "1635")
    assert "22ee13" not in reads_seen(sim)


def test_watch_refuses_a_blocked_did(p4, sim):
    sim.modules.setdefault(0x1301, {})
    sim.set(0x1301, 0xEE12, "01")
    with pytest.raises(SystemExit, match="nothing left to watch"):
        p4("watch", "1301:EE13", "--passes", "1", "--baseline", "0")
    assert "22ee13" not in reads_seen(sim)


def test_snapshot_skips_a_blocked_did_even_if_recorded_ok(p4, root, sim):
    sim.modules.setdefault(0x1301, {})
    sim.set(0x1301, 0xEE12, "01")
    for did in ("EE12", "EE13"):  # an old or hand-made record must not revive a blocked read
        store.append_jsonl(store.scan_path(0x1301), {"tgt": "1301", "did": did, "status": "ok", "data": "01"})
    p4("snapshot", "s", "1301")
    assert "22ee13" not in reads_seen(sim)
    assert "22ee12" in reads_seen(sim)


def test_snapshot_and_watch_never_store_the_vin(p4, root, sim):
    sim.set(0x1601, 0xF190, "59534d" + "3458585858585858585858585858")
    p4("scan", "1601", "--ranges", "F190")
    p4("snapshot", "v", "1601")
    p4("watch", "1601:F190", "--passes", "1", "--baseline", "0", "--name", "v", "--show-first")
    assert "59534d" not in next(root.glob("runs/*/snap-v.json")).read_text()
    assert "59534d" not in next(root.glob("runs/*/watch-v.log")).read_text()

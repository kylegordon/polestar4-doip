import json
import os

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


# -- offline analysis ---------------------------------------------------------
def test_global_options_cannot_be_abbreviated(root):
    # The ./p4 wrapper finds the subcommand by skipping the full option names only.
    with pytest.raises(SystemExit):
        main(["--ho", "127.0.0.1", "signals"])


def test_strings_masks_identifiers(root, capsys):
    vin = "YSM" + "4ZPAA0XX000000"  # split: no whole VIN in this file
    iccid, imei = "8944" + "12345678" + "90123456", "1234567" + "89012345"  # split so prepublish-check passes
    rows = [("E001", ("SW " + vin).encode().hex()), ("E002", iccid.encode().hex()),
            ("E003", b"BOOT v1.2.3".hex()), ("E004", "0102030405"), ("E005", ("IMEI:" + imei).encode().hex()),
            ("E006", ("vin " + vin.lower()).encode().hex()), ("E007", ("tel +" + "44 7700 900123").encode().hex()),
            ("E008", ("id " + "35-209900-" + "176148-1").encode().hex()), ("E009", ("to a.b" + "@example.com").encode().hex()),
            ("F18C", b"SER 0216A0038".hex()), ("F190", ("ABC" + "4ZPAA0XX000000").encode().hex())]
    for did, data in rows:
        store.append_jsonl(store.scan_path(0x1316, "2026-11-11"), {"tgt": "1316", "did": did, "status": "ok", "data": data})
    main(["strings", "1316"])
    out = capsys.readouterr().out
    assert "1316:E001 SW [VIN hidden]" in out
    assert "1316:E002 [number hidden]" in out
    assert "1316:E003 BOOT v1.2.3" in out
    assert "E004" not in out
    assert "1316:E005 IMEI:[number hidden]" in out
    assert "1316:E006 vin [VIN hidden]" in out
    assert "1316:E007 tel [phone hidden]" in out
    assert "1316:E008 id [number hidden]" in out
    assert "1316:E009 to [email hidden]" in out
    assert "F18C" not in out and "F190" not in out  # identity DIDs (serials, VIN) are never printed
    assert "4ZPAA0" not in out.upper() and "8944123" not in out and "1234567890" not in out and "900123" not in out


def write_day(root, marks, log_lines, day="2026-11-11", log="watch-drive.log"):
    import datetime
    d = root / "runs" / day
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "marks.jsonl", "w") as f:
        for hms, text in marks:
            t = datetime.datetime.combine(datetime.date.fromisoformat(day), datetime.time(*hms)).astimezone()
            f.write(json.dumps({"t": t.isoformat(timespec="seconds"), "mark": text}) + "\n")
    if log_lines:
        (d / log).write_text("".join(l + "\n" for l in log_lines))


def test_correlate_lists_changes_near_each_mark(root, capsys):
    write_day(root, [((16, 0, 10), "chassis Firm"), ((16, 5, 0), "nothing happens")], [
        "16:00:00 connected: 2 reads per pass -> x",
        "16:00:01 1614:D90F 00",
        "16:00:07 1631:D003 CHANGE 0000 -> 0100",       # 3 s before: outside the default 2 s
        "16:00:09 1001:D111 baseline-noise 96 -> 97",
        "16:00:11 1001:D112 MUTED after 01 -> 02 (changing more than 5 times in 10s; still logged)",
        "16:00:12 1614:D90F CHANGE 00 -> 40",
        "16:00:26 1631:D003 CHANGE 0100 -> 0200",       # 16 s after: outside the default 15 s
    ])
    main(["correlate", "2026-11-11"])
    out = capsys.readouterr().out
    assert "== 16:00:10 chassis Firm (3 changes)" in out
    assert "  +2s 1614:D90F 00 -> 40  (watch-drive.log)" in out
    assert "  -1s 1001:D111 baseline-noise 96 -> 97" in out
    assert "  +1s 1001:D112 MUTED 01 -> 02" in out
    assert "D003" not in out
    assert "== 16:05:00 nothing happens (0 changes; no watch log covers this time)" in out
    main(["correlate", "2026-11-11", "--before", "5"])
    assert "  -3s 1631:D003 0000 -> 0100" in capsys.readouterr().out


def test_correlate_rolls_over_midnight(root, capsys):
    write_day(root, [((23, 59, 58), "late")], ["23:59:50 connected", "00:00:03 1614:D90F CHANGE 00 -> 40"])
    main(["correlate", "2026-11-11"])
    out = capsys.readouterr().out
    assert "== 23:59:58 late (1 changes)" in out
    assert "  +5s 1614:D90F 00 -> 40" in out


def test_correlate_reads_a_watch_started_the_day_before(root, capsys):
    write_day(root, [], ["23:59:50 connected", "00:00:03 1614:D90F CHANGE 00 -> 40", "00:01:00 1614:D90F CHANGE 40 -> 00"])
    write_day(root, [((0, 0, 1), "after midnight")], [], day="2026-11-12")
    main(["correlate", "2026-11-12"])
    out = capsys.readouterr().out
    assert "== 00:00:01 after midnight (1 changes)" in out
    assert "  +2s 1614:D90F 00 -> 40" in out


def test_correlate_refuses_paths_and_bad_dates(root):
    write_day(root, [((16, 0, 0), "m")], ["16:00:00 connected"])
    with pytest.raises(SystemExit, match="file names"):
        main(["correlate", "2026-11-11", "../x.log"])
    with pytest.raises(SystemExit, match="YYYY-MM-DD"):
        main(["correlate", "../2026"])


def test_correlate_without_marks_says_so(root):
    with pytest.raises(SystemExit, match="no marks"):
        main(["correlate", "2026-11-11"])


# -- ./p4 wrapper: the one-tester lock ------------------------------------------
@pytest.mark.parametrize("argv,locked", [
    (["scan", "1316"], True), (["--host", "x", "scan", "1316"], True), (["--host=x", "scan", "1316"], True),
    (["--retry-wait", "1", "watch", "1601"], True), (["--ho", "x", "scan", "1316"], True), (["identify", "all"], True),
    (["strings", "all"], False), (["--retries", "3", "correlate", "2026-11-11"], False), (["mark", "x"], False),
    (["known", "1316"], False), (["diff", "a", "b"], False), (["signals"], False), (["--help"], False),
])
def test_wrapper_lock(tmp_path, argv, locked):
    import subprocess
    from conftest import REPO
    stub = tmp_path / "docker"
    stub.write_text('#!/bin/sh\n[ "$1" = image ] && exit 0\necho "$@"\n')
    stub.chmod(0o755)
    env = dict(os.environ, PATH="%s:%s" % (tmp_path, os.environ["PATH"]))
    out = subprocess.run(["sh", os.path.join(REPO, "p4"), *argv], env=env, capture_output=True, text=True, check=True).stdout
    assert ("--name p4-live" in out) == locked


# -- paced scan (careful mode for modules like 1301) --------------------------
PACED = ("--paced", "0", "--timeout", "0.05", "--recover-poll", "0.05")


def test_paced_scan_checks_module_and_gateway_after_every_read(p4, root, sim):
    p4("scan", "1601", "--ranges", "E37A-E37C", *PACED)
    assert [r["did"] for r in scan_records(root, "1601")] == ["E37A", "E37B", "E37C"]
    sent = [(t, uds.hex()) for t, uds in sim.seen if uds.hex() != "22dd0a"]
    # both answer before anything is read; then read, TesterPresent to the module, TesterPresent to the gateway
    assert sent == [(0x1601, "3e00"), (0x1001, "3e00")] + [
        x for d in ("e37a", "e37b", "e37c") for x in ((0x1601, "22" + d), (0x1601, "3e00"), (0x1001, "3e00"))]


def test_paced_scan_stops_at_a_knockout_did_and_never_reads_it_again(p4, root, sim):
    sim.knockout.add((0x1601, 0xE37B))
    with pytest.raises(SystemExit, match="still silent"):
        p4("scan", "1601", "--ranges", "E37A-E37C", *PACED, "--recover", "0.2")
    recs = {r["did"]: r for r in scan_records(root, "1601")}
    assert recs["E37B"]["status"] == "hazard" and "E37C" not in recs
    assert "22e37c" not in reads_seen(sim)
    sim.silent.clear()
    sim.knockout.clear()
    sim.seen.clear()
    p4("scan", "1601", "--ranges", "E37A-E37C", "--rescan", *PACED)
    assert "22e37b" not in reads_seen(sim)
    assert "22e37c" in reads_seen(sim)



def test_paced_scan_reports_recovery_time(p4, root, sim):
    import threading
    import time
    sim.knockout.add((0x1601, 0xE37B))

    def revive():  # bring the module back a little after the knockout
        deadline = time.monotonic() + 5
        while 0x1601 not in sim.silent and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(2.5)  # longer than the three TesterPresent attempts that notice the silence
        sim.silent.discard(0x1601)
    t = threading.Thread(target=revive)
    t.start()
    with pytest.raises(SystemExit, match=r"answered again [1-9]\d* s after DID E37B"):
        p4("scan", "1601", "--ranges", "E37A-E37C", *PACED, "--recover", "10")
    t.join()
    assert scan_records(root, "1601")[-1]["status"] == "hazard"


def test_paced_scan_reads_nothing_unless_module_and_gateway_answer_first(p4, root, sim):
    sim.silent.add(0x1001)
    with pytest.raises(SystemExit, match="nothing read"):
        p4("scan", "1601", "--ranges", "E37A-E37B", *PACED)
    assert scan_records(root, "1601") == []
    assert "22e37a" not in reads_seen(sim)


def test_paced_scan_reads_a_dropping_did_once_and_records_it(p4, root, sim):
    sim.knockout_drop.add((0x1601, 0xE37B))
    with pytest.raises(SystemExit, match="still silent"):
        p4("scan", "1601", "--ranges", "E37A-E37C", *PACED, "--recover", "0.2")
    assert reads_seen(sim).count("22e37b") == 1
    rec = scan_records(root, "1601")[-1]
    assert rec["did"] == "E37B" and rec["status"] == "hazard" and "dropped" in rec["why"]


def test_paced_scan_treats_a_gateway_nack_as_a_hazard(p4, root, sim):
    sim.nack_dids.add((0x1601, 0xE37B))
    with pytest.raises(SystemExit, match="answered again"):
        p4("scan", "1601", "--ranges", "E37A-E37C", *PACED, "--recover", "2")
    rec = scan_records(root, "1601")[-1]
    assert rec["did"] == "E37B" and rec["status"] == "hazard" and "NACK" in rec["why"]
    assert "22e37c" not in reads_seen(sim)


def test_paced_scan_records_nrc_and_timeouts_from_a_live_module(p4, root, sim):
    sim.ignore.add((0x1601, 0xE37C))
    p4("scan", "1601", "--ranges", "E37A-E37C", *PACED)
    assert [(r["did"], r["status"], r.get("code")) for r in scan_records(root, "1601")] == [
        ("E37A", "nrc", "31"), ("E37B", "ok", None), ("E37C", "timeout", None)]


def test_a_hazard_outranks_a_later_answer_and_is_skipped_by_every_scan(p4, root, sim):
    sim.set(0x1635, 0xE37B, "01")
    day1 = root / "runs" / "2026-01-01"
    day1.mkdir(parents=True)
    store.append_jsonl(str(day1 / "scan-1601.jsonl"), {"t": "x", "tgt": "1601", "did": "E37B", "status": "hazard", "why": "test"})
    p4("scan", "1601", "--ranges", "E37A")  # today's file
    day2 = root / "runs" / "2026-01-02"
    day2.mkdir(parents=True)
    store.append_jsonl(str(day2 / "scan-1601.jsonl"), {"t": "x", "tgt": "1601", "did": "E37B", "status": "ok", "data": "03"})
    assert store.load_scans(0x1601)[0xE37B]["status"] == "hazard"
    assert 0xE37B not in store.known_ok(0x1601)
    sim.seen.clear()
    p4("scan", "1601", "--ranges", "E37A-E37C", "--rescan")
    p4("scan", "1635", "--ranges", "E37B")
    p4("scan", "1601", "--like", "1635")
    assert ("1601", "22e37b") not in [("%04X" % t, u.hex()) for t, u in sim.seen]
    assert "HAZARD" in p4("known", "1601", "--list")


def test_paced_scan_interrupted_after_a_read_records_that_did(p4, root, sim, monkeypatch):
    import time as _time
    real_sleep = _time.sleep

    def interrupt(secs):
        if secs == 0.01:
            raise KeyboardInterrupt
        real_sleep(secs)
    monkeypatch.setattr("p4doip.cli.time.sleep", interrupt)
    with pytest.raises(SystemExit, match="interrupted after reading 1601 E37A"):
        p4("scan", "1601", "--ranges", "E37A-E37B", "--paced", "0.01", "--timeout", "0.05")
    rec = scan_records(root, "1601")[-1]
    assert rec["did"] == "E37A" and rec["status"] == "hazard" and "interrupted" in rec["why"]

import json
import os
import re

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
    assert parse_ranges("") == []  # a watch-only sweep slot scans nothing
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
    assert "1317 F18C OK 00000000" in out  # F18C is a masked DID (ECU serial number per docs/did-identity.md)
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


# -- adaptive timeout ----------------------------------------------------------
def adaptive_spy(monkeypatch):
    """Record the timeout asked for every DID read (usage-mode reads pass none, so they stay out)."""
    from p4doip import cli
    asked = []
    real = cli.Link.do

    def spy(self, method, *a, **kw):
        if method == "read_did" and len(a) >= 3:
            asked.append(a[2])
        return real(self, method, *a, **kw)
    monkeypatch.setattr(cli.Link, "do", spy)
    return asked


def test_adaptive_timeout_drops_probes_and_restores():
    from p4doip.cli import ADAPT_AFTER, ADAPT_PROBE_EVERY, AdaptiveTimeout
    assert AdaptiveTimeout(0.5).short == 0.2 and AdaptiveTimeout(1.0).short == 0.4
    assert AdaptiveTimeout(0.4).short == 0.2  # the 0.2 s floor
    a = AdaptiveTimeout(0.5)
    seq = []
    for _ in range(ADAPT_PROBE_EVERY + ADAPT_AFTER):
        seq.append(a.next())
        a.seen("timeout")
    assert seq[:ADAPT_AFTER] == [0.5] * ADAPT_AFTER
    assert set(seq[ADAPT_AFTER:ADAPT_AFTER + ADAPT_PROBE_EVERY - 1]) == {0.2}
    assert seq[ADAPT_AFTER + ADAPT_PROBE_EVERY - 1] == 0.5  # every 50th DID in the short state probes at full
    assert a.next() == 0.2                                  # and the state carries on afterwards
    a.seen("nrc")                                           # any non-timeout answer restores the full timeout
    assert a.next() == 0.5


def test_scan_adaptive_timeout_shortens_after_silent_dids(p4, root, sim, monkeypatch):
    asked = adaptive_spy(monkeypatch)
    sim.ignore = {(0x1601, d) for d in range(0xE370, 0xE386)}  # 22 DIDs the (alive) module never answers
    p4("scan", "1601", "--ranges", "E370-E385", "--adaptive-timeout", "--timeout", "0.05")
    assert asked[:20] == [0.05] * 20       # the first 20 silences cost the full timeout
    assert asked[20:] == [0.2] * 2         # then 40% of it, min 0.2 s
    assert [r["status"] for r in scan_records(root, "1601")] == ["timeout"] * 22  # recorded exactly as before


def test_scan_adaptive_timeout_an_answer_restores_the_full_timeout(p4, root, sim, monkeypatch):
    asked = adaptive_spy(monkeypatch)
    sim.ignore = {(0x1601, d) for d in range(0xE370, 0xE385)} | {(0x1601, 0xE386)}
    sim.set(0x1601, 0xE385, "07")
    p4("scan", "1601", "--ranges", "E370-E386", "--adaptive-timeout", "--timeout", "0.05")
    # E384 times out short, E385 answers (still asked short), E386 is back at the full timeout
    assert asked == [0.05] * 20 + [0.2, 0.2] + [0.05]


def test_adaptive_timeout_is_refused_with_paced(p4):
    with pytest.raises(SystemExit, match="paced"):
        p4("scan", "1601", "--ranges", "E37A", "--adaptive-timeout", "--paced", "0")


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
    assert "1316 F18C 00000000" in out  # masked DID: recorded as zeros, text not printed
    path = next(root.glob("runs/*/identify-1316.json"))
    assert json.loads(path.read_text()) == {"DD0A": "0d", "F18C": "00000000"}
    sim.silent.add(0x1316)
    assert "nothing written" in p4("identify", "1316")
    assert json.loads(path.read_text()) == {"DD0A": "0d", "F18C": "00000000"}


def test_all_means_every_catalogue_module(p4, sim):
    p4("dtc", "all")
    asked = {t for t, uds in sim.seen if uds[0] == 0x19}
    assert {0x1601, 0x1316, 0x1A01, 0x1BB4} <= asked and len(asked) == 43


def test_mark_goes_to_session_log_and_run_dir(p4, root):
    p4("mark", "left", "front", "door")
    assert root.joinpath("local", "session-log.md").read_text().rstrip().endswith("left front door")
    rec = store.read_jsonl(str(next(root.glob("runs/*/marks.jsonl"))))[0]
    assert rec["mark"] == "left front door" and "T" in rec["t"]


# -- whois ---------------------------------------------------------------------
def test_whois_profiles_a_module_with_masking_and_similar(p4, root, sim):
    docs = root / "docs"
    docs.mkdir()
    (docs / "did-map.csv").write_text("module,did,status,length_bytes,nrc\n"
                                      "1316,F18C,ok,4,\n1316,DD0A,ok,1,\n1317,F18C,ok,4,\n1317,DD0A,ok,1,\n")
    out = p4("whois", "1316")
    assert "1316: usage mode 0d" in out
    assert "00000000" in out and "02160038" not in out  # masked serial: zeros, raw value never printed
    assert "ECU serial number" in out                   # name from catalogue/dids.yaml
    assert "stored DTCs: 1" in out and "supported DTCs: NRC 12" in out
    assert "similar: 1317  1.00  2 shared, 0 only-here" in out


def test_whois_hints_when_the_module_is_not_in_did_map(p4, root, sim):
    docs = root / "docs"
    docs.mkdir()
    (docs / "did-map.csv").write_text("module,did,status,length_bytes,nrc\n1601,E37B,ok,1,\n")
    out = p4("whois", "1316")
    assert "not in did-map yet: run ./p4 scan 1316 to fingerprint it" in out
    assert "similar" not in out


def test_whois_on_a_missing_module_says_so(p4):
    with pytest.raises(SystemExit, match="does not exist"):
        p4("whois", "16A1")


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
    sim.set(0x1301, 0xEE15, "02")
    p4("scan", "1301", "--ranges", "EE12-EE15")
    assert "22ee13" not in reads_seen(sim) and "22ee14" not in reads_seen(sim)  # both blocked (EE14 since 2026-11-14)
    assert {r["did"] for r in scan_records(root, "1301")} == {"EE12", "EE15"}


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


# -- similar / ranges (offline, from docs/did-map.csv) ------------------------------------------
def test_similar_ranks_1317_first_and_scores_symmetrically(monkeypatch, capsys):
    from conftest import REPO
    monkeypatch.setenv("P4_ROOT", REPO)
    main(["similar", "1316", "--top", "1"])
    assert re.match(r"1317  1\.00  \d+ shared, \d+ only-here$", capsys.readouterr().out.strip())
    main(["similar", "1317", "--top", "1"])
    assert capsys.readouterr().out.strip().startswith("1316  1.00")  # symmetric: each is the other's best

    def score_of(target, module):
        main(["similar", target, "--top", "64"])
        line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith(module + "  "))
        return float(line.split()[1])
    assert score_of("1316", "1A30") == score_of("1A30", "1316")


def test_merge_did_ranges_gap_semantics():
    from p4doip.cli import merge_did_ranges, ranges_spec
    assert merge_did_ranges([0x103, 0x100, 0x101], 0) == [(0x100, 0x101), (0x103, 0x103)]
    assert merge_did_ranges([0x100, 0x103], 2) == [(0x100, 0x103)]
    assert ranges_spec([(0x100, 0x101), (0x103, 0x103)]) == "0100-0101,0103"


def test_ranges_specs_are_parseable_and_cover_every_answered_did(monkeypatch, capsys):
    from conftest import REPO
    monkeypatch.setenv("P4_ROOT", REPO)
    main(["ranges", "--module", "1601"])
    head, spec = capsys.readouterr().out.splitlines()[:2]
    m = re.match(r"1601: (\d+) ranges cover (\d+) of (\d+) answered; DEFAULT_RANGES cover (\d+) of them$", head)
    assert m and int(m.group(4)) <= int(m.group(3))  # the default sweep can only cover a subset
    assert m and int(m.group(1)) >= 1 and m.group(2) == m.group(3)  # every answered DID is covered
    parts = [tuple(int(x, 16) for x in p.split("-")) for p in spec.strip().split(",")]
    assert all(len(t) in (1, 2) for t in parts) and all(len(t) == 1 or t[0] <= t[1] for t in parts)
    for prev, nxt in zip(parts, parts[1:]):  # neighbours stay more than --gap apart or they would have merged
        assert nxt[0] - prev[-1] > 0x40 + 1
    main(["ranges", "--all"])
    head, spec = capsys.readouterr().out.splitlines()[:2]
    assert re.match(r"all: (\d+) ranges cover (\d+) of (\d+) answered \(DIDs on >= 3 modules\)$", head)
    assert all(t[0] <= 0xFFFF and (len(t) == 1 or t[0] <= t[1])
               for t in (tuple(int(x, 16) for x in p.split("-")) for p in spec.strip().split(",")))


# -- scandiff / dtcdiff (offline, from runs/) ---------------------------------------------------
def write_scan_day(root, day, tgt, rows):
    for did, status, extra in rows:
        store.append_jsonl(store.scan_path(int(tgt, 16), day), {"tgt": tgt, "did": did, "status": status, **extra})


def write_dtc_day(root, day, tgt, recs):
    d = root / "runs" / day
    d.mkdir(parents=True, exist_ok=True)
    for rec in recs:
        store.append_jsonl(str(d / ("dtc-%s.jsonl" % tgt)), rec)


def test_scandiff_groups_status_transitions(root, capsys):
    write_scan_day(root, "2026-11-10", "1601", [
        ("2B10", "ok", {"data": "01"}), ("2B11", "nrc", {"code": "31"}), ("2B13", "ok", {"data": "01"}),
        ("2B14", "ok", {"data": "01"}), ("2B15", "timeout", {}), ("2B16", "nrc", {"code": "12"}),
        ("2B17", "ok", {"data": "01"})])
    write_scan_day(root, "2026-11-11", "1601", [
        ("2B10", "ok", {"data": "02"}), ("2B11", "ok", {"data": "05"}), ("2B12", "ok", {"data": "01"}),
        ("2B13", "nrc", {"code": "22"}), ("2B14", "timeout", {}), ("2B15", "nrc", {"code": "33"}),
        ("2B16", "nrc", {"code": "12"})])
    main(["scandiff", "1601"])
    out = capsys.readouterr().out
    assert "newly answered OK:\n  2B12" in out
    assert "refused -> OK:\n  2B11" in out
    assert "was OK now refused:\n  2B13 NRC 22 (conditionsNotCorrect)" in out
    assert "was OK now silent:\n  2B14" in out
    assert "newly refused:\n  2B15 NRC 33 (securityAccessDenied)" in out
    assert ("2026-11-10 -> 2026-11-11: 5 changed (1 newly answered OK, 1 refused -> OK, "
            "1 was OK now refused, 1 was OK now silent, 1 newly refused)") in out
    assert "2B10" not in out and "2B16" not in out and "2B17" not in out  # unchanged, or not recorded on day B


def test_scandiff_needs_two_run_days(root):
    with pytest.raises(SystemExit, match="no runs"):
        main(["scandiff", "1601"])  # runs/ absent
    store.append_jsonl(store.scan_path(0x1601, "2026-11-10"), {"tgt": "1601", "did": "E37B", "status": "ok", "data": "03"})
    with pytest.raises(SystemExit, match="only one run day"):
        main(["scandiff", "1601"])
    with pytest.raises(SystemExit, match="no runs/2099-01-01/scan-1601"):
        main(["scandiff", "1601", "--day-a", "2099-01-01"])


def test_dtcdiff_reports_new_and_cleared_codes(root, capsys):
    write_dtc_day(root, "2026-11-10", "1601", [{"kind": "supported", "status": "nrc", "code": "12"},
                                               {"kind": "stored", "status": "ok", "raw": "5902ffd1234508d1234609"}])
    write_dtc_day(root, "2026-11-11", "1601", [{"kind": "stored", "status": "ok", "raw": "5902ffd1234609d1234708"}])
    main(["dtcdiff", "1601"])
    out = capsys.readouterr().out
    assert "1601 2026-11-10 -> 2026-11-11: 1 new, 1 gone, 1 unchanged" in out
    assert "  new   DTC D12347 status 08" in out
    assert "  gone  DTC D12345 status 08" in out
    main(["dtcdiff"])  # no targets = every module with dtc files
    assert capsys.readouterr().out == out
    write_dtc_day(root, "2026-11-10", "1635", [{"kind": "stored", "status": "nrc", "code": "12"}])
    main(["dtcdiff", "1635"])
    ro = capsys.readouterr()
    assert "1635: no stored-DTC answer recorded on 2026-11-10; skipped" in ro.err and ro.out == ""


def test_dtcdiff_without_run_days_says_so(root):
    with pytest.raises(SystemExit, match="no runs"):
        main(["dtcdiff"])
    write_dtc_day(root, "2026-11-10", "1601", [{"kind": "stored", "status": "ok", "raw": "5902ffd1234508"}])
    with pytest.raises(SystemExit, match="only one run day"):
        main(["dtcdiff", "1601"])


def test_strings_reads_utf16_and_hexwrapped_and_identity_dids(root, capsys):
    vin = "YSM" + "4ZPAA0XX000000"  # split: no whole VIN in this file
    utf16 = ("SW " + vin).encode("utf-16-le").hex()
    wrapped = ("TEL +" + "44 7700 900123").encode().hex().encode().hex()  # text wrapped in ASCII hex
    rows = [("F181", b"P3145678".hex()), ("F18C", b"SER 0216A0038".hex()),
            ("F190", ("ABC" + "4ZPAA0XX000000").encode().hex()), ("E0A0", utf16), ("E0A1", wrapped)]
    for did, data in rows:
        store.append_jsonl(store.scan_path(0x1316, "2026-11-11"), {"tgt": "1316", "did": did, "status": "ok", "data": data})
    main(["strings", "1316"])
    out = capsys.readouterr().out
    assert "1316:F181 P3145678" in out  # identity DIDs are searched now (only masked DIDs stay out)
    assert "1316:E0A0 SW [VIN hidden]" in out  # UTF-16LE text reaches the same masking
    assert "1316:E0A1 TEL [phone hidden]" in out  # ASCII-hex-wrapped text is unwrapped and masked
    assert "F18C" not in out and "F190" not in out  # masked DIDs never print, whatever they hold
    assert "0216A0038" not in out and "4ZPAA0" not in out.upper()


# -- ./p4 wrapper: the one-tester lock ------------------------------------------
@pytest.mark.parametrize("argv,locked", [
    (["scan", "1316"], True), (["--host", "x", "scan", "1316"], True), (["--host=x", "scan", "1316"], True),
    (["--retry-wait", "1", "watch", "1601"], True), (["--ho", "x", "scan", "1316"], True), (["identify", "all"], True),
    (["strings", "all"], False), (["--retries", "3", "correlate", "2026-11-11"], False), (["mark", "x"], False),
    (["known", "1316"], False), (["diff", "a", "b"], False), (["signals"], False), (["--help"], False),
    (["similar", "1316"], False), (["scandiff", "1601"], False), (["dtcdiff"], False), (["ranges", "--all"], False),
    (["whois", "1316"], True), (["sweep", "--plan", "plan.yaml"], True), (["read", "1601:E37B"], True),
    (["doctor"], True), (["hazards"], False), (["did", "E37B"], False), (["runs"], False), (["tree"], False),
    (["export"], False), (["report"], False),
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


# -- sweep (unattended scan plans) ---------------------------------------------
def write_plan(root, text):
    p = root / "sweep-plan.yaml"
    p.write_text(text)
    return str(p)


def test_sweep_runs_slots_watches_and_writes_progress(p4, root, sim):
    sim.script[(0x1601, 0xE37B)] = ["03", "05", "09"]  # the scan takes 03; the watch sees 05 then 09
    plan = write_plan(root, "slots:\n"
                            "  - {module: '1601', ranges: 'E37A-E37B', watch: 'E37B', watch_secs: 0.4}\n"
                            "  - {module: '1635', ranges: ''}\n")  # empty ranges: watch-only slot, scans nothing
    p4("sweep", "--plan", plan, "--timeout", "0.05")
    recs = {r["did"]: r["status"] for r in scan_records(root, "1601")}
    assert recs == {"E37A": "nrc", "E37B": "ok"}
    assert not list(root.glob("runs/*/scan-1635.jsonl")) and "224801" not in reads_seen(sim)
    log = next(root.glob("runs/*/watch-sweep-1601.log")).read_text()
    assert "1601:E37B CHANGE 05 -> 09" in log
    prog = json.loads(next(root.glob("runs/*/sweep.progress.json")).read_text())
    assert prog["current"] == "done" and prog["total"] == 2 and prog["remaining"] == []
    assert prog["gated"] == [] and prog["parked"] is False and "since" in prog and "watch_secs" in prog


def test_sweep_accepts_a_mapping_plan_and_records_parked(p4, root, sim):
    plan = write_plan(root, "parked: true\nslots:\n  - {module: '1601', ranges: 'E37B'}\n")
    p4("sweep", "--plan", plan, "--timeout", "0.05")
    prog = json.loads(next(root.glob("runs/*/sweep.progress.json")).read_text())
    assert prog["parked"] is True and prog["current"] == "done" and prog["total"] == 1
    assert scan_records(root, "1601")[0]["did"] == "E37B"


def test_sweep_budget_stops_between_slots(p4, root, sim):
    plan = write_plan(root, "slots:\n"
                            "  - {module: '1601', ranges: 'E37A-E37B', watch: 'E37B', watch_secs: 1.0}\n"
                            "  - {module: '1635', ranges: '4801'}\n"
                            "  - {module: '1A01', ranges: '42F2'}\n")
    out = p4("sweep", "--plan", plan, "--max-minutes", "0.01", "--timeout", "0.05")  # 0.6 s: gone after slot 1's watch
    assert [r["did"] for r in scan_records(root, "1601")] == ["E37A", "E37B"]  # slot 1 ran to the end
    assert not list(root.glob("runs/*/scan-1635.jsonl")) and not list(root.glob("runs/*/scan-1A01.jsonl"))
    assert "224801" not in reads_seen(sim) and "2242f2" not in reads_seen(sim)
    assert "stopping before 1635:4801; 2 slots left" in out
    prog = json.loads(next(root.glob("runs/*/sweep.progress.json")).read_text())
    assert prog["current"].startswith("stopped") and prog["remaining"] == ["1635:4801", "1A01:42F2"]


def test_sweep_sigterm_stops_after_the_current_slot(p4, root, sim, monkeypatch):
    import signal as py_signal
    import threading
    from p4doip import cli
    delivered = threading.Event()
    real_signal = py_signal.signal

    def capture(sig, fn):
        if sig == py_signal.SIGTERM:
            if not delivered.is_set():
                delivered.set()
                threading.Timer(0.25, fn, args=(sig, None)).start()  # SIGTERM arrives during slot 1's watch
            return None  # the test delivers the signal itself; nothing installed for real
        return real_signal(sig, fn)
    monkeypatch.setattr(py_signal, "signal", capture)
    plan = write_plan(root, "slots:\n"
                            "  - {module: '1601', ranges: 'E37A-E37B', watch: 'E37B', watch_secs: 0.8}\n"
                            "  - {module: '1635', ranges: '4801'}\n")
    p4("sweep", "--plan", plan, "--timeout", "0.05")
    assert [r["did"] for r in scan_records(root, "1601")] == ["E37A", "E37B"]  # slot 1 completed, watch included
    assert not list(root.glob("runs/*/scan-1635.jsonl"))
    prog = json.loads(next(root.glob("runs/*/sweep.progress.json")).read_text())
    assert prog["current"] == "stopped (SIGTERM)" and prog["remaining"] == ["1635:4801"]


def test_sweep_rejects_a_bad_plan_before_touching_the_car(p4, root):
    with pytest.raises(SystemExit, match="slot 1"):
        p4("sweep", "--plan", write_plan(root, "slots:\n  - {ranges: 'E37B'}\n"))
    with pytest.raises(SystemExit, match="no slots"):
        p4("sweep", "--plan", write_plan(root, "slots: []\n"))
    with pytest.raises(SystemExit, match="bad ranges"):
        p4("sweep", "--plan", write_plan(root, "slots:\n  - {module: '1601', ranges: 'zzzz'}\n"))
    assert not list(root.glob("runs/*/sweep.progress.json")) and not list(root.glob("runs/*/scan-*.jsonl"))


# -- didmap / DID registry / NRC names / masking ----------------------------
def test_stored_value_masks_car_identifiers():
    from p4doip.cli import MASKED_DIDS, stored_value
    assert stored_value(0xF190, b"VIN") == "000000"
    assert stored_value(0xF18C, b"abcd") == "00000000"
    assert stored_value(0xF192, b"abcd") == "00000000"
    assert stored_value(0xF198, b"abcd") == "00000000"
    assert stored_value(0xE37B, b"\x03") == "03"
    assert MASKED_DIDS == {0xF190, 0xF18C, 0xF192, 0xF198}


def test_did_registry_covers_every_identity_did():
    from conftest import REPO
    from p4doip import cli, decode
    reg = decode.load_dids(os.path.join(REPO, "catalogue", "dids.yaml"))
    assert [d for d in cli.IDENTITY_DIDS if d not in reg] == []
    assert {d for d, e in reg.items() if e.get("masked")} == cli.MASKED_DIDS
    identity = {d for d, e in reg.items() if e.get("family") == "identity"}
    assert identity - set(cli.IDENTITY_DIDS) == cli.IDENTITY_SKIP  # F190 only, deliberately unprobed


def test_nrc_names():
    from p4doip.client import nrc_name
    assert nrc_name(0x31) == "requestOutOfRange"
    assert nrc_name(0x33) == "securityAccessDenied"
    assert nrc_name(0x66) == "unlisted"


def test_known_prints_nrc_names(p4, root):
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E37A", "status": "nrc", "code": "33"})
    assert "securityAccessDenied" in p4("known", "1601", "--list")


def test_didmap_writes_checks_and_detects_stale(p4, root):
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E37B", "status": "ok", "data": "03"})
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E37A", "status": "nrc", "code": "31"})
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "2B1A", "status": "nrc", "code": "22"})
    p4("didmap")
    lines = (root / "docs" / "did-map.csv").read_text().strip().splitlines()
    assert lines[0] == "module,did,status,length_bytes,nrc"
    assert "1601,E37B,ok,1," in lines
    assert "1601,2B1A,nrc,,22" in lines
    assert not [line for line in lines if "E37A" in line]  # NRC 31 rows are not exported
    p4("didmap", "--check")  # fresh: no exit
    store.append_jsonl(store.scan_path(0x1601, "2026-11-13"), {"tgt": "1601", "did": "E36E", "status": "ok", "data": "0100"})
    with pytest.raises(SystemExit) as exc:
        p4("didmap", "--check")
    assert exc.value.code == 1


# -- review improvements ------------------------------------------------------
def test_similar_families_groups_twins(monkeypatch, capsys):
    from conftest import REPO
    monkeypatch.setenv("P4_ROOT", REPO)
    main(["similar", "--families"])
    out = capsys.readouterr().out
    fam = [line for line in out.splitlines() if line.startswith("family")]
    assert any("1316" in line and "1317" in line for line in fam)
    assert any("1670" in line and "1676" in line for line in fam)
    assert "modules standalone" in out


def test_similar_refused_scores_rear_door_pairs(monkeypatch, capsys):
    from conftest import REPO
    monkeypatch.setenv("P4_ROOT", REPO)
    main(["similar", "1A21", "--refused", "--top", "3"])
    assert capsys.readouterr().out.splitlines()[0].startswith("1A22")


def test_ranges_reports_default_coverage(monkeypatch, capsys):
    from conftest import REPO
    monkeypatch.setenv("P4_ROOT", REPO)
    main(["ranges", "--module", "1BB3"])
    assert "DEFAULT_RANGES cover" in capsys.readouterr().out


def test_ranges_min_modules_flag(monkeypatch, capsys):
    from conftest import REPO
    monkeypatch.setenv("P4_ROOT", REPO)
    main(["ranges", "--all", "--min-modules", "40"])
    assert ">= 40 modules" in capsys.readouterr().out


def test_utf16_with_padding_still_decodes():
    from p4doip.cli import readable_text
    # "SOFTWARE" as UTF-16LE with extra NUL/space padding around it
    padded = "00" + "SOFTWARE".encode().hex() + "00"  # plain ASCII first: control
    assert readable_text("53004f004600540057004100520005000500") == ""  # odd junk is not text
    inner = "53004f00460054005700410052004500"  # clean UTF-16LE "SOFTWARE"
    assert readable_text(inner) == "SOFTWARE"
    assert readable_text(inner + "0000") == "SOFTWARE"  # even NUL padding
    assert readable_text(inner + "000000") == "SOFTWARE"  # odd NUL padding: lanes must not shift
    assert readable_text("2020" + inner) == "SOFTWARE"  # leading space padding shifts lanes when stripped


# -- transient NRCs and pending caps ------------------------------------------
def test_transient_nrc_is_retried_then_recorded_ok(p4, root, sim):
    sim.nrc_script[(0x1601, 0xE37B)] = [0x21, 0x21]  # busy twice, then the value
    p4("scan", "1601", "--ranges", "E37B", "--timeout", "0.2")
    rec = scan_records(root, "1601")[-1]
    assert (rec["did"], rec["status"]) == ("E37B", "ok")


def test_exhausted_transient_nrc_stays_retryable(p4, root, sim):
    sim.nrc_script[(0x1601, 0xE37B)] = [0x21] * 10  # always busy
    p4("scan", "1601", "--ranges", "E37B", "--timeout", "0.2")
    rec = scan_records(root, "1601")[-1]
    assert rec["status"] == "nrc" and rec["code"] == "21" and rec["retryable"] is True
    before = len(reads_seen(sim))
    p4("scan", "1601", "--ranges", "E37B", "--timeout", "0.2")
    assert len(reads_seen(sim)) > before  # not settled: asked again


def test_retryable_rows_are_not_map_facts(p4, root):
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"),
                       {"tgt": "1601", "did": "2B1A", "status": "nrc", "code": "22", "retryable": True})
    p4("didmap")
    lines = (root / "docs" / "did-map.csv").read_text().strip().splitlines()
    assert not [line for line in lines if "2B1A" in line]
    assert "transient" in p4("known", "1601", "--list")


# -- catalogue hazards --------------------------------------------------------
def test_hazards_lists_block_and_caution(p4):
    out = p4("hazards")
    assert "1301:EE13" in out and "block" in out
    assert "1601:D928" in out and "caution" in out and "start-up" in out.lower()


def test_scan_skips_caution_unless_allowed(p4, root, sim):
    sim.set(0x1601, 0xD928, "01")
    p4("scan", "1601", "--ranges", "D928", "--timeout", "0.05")
    assert "22d928" not in reads_seen(sim)
    p4("--allow-caution", "scan", "1601", "--ranges", "D928", "--timeout", "0.05")
    assert "22d928" in reads_seen(sim)


def test_paced_scan_may_test_a_caution_did(p4, root, sim):
    sim.set(0x1601, 0xD928, "01")
    p4("scan", "1601", "--ranges", "D928", *PACED)
    assert "22d928" in reads_seen(sim)


def test_watch_refuses_a_caution_did_without_the_flag(p4, sim):
    with pytest.raises(SystemExit, match="nothing left to watch"):
        p4("watch", "1601:D928", "--passes", "1")
    out = p4("--allow-caution", "watch", "1601:D928", "--passes", "1")
    assert "1 reads per pass" in out  # the first value is quiet, but the watch ran


# -- sweep failure/dry-run/plan validation ------------------------------------
def test_sweep_failure_is_written_to_progress(p4, root, sim):
    plan = write_plan(root, "slots:\n  - {module: '16A1', ranges: 'E37B'}\n  - {module: '1601', ranges: 'E37B'}\n")
    with pytest.raises(SystemExit, match="NACK 03"):
        p4("sweep", "--plan", plan, "--timeout", "0.05")
    prog = json.loads(next(root.glob("runs/*/sweep.progress.json")).read_text())
    assert prog["current"].startswith("failed:") and prog["remaining"] == ["16A1:E37B", "1601:E37B"]


def test_sweep_dry_run_writes_nothing_and_connects_nothing(p4, root, sim):
    plan = write_plan(root, "slots:\n  - {module: '1601', ranges: 'E37A-E37B', watch: 'E37B', watch_secs: 5}\n")
    out = p4("sweep", "--plan", plan, "--dry-run")
    assert "2 to try" in out and "estimated total" in out
    assert not list(root.glob("runs/*")) and not sim.seen


def test_sweep_rejects_unknown_keys_before_touching_the_car(p4, root, sim):
    plan = write_plan(root, "slots:\n  - {module: '1601', ranges: 'E37B', watch_secs_too_long: 5}\n")
    with pytest.raises(SystemExit, match="unknown key"):
        p4("sweep", "--plan", plan)
    assert not sim.seen


def test_scan_bad_ranges_is_a_clear_error(p4):
    with pytest.raises(SystemExit, match="bad range"):
        p4("scan", "1601", "--ranges", "ZZZZ")


# -- dated watch logs, keepalive ---------------------------------------------
def test_watch_log_lines_carry_the_date(root, tmp_path):
    from p4doip.cli import WatchLog
    p = str(tmp_path / "w.log")
    WatchLog(p)("1601:E37B 03", show=False)
    line = open(p).read().strip()
    assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d)? ", line), line


def test_correlate_uses_the_date_in_a_new_log(root, capsys):
    import datetime
    write_day(root, [((16, 0, 10), "chassis Firm")], [])
    d = root / "runs" / "2026-11-11"
    t = datetime.datetime(2026, 11, 11, 16, 0, 9).astimezone().isoformat(timespec="seconds")
    (d / "watch-drive.log").write_text(
        "%s connected: 1 reads per pass\n%s 1614:D90F CHANGE 00 -> 03\n" % (t, t))
    main(["correlate", "2026-11-11"])
    out = capsys.readouterr().out
    assert "1614:D90F 00 -> 03" in out


def test_watch_keepalive_sends_tester_present(p4, sim):
    p4("watch", "1601:E37B", "--passes", "1", "--interval", "0.4", "--keepalive", "0.1", "--baseline", "0")
    assert sum(1 for _, uds in sim.seen if uds == b"\x3e\x00") >= 2


# -- DTC depth ---------------------------------------------------------------
def test_dtc_supported_success_and_status_legend(p4, sim):
    sim.supported[0x1601] = [bytes.fromhex("d1234508")]
    out = p4("dtc", "1601")
    assert "1601 supported: 1 DTCs" in out
    assert "D12345 status 08 (confirmedDTC)" in out


def test_dtc_freeze_frame(p4, sim):
    sim.freeze[(0x1601, 0xD12345)] = bytes.fromhex("deadbeef")
    out = p4("dtc", "1601", "--freeze", "D12345")
    assert "5904d12345" in out and "deadbeef" in out


def test_dtc_json(p4, sim):
    out = p4("dtc", "1601", "--json")
    recs = json.loads(out)
    assert [r["kind"] for r in recs] == ["stored", "supported"]
    assert recs[0]["dtcs"] == [{"dtc": "D12345", "status": "08"}]


# -- read / did / names / dids-file / JSON -----------------------------------
def test_read_one_or_more_dids(p4, sim):
    out = p4("read", "1601:E37B,2B15")
    assert "1601 E37B OK 03" in out and "1601 2B15 OK 00" in out


def test_read_masks_identifiers(p4, sim):
    vin = "YSM" + "4ZPAA0TF000000"
    sim.set(0x1601, 0xF190, vin.encode().hex())
    out = p4("read", "1601:F190")
    assert "OK " + "00" * len(vin) in out and vin not in out


def test_read_refuses_blocked_and_cautioned(p4, sim):
    with pytest.raises(SystemExit, match="refusing"):
        p4("read", "1301:EE13")
    with pytest.raises(SystemExit, match="caution"):
        p4("read", "1601:D928")
    assert p4("--allow-caution", "read", "1601:D928").startswith("1601 D928")


def test_read_repeat_and_json(p4, sim):
    out = p4("read", "1601:E37B", "--repeat", "2")
    assert out.count("1601 E37B OK 03") == 2
    recs = json.loads(p4("read", "1601:E37B", "--json"))
    assert recs[0]["module"] == "1601" and recs[0]["status"] == "ok" and recs[0]["data"] == "03"


def test_did_lookup_by_hex_and_text(p4):
    assert "epb_state" in p4("did", "E37B")
    assert "vehicle_speed" in p4("did", "speed")
    assert json.loads(p4("did", "E37B", "--json"))["signals"][0]["id"] == "epb_state"


def test_scan_dids_file(p4, root, sim):
    p = root / "dids.txt"
    p.write_text("# candidates\nE37A E37B\n2B15,2B20\n")
    p4("scan", "1601", "--dids-file", str(p), "--timeout", "0.05")
    assert [r["did"] for r in scan_records(root, "1601")] == ["E37A", "E37B", "2B15", "2B20"]


def test_scan_names_flag(p4, sim):
    out = p4("scan", "1001", "--ranges", "DD0A", "--names")
    assert "power mode" in out


def test_known_and_strings_names_flag(p4, root):
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "DD0A", "status": "ok", "data": "0d"})
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "F181", "status": "ok",
                                                               "data": b"P3145678".hex()})
    assert "power mode" in p4("known", "1601", "--list", "--names")
    assert "P3145678  [application software ID]" in p4("strings", "1601", "--names")


def test_json_outputs_smoke(p4, root, sim):
    p4("scan", "1601", "--ranges", "E37B", "--timeout", "0.05")
    known = json.loads(p4("known", "1601", "--json"))
    assert known["1601"]["ok"][0]["did"] == "E37B"
    assert len(json.loads(p4("signals", "--json"))) > 90
    whois = json.loads(p4("whois", "1601", "--json"))
    assert whois["module"] == "1601" and whois["dtc"]["stored"]["count"] == 1
    assert json.loads(p4("read", "1601:E37B", "--json"))[0]["data"] == "03"


# -- runs / tree / doctor / export / report ----------------------------------
def _populate_day(root):
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"),
                       {"v": 2, "tool": "x", "run": "2026-11-12T10:00:00+01:00", "usage_mode": "0d"})
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E37B", "status": "ok", "data": "03"})
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E37A", "status": "nrc", "code": "31"})
    store.append_jsonl(store.scan_path(0x1A01, "2026-11-12"), {"tgt": "1A01", "did": "42F2", "status": "ok", "data": "42"})
    store.append_jsonl(os.path.join(store.run_dir("2026-11-12"), "dtc-1601.jsonl"),
                       {"t": "2026-11-12T10:00:00+01:00", "kind": "stored", "status": "ok", "raw": "5902ffd1234508"})
    store.append_jsonl(os.path.join(store.run_dir("2026-11-12"), "marks.jsonl"),
                       {"t": "2026-11-12T10:05:00+01:00", "mark": "left front door"})
    with open(os.path.join(store.run_dir("2026-11-12"), "watch-1.log"), "w") as f:
        f.write("2026-11-12T10:05:00 1601:E37B CHANGE 03 -> 05\n")


def test_runs_lists_a_day(p4, root):
    _populate_day(root)
    out = p4("runs")
    assert "2026-11-12" in out and "scan  2" in out and "marks yes" in out


def test_tree_shows_answered_blocks(p4, root):
    _populate_day(root)
    out = p4("tree", "--module", "1601")
    assert "1601" in out and "1 ok" in out and "2 tried" in out


def test_doctor_offline_checks_the_project(p4, root):
    (root / "docs").mkdir()
    (root / "docs" / "did-map.csv").write_text("module,did,status,length_bytes,nrc\n")
    out = p4("doctor", "--offline")
    assert "OK" in out and "hazards" in out and "signals decode" in out


def test_export_json_and_csv_mask_identifiers(p4, root):
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"),
                       {"tgt": "1601", "did": "F190", "status": "ok", "data": "41" * 17})
    store.append_jsonl(store.scan_path(0x1601, "2026-11-12"), {"tgt": "1601", "did": "E37B", "status": "ok", "data": "03"})
    recs = json.loads(p4("export", "--module", "1601"))
    f190 = next(r for r in recs if r["did"] == "F190")
    assert f190["data"] == "00" * 17
    csv_text = p4("export", "--module", "1601", "--format", "csv")
    assert csv_text.splitlines()[0].startswith("module,did,status") and "F190" in csv_text


def test_report_summarises_a_day(p4, root):
    _populate_day(root)
    out = p4("report", "2026-11-12")
    assert "# Run 2026-11-12" in out and "| 1601 | 1 | 1 | 0 | 0 |" in out
    assert "left front door" in out and "watch-1.log: 1 changes" in out


# -- experimental multi-DID read ---------------------------------------------
def test_read_multi_splits_with_known_lengths(p4, root, sim):
    (root / "docs").mkdir()
    (root / "docs" / "did-map.csv").write_text(
        "module,did,status,length_bytes,nrc\n1601,E37B,ok,1,\n1601,2B15,ok,1,\n")
    out = p4("read", "1601:E37B,2B15", "--multi")
    assert "1601 E37B OK 03" in out and "1601 2B15 OK 00" in out


def test_read_multi_without_lengths_reports_raw(p4, sim):
    out = p4("read", "1601:E37B,2B15", "--multi")
    assert "no split" in out and "62e37b032b1500" in out


def test_read_multi_refuses_blocked_batch(p4, sim):
    with pytest.raises(SystemExit, match="refusing"):
        p4("read", "1301:EE13,EE12", "--multi")


# -- provenance, skip-silent, sweep log, doctor live -------------------------
def test_scan_header_records_provenance(p4, root, monkeypatch):
    monkeypatch.setenv("P4_COMMIT", "abc1234")
    p4("scan", "1601", "--ranges", "E37B", "--timeout", "0.05", "--skip-silent-after", "7")
    header = store.read_jsonl(store.scan_path(0x1601, "2026-11-14"))[0]
    assert header["v"] == 2 and header["tool"] and header["commit"] == "abc1234"
    assert header["timeout"] == 0.05 and header["skip_silent_after"] == 7


def test_skip_silent_after_skips_recent_timeouts(p4, root, sim):
    import datetime
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    store.append_jsonl(store.scan_path(0x1601, "2026-11-13"),
                       {"t": now, "tgt": "1601", "did": "E37A", "status": "timeout"})
    p4("scan", "1601", "--ranges", "E37A", "--timeout", "0.05", "--skip-silent-after", "2")
    assert "22e37a" not in reads_seen(sim)


def test_sweep_writes_a_log(p4, root, sim):
    plan = write_plan(root, "slots:\n  - {module: '1601', ranges: 'E37B'}\n")
    p4("sweep", "--plan", plan, "--timeout", "0.05")
    log = next(root.glob("runs/*/sweep.log")).read_text()
    assert "scan 1601:E37B: start" in log and "1 new OK" in log


def test_doctor_with_the_simulated_gateway(p4, root, sim):
    (root / "docs").mkdir()
    (root / "docs" / "did-map.csv").write_text("module,did,status,length_bytes,nrc\n")
    out = p4("doctor")
    assert "OK" in out and "gateway" in out and "informational" in out

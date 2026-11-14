import time

import pytest

from p4doip import client
from p4doip.client import ConnectionLost, DoIP, ReadOnlyViolation, check_read_only


@pytest.fixture
def c(sim):
    with DoIP("127.0.0.1", sim.port) as conn:
        yield conn


def test_activation_reports_gateway(c):
    assert c.gateway == 0x1001


def test_read_ok(c):
    r = c.read_did(0x1601, 0xE37B)
    assert (r.status, r.payload.hex()) == ("ok", "03")
    assert r.text() == "OK 03"


def test_unknown_did_is_nrc_31(c):
    r = c.read_did(0x1601, 0x1234)
    assert (r.status, r.code) == ("nrc", 0x31)


def test_unknown_address_is_nack_03(c):
    r = c.read_did(0x16A1, 0x2B24)
    assert (r.status, r.code) == ("nack", 0x03)


def test_nack_about_another_address_is_not_ours(sim, c):
    sim.nack_source = 0x1999
    assert c.read_did(0x16A1, 0x2B24, timeout=0.2).status == "timeout"


def test_silent_module_times_out(sim, c):
    sim.silent.add(0x1601)
    assert c.read_did(0x1601, 0xE37B, timeout=0.2).status == "timeout"


def test_response_pending_extends_the_deadline(sim, c):
    sim.pending.add((0x1601, 0xE37B))
    sim.delay[(0x1601, 0xE37B)] = 0.4  # the real answer comes after the 0.2 s timeout
    assert c.read_did(0x1601, 0xE37B, timeout=0.2).payload.hex() == "03"


def test_stale_positive_reply_for_another_did_is_skipped(sim, c):
    sim.stale.add((0x1601, 0xE37B))
    assert c.read_did(0x1601, 0xE37B).payload.hex() == "03"


def test_late_negative_reply_is_not_blamed_on_the_next_did(sim, c):
    sim.delay[(0x1601, 0x1234)] = 0.3  # its NRC 31 arrives after we gave up
    assert c.read_did(0x1601, 0x1234, timeout=0.1).status == "timeout"
    r = c.read_did(0x1601, 0xE37B)     # without resync this would be recorded as NRC 31
    assert (r.status, r.payload.hex()) == ("ok", "03")


def test_late_dtc_reply_is_not_taken_for_another_sub_function(c):
    assert DoIP._matches(bytes.fromhex("190a"), bytes.fromhex("5902ff")) is None
    assert DoIP._matches(bytes.fromhex("1902ff"), bytes.fromhex("5902ff")) == "ok"


def test_alive_check_is_answered(sim, c):
    sim.alive_check_next = True
    assert c.read_did(0x1601, 0xE37B).payload.hex() == "03"
    c.read_did(0x1601, 0xE37B)  # gives the simulator time to have received the reply
    assert 0x0008 in sim.frames


def test_functional_read_collects_every_module(c):
    got = c.request_all(0x1FFF, bytes.fromhex("22dd0a"), window=0.5)
    assert sorted(got) == [0x1001, 0x1316, 0x1A01]
    assert all(r.payload.hex() == "0d" for r in got.values())


def test_tester_present(c):
    assert c.tester_present(0x1316).status == "ok"
    assert c.tester_present(0x1999).status == "nack"


# -- read-only guarantee ----------------------------------------------------
def test_allowed_services_are_exactly_the_three_reads():
    assert set(client.ALLOWED_SIDS) == {0x22, 0x19, 0x3E}


@pytest.mark.parametrize("sid", range(256))
def test_every_other_service_is_refused(sid):
    uds = bytes([sid, 0x00, 0x00])
    if sid in (0x22, 0x19, 0x3E):
        check_read_only(uds)
    else:
        with pytest.raises(ReadOnlyViolation):
            check_read_only(uds)


@pytest.mark.parametrize("uds", [
    "1003",        # session control
    "1101",        # ECU reset
    "14ffffff",    # clear DTCs
    "2705",        # security access seed
    "2706aabbcc",  # security access key
    "2e2b2400",    # write DID
    "2f2b240301",  # IO control
    "31013000",    # routine control
    "3101302d",
    "2800",        # communication control
    "8502",        # control DTC setting
    "",            # nothing
    "22",          # malformed read
    "22e3",
    "22e37b2b1a",  # multi-DID read: not handled, so not sent
    "19",          # DTC read without sub-function
])
def test_refused_requests_never_reach_the_gateway(sim, c, uds):
    with pytest.raises(ReadOnlyViolation):
        c.request(0x1601, bytes.fromhex(uds))
    with pytest.raises(ReadOnlyViolation):
        c.request_all(0x1FFF, bytes.fromhex(uds), window=0.1)
    assert sim.seen == []


def test_reads_are_allowed():
    for uds in ("22e37b", "1902ff", "190a", "3e00"):
        check_read_only(bytes.fromhex(uds))


def test_only_the_client_module_sends_on_sockets():
    import os
    import p4doip
    pkg = os.path.dirname(p4doip.__file__)
    offenders = [f for f in os.listdir(pkg) if f.endswith(".py") and f not in ("client.py", "sim.py")
                 and ("sendall" in open(os.path.join(pkg, f)).read() or "import socket" in open(os.path.join(pkg, f)).read())]
    assert offenders == []


# -- connection handling ------------------------------------------------------
def test_second_tester_is_dropped(sim, c):
    with pytest.raises(ConnectionLost):
        DoIP("127.0.0.1", sim.port, connect_timeout=1).connect()
    assert c.read_did(0x1601, 0xE37B).status == "ok"  # the first one is unaffected


def test_gateway_dropping_us_raises_and_frees_the_socket(sim, c):
    sim.drop_after = 0
    with pytest.raises(ConnectionLost):
        c.read_did(0x1601, 0xE37B)
    assert c.sock is None  # nothing left holding the gateway's single tester slot


def test_reconnect_after_drop_works(sim, c):
    sim.drop_after = 0
    with pytest.raises(ConnectionLost):
        c.read_did(0x1601, 0xE37B)
    for _ in range(50):  # the simulator frees its slot a moment after dropping us
        try:
            c.connect()
            break
        except ConnectionLost:
            time.sleep(0.02)
    assert c.read_did(0x1601, 0xE37B).payload.hex() == "03"


def test_activation_refusal_is_reported(sim):
    sim.activation_code = 0x00
    with pytest.raises(client.ActivationRefused):
        DoIP("127.0.0.1", sim.port).connect()


def test_garbage_framing_is_connection_lost(sim, c):
    c.buf = b"\x00\x00\x80\x01\x00\x00\x00\x00"
    with pytest.raises(ConnectionLost, match="framing"):
        c.read_did(0x1601, 0xE37B)
    assert c.sock is None


# -- blocklist (module, DID) -------------------------------------------------
def test_blocked_read_is_refused_on_its_module_and_on_functional_targets(sim, c):
    with pytest.raises(client.BlockedRead, match="1301:EE13"):
        c.read_did(0x1301, 0xEE13)
    for functional in (0x1FFF, 0xE400):
        with pytest.raises(client.BlockedRead):
            c.request_all(functional, b"\x22\xee\x13", window=0.1)
    assert sim.seen == []


def test_blocked_read_is_a_read_only_violation():
    assert issubclass(client.BlockedRead, ReadOnlyViolation)


def test_same_did_on_another_module_is_allowed(sim, c):
    sim.set(0x1635, 0xEE13, "00d46d97")
    assert c.read_did(0x1635, 0xEE13).status == "ok"
    assert client.blocked_reason(0x1635, 0xEE13) is None
    assert client.blocked_reason(0x1301, 0xEE12) is None


def test_multi_did_read_including_a_blocked_did_is_refused(sim, c):
    # multi=True, so the length check passes and the block check itself must refuse it, before the socket
    with pytest.raises(client.BlockedRead, match="1301:EE13"):
        c.read_dids(0x1301, [0xEE12, 0xEE13])
    with pytest.raises(client.BlockedRead):
        c.request(0x1301, bytes.fromhex("22ee12ee13"), multi=True)
    assert sim.seen == []


def test_multi_did_read_including_a_caution_did_needs_allow_caution(sim, c):
    assert client.caution_reason(0x1601, 0xD928), "test assumes 1601:D928 is a caution read in catalogue/hazards.yaml"
    with pytest.raises(client.CautionedRead, match="1601:D928"):
        c.read_dids(0x1601, [0xE37B, 0xD928])
    assert sim.seen == []


def test_read_dids_lists_every_did_of_a_read():
    assert client.read_dids(bytes.fromhex("22ee12ee13")) == [0xEE12, 0xEE13]
    assert client.read_dids(bytes.fromhex("22e37b")) == [0xE37B]
    assert client.read_dids(bytes.fromhex("3e00")) == []


@pytest.mark.parametrize("target", [0x1FFF, 0xE400, 0xE401, 0xE000, 0xEFFF])
def test_blocked_did_is_refused_on_any_functional_address(target):
    assert client.blocked_reason(target, 0xEE13)
    assert client.blocked_reason(0xF000, 0xEE13) is None


def test_pending_cap_turns_a_stuck_ecu_into_a_timeout(sim, c):
    sim.pending.add((0x1601, 0xE37B))
    sim.pending_count[(0x1601, 0xE37B)] = 50
    start = time.monotonic()
    r = c.read_did(0x1601, 0xE37B, timeout=0.2)
    assert r.status == "timeout" and "response-pending" in r.note
    assert time.monotonic() - start < 2.0


def test_multi_did_read_is_one_request_and_needs_the_flag(sim, c):
    r = c.read_dids(0x1601, [0xE37B, 0x2B15])
    assert r.status == "ok" and r.data[1:3] == b"\xe3\x7b"
    sent = [uds for tgt, uds in sim.seen if tgt == 0x1601 and uds[:1] == b"\x22"]
    assert sent == [b"\x22\xe3\x7b\x2b\x15"]
    with pytest.raises(ReadOnlyViolation):
        c.request(0x1601, b"\x22\xe3\x7b\x2b\x15")  # multi is opt-in, not implicit

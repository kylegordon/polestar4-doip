import os

import pytest

from p4doip.client import blocked_reason
from p4doip.sim import SimGateway

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Values recorded from the car on 2026-11-10 (identity fields left out).
CAR = {
    "1001": {"DD0A": "0d"},
    "1601": {"E37B": "03", "2B1A": "00000100", "2B15": "00", "2B20": "0000056b", "2B24": "00010000"},
    "1635": {"4801": "77a7", "49EF": "01", "DA19": "ff03a6cf37"},
    "1A01": {"42F2": "42", "421B": "00000000", "4223": "000000", "DD0A": "0d"},
    "1316": {"F18C": "02160038", "DD0A": "0d"},
    "1317": {"F18C": "02160045"},
    "1251": {"F18C": "00000001"},
}


@pytest.fixture
def sim():
    with SimGateway({t: dict(d) for t, d in CAR.items()}) as s:
        yield s
        # Suite-wide invariant: whatever a test did, only reads ever reached the gateway.
        assert {uds[0] for _, uds in s.seen} <= {0x22, 0x19, 0x3E}, "a non-read UDS request was sent"
        # ...and no blocked read reached the gateway.
        sent = [(tgt, uds) for tgt, uds in s.seen if uds[:1] == b"\x22" and len(uds) == 3]
        assert not [x for x in sent if blocked_reason(x[0], int.from_bytes(x[1][1:3], "big"))], "a blocked read was sent"


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A scratch project root so commands can write runs/ and session-log.md."""
    monkeypatch.setenv("P4_ROOT", str(tmp_path))
    os.symlink(os.path.join(REPO, "catalogue"), tmp_path / "catalogue")
    return tmp_path


@pytest.fixture
def p4(sim, root, capsys):
    """Run a p4 command against the simulator; returns its stdout."""
    from p4doip.cli import main

    def run(*argv):
        main(["--host", "127.0.0.1", "--port", str(sim.port), "--retries", "5", "--retry-wait", "0.05", *argv])
        return capsys.readouterr().out
    return run

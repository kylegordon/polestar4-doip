"""Read-only DoIP/UDS client.

Only UDS services in ALLOWED_SIDS can be sent. There is no flag to widen that:
anything that writes, runs routines, changes session or unlocks security is out
of scope for this tool. Every diagnostic send goes through _send_diag, which
calls check_read_only first.
"""
import socket
import struct
import time
from dataclasses import dataclass

ALLOWED_SIDS = {0x22: "ReadDataByIdentifier", 0x19: "ReadDTCInformation", 0x3E: "TesterPresent"}
PORT = 13400
NACK_UNKNOWN_TARGET = 0x03

# Reads that are harmless in UDS terms but upset a module on this car. Keyed on (module, DID): the same
# DID can be a normal signal on another module (1635:EE13 is the HV discharge counter). Functional
# targets reach every module, so a blocked DID is refused there too.
BLOCKED_READS = {
    (0x1301, 0xEE13): "knocks the Mobileye driver assistance ECU (1301) off the network for about a minute "
                      "(seen twice, parked, 2026-11-11)",
}
FUNCTIONAL_TARGETS = {0x1FFF, 0xE400}  # seen on this car (1FFF works, E400 is rejected)


def is_functional(target: int) -> bool:
    """True for addresses that may reach more than one module: 1FFF here, and the ISO 13400 non-physical
    range E000-EFFF (legislated and manufacturer functional groups)."""
    return target in FUNCTIONAL_TARGETS or 0xE000 <= target <= 0xEFFF


class ReadOnlyViolation(Exception):
    """Raised before anything is sent if a request is not a read."""


class BlockedRead(ReadOnlyViolation):
    """Raised before anything is sent if a read is on BLOCKED_READS."""


def blocked_reason(target: int, did: int) -> str | None:
    """Why reading `did` from `target` is refused, or None if it is allowed."""
    for (module, bad), why in BLOCKED_READS.items():
        if did == bad and (target == module or is_functional(target)):
            return "%04X:%04X %s" % (module, bad, why)
    return None


def check_not_blocked(target: int, uds: bytes) -> None:
    if uds[:1] == b"\x22" and len(uds) == 3:
        why = blocked_reason(target, struct.unpack(">H", uds[1:3])[0])
        if why:
            raise BlockedRead("refusing to read %04X:%s: %s" % (target, uds[1:3].hex().upper(), why))


class ConnectionLost(Exception):
    """The gateway closed or reset the connection (another tester connected?). The socket is already closed."""


class ActivationRefused(Exception):
    pass


@dataclass
class Result:
    status: str          # ok | nrc | nack | timeout
    data: bytes = b""    # full positive UDS response (status ok)
    code: int | None = None  # NRC (status nrc) or DoIP NACK code (status nack)

    @property
    def payload(self) -> bytes:
        """Positive 0x22 response without the 62 + DID echo."""
        return self.data[3:] if self.data[:1] == b"\x62" else self.data[1:]

    def text(self) -> str:
        if self.status == "ok":
            return "OK " + self.payload.hex()
        if self.status == "nrc":
            return "NRC %02X" % self.code
        if self.status == "nack":
            return "NACK %02X" % self.code
        return "no response"


def check_read_only(uds: bytes) -> None:
    if not uds or uds[0] not in ALLOWED_SIDS:
        raise ReadOnlyViolation(
            "UDS service 0x%s is not a read; refusing to send" % (uds[:1].hex() or "??"))
    if uds[0] == 0x22 and len(uds) != 3:
        raise ReadOnlyViolation("0x22 must carry exactly one DID, got %s" % uds.hex())
    if uds[0] == 0x19 and len(uds) < 2:
        raise ReadOnlyViolation("0x19 needs a sub-function")


def frame(ptype: int, payload: bytes) -> bytes:
    return struct.pack(">BBHI", 0x02, 0xFD, ptype, len(payload)) + payload


class DoIP:
    def __init__(self, host: str, port: int = PORT, tester: int = 0x0E80, connect_timeout: float = 5.0):
        self.host, self.port, self.tester, self.connect_timeout = host, port, tester, connect_timeout
        self.sock = None
        self.buf = b""
        self.gateway = None
        self._desync = False  # a request timed out: its answer may still arrive

    # -- connection -------------------------------------------------------
    def connect(self) -> "DoIP":
        self.close()
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError as e:
            self.sock = None
            raise ConnectionLost("connect failed: %s" % e) from e
        self.buf = b""
        self._desync = False
        self._send(frame(0x0005, struct.pack(">HB", self.tester, 0x00) + b"\x00" * 4))
        got = self._recv(time.monotonic() + self.connect_timeout)
        if got is None:
            self.close()
            raise ConnectionLost("no routing activation response")
        ptype, p = got
        if ptype != 0x0006 or len(p) < 5 or p[4] != 0x10:
            self.close()
            raise ActivationRefused("routing activation refused: type %04X payload %s" % (ptype, p.hex()))
        self.gateway = struct.unpack(">H", p[2:4])[0]
        return self

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    def _lost(self, why: str, cause: Exception | None = None):
        self.close()  # never hold the gateway's single tester slot with a dead session
        raise ConnectionLost(why) from cause

    # -- framing ----------------------------------------------------------
    def _send(self, data: bytes) -> None:
        if self.sock is None:
            raise ConnectionLost("not connected")
        try:
            self.sock.sendall(data)
        except OSError as e:
            self._lost("send failed: %s" % e, e)

    def _recv(self, deadline: float):
        """Return (payload_type, payload) or None at the deadline."""
        while True:
            if len(self.buf) >= 8:
                if self.buf[0] ^ self.buf[1] != 0xFF:
                    self._lost("lost DoIP framing: %s" % self.buf[:8].hex())
                ptype, ln = struct.unpack(">HI", self.buf[2:8])
                if len(self.buf) >= 8 + ln:
                    payload, self.buf = self.buf[8:8 + ln], self.buf[8 + ln:]
                    if ptype == 0x0007:  # alive check: answer and carry on
                        self._send(frame(0x0008, struct.pack(">H", self.tester)))
                        continue
                    return ptype, payload
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            try:
                self.sock.settimeout(left)
                chunk = self.sock.recv(65536)
            except socket.timeout:
                return None
            except (OSError, AttributeError) as e:
                self._lost("receive failed: %s" % e, e)
            if not chunk:
                self._lost("gateway closed the connection")
            self.buf += chunk

    def _drain(self, quiet: float = 0.25, limit: float = 2.0) -> None:
        """After a timeout, swallow late answers so they are not mistaken for the next request's."""
        end = time.monotonic() + limit
        while time.monotonic() < end and self._recv(min(end, time.monotonic() + quiet)) is not None:
            pass
        self._desync = False

    def _send_diag(self, target: int, uds: bytes) -> None:
        check_read_only(uds)
        check_not_blocked(target, uds)
        if self.sock is None:
            raise ConnectionLost("not connected")
        if self._desync:
            self._drain()
        self._send(frame(0x8001, struct.pack(">HH", self.tester, target) + uds))

    @staticmethod
    def _matches(uds: bytes, resp: bytes) -> str | None:
        """Classify a UDS response to our request: ok | nrc | pending | None (not ours)."""
        if not resp:
            return None
        if resp[0] == 0x7F:
            if len(resp) >= 3 and resp[1] == uds[0]:
                return "pending" if resp[2] == 0x78 else "nrc"
            return None
        if resp[0] != uds[0] + 0x40:
            return None
        if uds[0] == 0x22 and resp[1:3] != uds[1:3]:
            return None  # reply for another DID
        if uds[0] == 0x19 and resp[1:2] != uds[1:2]:
            return None  # reply for another sub-function
        return "ok"

    # -- requests ---------------------------------------------------------
    def request(self, target: int, uds: bytes, timeout: float = 1.0) -> Result:
        """Physical request: one answer expected from `target`."""
        self._send_diag(target, uds)
        deadline = time.monotonic() + timeout
        while True:
            got = self._recv(deadline)
            if got is None:
                self._desync = True
                return Result("timeout")
            ptype, p = got
            if len(p) < 5 or struct.unpack(">H", p[:2])[0] != target:
                continue  # ACK/NACK/answer about some other address
            if ptype == 0x8003:
                return Result("nack", code=p[4])
            if ptype == 0x8001:
                kind = self._matches(uds, p[4:])
                if kind == "pending":
                    deadline = time.monotonic() + 5.0
                elif kind == "nrc":
                    return Result("nrc", code=p[6])
                elif kind == "ok":
                    return Result("ok", data=p[4:])
            # 0x8002 positive ACKs and anything else: keep waiting

    def request_all(self, target: int, uds: bytes, window: float = 3.0) -> dict[int, Result]:
        """Functional request (e.g. target 0x1FFF): collect every module's answer."""
        self._send_diag(target, uds)
        out: dict[int, Result] = {}
        deadline = time.monotonic() + window
        while True:
            got = self._recv(deadline)
            if got is None:
                self._desync = True  # stragglers may still be on their way
                return out
            ptype, p = got
            if len(p) < 5:
                continue
            src = struct.unpack(">H", p[:2])[0]
            if ptype == 0x8003:
                out[src] = Result("nack", code=p[4])
            elif ptype == 0x8001:
                kind = self._matches(uds, p[4:])
                if kind == "pending":
                    deadline = max(deadline, time.monotonic() + 5.0)
                elif kind == "nrc":
                    out.setdefault(src, Result("nrc", code=p[6]))
                elif kind == "ok":
                    out[src] = Result("ok", data=p[4:])

    def read_did(self, target: int, did: int, timeout: float = 1.0) -> Result:
        return self.request(target, b"\x22" + struct.pack(">H", did), timeout)

    def tester_present(self, target: int, timeout: float = 0.5) -> Result:
        return self.request(target, b"\x3e\x00", timeout)

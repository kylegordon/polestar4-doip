"""Fake DoIP gateway for offline tests, built from recorded reads.

Behaviour copied from what the car did on 2026-11-10:
- routing activation answers 0006 with code 0x10 from gateway 0x1001
- unknown target address -> DoIP NACK 0x03
- unknown DID -> NRC 0x31; any non-read service -> NRC 0x11 (and is recorded)
- only one tester connection at a time: a second one is dropped

Knobs (pending, stale, delay, ignore, silent, knockout, knockout_drop, nack_dids, script, drop_after, activation_code,
nack_code, alive_check_next) let tests reproduce awkward timing a real gateway can show.
"""
import socket
import struct
import threading

from .client import frame


class SimGateway:
    def __init__(self, modules: dict[str, dict[str, str]], gateway: int = 0x1001):
        # modules: {"1601": {"E37B": "03", ...}}
        self.modules = {int(t, 16): {int(d, 16): bytes.fromhex(v) for d, v in dids.items()}
                        for t, dids in modules.items()}
        self.gateway = gateway
        self.pending: set[tuple[int, int]] = set()   # answer 7F 22 78 first
        self.pending_count: dict[tuple[int, int], int] = {}  # ... this many times (default 1)
        self.nrc_script: dict[tuple[int, int], list[int]] = {}  # negative responses served in order
        self.supported: dict[int, list[bytes]] = {}  # 19 0A: 4-byte DTC records per module (default NRC 12)
        self.freeze: dict[tuple[int, int], bytes] = {}  # (module, DTC) -> 19 04 extra bytes
        self.stale: set[tuple[int, int]] = set()     # send an unrelated positive reply first
        self.delay: dict[tuple[int, int], float] = {}  # final answer arrives this many seconds late
        self.ignore: set[tuple[int, int]] = set()    # DIDs a live module never answers
        self.silent: set[int] = set()                # modules that never answer
        self.knockout: set[tuple[int, int]] = set()  # reading this DID silences its module (like 1301:EE13)
        self.knockout_drop: set[tuple[int, int]] = set()  # ...and also closes the tester's connection
        self.nack_dids: set[tuple[int, int]] = set()  # the gateway NACKs a read of this DID
        self.script: dict[tuple[int, int], list[str]] = {}  # values served in order; the last one repeats
        self.seen: list[tuple[int, bytes]] = []      # every UDS request received
        self.frames: list[int] = []                  # every DoIP payload type received
        self.alive_check_next = False
        self.drop_after: int | None = None           # close the connection after this many more requests
        self.activation_code = 0x10
        self.nack_code = 0x03
        self.nack_source: int | None = None          # report NACKs as coming from this address instead
        self._busy = threading.Lock()
        self._srv = socket.socket()
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(4)
        self.port = self._srv.getsockname()[1]
        self._stop = False
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    def set(self, target: int, did: int, value: str) -> None:
        self.modules[target][did] = bytes.fromhex(value)

    def close(self) -> None:
        self._stop = True
        try:
            self._srv.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------------
    def _accept(self):
        while not self._stop:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            if not self._busy.acquire(blocking=False):
                conn.close()  # one tester at a time
                continue
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        buf = b""
        lock = threading.Lock()

        def send(data):
            try:
                with lock:
                    conn.sendall(data)
            except OSError:
                pass

        try:
            while True:
                while len(buf) < 8 or len(buf) < 8 + struct.unpack(">I", buf[4:8])[0]:
                    chunk = conn.recv(65536)
                    if not chunk:
                        return
                    buf += chunk
                ptype, ln = struct.unpack(">HI", buf[2:8])
                payload, buf = buf[8:8 + ln], buf[8 + ln:]
                self.frames.append(ptype)
                if ptype == 0x8001 and payload[4:5] == b"\x22" and len(payload) >= 7:
                    key = (struct.unpack(">H", payload[2:4])[0], struct.unpack(">H", payload[5:7])[0])
                    if key in self.knockout_drop:
                        self.seen.append((key[0], payload[4:]))
                        self.silent.add(key[0])
                        return
                if ptype == 0x8001 and self.drop_after is not None:
                    if self.drop_after == 0:
                        self.drop_after = None
                        return
                    self.drop_after -= 1
                for wait, out in self._handle(ptype, payload):
                    if wait:
                        threading.Timer(wait, send, args=(out,)).start()
                    else:
                        send(out)
        except OSError:
            pass
        finally:
            conn.close()
            self._busy.release()

    def _handle(self, ptype, p):
        if ptype == 0x0005:
            tester = p[:2]
            return [(0, frame(0x0006, tester + struct.pack(">HB", self.gateway, self.activation_code) + b"\x00" * 4))]
        if ptype != 0x8001:
            return []
        tester, target = struct.unpack(">HH", p[:4])
        uds = p[4:]
        self.seen.append((target, uds))
        out = []
        if self.alive_check_next:
            self.alive_check_next = False
            out.append((0, frame(0x0007, b"")))
        if target == 0x1FFF:
            out.append((0, frame(0x8002, struct.pack(">HHB", target, tester, 0))))
            for addr in sorted(self.modules):
                if addr not in self.silent:
                    r = self._uds(addr, uds)
                    if r[:1] != b"\x7f":  # functional: negative answers are suppressed
                        out.append((0, frame(0x8001, struct.pack(">HH", addr, tester) + r)))
            return out
        if target not in self.modules:
            src = target if self.nack_source is None else self.nack_source
            return out + [(0, frame(0x8003, struct.pack(">HHB", src, tester, self.nack_code)))]
        out.append((0, frame(0x8002, struct.pack(">HHB", target, tester, 0))))
        if target in self.silent:
            return out
        key = (target, struct.unpack(">H", uds[1:3])[0]) if uds[:1] == b"\x22" and len(uds) >= 3 else None
        if key in self.nack_dids:
            return out[:-1] + [(0, frame(0x8003, struct.pack(">HHB", target, tester, self.nack_code)))]
        if key in self.knockout:
            self.silent.add(target)
            return out
        if key in self.ignore:
            return out
        if key in self.stale:
            out.append((0, frame(0x8001, struct.pack(">HH", target, tester) + b"\x62\xff\xff\xaa")))
        if key in self.pending:
            for _ in range(self.pending_count.get(key, 1)):
                out.append((0, frame(0x8001, struct.pack(">HH", target, tester) + b"\x7f\x22\x78")))
        out.append((self.delay.get(key, 0), frame(0x8001, struct.pack(">HH", target, tester) + self._uds(target, uds))))
        return out

    def _uds(self, addr, uds):
        sid = uds[0]
        if sid == 0x3E:
            return b"\x7e\x00"
        if sid == 0x22 and len(uds) > 3:
            out = b"\x62"
            for i in range(1, len(uds) - 1, 2):
                did = struct.unpack(">H", uds[i:i + 2])[0]
                val = self.modules[addr].get(did)
                if val is None:
                    return b"\x7f\x22\x31"  # one unknown DID fails the whole request
                out += uds[i:i + 2] + val
            return out
        if sid == 0x22 and len(uds) >= 3:
            did = struct.unpack(">H", uds[1:3])[0]
            nrcs = self.nrc_script.get((addr, did))
            if nrcs:
                code = nrcs.pop(0)
                if not nrcs:
                    del self.nrc_script[(addr, did)]
                return b"\x7f\x22" + bytes([code])
            val = self.modules[addr].get(did)
            seq = self.script.get((addr, did))
            if seq:
                val = bytes.fromhex(seq.pop(0) if len(seq) > 1 else seq[0])
            return b"\x62" + uds[1:3] + val if val is not None else b"\x7f\x22\x31"
        if sid == 0x19 and uds[1:2] == b"\x02":
            return b"\x59\x02\xff" + bytes.fromhex("d1234508")  # one stored DTC
        if sid == 0x19 and uds[1:2] == b"\x0a":
            recs = self.supported.get(addr)
            if recs is not None:
                return b"\x59\x0a\xff" + b"".join(recs)
            return b"\x7f\x19\x12"
        if sid == 0x19 and uds[1:2] == b"\x04" and len(uds) >= 5:
            dtc = int.from_bytes(uds[2:5], "big")
            extra = self.freeze.get((addr, dtc))
            if extra is not None:
                return b"\x59\x04" + uds[2:5] + b"\x08\x01\x01" + extra
            return b"\x7f\x19\x31"
        if sid == 0x19:
            return b"\x7f\x19\x12"
        return bytes([0x7F, sid, 0x11])

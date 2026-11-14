"""Offline: decode DoIP/UDS from pcap files (classic pcap, Ethernet). Read-only analysis.
Usage: pcap_uds.py out.tsv file1.pcap [file2.pcap ...]"""
import collections
import struct
import sys

SVC = {0x10: "DiagSessionControl", 0x11: "ECUReset", 0x14: "ClearDTC", 0x19: "ReadDTC",
       0x22: "ReadDID", 0x23: "ReadMemory", 0x27: "SecurityAccess", 0x28: "CommControl",
       0x2E: "WriteDID", 0x2F: "IOControl", 0x31: "RoutineControl", 0x34: "RequestDownload",
       0x3E: "TesterPresent", 0x85: "ControlDTCSetting"}


def packets(path):
    with open(path, "rb") as f:
        gh = f.read(24)
        if len(gh) < 24:
            return
        endian = "<" if gh[:4] == b"\xd4\xc3\xb2\xa1" else ">"
        while True:
            h = f.read(16)
            if len(h) < 16:
                return
            ts, tu, incl, _ = struct.unpack(endian + "IIII", h)
            yield ts + tu / 1e6, f.read(incl)


streams = collections.defaultdict(lambda: {"next": None, "buf": b""})
rows = []


def handle(ts, p):
    ptype, ln = struct.unpack(">HI", p[2:8])
    pl = p[8:8 + ln]
    if ptype == 0x8001:
        src, tgt = struct.unpack(">HH", pl[:4])
        rows.append((ts, src, tgt, pl[4:]))
    elif ptype in (0x0005, 0x0006):
        rows.append((ts, -1, -1, b"DOIP%04x:" % ptype + pl.hex().encode()))


for path in sys.argv[2:]:
    for ts, f in packets(path):
        if len(f) < 34 or f[12:14] != b"\x08\x00" or f[23] != 6:
            continue
        ihl = (f[14] & 0x0F) * 4
        t = 14 + ihl
        sp, dp, seq = struct.unpack(">HHI", f[t:t + 8])
        if 13400 not in (sp, dp):
            continue
        doff = (f[t + 12] >> 4) * 4
        tot = struct.unpack(">H", f[16:18])[0]
        data = f[t + doff:14 + tot]
        st = streams[(f[26:30], sp, f[30:34], dp)]
        if f[t + 13] & 0x02:  # SYN
            st["next"], st["buf"] = seq + 1, b""
            continue
        if not data:
            continue
        if st["next"] is None:
            st["next"] = seq
        if seq != st["next"]:
            if (seq - st["next"]) & 0x80000000:
                continue  # retransmission
            st["buf"] = b""  # gap: resync
        st["next"] = (seq + len(data)) & 0xFFFFFFFF
        b = st["buf"] + data
        while len(b) >= 8 and b[0] == 0x02 and b[1] == 0xFD:
            ln = struct.unpack(">I", b[4:8])[0]
            if len(b) < 8 + ln:
                break
            handle(ts, b[:8 + ln])
            b = b[8 + ln:]
        st["buf"] = b if (len(b) < 8 or b[:2] == b"\x02\xfd") else b""

with open(sys.argv[1], "w") as o:
    o.write("time\tsrc\ttgt\tservice\tuds_hex\n")
    for ts, src, tgt, u in rows:
        if src < 0:
            o.write("%.3f\t-\t-\tDoIP\t%s\n" % (ts, u.decode()))
            continue
        sid = u[0] if u else 0
        name = "NRC" if sid == 0x7F else SVC.get(sid & 0xBF, "0x%02X" % sid) + ("+" if sid & 0x40 else "")
        o.write("%.3f\t%04X\t%04X\t%s\t%s\n" % (ts, src, tgt, name, u.hex()))

# summary
req = collections.Counter()
for ts, src, tgt, u in rows:
    if src == 0x0E80 and u:
        key = (tgt, u[0], u[1:3].hex() if u[0] in (0x22, 0x31, 0x2E, 0x2F) else u[1:2].hex())
        req[key] += 1
print("requests by tester 0x0E80: target service sub/DID count")
for (tgt, sid, sub), n in sorted(req.items()):
    print("%04X %-20s %-6s %d" % (tgt, SVC.get(sid, "0x%02X" % sid), sub, n))

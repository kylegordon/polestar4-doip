import os

import pytest
import yaml

from p4doip import decode

from conftest import REPO

SIGNALS = decode.load(os.path.join(REPO, "catalogue", "signals.yaml"))
with open(os.path.join(REPO, "catalogue", "modules.yaml")) as f:
    MODULES = yaml.safe_load(f)

EXAMPLES = [(s, ex) for s in SIGNALS for ex in s.get("examples", [])]


def test_every_signal_has_an_example():
    assert [s["id"] for s in SIGNALS if not s.get("examples")] == []


@pytest.mark.parametrize("sig,ex", EXAMPLES, ids=["%s:%s" % (s["id"], ex["raw"]) for s, ex in EXAMPLES])
def test_example_decodes_to_recorded_value(sig, ex):
    got = decode.decode(sig, bytes.fromhex(ex["raw"]))
    if isinstance(ex["value"], float):
        assert got == pytest.approx(ex["value"], abs=1e-6)
    else:
        assert got == ex["value"]


def test_signal_ids_are_unique():
    ids = [s["id"] for s in SIGNALS]
    assert len(ids) == len(set(ids))


def test_signal_modules_exist_in_module_catalogue():
    known = {m["addr"] for m in MODULES}
    used = {mod for s in SIGNALS for mod in s["module"].split(",")}
    assert used - known == set()


def test_module_addresses_are_unique_quoted_hex():
    addrs = [m["addr"] for m in MODULES]
    assert all(isinstance(a, str) and len(a) == 4 and int(a, 16) for a in addrs)
    assert len(addrs) == len(set(addrs))
    assert {m["status"] for m in MODULES} <= {"confirmed", "unverified", "unknown"}


def test_modules_with_confirmed_signals_are_marked_confirmed():
    status = {m["addr"]: m["status"] for m in MODULES}
    for s in SIGNALS:
        if s["confidence"] == "C":
            for mod in s["module"].split(","):
                assert status[mod] == "confirmed", "%s has a confirmed signal (%s)" % (mod, s["id"])


def test_short_payload_is_an_error_not_a_wrong_value():
    sig = next(s for s in SIGNALS if s["id"] == "tailgate_position")
    with pytest.raises(ValueError):
        decode.decode(sig, bytes.fromhex("01"))


def test_unknown_enum_value_is_reported_not_guessed():
    sig = next(s for s in SIGNALS if s["id"] == "epb_state")
    assert decode.decode(sig, bytes.fromhex("07")) == "unknown(07)"


def test_ascii_hex_encoding_decodes_the_software_release():
    # 1001 D0D0 holds "4.2.11" as ASCII hex digits written in ASCII (DISCOVERIES.md, docs/findings.md).
    sig = {"id": "release", "encoding": "ascii-hex"}
    assert decode.decode(sig, bytes.fromhex("333432653332326533313331")) == "4.2.11"


def test_ascii_hex_encoding_applies_to_a_byte_slice():
    sig = {"id": "release", "offset": 2, "len": 12, "encoding": "ascii-hex"}
    assert decode.decode(sig, bytes.fromhex("ffff" + "333432653332326533313331" + "00")) == "4.2.11"


def test_ascii_hex_encoding_bad_input_is_an_error_not_a_guess():
    sig = {"id": "release", "encoding": "ascii-hex"}
    with pytest.raises(ValueError):
        decode.decode(sig, bytes.fromhex("2e2e"))  # ".." is not a hex digit


def test_repeat_returns_one_value_per_element():
    # 1635 DA31 shape: 130 x u16 cell-group voltages in mV; valid count is in sibling EE19, so a fixed count.
    sig = {"id": "cell_group_mv", "repeat": {"count": 3, "len": 2}}
    assert decode.decode(sig, bytes.fromhex("0ea30fa0ffff")) == [3747, 4000, 65535]


def test_repeat_scales_each_element():
    # 1635 EE83 shape: 30 temperatures, 0.01 C with a -50 offset; valid count is in sibling EE20.
    sig = {"id": "pack_temps", "repeat": {"count": 3, "len": 2, "scale": 0.01, "add": -50}}
    assert decode.decode(sig, bytes.fromhex("16440fa01684")) == [pytest.approx(7.0), pytest.approx(-10.0), pytest.approx(7.64)]


def test_repeat_within_a_padded_payload():
    # 1BB3/1BB4 7022 shape: 32 segment bytes (two rows of 16) among ff padding.
    sig = {"id": "matrix_segments", "offset": 1, "len": 4, "repeat": {"count": 4, "len": 1}}
    assert decode.decode(sig, bytes.fromhex("10000f5000ff")) == [0, 15, 80, 0]


def test_repeat_with_raw_encoding_returns_hex_entries():
    # 1A12 D938 shape: rolling log, newest first, 10-byte entries whose field layout is not yet confirmed.
    sig = {"id": "window_log", "repeat": {"count": 2, "len": 10, "encoding": "raw"}}
    assert decode.decode(sig, bytes.fromhex("aa" * 10 + "bb" * 10)) == ["aa" * 10, "bb" * 10]


def test_repeat_short_payload_is_an_error_not_a_wrong_value():
    sig = {"id": "cell_group_mv", "repeat": {"count": 3, "len": 2}}
    with pytest.raises(ValueError):
        decode.decode(sig, bytes.fromhex("0ea3"))


def test_unquoted_hex_in_catalogue_is_rejected(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("- {id: x, module: 1635, did: \"4801\", name: n, confidence: C}\n")
    with pytest.raises(ValueError, match="quoted hex"):
        decode.load(str(p))


# -- decoder extensions ------------------------------------------------------
def test_ascii_encoding():
    sig = {"id": "part", "encoding": "ascii"}
    assert decode.decode(sig, b"P3145678\x00\x00") == "P3145678"


def test_utf16_encodings():
    assert decode.decode({"id": "u", "encoding": "utf-16le"}, "SOFTWARE".encode("utf-16-le")) == "SOFTWARE"
    assert decode.decode({"id": "u", "encoding": "utf-16be"}, "SOFTWARE".encode("utf-16-be")) == "SOFTWARE"


def test_utf8_encoding():
    assert decode.decode({"id": "u", "encoding": "utf-8"}, "Batterie".encode()) == "Batterie"


def test_little_endian_integer():
    sig = {"id": "v", "type": "u", "len": 2, "endian": "little", "scale": 0.1}
    assert decode.decode(sig, bytes.fromhex("e803")) == pytest.approx(100.0)


def test_repeat_count_from_a_sibling_did():
    sig = {"id": "cells", "repeat": {"len": 2,
                                     "count_from": {"did": "EE19", "offset": 0, "len": 2, "max": 4}}}
    context = {0xEE19: bytes.fromhex("0002")}
    assert decode.decode(sig, bytes.fromhex("0ea30fa0ffffffff"), context) == [3747, 4000]


def test_repeat_count_from_is_clamped_and_needs_context():
    sig = {"id": "cells", "repeat": {"len": 2, "count_from": {"did": "EE19", "max": 2}}}
    assert decode.decode(sig, bytes.fromhex("000100020003"), {0xEE19: bytes.fromhex("0009")}) == [1, 2]
    with pytest.raises(ValueError, match="context"):
        decode.decode(sig, bytes.fromhex("00010002"), None)
    with pytest.raises(ValueError, match="missing"):
        decode.decode(sig, bytes.fromhex("00010002"), {})


def test_describe_passes_the_context():
    sig = {"id": "cells", "repeat": {"len": 2, "count_from": {"did": "EE19"}}}
    out = decode.describe([sig], bytes.fromhex("00010002"), {0xEE19: bytes.fromhex("0001")})
    assert out == "cells=[1]"


def test_dtc_registry_loader(tmp_path):
    p = tmp_path / "dtc.yaml"
    p.write_text('- {dtc: "D12345", name: "example", module: "1601"}\n')
    reg = decode.load_dtcs(str(p))
    assert reg[0xD12345]["name"] == "example"


def test_dtc_registry_rejects_bad_code(tmp_path):
    p = tmp_path / "dtc.yaml"
    p.write_text('- {dtc: "123", name: "short"}\n')
    with pytest.raises(ValueError, match="6-hex"):
        decode.load_dtcs(str(p))

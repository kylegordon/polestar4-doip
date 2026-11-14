"""privacy.py: one masking and text-extraction implementation for CLI, web and tests."""
import pytest

from p4doip import privacy


def test_masked_dids_are_the_registry_contract():
    assert privacy.MASKED_DIDS == {0xF190, 0xF18C, 0xF192, 0xF198}


def test_stored_value_masks_every_identifier_did():
    assert privacy.stored_value(0xF190, b"VIN") == "000000"
    assert privacy.stored_value(0xF18C, b"abcd") == "00000000"
    assert privacy.stored_value(0xE37B, b"\x03") == "03"


@pytest.mark.parametrize("text,hidden", [
    ("VIN YSM" + "4ZPAA0TF000000", "[VIN hidden]"),
    ("mail a.b" + "@example.com", "[email hidden]"),
    ("tel +" + "44 7700 900123", "[phone hidden]"),
    ("id 89" + "441234567890123456", "[number hidden]"),
    ("no identifiers here", "no identifiers here"),
])
def test_mask(text, hidden):
    assert hidden in privacy.mask(text)


def test_readable_text_keeps_the_whole_payload_contract():
    assert privacy.readable_text(b"BOOT v1.2.3".hex()) == "BOOT v1.2.3"
    assert privacy.readable_text(b"\x01\x02\x03\x04\x05".hex()) == ""


def test_runs_find_text_after_a_binary_header():
    raw = bytes.fromhex("deadbeefcafebabe") + b"HELLO" + b"\x00\x01"
    assert privacy.readable_runs(raw.hex()) == ["HELLO"]


def test_runs_find_text_before_a_binary_tail():
    raw = b"HELLO" + bytes.fromhex("cafebabe")
    assert privacy.readable_runs(raw.hex()) == ["HELLO"]


def test_runs_find_utf16le_and_be():
    le = "SOFTWARE".encode("utf-16-le") + b"\x00\x00"
    be = "P417_EU".encode("utf-16-be") + b"\x00\x00"
    assert "SOFTWARE" in privacy.readable_runs((b"\x01\x02" + le).hex())
    assert "P417_EU" in privacy.readable_runs((b"\x01\x02" + be).hex())


def test_runs_find_hexwrapped_text_inside_a_payload():
    inner = b"RELEASE 4.2.11".hex().encode()  # ASCII hex digits inside a binary record
    raw = bytes.fromhex("aabbccdd") + inner + bytes.fromhex("eeff")
    assert "RELEASE 4.2.11" in privacy.readable_runs(raw.hex())


def test_runs_mask_identifiers_and_dedupe():
    vin = "YSM" + "4ZPAA0TF000000"
    raw = b"SW " + vin.encode() + b"\x00\x00" + b"SW " + vin.encode()
    runs = privacy.readable_runs(raw.hex())
    assert runs == ["SW [VIN hidden]"]


def test_text_of_prefers_whole_payload_then_falls_back():
    assert privacy.text_of(b"BOOT v1".hex()) == "BOOT v1"
    raw = bytes.fromhex("deadbeefcafe") + b"EMBEDDED"
    assert privacy.text_of(raw.hex()) == "EMBEDDED"

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


def test_unquoted_hex_in_catalogue_is_rejected(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("- {id: x, module: 1635, did: \"4801\", name: n, confidence: C}\n")
    with pytest.raises(ValueError, match="quoted hex"):
        decode.load(str(p))

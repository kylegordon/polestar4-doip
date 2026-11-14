"""catalogue/hazards.yaml and its enforcement in the client."""
import os

import pytest

from p4doip import hazards
from p4doip.client import CautionedRead, DoIP, caution_reason

from conftest import REPO


@pytest.fixture(autouse=True)
def _fresh_cache():
    hazards.clear_cache()
    yield
    hazards.clear_cache()


def write_hazards(root, text):
    """Write into a real directory: the root fixture's catalogue is a symlink to the repo, and writing
    through it would overwrite catalogue/hazards.yaml in the working tree."""
    d = os.path.join(str(root), "catalogue")
    if os.path.islink(d):
        os.unlink(d)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "hazards.yaml"), "w") as f:
        f.write(text)


def test_repo_hazards_file_is_valid():
    hs = hazards.load(os.path.join(REPO, "catalogue", "hazards.yaml"))
    assert {(h.module, h.did, h.action) for h in hs} >= {(0x1301, 0xEE13, "block"), (0x1601, 0xD928, "caution")}
    assert all(h.why for h in hs)


def test_missing_file_still_blocks_the_builtin(root, monkeypatch):
    monkeypatch.setenv("P4_ROOT", str(root))
    hs = hazards.load()
    assert (0x1301, 0xEE13, "block") in {(h.module, h.did, h.action) for h in hs}


def test_bad_action_is_an_error(root, monkeypatch):
    monkeypatch.setenv("P4_ROOT", str(root))
    write_hazards(root, '- {module: "1601", did: "D928", action: "maybe", why: "x"}\n')
    with pytest.raises(ValueError, match="action"):
        hazards.load()


def test_builtin_block_cannot_be_downgraded(root, monkeypatch):
    monkeypatch.setenv("P4_ROOT", str(root))
    write_hazards(root, '- {module: "1301", did: "EE13", action: caution, why: "x"}\n')
    with pytest.raises(ValueError, match="downgrade"):
        hazards.load()


def test_duplicate_entries_are_an_error(root, monkeypatch):
    monkeypatch.setenv("P4_ROOT", str(root))
    write_hazards(root, '- {module: "1601", did: "D928", action: caution, why: "a"}\n'
                        '- {module: "1601", did: "D928", action: caution, why: "b"}\n')
    with pytest.raises(ValueError, match="duplicates"):
        hazards.load()


def test_caution_applies_to_the_module_and_functional_targets(root, monkeypatch):
    monkeypatch.setenv("P4_ROOT", str(root))
    write_hazards(root, '- {module: "1601", did: "D928", action: caution, why: "wake race"}\n')
    assert caution_reason(0x1601, 0xD928) and caution_reason(0x1FFF, 0xD928)
    assert caution_reason(0x1601, 0xD929) is None and caution_reason(0x1635, 0xD928) is None


def test_client_refuses_a_caution_read_unless_allowed(sim, monkeypatch):
    monkeypatch.setenv("P4_ROOT", REPO)
    hazards.clear_cache()
    with pytest.raises(CautionedRead):
        with DoIP("127.0.0.1", sim.port) as c:
            c.read_did(0x1601, 0xD928)
    with DoIP("127.0.0.1", sim.port, allow_caution=True) as c:
        assert c.read_did(0x1601, 0xD928).status in ("ok", "nrc")

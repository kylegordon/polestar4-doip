"""scripts/prepublish-check.sh must catch identifying content in the index and in history (needs git)."""
import os
import shutil
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
FAKE_VIN = "YSM" + "4ZPAA0TF000000"  # split so this file never holds a whole VIN


def run(repo, *cmd):
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    os.makedirs(tmp_path / "scripts")
    shutil.copy(os.path.join(REPO, "scripts", "prepublish-check.sh"), tmp_path / "scripts")
    run(tmp_path, "git", "init", "-q")
    run(tmp_path, "git", "config", "user.email", "t@example.invalid")
    run(tmp_path, "git", "config", "user.name", "t")
    (tmp_path / "ok.txt").write_text("nothing to see\n")
    run(tmp_path, "git", "add", "-A")
    return tmp_path


def check(repo):
    return run(repo, "sh", "scripts/prepublish-check.sh").returncode


def test_clean_repo_passes(repo):
    assert check(repo) == 0
    run(repo, "git", "commit", "-qm", "clean")
    assert check(repo) == 0


def test_vin_in_index_fails_even_if_removed_from_working_tree(repo):
    (repo / "x.txt").write_text("vin %s\n" % FAKE_VIN)
    run(repo, "git", "add", "x.txt")
    (repo / "x.txt").write_text("clean\n")
    assert check(repo) == 1


def test_vin_in_history_fails_after_deletion(repo):
    (repo / "x.txt").write_text("vin %s\n" % FAKE_VIN)
    run(repo, "git", "add", "x.txt")
    run(repo, "git", "commit", "-qm", "oops")
    run(repo, "git", "rm", "-q", "x.txt")
    run(repo, "git", "commit", "-qm", "remove")
    assert check(repo) == 1


@pytest.mark.parametrize("path", ["runs/2026-11-11/scan-1601.jsonl", "local/notes.md", "captures/a.pcap", "sub/runs/x.jsonl", "NEXT.md"])
def test_private_paths_fail(repo, path):
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text("x\n")
    run(repo, "git", "add", "-f", path)
    assert check(repo) == 1


@pytest.mark.parametrize("text", [  # split so this file itself passes the check
    "iccid 8988" + "23900000" + "00000000", "imei 3512345" + "67890123", "+44 20" + " 0000 0000", "/ho" + "me/someone/x",
    "en" + "x001122334455", "H" + "anterill", "hex vin 59534d" + "34" * 14])
def test_identifying_content_fails(repo, text):
    (repo / "x.txt").write_text(text + "\n")
    run(repo, "git", "add", "x.txt")
    assert check(repo) == 1


def test_imei_at_line_start_in_history_fails(repo):
    (repo / "x.txt").write_text("3512345" + "67890123,x\n")
    run(repo, "git", "add", "x.txt")
    run(repo, "git", "commit", "-qm", "oops")
    run(repo, "git", "rm", "-q", "x.txt")
    run(repo, "git", "commit", "-qm", "remove")
    assert check(repo) == 1


def test_vin_in_commit_message_fails(repo):
    run(repo, "git", "commit", "-qm", "clean")
    run(repo, "git", "commit", "-q", "--allow-empty", "-m", "car %s" % FAKE_VIN)
    assert check(repo) == 1


def test_any_binary_file_fails(repo):
    (repo / "pic.GIF").write_bytes(b"GIF89a\x00\x01\x02\x00\xff")
    run(repo, "git", "add", "pic.GIF")
    assert check(repo) == 1


def test_binary_in_history_fails_after_deletion(repo):
    (repo / "pic.gif").write_bytes(b"GIF89a\x00\x01\x02\x00\xff")
    run(repo, "git", "add", "pic.gif")
    run(repo, "git", "commit", "-qm", "img")
    run(repo, "git", "rm", "-q", "pic.gif")
    run(repo, "git", "commit", "-qm", "remove")
    assert check(repo) == 1


def test_scripts_are_posix_sh():
    """The shebang is /bin/sh; bash-only builtins silently skip checks under dash (CI/capture Linux)."""
    import glob
    for path in glob.glob(os.path.join(REPO, "scripts", "*.sh")):
        text = open(path).read()
        assert "compgen" not in text and "[[" not in text, path


# The one known false positive pushed in ea12ced (an 8-byte 1A01:EE71 reading that is all decimal digits), built
# from halves so this file never holds a 15-16 digit run itself.
_A, _B, _C = "00020000", "00000000", "00000100"
EXCUSED = '   examples: [{raw: "%s%s", value: "on"}, {raw: "%s%s", value: "off"}]}  # first 8 of 200 bytes' % (_A, _C, _B, _C)


def _commit_then_remove(repo, text):
    (repo / "x.yaml").write_text(text + "\n")
    run(repo, "git", "add", "x.yaml")
    run(repo, "git", "commit", "-qm", "add")
    run(repo, "git", "rm", "-q", "x.yaml")
    run(repo, "git", "commit", "-qm", "remove")


def test_the_excused_line_in_history_passes(repo):
    _commit_then_remove(repo, EXCUSED)
    assert check(repo) == 0


def test_the_excused_line_with_anything_added_still_fails(repo):
    _commit_then_remove(repo, EXCUSED + " " + FAKE_VIN)
    assert check(repo) == 1


def test_the_excused_line_in_the_index_fails(repo):
    (repo / "x.yaml").write_text(EXCUSED + "\n")
    run(repo, "git", "add", "x.yaml")
    assert check(repo) == 1

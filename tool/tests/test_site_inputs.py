"""The public site reads git-tracked, non-private files only (tool/p4doip/site/inputs.py)."""
import os
import shutil
import subprocess

import pytest

from p4doip.site.inputs import InputError, Inputs, tracked_files


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("public\n")
    (tmp_path / "docs" / "untracked.md").write_text("draft\n")
    for d in ("runs", "local", "captures", "external", "sub/runs"):
        (tmp_path / d).mkdir(parents=True)
        (tmp_path / d / "x.txt").write_text("CANARY\n")
    (tmp_path / "NEXT.md").write_text("CANARY\n")
    return tmp_path


def test_reads_a_tracked_file(tree):
    inp = Inputs(str(tree), frozenset({"docs/a.md"}))
    assert inp.read_input("docs/a.md") == "public\n"
    assert inp.read_paths == ["docs/a.md"]


def test_refuses_untracked_file(tree):
    inp = Inputs(str(tree), frozenset({"docs/a.md"}))
    with pytest.raises(InputError, match="not tracked"):
        inp.read_input("docs/untracked.md")


@pytest.mark.parametrize("path", ["runs/x.txt", "local/x.txt", "captures/x.txt", "external/x.txt",
                                  "sub/runs/x.txt", "NEXT.md", "LOCAL/x.txt", "docs/../runs/x.txt"])
def test_refuses_private_paths_even_if_tracked(tree, path):
    inp = Inputs(str(tree), frozenset({path, "runs/x.txt", "local/x.txt", "NEXT.md"}))
    with pytest.raises(InputError, match="private"):
        inp.read_input(path)
    with pytest.raises(InputError):
        inp.input_path(path)
    assert inp.read_paths == []


@pytest.mark.parametrize("path", ["../etc/passwd", "/etc/passwd", ".."])
def test_refuses_paths_outside_the_tree(tree, path):
    inp = Inputs(str(tree), frozenset({path}))
    with pytest.raises(InputError, match="inside the repository"):
        inp.read_input(path)


def test_refuses_a_tracked_symlink_out_of_the_tree(tree, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_text("CANARY\n")
    os.symlink(outside, tree / "docs" / "link.md")
    inp = Inputs(str(tree), frozenset({"docs/link.md"}))
    with pytest.raises(InputError, match="outside"):
        inp.read_input("docs/link.md")


def test_manifest_lists_tracked_files(tree):
    (tree / "manifest").write_text("docs/a.md\n\n")
    assert tracked_files(str(tree), str(tree / "manifest")) == frozenset({"docs/a.md"})


def test_empty_or_missing_manifest_fails_closed(tree):
    (tree / "manifest").write_text("\n")
    with pytest.raises(InputError, match="empty"):
        tracked_files(str(tree), str(tree / "manifest"))
    with pytest.raises(InputError, match="cannot read manifest"):
        tracked_files(str(tree), str(tree / "missing"))


def test_not_a_git_checkout_fails_closed(tree):
    with pytest.raises(InputError, match="tracked files"):
        tracked_files(str(tree))


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_ls_files_excludes_untracked_and_ignored(tree):
    def git(*a):
        subprocess.run(["git", "-C", str(tree), *a], check=True, capture_output=True)
    git("init", "-q")
    (tree / ".gitignore").write_text("runs/\nlocal/\ncaptures/\nexternal/\nNEXT.md\n")
    git("add", ".gitignore", "docs/a.md")
    files = tracked_files(str(tree))
    assert files == frozenset({".gitignore", "docs/a.md"})

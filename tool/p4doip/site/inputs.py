"""The one gate every public-site input goes through.

Only files tracked in git can be read, and never anything under runs/, local/, captures/, external/ or a
NEXT.md, even if one of them were tracked by mistake (scripts/prepublish-check.sh fails on that too).
The tracked list comes from `git ls-files` in a checkout, or from a manifest written next to a
`git archive` export (`git ls-tree -r --name-only HEAD`), which has no .git directory.
"""
import os
import posixpath
import re
import subprocess

# Same private-path rule as scripts/prepublish-check.sh (any path component, case-insensitive).
PRIVATE = re.compile(r"(^|/)(local|runs|captures|external)/|(^|/)NEXT\.md$", re.I)


class InputError(Exception):
    """A read the public site must not make, or a tracked-file list it cannot get."""


def tracked_files(root: str, manifest: str | None = None) -> frozenset[str]:
    """Paths tracked in git, relative to root with / separators. Fails closed: no list, no build."""
    if manifest is not None:
        try:
            with open(manifest, encoding="utf-8") as f:
                text = f.read()
            # NUL-separated (git ls-tree -z) or one path per line.
            names = text.split("\0") if "\0" in text else text.split("\n")
        except OSError as e:
            raise InputError("cannot read manifest %s: %s" % (manifest, e)) from e
    else:
        try:
            out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError) as e:
            raise InputError("cannot list tracked files in %s (not a git checkout? pass --manifest): %s"
                             % (root, e)) from e
        names = out.decode("utf-8", errors="strict").split("\0")
    files = frozenset(n for n in names if n)
    if not files:
        raise InputError("the tracked-file list is empty")
    return files


class Inputs:
    """Read access to `root`, limited to `tracked` paths that are not private."""

    def __init__(self, root: str, tracked: frozenset[str]):
        self.root = os.path.realpath(root)
        self.tracked = tracked
        self.read_paths: list[str] = []  # every path handed out, for tests and the build summary

    def _check(self, rel: str) -> str:
        norm = posixpath.normpath(rel.replace(os.sep, "/"))
        if rel.startswith("/") or os.path.isabs(rel) or norm == ".." or norm.startswith("../"):
            raise InputError("%s: not a path inside the repository" % rel)
        if PRIVATE.search(norm):
            raise InputError("%s: private path; the public site never reads it" % rel)
        if norm not in self.tracked:
            raise InputError("%s: not tracked in git; the public site reads tracked files only" % rel)
        full = os.path.realpath(os.path.join(self.root, norm))
        if os.path.commonpath([full, self.root]) != self.root:
            raise InputError("%s: resolves outside the repository" % rel)
        # No symlinks anywhere on the path: a tracked link could point into local/ or runs/.
        if os.path.relpath(full, self.root).replace(os.sep, "/") != norm:
            raise InputError("%s: is or passes through a symlink; the public site reads plain files only" % rel)
        if not os.path.isfile(full):
            raise InputError("%s: tracked but missing from the tree" % rel)
        self.read_paths.append(norm)
        return full

    def input_path(self, rel: str) -> str:
        """The checked absolute path, for loaders that open the file themselves (decode, hazards)."""
        return self._check(rel)

    def read_input(self, rel: str) -> str:
        """The text of a tracked, non-private file."""
        with open(self._check(rel), encoding="utf-8") as f:
            return f.read()

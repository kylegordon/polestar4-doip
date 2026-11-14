"""Hazards: reads that are known to upset a module, kept with the repository instead of in one runs/ tree.

`catalogue/hazards.yaml` is the source of truth; a built-in entry for 1301:EE13 is always applied so the
guard survives a missing or damaged file. Two actions:

- **block**: refused on the module and on any functional address. This is a hard, permanent stop.
- **caution**: refused by default, allowed only with `--allow-caution` (or a paced scan, which is the
  designed way to test one). For reads that upset a module once under specific conditions (e.g. first
  seconds after wake) rather than for a specific DID.

The file is validated strictly: an unknown action, a duplicate or a downgrade of a built-in block is an
error, because silently losing a protection is worse than refusing to start.
"""
import os
from dataclasses import dataclass

import yaml

BUILTIN_BLOCKED = {
    (0x1301, 0xEE13): "knocks the Mobileye driver assistance ECU (1301) off the network for about a minute "
                      "(seen twice, parked, 2026-11-11)",
}


@dataclass(frozen=True)
class Hazard:
    module: int
    did: int
    action: str          # block | caution
    why: str
    evidence: str = ""
    severity: str = ""
    source: str = "built-in"


def catalogue_path() -> str:
    return os.path.join(os.environ.get("P4_ROOT", os.getcwd()), "catalogue", "hazards.yaml")


def _parse_entry(raw: dict, n: int, source: str) -> Hazard:
    if not isinstance(raw, dict):
        raise ValueError("%s: entry %d is not a mapping" % (source, n))
    for key in ("module", "did"):
        if not isinstance(raw.get(key), str):
            raise ValueError("%s: entry %d: %s must be a quoted hex string" % (source, n, key))
        try:
            int(raw[key], 16)
        except ValueError:
            raise ValueError("%s: entry %d: %s %r is not hex" % (source, n, key, raw[key]))
    action = raw.get("action")
    if action not in ("block", "caution"):
        raise ValueError("%s: entry %d: action must be 'block' or 'caution'" % (source, n))
    if not raw.get("why"):
        raise ValueError("%s: entry %d: why is required" % (source, n))
    return Hazard(int(raw["module"], 16), int(raw["did"], 16), action, str(raw["why"]),
                  str(raw.get("evidence", "")), str(raw.get("severity", "")), source)


_CACHE: dict[tuple[str, float | None], list[Hazard]] = {}


def clear_cache() -> None:
    """Tests (and a long-lived process after an edit) can force a re-read."""
    _CACHE.clear()


def load(path: str | None = None) -> list[Hazard]:
    """All hazards: the built-in block plus catalogue/hazards.yaml. Cached until the file changes."""
    path = path or catalogue_path()
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        mtime = None
    key = (path, mtime)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit

    out = {(module, did): Hazard(module, did, "block", why) for (module, did), why in BUILTIN_BLOCKED.items()}
    if mtime is not None:
        try:
            with open(path) as f:
                doc = yaml.safe_load(f) or []
        except (OSError, yaml.YAMLError) as e:
            raise ValueError("cannot read %s: %s" % (path, e)) from e
        if not isinstance(doc, list):
            raise ValueError("%s must be a list of hazards" % path)
        seen: set[tuple[int, int]] = set()
        for n, raw in enumerate(doc, 1):
            h = _parse_entry(raw, n, path)
            if (h.module, h.did) in seen:
                raise ValueError("%s: entry %d duplicates %04X:%04X" % (path, n, h.module, h.did))
            seen.add((h.module, h.did))
            old = out.get((h.module, h.did))
            if old is not None and old.action == "block" and h.action != "block":
                raise ValueError("%s: entry %d cannot downgrade the built-in block on %04X:%04X"
                                 % (path, n, h.module, h.did))
            out[(h.module, h.did)] = h
    result = sorted(out.values(), key=lambda h: (h.action != "block", h.module, h.did))
    _CACHE[key] = result
    return result


def entries() -> list[Hazard]:
    return load()


def _reason(target: int, did: int, functional: bool, action: str) -> str | None:
    for h in load():
        if h.did == did and h.action == action and (target == h.module or functional):
            return "%04X:%04X %s [%s] %s" % (h.module, h.did, h.action, h.source, h.why)
    return None


def blocked_reason(target: int, did: int, functional: bool = False) -> str | None:
    return _reason(target, did, functional, "block")


def caution_reason(target: int, did: int, functional: bool = False) -> str | None:
    return _reason(target, did, functional, "caution")

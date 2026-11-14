"""Decode raw DID payloads using catalogue/signals.yaml.

A signal picks bytes [offset : offset+len] of the payload, then either
- maps them through `values` (hex string -> label),
- tests `bits` (hex mask -> label) and returns the labels that are set,
- reads them as an unsigned (`type: u`) or signed (`type: s`) integer * scale + add, or
- decodes text: `ascii`, `utf-16le`, `utf-16be`, `utf-8`, `ascii-hex` (ASCII hex digits,
  hex-decoded then read as text) or `raw` (hex string).

Integers/bits read big-endian unless `endian: little` is set. A signal with
`repeat: {count: N | count_from: {did: "EE19", offset: 0, len: 2, max: N}, len: bytes per element, ...}`
reads N back-to-back fixed-size elements by the rules above and returns a list; `count_from` reads the
valid-element count from a sibling DID in the same module, so `decode()` gets a context of sibling payloads.
"""
import os
import re
from typing import Literal

import yaml

from . import store

REQUIRED = {"id", "module", "did", "name", "confidence"}


def load(path: str | None = None) -> list[dict]:
    path = path or os.path.join(store.root(), "catalogue", "signals.yaml")
    with open(path) as f:
        sigs = yaml.safe_load(f) or []
    for s in sigs:
        missing = REQUIRED - set(s)
        if missing:
            raise ValueError("signal %r is missing %s" % (s.get("id"), sorted(missing)))
        for key in ("module", "did"):
            if not isinstance(s[key], str):
                raise ValueError("signal %s: %s must be a quoted hex string" % (s["id"], key))
        if s["confidence"] not in ("C", "P"):
            raise ValueError("signal %s: confidence must be C or P" % s["id"])
    return sigs


def load_dids(path: str | None = None) -> dict[int, dict]:
    """catalogue/dids.yaml: DID -> {name, family, ...} annotations. Names only; values never live here."""
    path = path or os.path.join(store.root(), "catalogue", "dids.yaml")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        entries = yaml.safe_load(f) or []
    out: dict[int, dict] = {}
    for e in entries:
        if not isinstance(e.get("did"), str):
            raise ValueError("dids.yaml: did must be a quoted hex string, got %r" % e.get("did"))
        out[int(e["did"], 16)] = e
    return out


def load_dtcs(path: str | None = None) -> dict[int, dict]:
    """catalogue/dtc.yaml: DTC (3-byte int) -> {name, module, source}. Missing or empty is fine."""
    path = path or os.path.join(store.root(), "catalogue", "dtc.yaml")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        entries = yaml.safe_load(f) or []
    out: dict[int, dict] = {}
    for e in entries:
        if not isinstance(e.get("dtc"), str) or not re.fullmatch(r"[0-9a-fA-F]{6}", e["dtc"]):
            raise ValueError("dtc.yaml: dtc must be a quoted 6-hex-digit string, got %r" % e.get("dtc"))
        out[int(e["dtc"], 16)] = e
    return out


def index(sigs: list[dict]) -> dict[tuple[int, int], list[dict]]:
    out: dict[tuple[int, int], list[dict]] = {}
    for s in sigs:
        for mod in s["module"].split(","):
            out.setdefault((int(mod, 16), int(s["did"], 16)), []).append(s)
    return out


ENCODINGS = {"ascii", "ascii-hex", "utf-16le", "utf-16be", "utf-8", "raw"}


def _count_from(spec: dict, context: dict | None) -> int:
    """The repeat count held in a sibling DID (e.g. EE19 says how many of DA31's 130 slots are valid)."""
    if not isinstance(spec, dict) or "did" not in spec:
        raise ValueError("count_from needs {did, offset?, len?, max?}")
    if context is None:
        raise ValueError("count_from needs sibling payloads (context) but none were supplied")
    try:
        key = int(spec["did"], 16) if isinstance(spec["did"], str) else int(spec["did"])
    except (TypeError, ValueError):
        raise ValueError("count_from did %r is not hex" % spec.get("did"))
    raw = context.get(key)
    if raw is None:
        raise ValueError("count_from did %04X is missing from the context" % key)
    off = int(spec.get("offset", 0))
    ln = int(spec.get("len", 2))
    if len(raw) < off + ln:
        raise ValueError("count_from did %04X is shorter than %d bytes" % (key, off + ln))
    n = int.from_bytes(raw[off:off + ln], "big")
    hi = int(spec.get("max", 10000))
    return max(0, min(n, hi))


def decode(sig: dict, data: bytes, context: dict | None = None):
    """Decode one signal from a DID payload. `context` maps a sibling DID (int) to its payload, for count_from."""
    off = sig.get("offset", 0)
    part = data[off:off + sig["len"]] if "len" in sig else data[off:]
    if "len" in sig and len(part) < sig["len"]:
        raise ValueError("signal %s needs %d bytes at offset %d, got %s" % (sig["id"], sig["len"], off, data.hex()))
    if "repeat" in sig:
        r = sig["repeat"]
        count = r.get("count")
        if count is None and "count_from" in r:
            count = _count_from(r["count_from"], context)
        if count is None:
            raise ValueError("signal %s: repeat needs count or count_from" % sig["id"])
        if len(part) < count * r["len"]:
            raise ValueError("signal %s needs %d bytes at offset %d, got %s" % (sig["id"], count * r["len"], off, data.hex()))
        # r doubles as the per-element spec; the element slice is exactly r["len"] bytes.
        return [decode(r, part[i * r["len"]:(i + 1) * r["len"]]) for i in range(count)]
    if "encoding" in sig:
        enc = sig["encoding"]
        if enc == "ascii-hex":
            return bytes.fromhex(part.decode("ascii")).decode("ascii")
        if enc == "raw":
            return part.hex()
        if enc == "ascii":
            return part.decode("ascii", errors="replace").rstrip("\x00 ")
        if enc == "utf-8":
            return part.decode("utf-8", errors="replace").rstrip("\x00 ")
        if enc in ("utf-16le", "utf-16be"):
            return part.decode(enc, errors="replace").rstrip("\x00 ")
        raise ValueError("signal %s: unknown encoding %s (known: %s)" % (sig["id"], enc, ", ".join(sorted(ENCODINGS))))
    if "values" in sig:
        return sig["values"].get(part.hex(), "unknown(%s)" % part.hex())
    order: Literal["little", "big"] = "little" if sig.get("endian") == "little" else "big"
    n = int.from_bytes(part, order, signed=sig.get("type") == "s")
    if "bits" in sig:
        return sorted(label for mask, label in sig["bits"].items() if n & int(mask, 16))
    if "scale" in sig or "add" in sig:
        return round(n * sig.get("scale", 1) + sig.get("add", 0), 6)
    return n


def describe(sigs_for_did: list[dict], data: bytes, context: dict | None = None) -> str:
    parts = []
    for s in sigs_for_did:
        try:
            v = decode(s, data, context)
        except ValueError as e:
            v = "decode error: %s" % e
        parts.append("%s=%s%s" % (s["id"], v, s.get("unit", "")))
    return "; ".join(parts)

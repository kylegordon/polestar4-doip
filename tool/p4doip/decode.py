"""Decode raw DID payloads using catalogue/signals.yaml.

A signal picks bytes [offset : offset+len] of the payload, then either
- maps them through `values` (hex string -> label),
- tests `bits` (hex mask -> label) and returns the labels that are set, or
- reads them as an unsigned (`type: u`) or signed (`type: s`) integer * scale + add.
"""
import os

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


def index(sigs: list[dict]) -> dict[tuple[int, int], list[dict]]:
    out: dict[tuple[int, int], list[dict]] = {}
    for s in sigs:
        for mod in s["module"].split(","):
            out.setdefault((int(mod, 16), int(s["did"], 16)), []).append(s)
    return out


def decode(sig: dict, data: bytes):
    off = sig.get("offset", 0)
    part = data[off:off + sig["len"]] if "len" in sig else data[off:]
    if "len" in sig and len(part) < sig["len"]:
        raise ValueError("signal %s needs %d bytes at offset %d, got %s" % (sig["id"], sig["len"], off, data.hex()))
    if "values" in sig:
        return sig["values"].get(part.hex(), "unknown(%s)" % part.hex())
    n = int.from_bytes(part, "big", signed=sig.get("type") == "s")
    if "bits" in sig:
        return sorted(label for mask, label in sig["bits"].items() if n & int(mask, 16))
    if "scale" in sig or "add" in sig:
        return round(n * sig.get("scale", 1) + sig.get("add", 0), 6)
    return n


def describe(sigs_for_did: list[dict], data: bytes) -> str:
    parts = []
    for s in sigs_for_did:
        try:
            v = decode(s, data)
        except ValueError as e:
            v = "decode error: %s" % e
        parts.append("%s=%s%s" % (s["id"], v, s.get("unit", "")))
    return "; ".join(parts)

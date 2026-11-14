"""Text extraction and identifier masking shared by the CLI and the status site.

One implementation, one set of tests: the VIN, serials, emails, phone numbers and long
digit runs are hidden the same way wherever a DID value is shown. `stored_value` is also
the single definition of which DIDs may never be written to `runs/` in the clear.
"""
import re

# DIDs whose value identifies this car (docs/did-identity.md): recorded as zeros, never printed.
# The machine-readable twin is catalogue/dids.yaml (`masked: true`); a test keeps them in step.
MASKED_DIDS = {0xF190, 0xF18C, 0xF192, 0xF198}

VIN_LIKE = re.compile(r"(?:YSM|LPS|LRW|YV1)[A-HJ-NPR-Z0-9]{14}", re.I)  # Polestar/Volvo/Geely WMIs
LONG_NUMBER = re.compile(r"\d(?:[ .-]?\d){9,}")  # ICCID, IMEI, phone numbers, serials; separators allowed
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+[1-9][0-9]{1,2}[ -]?[0-9]{2,4}[ -]?[0-9]{3,4}[ -]?[0-9]{3,4}")

PRINTABLE_RUN = re.compile(rb"[\x20-\x7e]{4,}")
HEX_RUN = re.compile(rb"(?:[0-9a-fA-F]{2}){4,}")


def stored_value(did: int, payload: bytes) -> str:
    """Hex of a DID value as written to runs/ and logs. Masked DIDs are recorded as zeros of the same length."""
    return "00" * len(payload) if did in MASKED_DIDS else payload.hex()


def mask(s: str) -> str:
    """Hide every identifier class we know about, in a stable order (VIN before numbers)."""
    s = VIN_LIKE.sub("[VIN hidden]", s)
    s = EMAIL.sub("[email hidden]", s)
    s = PHONE.sub("[phone hidden]", s)
    return LONG_NUMBER.sub("[number hidden]", s)


def utf16_ascii(raw: bytes) -> bytes:
    """UTF-16LE ASCII text ('S\\0W\\0...'): every odd byte is 0x00, so keep just the even ones. Tested on
    the payload as-is and stripped of padding, so trailing padding cannot shift the byte lanes."""
    for data in (raw, raw.strip(b"\x00\xff\x20")):
        if len(data) >= 8:
            even, odd = data[0::2], data[1::2]
            if sum(c == 0 for c in odd) / len(odd) >= 0.9 and sum(32 <= c < 127 for c in even) / len(even) >= 0.9:
                return even
    return raw


def hexwrapped(raw: bytes) -> bytes:
    """DIDs that store text as an ASCII hex string ('424f4f54...' = 'BOOT...'): unwrap the inner text."""
    if len(raw) >= 8 and len(raw) % 2 == 0 and all(c in b"0123456789abcdefABCDEF" for c in raw):
        inner = bytes.fromhex(raw.decode())
        if len(inner) >= 4 and all(32 <= c < 127 for c in inner):
            return inner
    return raw


def readable_text(hexdata: str) -> str:
    """Printable text in a DID value with identifiers masked, or '' if the value isn't mostly text.

    Plain ASCII, UTF-16LE ('S\\0W\\0...') and ASCII-hex-wrapped ('424f4f54...' = 'BOOT...') payloads all reach
    the same masking: VIN-like strings, email addresses, phone numbers and any run of 10+ digits (spaces, dots
    or dashes allowed between them) are hidden, so the output can go into a web search. Wider than
    scripts/prepublish-check.sh on purpose.
    """
    try:
        raw = bytes.fromhex(hexdata)
    except ValueError:
        return ""
    # Unwrap order: UTF-16LE first, then hex-unwrap — hexwrapped only fires on all-hex-digit payloads,
    # so it cannot re-transform UTF-16 output. utf16_ascii tests both the raw lanes and the stripped
    # payload, so NUL/FF/space padding cannot shift the even/odd byte lanes.
    raw = hexwrapped(utf16_ascii(raw)).strip(b"\x00\xff\x20")
    if len(raw) < 4 or sum(1 for c in raw if 32 <= c < 127) / len(raw) < 0.9:
        return ""
    s = "".join(chr(c) if 32 <= c < 127 else "." for c in raw)
    if not re.search(r"[A-Za-z0-9]{3}", s):
        return ""
    return mask(s)


def _utf16_runs(raw: bytes, min_len: int) -> list[str]:
    """Printable runs in UTF-16LE/BE text, only when the payload really looks like UTF-16 lanes."""
    out: list[str] = []
    for endian, zero_lane in (("utf-16-le", raw[1::2]), ("utf-16-be", raw[0::2])):
        if len(zero_lane) < 4 or sum(c == 0 for c in zero_lane) / len(zero_lane) < 0.5:
            continue
        try:
            text = raw.decode(endian, errors="replace")
        except (LookupError, UnicodeError):
            continue
        for run in re.findall(r"[ -~]{%d,}" % min_len, text):
            out.append(run)
    return out


def _hex_runs(raw: bytes, min_len: int) -> list[str]:
    """Text stored as an ASCII hex string inside a larger binary value ('...48454c4c4f...')."""
    out: list[str] = []
    for m in HEX_RUN.finditer(raw):
        digits = m.group()
        if len(digits) % 2:
            digits = digits[:-1]
        try:
            inner = bytes.fromhex(digits.decode())
        except ValueError:
            continue
        if len(inner) >= min_len and sum(1 for c in inner if 32 <= c < 127) / len(inner) >= 0.9:
            out.extend(r.group().decode("ascii") for r in PRINTABLE_RUN.finditer(inner))
    return out


def readable_runs(hexdata: str, min_len: int = 4) -> list[str]:
    """Every printable text run anywhere in a DID value, masked and de-duplicated.

    Unlike `readable_text`, this finds text after a binary header or in the middle of a
    struct, and handles UTF-16LE/BE and hex-wrapped text inside larger payloads. It is the
    fallback used by `p4 strings` and the status site when the whole payload is not text.
    """
    try:
        raw = bytes.fromhex(hexdata)
    except ValueError:
        return []
    runs = [m.group().decode("ascii") for m in PRINTABLE_RUN.finditer(raw)]
    runs += _utf16_runs(raw, min_len)
    runs += _hex_runs(raw, min_len)
    out: list[str] = []
    for run in runs:
        run = run.strip()
        if len(run) < min_len or not re.search(r"[A-Za-z0-9]{3}", run):
            continue
        masked = mask(run)
        if masked not in out:
            out.append(masked)
    return out


def text_of(hexdata: str) -> str:
    """One display string: the whole-payload reading when it is text, else the runs found inside."""
    whole = readable_text(hexdata)
    if whole:
        return whole
    return " | ".join(readable_runs(hexdata))

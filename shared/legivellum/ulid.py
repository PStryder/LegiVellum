"""ULID generation for receipt identifiers, with no third-party dependency.

The stack had two mutually exclusive ULID packages in play. `ulid-py` exposes
`ulid.new()`; `python-ulid` exposes `ULID()` and has no `new()`. Both install a
top-level module named `ulid`, so they cannot coexist, and they were pinned
inconsistently across five files -- including two `pyproject.toml` files both
declaring `name = "legivellum"` with different pins.

Picking either one would have forced that pin onto every component that
installs this package, and components outside the current change scope pin the
other. So the protocol package depends on neither: a ULID is a 48-bit
millisecond timestamp followed by 80 bits of randomness, rendered in Crockford
Base32, and that is short enough to own outright.

The properties that matter to the protocol, and that the tests pin:

- 26 characters, Crockford Base32, so a receipt id is URL- and log-safe.
- Lexicographic order matches creation order at millisecond resolution, which
  is why receipt ids are ULIDs rather than UUID4 -- the ledger sorts by them.
- 80 bits of `secrets`-grade randomness per id, so ids minted in the same
  millisecond by different processes do not collide.
"""

from __future__ import annotations

import hashlib
import secrets
import time

# Crockford Base32: no I, L, O or U, so the alphabet survives transcription.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_TIME_BITS = 48
_RANDOM_BITS = 80
_TOTAL_CHARS = 26
_MAX_TIME_MS = (1 << _TIME_BITS) - 1


def _encode(value: int, length: int) -> str:
    """Render an integer as fixed-length Crockford Base32."""
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_ulid(timestamp_ms: int | None = None) -> str:
    """Return a new 26-character ULID.

    Args:
        timestamp_ms: Millisecond epoch to encode. Defaults to now. Present so
            ordering can be tested deterministically rather than by sleeping.
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    if not 0 <= timestamp_ms <= _MAX_TIME_MS:
        raise ValueError(
            f"timestamp_ms {timestamp_ms} outside the 48-bit ULID range "
            f"(0..{_MAX_TIME_MS})"
        )

    randomness = secrets.randbits(_RANDOM_BITS)
    # 48 bits -> 10 chars (50 bits of space), 80 bits -> 16 chars. 26 total.
    return _encode(timestamp_ms, 10) + _encode(randomness, 16)


def is_ulid(value: str) -> bool:
    """Whether a string is shaped like a ULID this module would emit."""
    return (
        isinstance(value, str)
        and len(value) == _TOTAL_CHARS
        and all(c in _CROCKFORD for c in value)
    )


def timestamp_ms_of(value: str) -> int:
    """Recover the millisecond timestamp encoded in a ULID."""
    if not is_ulid(value):
        raise ValueError(f"not a ULID: {value!r}")
    result = 0
    for char in value[:10]:
        result = (result << 5) | _CROCKFORD.index(char)
    return result


def derive_ulid(*parts: str) -> str:
    """Derive a stable, ULID-shaped identifier from the things that define it.

    An obligation is opened by one receipt and closed by another, and most
    emitters build those in separate calls with no shared state -- CogniGate
    builds `accepted` when a lease starts and `complete` when it ends, from
    different code paths. Minting a random id in each would give one obligation
    two identities, and the closing receipt would name an obligation that was
    never opened.

    So the id is derived from the identifiers that already pin the obligation
    down (for a leased job, the lease id). Same inputs, same id; different
    inputs, different id, with 128 bits of hash so collisions are not a
    practical concern.

    The result is the same 26-character Crockford Base32 shape as `new_ulid`,
    so nothing downstream needs to know which way an id was produced. It is
    NOT time-ordered -- derived ids sort arbitrarily, which is fine because
    ordering is a property of `receipt_id`, not of obligation identity.
    """
    if not parts or any(not p for p in parts):
        raise ValueError("derive_ulid requires at least one non-empty part")
    # Length-prefix each part so ("a", "bc") and ("ab", "c") cannot collide.
    material = "\x1f".join(f"{len(p)}:{p}" for p in parts).encode("utf-8")
    digest = hashlib.blake2b(material, digest_size=16).digest()
    return _encode(int.from_bytes(digest, "big"), _TOTAL_CHARS)[-_TOTAL_CHARS:]

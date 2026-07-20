"""Pure-Python ULID generation. No external dependency in v0.

ULID = 48-bit timestamp + 80-bit randomness, Crockford-base32 encoded.
Time-ordered, URL-safe, 26 chars.
"""
import os
import time

_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """Returns a 26-char Crockford-base32 ULID."""
    timestamp_ms = int(time.time() * 1000)
    timestamp_bytes = timestamp_ms.to_bytes(6, "big")
    randomness_bytes = os.urandom(10)
    full_bytes = timestamp_bytes + randomness_bytes
    return _encode_base32(full_bytes)


def _encode_base32(data: bytes) -> str:
    """Crockford base32, 16 bytes -> 26 chars."""
    if len(data) != 16:
        raise ValueError("ULID requires exactly 16 bytes")
    n = int.from_bytes(data, "big")
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD_BASE32[n & 0x1F])
        n >>= 5
    return "".join(reversed(chars))

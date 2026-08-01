"""Canonical, version-stable encoding of hashable dict keys to bytes.

The Bloomier filters hash keys by serializing them to bytes first.  This
module provides a deterministic encoder that:

* covers the hashable built-in types (None, bool, int, float, complex, str,
  bytes, bytearray, tuple, frozenset, recursively);
* produces identical bytes on every platform, Python version, and process —
  unlike ``marshal``, whose format is CPython internal state with no
  stability guarantee;
* raises ``TypeError`` for anything else (``range``, ``slice``,
  user-defined objects, ...).

Pass a custom ``key_encoder`` callable to the filter constructor to support
additional key types.  An encoder must be deterministic and injective on the
keys you use, and the same encoder must be used to build and query a filter.

Byte format (all multi-byte integers are big-endian):

    None       0x00
    bool       0x01 <0|1>
    int        0x02 <sign: 0x00 | 0xFF> <len:u32> <|n|: minimal big-endian>
    float      0x03 <8-byte IEEE-754 double>
    complex    0x04 <8-byte real> <8-byte imaginary>
    str        0x05 <len:u32> <UTF-8 (lone surrogates preserved)>
    bytes      0x06 <len:u32> <raw bytes>
    tuple      0x07 <count:u32> <elements, in order>
    frozenset  0x08 <count:u32> <elements, sorted by their encoded bytes>
    range      0x09 <start:int> <stop:int> <step:int>

``slice``, ``memoryview``, and identity-hashable objects (classes, functions,
instances) are intentionally unsupported: slices are unhashable, memoryview
equality is format-aware, and identity objects have no canonical byte form —
use the ``key_encoder`` hook for those.
"""

import struct

_TAG_NONE = 0x00
_TAG_BOOL = 0x01
_TAG_INT = 0x02
_TAG_FLOAT = 0x03
_TAG_COMPLEX = 0x04
_TAG_STR = 0x05
_TAG_BYTES = 0x06
_TAG_TUPLE = 0x07
_TAG_FROZENSET = 0x08
_TAG_RANGE = 0x09

_U32 = struct.Struct(">I")   # unsigned 32-bit, big-endian
_F64 = struct.Struct(">d")   # IEEE-754 double, big-endian


def _cache_key(key):
    """Equality-faithful, hashable stand-in for ``key`` for the encode cache.

    Plain dict keys are not faithful here: values that compare equal in
    Python can still encode differently (``True == 1``, ``0.0 == -0.0``,
    distinct NaN payloads), so bools get a tag and floats/complexes are
    represented by their exact IEEE-754 bit patterns.  The returned value
    is equal iff ``key`` encodes identically.
    """
    if key is None:
        return None
    if key is True:
        return (_TAG_BOOL, True)
    if key is False:
        return (_TAG_BOOL, False)
    if isinstance(key, int):
        return (_TAG_INT, key)
    if isinstance(key, float):
        return (_TAG_FLOAT, _F64.pack(key))
    if isinstance(key, complex):
        return (_TAG_COMPLEX, _F64.pack(key.real), _F64.pack(key.imag))
    if isinstance(key, str):
        return (_TAG_STR, key)
    if isinstance(key, bytes):
        return (_TAG_BYTES, key)
    if isinstance(key, bytearray):
        return (_TAG_BYTES, bytes(key))
    if isinstance(key, tuple):
        return (_TAG_TUPLE,) + tuple(_cache_key(e) for e in key)
    if isinstance(key, frozenset):
        return (_TAG_FROZENSET, frozenset(_cache_key(e) for e in key))
    if isinstance(key, range):
        return (_TAG_RANGE, key)
    raise TypeError(
        f"unsupported key type {type(key).__name__!r}; "
        "pass a custom key_encoder to the filter constructor"
    )


# Bounded memoization of encoded bytes: repeated queries of the same keys
# skip re-serialization (and frozenset re-sorting).  Dropped wholesale when
# full — per-entry FIFO eviction would leave the dict's hash table full of
# dummy entries that grow without bound under churn.  Bounded by entry count
# AND total bytes; benign under the GIL (a concurrent miss only recomputes).
_ENCODE_CACHE_SIZE = 8192
_ENCODE_CACHE_MAX_BYTES = 1 << 20   # 1 MiB
_encode_cache = {}
_encode_cache_bytes = 0


def encode_key(key) -> bytes:
    """Serialize ``key`` to canonical bytes (see module docstring).

    The encoding is injective on the supported types: two keys encode to the
    same bytes only if they are the same key (note that bool and int share
    dict semantics, e.g. ``1 == True``, but still encode differently).

    Results are memoized in a small bounded cache; the cache key faithfully
    distinguishes values that compare equal but encode differently.
    """
    global _encode_cache_bytes
    cache_key = _cache_key(key)
    try:
        return _encode_cache[cache_key]
    except KeyError:
        pass
    encoded = _encode_key_impl(key)
    if (len(_encode_cache) >= _ENCODE_CACHE_SIZE
            or _encode_cache_bytes + len(encoded) > _ENCODE_CACHE_MAX_BYTES):
        _encode_cache.clear()
        _encode_cache_bytes = 0
    _encode_cache[cache_key] = encoded
    _encode_cache_bytes += len(encoded)
    return encoded


def _encode_key_impl(key) -> bytes:
    if key is None:
        return b"\x00"
    if key is True:
        return b"\x01\x01"
    if key is False:
        return b"\x01\x00"
    if isinstance(key, int):
        mag = key if key >= 0 else -key
        size = (mag.bit_length() + 7) // 8
        sign = b"\x00" if key >= 0 else b"\xff"
        return b"\x02" + sign + _U32.pack(size) + mag.to_bytes(size, "big")
    if isinstance(key, float):
        return b"\x03" + _F64.pack(key)
    if isinstance(key, complex):
        return b"\x04" + _F64.pack(key.real) + _F64.pack(key.imag)
    if isinstance(key, str):
        data = key.encode("utf-8", "surrogatepass")
        return b"\x05" + _U32.pack(len(data)) + data
    if isinstance(key, (bytes, bytearray)):
        data = bytes(key)
        return b"\x06" + _U32.pack(len(data)) + data
    if isinstance(key, tuple):
        parts = [encode_key(e) for e in key]
        return b"\x07" + _U32.pack(len(parts)) + b"".join(parts)
    if isinstance(key, frozenset):
        # Sort by encoded bytes so output is independent of per-process set
        # iteration order.
        parts = sorted(encode_key(e) for e in key)
        return b"\x08" + _U32.pack(len(parts)) + b"".join(parts)
    if isinstance(key, range):
        return b"\x09" + encode_key((key.start, key.stop, key.step))
    raise TypeError(
        f"unsupported key type {type(key).__name__!r}; "
        "pass a custom key_encoder to the filter constructor"
    )

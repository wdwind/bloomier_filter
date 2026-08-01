# Bloomier Filter in Python

A Python implementation of the [Bloomier Filter](https://www.cs.princeton.edu/~chazelle/pubs/soda-rev04.pdf) (**not bloom filter**) by Chazelle, Bernard, et al.

In detail, both the immutable and the mutable Bloomier filters are implemented. The immutable version only supports `int` value, and it can be extended to support different types of value with customized encoder/decoder. The mutable version is more powerful and can handle different types of value by default.

### Keys

Keys are serialized to bytes before hashing by a built-in canonical encoder (`bloomier/key_encoding.py`) covering `None`, `bool`, `int`, `float`, `complex`, `str`, `bytes`, `tuple`, `frozenset`, and `range` (recursively). The encoding is deterministic across processes, platforms, and Python versions (frozenset elements are sorted, floats are big-endian IEEE-754), so a filter can be built and queried in different processes. For other key types (e.g. `uuid.UUID`, `datetime`, user classes), pass a custom `key_encoder` callable (`key -> bytes`) to the constructor; use the same encoder to build and query a filter.

### Values (immutable filter)

`int` values must satisfy `abs(value) < 2 ** val_max_bit_length` — negative values are supported and recovered exactly (XOR is two's-complement). Absent keys are detected with the same bit-length bound as a sentinel, giving a false-positive probability of roughly `2 ** (val_max_bit_length + 1) / 2 ** 64` per query; keep `val_max_bit_length` well below 63 (larger values are rejected at construction).

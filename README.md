# Bloomier Filter in Python

A Python implementation of the [Bloomier Filter](https://www.cs.princeton.edu/~chazelle/pubs/soda-rev04.pdf) (**not bloom filter**) by Chazelle, Bernard, et al.

In detail, both the immutable and the mutable Bloomier filters are implemented. The immutable version only supports `int` value, and it can be extended to support different types of value with customized encoder/decoder. The mutable version is more powerful and can handle different types of value by default.

### Keys

Keys are serialized to bytes before hashing by a built-in canonical encoder (`bloomier/key_encoding.py`) covering `None`, `bool`, `int`, `float`, `complex`, `str`, `bytes`, `tuple`, `frozenset`, and `range` (recursively). The encoding is deterministic across processes, platforms, and Python versions (frozenset elements are sorted, floats are big-endian IEEE-754), so a filter can be built and queried in different processes. Encoded bytes are memoized in a small bounded cache, so repeated queries of the same keys skip re-serialization. For other key types (e.g. `uuid.UUID`, `datetime`, user classes), pass a custom `key_encoder` callable (`key -> bytes`) to the constructor; use the same encoder to build and query a filter.

Neighbor slots and the per-key XOR mask are derived with double hashing from two 64-bit `wyhash` hashes (`neighbor_i = (h1 + (i+1)*h2) % size`, `mask = h1`, with `h2` forced coprime with the table size), which keeps every key's slots pairwise distinct and uses two hash calls instead of `num_hashes + 1`.

### Values (immutable filter)

`int` values must satisfy `abs(value) < 2 ** val_max_bit_length` — negative values are supported and recovered exactly (XOR is two's-complement). Absent keys are detected with the same bit-length bound as a sentinel, giving a false-positive probability of roughly `2 ** (val_max_bit_length + 1) / 2 ** 64` per query; keep `val_max_bit_length` well below 63 (larger values are rejected at construction).

### Load factor (choosing `size`)

The peeling construction needs empty table slots, so the table must be sized well above the key count. Keep the load factor `#keys / size` at or below ~50–60%. `build_filter` only rejects `#keys > size`; at higher loads the build instead fails with `RuntimeError: No valid ordering found` — retry with a different `seed`, or increase `size`. Measured build success at `num_hashes=3` (40 seeds): ~90% at 20% load, ~80% at 30%, ~45% at 60%, ~30% at 70%. Rule of thumb: `size ≈ 2 × #keys`.

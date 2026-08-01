import math

import wyhash

from .key_encoding import encode_key


class BloomierBase:
    def __init__(self, size: int, num_hashes: int, seed: int = 0, key_encoder=None):
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"size must be a positive integer, got {size!r}")
        if not isinstance(num_hashes, int) or num_hashes <= 0:
            raise ValueError(f"num_hashes must be a positive integer, got {num_hashes!r}")
        if key_encoder is not None and not callable(key_encoder):
            raise TypeError("key_encoder must be callable or None")
        self._size = size
        self._num_hashes = num_hashes
        self._seed = seed
        # Serialize keys to bytes for hashing; see key_encoding.encode_key.
        self._encode_key = key_encoder if key_encoder is not None else encode_key
        self._secret = wyhash.make_secret(seed)

    def _hash_all(self, key):
        """Return (neighbors_list, mask_int) with a single key encoding.

        Double hashing (Kirsch & Mitzenmacher): ``mask = h1`` and
        ``neighbor_i = (h1 + (i+1)*h2) % size`` from two wyhash calls instead
        of ``num_hashes + 1``.  ``h2`` is forced coprime with ``size`` (odd,
        then bumped past shared factors), so a key's slots are pairwise
        distinct whenever ``num_hashes <= size``; the fail-fast duplicate-slot
        check in ``_find_match`` guards the ``num_hashes > size`` case.
        """
        key_bytes = self._encode_key(key)
        h1 = wyhash.hash(key_bytes, self._seed, self._secret)
        h2 = wyhash.hash(key_bytes, self._seed + 1, self._secret) | 1
        size = self._size
        # Slots collide iff d*h2 ≡ 0 (mod size) for some |d| < num_hashes;
        # coprime h2 makes that impossible.  A random odd h2 is already
        # coprime with all but the odd part of size, so this rarely iterates.
        while math.gcd(h2, size) != 1:
            h2 += 2
        num_hashes = self._num_hashes
        return [(h1 + (i + 1) * h2) % size for i in range(num_hashes)], h1

    def _find_match(self, keys: list) -> list:
        """Order ``keys`` so each can be assigned a private tweak slot.

        Returns a list of ``(key, tweak, neighbors, mask)`` tuples in the
        order the builder must fill the table (deepest-peeled keys first).
        Peeling is iterative and every key is hashed exactly once: the
        precomputed ``(neighbors, mask)`` pairs are threaded through the
        peeling levels instead of re-encoding/re-hashing surviving keys.
        """
        if not keys:
            return []

        # Pre-compute hashes + masks for every key once (parallel list, no dict).
        precomputed = [self._hash_all(key) for key in keys]

        # Fail fast on intra-key hash collisions: the XOR invariant requires
        # distinct slots per key, so the user must retry with other parameters.
        for key, (neighbors, _) in zip(keys, precomputed):
            if len(set(neighbors)) != len(neighbors):
                dup_slots = sorted({n for n in neighbors if neighbors.count(n) > 1})
                raise RuntimeError(
                    f"Hash functions collide for key {key!r}: duplicate table "
                    f"slot(s) {dup_slots}. Try a different seed, size, or "
                    f"num_hashes."
                )

        levels = []
        level_keys = keys
        level_pre = precomputed
        while level_keys:
            # Identify non-singleton positions using bytearray for O(1)
            # indexing.  Much faster than set() for dense integer keys in
            # [0, size).
            non_singletons = bytearray(self._size)
            seen = bytearray(self._size)
            for neighbors, _ in level_pre:
                for n in neighbors:
                    if seen[n]:
                        non_singletons[n] = 1
                    seen[n] = 1

            peeled = []
            next_keys = []
            next_pre = []
            for key, (neighbors, mask) in zip(level_keys, level_pre):
                for neighbor in neighbors:
                    if not non_singletons[neighbor]:
                        peeled.append((key, neighbor, neighbors, mask))
                        break
                else:
                    next_keys.append(key)
                    next_pre.append((neighbors, mask))

            if not peeled:
                raise RuntimeError(
                    "No valid ordering found; try a different hash seed or "
                    "increase the table size."
                )
            levels.append(peeled)
            level_keys = next_keys
            level_pre = next_pre

        # Deepest-peeled level first (reversed(levels)); iteration order
        # within a level is preserved.
        return [item for level in reversed(levels) for item in level]

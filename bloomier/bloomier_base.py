import marshal
import wyhash

# Bind once at module level to avoid global lookup in hot paths.
_dumps = marshal.dumps


class BloomierBase:
    def __init__(self, size: int, num_hashes: int, seed: int = 0):
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"size must be a positive integer, got {size!r}")
        if not isinstance(num_hashes, int) or num_hashes <= 0:
            raise ValueError(f"num_hashes must be a positive integer, got {num_hashes!r}")
        self._size = size
        self._num_hashes = num_hashes
        self._seed = seed
        # Pre-compute secrets so we never call make_secret in hot paths.
        self._secrets = [wyhash.make_secret(seed + i) for i in range(num_hashes + 1)]

    def _hash_all(self, key):
        """Return (neighbors_list, mask_int) with a single key marshalling."""
        key_bytes = _dumps(key)
        neighbors = [wyhash.hash(key_bytes, self._seed + i, self._secrets[i]) % self._size
                     for i in range(self._num_hashes)]
        mask = wyhash.hash(key_bytes, self._seed + self._num_hashes,
                           self._secrets[self._num_hashes])
        return neighbors, mask

    def _find_match(self, keys: list) -> list:
        if not keys:
            return []

        # Pre-compute hashes + masks for every key once (parallel list, no dict).
        precomputed = [self._hash_all(key) for key in keys]

        # Fail fast if any key's own hash functions collide: the XOR
        # encode/decode invariant is only defined when each key's hash slots
        # are distinct, so a duplicate means the user must retry with a
        # different seed / size / num_hashes rather than us working around it.
        for key, (neighbors, _) in zip(keys, precomputed):
            if len(set(neighbors)) != len(neighbors):
                dup_slots = sorted({n for n in neighbors if neighbors.count(n) > 1})
                raise RuntimeError(
                    f"Hash functions collide for key {key!r}: duplicate table "
                    f"slot(s) {dup_slots}. Try a different seed, size, or "
                    f"num_hashes."
                )

        # Identify non-singleton positions using bytearray for O(1) indexing.
        # Much faster than set() for dense integer keys in [0, size).
        non_singletons = bytearray(self._size)
        seen = bytearray(self._size)
        for neighbors, _ in precomputed:
            for n in neighbors:
                if seen[n]:
                    non_singletons[n] = 1
                seen[n] = 1

        ordered = []
        remaining = []

        for key, (neighbors, mask) in zip(keys, precomputed):
            for neighbor in neighbors:
                if not non_singletons[neighbor]:
                    ordered.append((key, neighbor, neighbors, mask))
                    break
            else:
                remaining.append(key)

        if not ordered:
            raise RuntimeError(
                "No valid ordering found; try a different hash seed or increase the table size."
            )

        if remaining:
            ordered = self._find_match(remaining) + ordered

        return ordered

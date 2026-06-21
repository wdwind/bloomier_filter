import marshal
import wyhash


class BloomierBase:
    def __init__(self, size: int, num_hashes: int, seed: int = 0):
        self._size = size
        self._num_hashes = num_hashes
        self._seed = seed

    def _find_match(self, keys: list) -> list:
        if not keys:
            return []

        ordered_key_neighbors = []
        non_singletons = self._get_non_singletons(keys)
        remaining = []

        for key in keys:
            neighbors = self._hash(key)
            matched = False
            for neighbor in neighbors:
                if neighbor not in non_singletons:
                    ordered_key_neighbors.append((key, neighbor, neighbors))
                    matched = True
                    break
            if not matched:
                remaining.append(key)

        if not ordered_key_neighbors:
            raise RuntimeError(
                "No valid ordering found; try a different hash seed or increase the table size."
            )

        if remaining:
            ordered_key_neighbors = self._find_match(remaining) + ordered_key_neighbors

        return ordered_key_neighbors

    def _hash(self, key) -> list:
        key_bytes = marshal.dumps(key)
        return [wyhash.hash(key_bytes, self._seed + i,
                            wyhash.make_secret(self._seed + i)) % self._size
                for i in range(self._num_hashes)]

    def _get_mask(self, key) -> int:
        return wyhash.hash(marshal.dumps(key), self._seed + self._num_hashes,
                           wyhash.make_secret(self._seed + self._num_hashes))

    def _get_non_singletons(self, keys) -> set:
        non_singletons = set()
        seen = set()
        for key in keys:
            neighbors = self._hash(key)
            for neighbor in neighbors:
                if neighbor in seen:
                    non_singletons.add(neighbor)
                seen.add(neighbor)
        return non_singletons

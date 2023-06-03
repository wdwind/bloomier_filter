import marshal
import wyhash

class BloomierBase:
    def __init__(self, size: int, num_hashes: int, seed: int = 0):
        self._size = size
        self._num_hashes = num_hashes
        self._seed = seed

    def _find_match(self, keys: list) -> list:
        if len(keys) == 0:
            return []

        ordered_key_neighbors = []
        non_singletons = self._get_non_singletons(keys)
        for key in keys:
            neighbors = self._hash(key)
            for neighbor in self._hash(key):
                if neighbor not in non_singletons:
                    ordered_key_neighbors.append((key, neighbor, neighbors))
                    keys.remove(key)
                    break

        if len(ordered_key_neighbors) == 0:
            raise RuntimeError('Invalid hash methods, try a different hash seed.')

        if len(keys) != 0:
            ordered_key_neighbors = self._find_match(keys) + ordered_key_neighbors

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

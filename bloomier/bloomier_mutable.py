from .bloomier_base import BloomierBase


class BloomierFilterMutable(BloomierBase):
    def __init__(self, size: int, num_hashes: int, seed: int = 0):
        super().__init__(size, num_hashes, seed)
        self._table1 = [0] * size
        # Each table2 slot holds a (key, value) pair once the filter is built.
        # Storing the key lets get()/set() verify that a decoded tweak really
        # belongs to the queried key; without it, an absent key whose decode
        # lands in [0, size) would silently overwrite another key's value.
        self._table2 = [None] * size

    def build_filter(self, input_dict: dict) -> None:
        self._validate(input_dict)
        self._table1 = [0] * self._size
        self._table2 = [None] * self._size
        ordered = self._find_match(list(input_dict.keys()))
        for key, tweak, neighbors, mask in ordered:
            tweak_encoded = tweak ^ mask
            for neighbor in neighbors:
                if neighbor != tweak:
                    tweak_encoded ^= self._table1[neighbor]
            self._table1[tweak] = tweak_encoded
            self._table2[tweak] = (key, input_dict[key])

    def get(self, key):
        neighbors, mask = self._hash_all(key)
        tweak = mask
        for neighbor in neighbors:
            tweak ^= self._table1[neighbor]
        if tweak >= self._size:
            return None
        entry = self._table2[tweak]
        if entry is None or entry[0] != key:
            return None
        return entry[1]

    def set(self, key, val):
        neighbors, mask = self._hash_all(key)
        tweak = mask
        for neighbor in neighbors:
            tweak ^= self._table1[neighbor]
        if tweak >= self._size:
            return False
        entry = self._table2[tweak]
        if entry is None or entry[0] != key:
            return False
        self._table2[tweak] = (key, val)
        return True

    def _validate(self, input_dict: dict) -> None:
        if len(input_dict) > self._size:
            raise ValueError('The size of the input dict should be smaller than the size of the filter.')

from .bloomier_base import BloomierBase


class BloomierFilterMutable(BloomierBase):
    def __init__(self, size: int, num_hashes: int, seed: int = 0):
        super().__init__(size, num_hashes, seed)
        self._table1 = [0] * size
        self._table2 = [0] * size

    def build_filter(self, input_dict: dict) -> None:
        self._validate(input_dict)
        ordered_key_neighbors = self._find_match(list(input_dict.keys()))
        for key, tweak, neighbors in ordered_key_neighbors:
            tweak_encoded = tweak
            tweak_encoded ^= self._get_mask(key)
            for neighbor in neighbors:
                if neighbor != tweak:
                    tweak_encoded ^= self._table1[neighbor]
            self._table1[tweak] = tweak_encoded
            self._table2[tweak] = input_dict[key]

    def get(self, key):
        tweak = self._get_mask(key)
        for neighbor in self._hash(key):
            tweak ^= self._table1[neighbor]
        if tweak >= self._size:
            return None
        return self._table2[tweak]

    def set(self, key, val):
        tweak = self._get_mask(key)
        for neighbor in self._hash(key):
            tweak ^= self._table1[neighbor]
        if tweak >= self._size:
            return False
        else:
            self._table2[tweak] = val
            return True

    def _validate(self, input_dict: dict) -> None:
        if len(input_dict) > self._size:
            raise ValueError('The size of the input dict should be smaller than the size of the filter.')

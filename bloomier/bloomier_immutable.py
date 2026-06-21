from .bloomier_base import BloomierBase


class BloomierFilterImmutable(BloomierBase):
    def __init__(self, size: int, num_hashes: int, val_max_bit_length: int, seed: int = 0):
        super().__init__(size, num_hashes, seed)
        self._val_max_bit_length = val_max_bit_length
        self._table1 = [0] * size

    def build_filter(self, input_dict: dict) -> None:
        self._validate(input_dict)
        self._table1 = [0] * self._size
        ordered = self._find_match(list(input_dict.keys()))
        for key, tweak, neighbors, mask in ordered:
            val = input_dict[key] ^ mask
            for neighbor in neighbors:
                val ^= self._table1[neighbor]
            self._table1[tweak] = val

    def get(self, key):
        neighbors, mask = self._hash_all(key)
        result = mask
        for neighbor in neighbors:
            result ^= self._table1[neighbor]
        if result.bit_length() > self._val_max_bit_length:
            return None
        return result

    def _validate(self, input_dict: dict) -> None:
        if len(input_dict) > self._size:
            raise ValueError('The size of the input dict should be smaller than the size of the filter.')
        for key, val in input_dict.items():
            if not isinstance(val, int):
                raise TypeError('Value should be integers.')
            if val.bit_length() > self._val_max_bit_length:
                raise ValueError(f'Value {val} should be smaller than {1 << self._val_max_bit_length}.')

from .bloomier_base import BloomierBase


class BloomierFilterImmutable(BloomierBase):
    def __init__(self, size: int, num_hashes: int, val_max_bit_length: int, seed: int = 0):
        super().__init__(size, num_hashes, seed)
        self._val_max_bit_length = val_max_bit_length
        self._table1 = [0 for _ in range(size)]

    def construct(self, input_dict: dict):
        self._validate(input_dict)
        ordered_key_neighbors = self._find_match(list(input_dict.keys()))
        for key, tweak, neighbors in ordered_key_neighbors:
            val = input_dict.get(key)
            val ^= self._get_mask(key)
            for neighbor in neighbors:
                val ^= self._table1[neighbor]
            self._table1[tweak] = val

    def get(self, key):
        result = self._get_mask(key)
        for neighbor in self._hash(key):
            result ^= self._table1[neighbor]
        if result.bit_length() > self._val_max_bit_length:
            return None
        return result

    def _validate(self, input_dict: dict):
        if len(input_dict) > self._size:
            raise Exception('The size of the input dict should be smaller than the size of the filter.')
        for key, val in input_dict.items():
            if type(val) != int:
                raise Exception('Value should be integers.')
            if val.bit_length() > self._val_max_bit_length:
                raise Exception(f'Value {val} should be smaller than {1 << self._val_max_bit_length}.')

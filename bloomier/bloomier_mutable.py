from .bloomier_base import BloomierBase


class BloomierFilterMutable(BloomierBase):
    def __init__(self, size: int, num_hashes: int, seed: int = 0):
        super().__init__(size, num_hashes, seed)
        self.__table1 = [0 for _ in range(size)]
        self.__table2 = [0 for _ in range(size)]

    def construct(self, input_dict: dict):
        self.__validate(input_dict)
        ordered_key_neighbors = self._find_match(list(input_dict.keys()))
        for key, tweak, neighbors in ordered_key_neighbors:
            tweak_encoded = tweak
            tweak_encoded ^= self._get_mask(key)
            for neighbor in neighbors:
                if neighbor != tweak:
                    tweak_encoded ^= self.__table1[neighbor]
            self.__table1[tweak] = tweak_encoded
            self.__table2[tweak] = input_dict.get(key)

    def get(self, key):
        tweak = self._get_mask(key)
        for neighbor in self._hash(key):
            tweak ^= self.__table1[neighbor]
        if tweak >= self._size:
            return None
        return self.__table2[tweak]

    def set(self, key, val):
        tweak = self._get_mask(key)
        for neighbor in self._hash(key):
            tweak ^= self.__table1[neighbor]
        if tweak >= self._size:
            return False
        else:
            self.__table2[tweak] = val
            return True

    def __validate(self, input_dict: dict):
        if len(input_dict) > self._size:
            raise Exception('The size of the input dict should be smaller than the size of the filter.')


bf = BloomierFilterMutable(100, 10, 0)


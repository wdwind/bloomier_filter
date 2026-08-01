from .bloomier_base import BloomierBase


class BloomierFilterImmutable(BloomierBase):
    """Immutable Bloomier filter: build once, then query values for keys.

    Values are integers with ``abs(value) < 2 ** val_max_bit_length``, i.e.
    ``value.bit_length() <= val_max_bit_length``.  Negative values are
    supported and recovered exactly: Python's ``^`` is two's-complement XOR,
    so sign is preserved through the encode/decode chain.

    The same bit-length bound doubles as the absent-key sentinel: ``get()``
    returns ``None`` when the decoded value would exceed it.  Per absent-key
    query the false-positive probability is roughly
    ``2 ** (val_max_bit_length + 1) / 2 ** 64`` (negative stored values widen
    the window to both signs).  Keep ``val_max_bit_length`` well below 63;
    values >= 63 are rejected at construction because the sentinel would then
    match most random 64-bit decodes.
    """

    def __init__(self, size: int, num_hashes: int, val_max_bit_length: int, seed: int = 0, key_encoder=None):
        super().__init__(size, num_hashes, seed, key_encoder)
        if not isinstance(val_max_bit_length, int) or val_max_bit_length < 0:
            raise ValueError(
                f"val_max_bit_length must be a non-negative integer, got {val_max_bit_length!r}"
            )
        if val_max_bit_length >= 63:
            raise ValueError(
                f"val_max_bit_length must be < 63 (got {val_max_bit_length}): "
                "the absent-key sentinel is a bit-length bound on ~64-bit hash "
                "results, so larger values would make most absent keys look present."
            )
        self._val_max_bit_length = val_max_bit_length
        self._table1 = [0] * size

    def build_filter(self, input_dict: dict) -> None:
        self._validate(input_dict)
        table1 = self._table1 = [0] * self._size
        ordered = self._find_match(list(input_dict.keys()))
        for key, tweak, neighbors, mask in ordered:
            val = input_dict[key] ^ mask
            for neighbor in neighbors:
                val ^= table1[neighbor]
            table1[tweak] = val

    def get(self, key):
        """Return the stored value for ``key``, or ``None`` if not present.

        The decoded XOR result equals the stored value exactly for built keys
        (two's-complement XOR preserves sign).  Absent keys are detected via
        the ``val_max_bit_length`` bit-length sentinel — see the class
        docstring for the resulting false-positive probability.
        """
        neighbors, mask = self._hash_all(key)
        table1 = self._table1
        result = mask
        for neighbor in neighbors:
            result ^= table1[neighbor]
        if result.bit_length() > self._val_max_bit_length:
            return None
        return result

    def _validate(self, input_dict: dict) -> None:
        """Check the value domain: ints with ``abs(v) < 2 ** val_max_bit_length``."""
        if len(input_dict) > self._size:
            raise ValueError('The size of the input dict should be smaller than the size of the filter.')
        for key, val in input_dict.items():
            if not isinstance(val, int):
                raise TypeError('Value should be integers.')
            if val.bit_length() > self._val_max_bit_length:
                raise ValueError(f'Value {val} should be smaller than {1 << self._val_max_bit_length}.')

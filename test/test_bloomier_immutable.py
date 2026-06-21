import unittest

from bloomier.bloomier_immutable import BloomierFilterImmutable


class BloomierFilterImmutableTest(unittest.TestCase):

    def test_int_dict(self):
        test_dict = {}
        for i in range(1000):
            test_dict[i] = i

        bf = BloomierFilterImmutable(size=10000, num_hashes=10, val_max_bit_length=10, seed=123)
        bf.build_filter(test_dict)

        for i in range(1000):
            self.assertEqual(i, bf.get(i))

        for i in range(1000, 10000):
            self.assertIsNone(bf.get(i))
            self.assertIsNone(bf.get(str(i)))

    def test_str_key_dict(self):
        test_dict = {}
        for i in range(1000):
            test_dict[str(i)] = i + 1

        bf = BloomierFilterImmutable(size=10000, num_hashes=10, val_max_bit_length=10, seed=123)
        bf.build_filter(test_dict)

        for i in range(1000):
            self.assertEqual(test_dict[str(i)], bf.get(str(i)))

        for i in range(1000, 10000):
            self.assertIsNone(bf.get(i))
            self.assertIsNone(bf.get(str(i)))

    def test_filter_full(self):
        bf = BloomierFilterImmutable(1, 2, 8)
        input_dict = {'key1': 5, 'key2': 10}
        self.assertRaises(ValueError, bf.build_filter, input_dict)

    def test_empty_dict(self):
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        bf.build_filter({})
        self.assertIsNone(bf.get(42))
        self.assertIsNone(bf.get("nonexistent"))

    def test_single_key(self):
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8, seed=1)
        bf.build_filter({42: 7})
        self.assertEqual(7, bf.get(42))
        self.assertIsNone(bf.get(43))
        self.assertIsNone(bf.get("other"))

    def test_get_on_unbuilt_filter(self):
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        # Table is all zeros; result is the masked value XOR zero.
        # The result's bit_length may or may not exceed val_max_bit_length,
        # so the outcome is not deterministic, but we can verify it does not crash.
        result = bf.get(42)
        self.assertIn(type(result), (int, type(None)))

    def test_zero_value(self):
        test_dict = {10: 0, 20: 5, 30: 10}
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        bf.build_filter(test_dict)
        self.assertEqual(0, bf.get(10))
        self.assertEqual(5, bf.get(20))
        self.assertEqual(10, bf.get(30))
        self.assertIsNone(bf.get(99))

    def test_value_at_bit_limit(self):
        # val_max_bit_length=4 → max allowed value is 15 (1111 binary)
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=4)
        bf.build_filter({"a": 15})
        self.assertEqual(15, bf.get("a"))

    def test_value_exceeds_bit_limit_raises(self):
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=4)
        with self.assertRaises(ValueError):
            bf.build_filter({"a": 16})  # 16 needs 5 bits

    def test_non_integer_value_raises(self):
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        with self.assertRaises(TypeError):
            bf.build_filter({"a": "string_value"})
        with self.assertRaises(TypeError):
            bf.build_filter({"a": 3.14})
        with self.assertRaises(TypeError):
            bf.build_filter({"a": None})

    def test_negative_values(self):
        # Small negative values (within bit_length) are recovered correctly
        # via bitwise XOR, since Python's int.bit_length() uses abs().
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        bf.build_filter({"a": -1, "b": 5})
        self.assertEqual(-1, bf.get("a"))
        self.assertEqual(5, bf.get("b"))

    def test_negative_value_exceeds_bit_limit_raises(self):
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        with self.assertRaises(ValueError):
            bf.build_filter({"a": -512})  # abs(-512) needs 10 bits > 8
        with self.assertRaises(ValueError):
            bf.build_filter({"a": 512})   # 512 needs 10 bits > 8

    def test_rebuild_filter(self):
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        bf.build_filter({"a": 1, "b": 2})
        self.assertEqual(1, bf.get("a"))
        self.assertEqual(2, bf.get("b"))
        # Rebuild with different data; new keys must work correctly.
        bf.build_filter({"x": 10, "y": 20})
        self.assertEqual(10, bf.get("x"))
        self.assertEqual(20, bf.get("y"))
        # Old keys must not be retrievable after rebuild.
        self.assertIsNone(bf.get("a"))
        self.assertIsNone(bf.get("b"))

    def test_deterministic_same_seed(self):
        d = {i: i % 256 for i in range(50)}
        bf1 = BloomierFilterImmutable(size=500, num_hashes=5, val_max_bit_length=8, seed=42)
        bf2 = BloomierFilterImmutable(size=500, num_hashes=5, val_max_bit_length=8, seed=42)
        bf1.build_filter(d)
        bf2.build_filter(d)
        for k in d:
            self.assertEqual(bf1.get(k), bf2.get(k))
        # Table internals should be identical
        self.assertEqual(bf1._table1, bf2._table1)

    def test_different_seeds_both_work(self):
        d = {i: i % 256 for i in range(50)}
        bf1 = BloomierFilterImmutable(size=500, num_hashes=5, val_max_bit_length=8, seed=1)
        bf2 = BloomierFilterImmutable(size=500, num_hashes=5, val_max_bit_length=8, seed=9999)
        bf1.build_filter(d)
        bf2.build_filter(d)
        for k in d:
            self.assertEqual(bf1.get(k), d[k])
            self.assertEqual(bf2.get(k), d[k])

    def test_nonexistent_key_returns_none(self):
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        bf.build_filter({1: 10, 2: 20, 3: 30})
        self.assertIsNone(bf.get(999))
        self.assertIsNone(bf.get("missing"))
        self.assertIsNone(bf.get(None))
        self.assertIsNone(bf.get(3.14))

    def test_tuple_keys(self):
        d = {(1, 2): 10, (3, 4): 20}
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        bf.build_filter(d)
        self.assertEqual(10, bf.get((1, 2)))
        self.assertEqual(20, bf.get((3, 4)))
        self.assertIsNone(bf.get((5, 6)))

    def test_same_value_multiple_keys(self):
        d = {"a": 5, "b": 5, "c": 5}
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8)
        bf.build_filter(d)
        self.assertEqual(5, bf.get("a"))
        self.assertEqual(5, bf.get("b"))
        self.assertEqual(5, bf.get("c"))


if __name__ == '__main__':
    unittest.main()

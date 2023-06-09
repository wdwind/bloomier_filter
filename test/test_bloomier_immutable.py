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


if __name__ == '__main__':
    unittest.main()

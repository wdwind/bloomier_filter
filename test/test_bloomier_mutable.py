import unittest
from random import random

from bloomier.bloomier_mutable import BloomierFilterMutable


class BloomierFilterMutableTest(unittest.TestCase):

    def test_int_dict(self):
        test_dict = {}
        for i in range(1000):
            test_dict[i] = i + 1

        bf = BloomierFilterMutable(size=10000, num_hashes=10, seed=123)
        bf.construct(test_dict)

        for i in range(1000):
            self.assertEqual(test_dict[i], bf.get(i))

        for i in range(1000, 10000):
            self.assertIsNone(bf.get(i))
            self.assertIsNone(bf.get(str(i)))

    def test_str_dict(self):
        test_dict = {}
        for i in range(1000):
            test_dict[str(i)] = str(i) + str(random())

        bf = BloomierFilterMutable(size=10000, num_hashes=10, seed=123)
        bf.construct(test_dict)

        for i in range(1000):
            self.assertEqual(test_dict[str(i)], bf.get(str(i)))

        for i in range(1000, 10000):
            self.assertIsNone(bf.get(i))
            self.assertIsNone(bf.get(str(i)))

    def test_update(self):
        test_dict = {}
        for i in range(1000):
            test_dict[i] = i + 1

        bf = BloomierFilterMutable(size=10000, num_hashes=10, seed=123)
        bf.construct(test_dict)

        for i in range(1000):
            self.assertEqual(test_dict[i], bf.get(i))

        # Update
        for i in range(1000):
            test_dict[i] = i + 2
            bf.set(i, i + 2)

        for i in range(1000):
            self.assertEqual(test_dict[i], bf.get(i))


if __name__ == '__main__':
    unittest.main()

import unittest
from random import random

from bloomier.bloomier_mutable import BloomierFilterMutable


class BloomierFilterMutableTest(unittest.TestCase):

    # --- Existing tests (preserved) ---

    def test_int_dict(self):
        test_dict = {}
        for i in range(1000):
            test_dict[i] = i + 1

        bf = BloomierFilterMutable(size=10000, num_hashes=10, seed=123)
        bf.build_filter(test_dict)

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
        bf.build_filter(test_dict)

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
        bf.build_filter(test_dict)

        for i in range(1000):
            self.assertEqual(test_dict[i], bf.get(i))

        # Update
        for i in range(1000):
            test_dict[i] = i + 2
            bf.set(i, i + 2)

        for i in range(1000):
            self.assertEqual(test_dict[i], bf.get(i))

    # --- New tests ---

    def test_empty_dict(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({})
        self.assertIsNone(bf.get(42))
        self.assertIsNone(bf.get("nonexistent"))

    def test_single_key(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({42: "val"})
        self.assertEqual("val", bf.get(42))
        self.assertIsNone(bf.get(43))

    def test_get_on_unbuilt_filter(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3)
        result = bf.get(42)
        # With zero-initialized tables the tweak may be out of range,
        # so result is either None or 0 (from table2[0]).
        self.assertIn(result, (None, 0))

    def test_set_on_unbuilt_filter(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3)
        # If tweak resolves to < size, set succeeds; otherwise False.
        # Either way, should not crash.
        result = bf.set(42, "new_val")
        self.assertIn(result, (True, False))

    def test_filter_full_raises(self):
        bf = BloomierFilterMutable(size=1, num_hashes=2)
        with self.assertRaises(ValueError):
            bf.build_filter({"a": 1, "b": 2})

    def test_set_unknown_key(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({"a": 1, "b": 2})
        # Key "c" was not in the build dict, so tweak info not present.
        result = bf.set("c", 99)
        # Typically returns False because tweak is out of range.
        self.assertFalse(result)

    def test_set_overwrite_different_types(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({"a": 1})
        self.assertEqual(1, bf.get("a"))
        # Overwrite with string
        self.assertTrue(bf.set("a", "hello"))
        self.assertEqual("hello", bf.get("a"))
        # Overwrite with float
        self.assertTrue(bf.set("a", 3.14))
        self.assertEqual(3.14, bf.get("a"))
        # Overwrite with None
        self.assertTrue(bf.set("a", None))
        self.assertIsNone(bf.get("a"))

    def test_mixed_value_types_in_build(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({
            "int": 42,
            "str": "hello",
            "float": 3.14,
            "none": None,
            "list": [1, 2, 3],
            "tuple": (4, 5),
            "bool": True,
            "dict": {"nested": "yes"},
        })
        self.assertEqual(42, bf.get("int"))
        self.assertEqual("hello", bf.get("str"))
        self.assertEqual(3.14, bf.get("float"))
        self.assertIsNone(bf.get("none"))
        self.assertEqual([1, 2, 3], bf.get("list"))
        self.assertEqual((4, 5), bf.get("tuple"))
        self.assertEqual(True, bf.get("bool"))
        self.assertEqual({"nested": "yes"}, bf.get("dict"))

    def test_rebuild_filter(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({"a": "first", "b": "second"})
        self.assertEqual("first", bf.get("a"))
        # Rebuild with different data; new keys must work correctly.
        bf.build_filter({"x": "new_x", "y": "new_y"})
        self.assertEqual("new_x", bf.get("x"))
        self.assertEqual("new_y", bf.get("y"))
        # Old keys must not be retrievable after rebuild.
        self.assertIsNone(bf.get("a"))
        self.assertIsNone(bf.get("b"))

    def test_deterministic_same_seed(self):
        d = {f"key{i}": f"val{i}" for i in range(50)}
        bf1 = BloomierFilterMutable(size=500, num_hashes=5, seed=42)
        bf2 = BloomierFilterMutable(size=500, num_hashes=5, seed=42)
        bf1.build_filter(d)
        bf2.build_filter(d)
        for k in d:
            self.assertEqual(bf1.get(k), bf2.get(k))
        self.assertEqual(bf1._table1, bf2._table1)
        self.assertEqual(bf1._table2, bf2._table2)

    def test_different_seeds_both_work(self):
        d = {f"key{i}": f"val{i}" for i in range(50)}
        bf1 = BloomierFilterMutable(size=500, num_hashes=5, seed=1)
        bf2 = BloomierFilterMutable(size=500, num_hashes=5, seed=9999)
        bf1.build_filter(d)
        bf2.build_filter(d)
        for k in d:
            self.assertEqual(bf1.get(k), d[k])
            self.assertEqual(bf2.get(k), d[k])

    def test_nonexistent_key_returns_none(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({1: "a", 2: "b"})
        self.assertIsNone(bf.get(999))
        self.assertIsNone(bf.get("missing"))
        self.assertIsNone(bf.get(None))
        self.assertIsNone(bf.get(3.14))

    def test_tuple_keys(self):
        d = {(1, 2): "first", (3, 4): "second"}
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter(d)
        self.assertEqual("first", bf.get((1, 2)))
        self.assertEqual("second", bf.get((3, 4)))
        self.assertIsNone(bf.get((5, 6)))

    def test_same_value_multiple_keys(self):
        shared = object()
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({"a": shared, "b": shared, "c": shared})
        self.assertIs(shared, bf.get("a"))
        self.assertIs(shared, bf.get("b"))
        self.assertIs(shared, bf.get("c"))

    def test_update_chain(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({"k": 0})
        for i in range(1, 20):
            self.assertTrue(bf.set("k", i))
            self.assertEqual(i, bf.get("k"))

    def test_set_returns_false_for_missing_key(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({"a": 1})
        # "z" is not in the filter — tweak lookup fails
        self.assertFalse(bf.set("z", 99))


if __name__ == '__main__':
    unittest.main()

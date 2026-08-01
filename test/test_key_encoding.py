"""Unit tests for the canonical key encoder and the key_encoder hook."""

import os
import subprocess
import sys
import unittest

from bloomier.bloomier_immutable import BloomierFilterImmutable
from bloomier.bloomier_mutable import BloomierFilterMutable
from bloomier.key_encoding import encode_key

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class EncodeKeyTest(unittest.TestCase):
    """encode_key must be deterministic and injective on supported types."""

    def test_deterministic(self):
        keys = [
            None, True, False,
            0, 1, -1, 2 ** 100, -2 ** 100,
            0.5, -0.0, 1 + 2j,
            "", "abc", "\udcff",           # lone surrogate must survive
            b"", b"abc", bytearray(b"xy"),
            (1, 2), (1, (2, 3)),
            frozenset({1, 2, 3}), frozenset({"a", "b"}),
            range(5), range(1, 10, 2),
        ]
        for k in keys:
            self.assertEqual(encode_key(k), encode_key(k), f"key {k!r}")

    def test_injective(self):
        pairs = [
            (1, True),                  # int vs bool (same dict semantics!)
            (1, 1.0),                   # int vs float
            (0, 0.0),                   # int vs float
            (0.0, -0.0),                # float sign bit
            (1, -1),                    # int sign
            ("a", b"a"),                # str vs bytes
            ("", ()),                   # str vs empty tuple
            (b"", ()),                  # bytes vs empty tuple
            ((1, 2), (2, 1)),           # tuple order matters
            ((1, 2), (1, 2, 3)),
            (frozenset({1, 2}), (1, 2)),  # frozenset vs tuple
            (2 ** 64, 2 ** 64 + 1),
            (1, (1,)),
            (range(3), (0, 3, 1)),   # range vs tuple
            (range(3), range(4)),
            (range(1, 5, 2), range(1, 5, 3)),
        ]
        for a, b in pairs:
            self.assertNotEqual(encode_key(a), encode_key(b), f"{a!r} vs {b!r}")

    def test_frozenset_sorted(self):
        # Elements must be sorted by their encoded bytes, independent of the
        # set's (process-dependent) iteration order.
        fs = frozenset({3, 1, 2})
        parts = sorted(encode_key(e) for e in fs)
        expected = b"\x08" + len(parts).to_bytes(4, "big") + b"".join(parts)
        self.assertEqual(encode_key(fs), expected)
        self.assertEqual(encode_key(frozenset({3, 1, 2})), encode_key(frozenset({2, 1, 3})))

    def test_int_encoding_is_canonical(self):
        # No leading zeros: 0 has an empty magnitude, 256 needs two bytes.
        self.assertEqual(encode_key(0), b"\x02\x00\x00\x00\x00\x00")
        self.assertEqual(encode_key(256), b"\x02\x00\x00\x00\x00\x02\x01\x00")
        self.assertEqual(encode_key(-256), b"\x02\xff\x00\x00\x00\x02\x01\x00")

    def test_float_encoding_is_big_endian(self):
        self.assertEqual(encode_key(0.5), b"\x03\x3f\xe0\x00\x00\x00\x00\x00\x00")
        self.assertNotEqual(encode_key(1 + 2j), encode_key(1.0))

    def test_range_encoding(self):
        # Equal ranges (same start/stop/step) must encode identically.
        self.assertEqual(encode_key(range(0, 3)), encode_key(range(0, 3, 1)))
        self.assertEqual(encode_key(range(3)), b"\x09" + encode_key((0, 3, 1)))

    def test_nested_structures(self):
        self.assertEqual(
            encode_key((1, (2, frozenset({3, 4})))),
            encode_key((1, (2, frozenset({4, 3})))),
        )

    def test_unsupported_type_raises(self):
        for bad in [slice(1, 2), object(), [1, 2], {"a": 1}]:
            with self.assertRaises(TypeError):
                encode_key(bad)

    def test_deterministic_across_processes(self):
        """Identical bytes in fresh processes, despite per-process hash
        randomization changing set iteration order."""
        code = (
            "from bloomier.key_encoding import encode_key; "
            "print(encode_key(('k', 42, frozenset({'a', 'b', 'c'}), -2**70, 0.5)).hex())"
        )
        outputs = {
            subprocess.check_output([sys.executable, "-c", code], cwd=_REPO_ROOT)
            .decode()
            .strip()
            for _ in range(2)
        }
        self.assertEqual(1, len(outputs))


class KeyEncoderHookTest(unittest.TestCase):
    """A custom key_encoder must be used for hashing, consistently."""

    def test_custom_encoder_enables_unsupported_key_types(self):
        class K:
            """A hashable, equal-comparable custom key type."""

            def __init__(self, x):
                self.x = x

            def __hash__(self):
                return hash(self.x)

            def __eq__(self, other):
                return isinstance(other, K) and other.x == self.x

        def enc(key):
            if isinstance(key, K):
                return b"k:" + str(key.x).encode()
            raise TypeError(f"unsupported: {key!r}")

        bf = BloomierFilterMutable(size=1000, num_hashes=5, seed=3, key_encoder=enc)
        bf.build_filter({K(5): "r"})
        self.assertEqual("r", bf.get(K(5)))
        self.assertIsNone(bf.get(K(6)))

    def test_custom_encoder_is_actually_called(self):
        calls = []

        def enc(key):
            calls.append(key)
            return str(key).encode()

        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1, key_encoder=enc)
        bf.build_filter({"a": 1, "b": 2})
        self.assertEqual(1, bf.get("a"))
        self.assertIn("a", calls)
        self.assertIn("b", calls)

    def test_immutable_accepts_key_encoder(self):
        bf = BloomierFilterImmutable(
            size=100, num_hashes=3, val_max_bit_length=8, seed=1,
            key_encoder=lambda k: str(k).encode(),
        )
        bf.build_filter({"a": 5})
        self.assertEqual(5, bf.get("a"))

    def test_non_callable_key_encoder_raises(self):
        with self.assertRaises(TypeError):
            BloomierFilterMutable(size=100, num_hashes=3, key_encoder=123)


if __name__ == '__main__':
    unittest.main()

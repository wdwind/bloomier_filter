"""Regression tests for three bugs that were found and fixed.

These tests deterministically trigger each bug's failure mode.  They failed
before the fixes and must keep passing to prevent regressions — do not weaken
or delete them.

Bug 1 — a key whose hash functions collide with each other (duplicate slots in
         its own neighbor list) used to be silently worked around.  The XOR
         encode/decode invariant is only sound when a key's hash slots are
         distinct, so `_find_match` now fails fast with RuntimeError and tells
         the user to retry with different hash parameters (seed/size/num_hashes)
         instead of swallowing the collision.
Bug 2 — constructor args were never validated: size=0 / size<0 / num_hashes=0
         were accepted at __init__ and only blew up later with confusing errors
         (ZeroDivisionError from "% 0", a misleading "dict too big" ValueError,
         or a bogus "No valid ordering found").  Fixed by validating size and
         num_hashes in BloomierBase.__init__.
Bug 3 — mutable set() on a key that was never built in could decode to a valid
         in-range tweak and silently overwrite another key's value.  Fixed by
         storing the (key, value) pair in table2 and verifying the key on every
         get()/set(); decodes that don't match the stored key are refused.

Bugs 1 and 3 are triggered deterministically by monkey-patching _hash_all: their
natural trigger probability is far too low for reliable black-box triggering
(≈ C(k,2)/size per key, and ≈ size/2**64 respectively).
"""
import unittest
from unittest import mock

from bloomier.bloomier_base import BloomierBase
from bloomier.bloomier_immutable import BloomierFilterImmutable
from bloomier.bloomier_mutable import BloomierFilterMutable

_REAL_HASH = BloomierBase._hash_all


def _hash_with_self_collision(self, key):
    """Hash stand-in: key 'collide' maps every hash function to the same slot 7.

    Every slot of 'collide' is duplicated *within its own* neighbor list, which
    breaks the XOR encode/decode invariant — the filter must reject this key
    with RuntimeError instead of working around it.
    """
    if key == "collide":
        return ([7] * self._num_hashes, 12345)
    return _REAL_HASH(self, key)


class TestBug1SelfCollidingKeyFailsFast(unittest.TestCase):
    """Bug 1: a key whose own hash functions collide must fail fast with a
    clear RuntimeError (retry with different hash parameters), not be silently
    worked around."""

    def test_immutable_build_fails_on_self_colliding_hash(self):
        bf = BloomierFilterImmutable(size=100, num_hashes=3, val_max_bit_length=8, seed=0)
        with mock.patch.object(BloomierBase, "_hash_all", _hash_with_self_collision):
            with self.assertRaises(RuntimeError) as cm:
                bf.build_filter({"collide": 42, "other": 1})
        self.assertIn("collide", str(cm.exception))

    def test_mutable_build_fails_on_self_colliding_hash(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=0)
        with mock.patch.object(BloomierBase, "_hash_all", _hash_with_self_collision):
            with self.assertRaises(RuntimeError) as cm:
                bf.build_filter({"collide": "val", "other": "val2"})
        self.assertIn("collide", str(cm.exception))


class TestBug2NoConstructorValidation(unittest.TestCase):
    """Bug 2: invalid size / num_hashes must raise ValueError at __init__.

    Before the fix the constructor accepted them; the failure only surfaced
    later (or not at all), e.g. ZeroDivisionError from "hash % 0" on size=0, or
    a bogus "No valid ordering found" for num_hashes=0.
    """

    def test_immutable_size_zero_rejected_at_init(self):
        with self.assertRaises(ValueError):
            BloomierFilterImmutable(size=0, num_hashes=3, val_max_bit_length=8)

    def test_immutable_size_negative_rejected_at_init(self):
        with self.assertRaises(ValueError):
            BloomierFilterImmutable(size=-5, num_hashes=3, val_max_bit_length=8)

    def test_immutable_num_hashes_zero_rejected_at_init(self):
        with self.assertRaises(ValueError):
            BloomierFilterImmutable(size=100, num_hashes=0, val_max_bit_length=8)

    def test_mutable_size_zero_rejected_at_init(self):
        with self.assertRaises(ValueError):
            BloomierFilterMutable(size=0, num_hashes=3)

    def test_mutable_num_hashes_zero_rejected_at_init(self):
        with self.assertRaises(ValueError):
            BloomierFilterMutable(size=100, num_hashes=0)


class TestBug3MutableSetCorruptsOnDecodedCollision(unittest.TestCase):
    """Bug 3: set() on a key that was never built in must refuse and must not
    overwrite an existing entry.

    Before the fix, if the absent key's decoded tweak landed in [0, size),
    set() returned True and silently overwrote the value of whichever key owned
    that tweak.  The absent key is forced to hash identically to the built key
    "k" so its decode deterministically yields "k"'s in-range tweak.
    """

    def test_set_on_absent_key_corrupts_built_key(self):
        bf = BloomierFilterMutable(size=100, num_hashes=3, seed=1)
        bf.build_filter({"k": "original"})

        def absent_key_hashes_like_k(self, key):
            if key == "x":
                return _REAL_HASH(self, "k")   # indistinguishable from built key "k"
            return _REAL_HASH(self, key)

        with mock.patch.object(BloomierBase, "_hash_all", absent_key_hashes_like_k):
            result = bf.set("x", "CORRUPTED")   # decodes to "k"'s tweak -> in range
            corrupted = bf.get("k")

        self.assertFalse(result,
                         "set() on an absent key must refuse (return False)")
        self.assertEqual("original", corrupted,
                         "set() on an absent key must not corrupt an existing entry")


if __name__ == '__main__':
    unittest.main()

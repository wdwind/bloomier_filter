import time
import unittest

from bloomier.bloomier_immutable import BloomierFilterImmutable
from bloomier.bloomier_mutable import BloomierFilterMutable


def _timeit(fn, iterations=1000):
    """Time fn over many iterations, return average seconds per call."""
    # Warmup
    for _ in range(10):
        fn()
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - start
    return elapsed / iterations


def _build_time(cls, size, num_hashes, d, **kw):
    """Measure build time for a filter class."""
    def _build():
        bf = cls(size=size, num_hashes=num_hashes, **kw)
        bf.build_filter(d)
    # Fewer iterations for build since it's heavier
    return _timeit(_build, iterations=20)


def _lookup_time(bf, keys, iterations=5000):
    """Measure average get() time across a list of keys."""
    def _lookup():
        for k in keys:
            bf.get(k)
    return _timeit(_lookup, iterations=iterations)


class PerformanceTest(unittest.TestCase):
    """Tests that verify algorithmic scaling properties, not absolute speed.

    These tests use generous thresholds to avoid flakiness on different
    hardware, but will catch severe (e.g. 5-10x) regressions.
    """

    # ------------------------------------------------------------------
    # Build scaling
    # ------------------------------------------------------------------

    def test_immutable_build_scales_linearly(self):
        """Build time should be roughly linear in the number of keys."""
        size = 10000
        d_small = {i: i % 256 for i in range(200)}
        d_large = {i: i % 256 for i in range(1000)}

        t_small = _build_time(BloomierFilterImmutable, size, 3, d_small, val_max_bit_length=8)
        t_large = _build_time(BloomierFilterImmutable, size, 3, d_large, val_max_bit_length=8)

        # 5x the keys (200 → 1000) should take less than 10x the time.
        # A super-linear regression (e.g. accidental O(n²)) would violate this.
        ratio = t_large / t_small
        self.assertLess(ratio, 10.0,
                        f"Build scaling appears super-linear: {ratio:.1f}x for 5x keys")

    def test_mutable_build_scales_linearly(self):
        """Mutable build should also scale linearly."""
        size = 10000
        d_small = {i: str(i) for i in range(200)}
        d_large = {i: str(i) for i in range(1000)}

        t_small = _build_time(BloomierFilterMutable, size, 3, d_small)
        t_large = _build_time(BloomierFilterMutable, size, 3, d_large)

        ratio = t_large / t_small
        self.assertLess(ratio, 10.0,
                        f"Mutable build scaling appears super-linear: {ratio:.1f}x for 5x keys")

    # ------------------------------------------------------------------
    # Lookup is O(1) — independent of filter cardinality
    # ------------------------------------------------------------------

    def test_immutable_lookup_is_constant_time(self):
        """Lookup time should not grow with the number of keys in the filter."""
        size = 5000
        num_hashes = 3

        bf_small = BloomierFilterImmutable(size=size, num_hashes=num_hashes, val_max_bit_length=8)
        bf_small.build_filter({i: i % 256 for i in range(100)})

        bf_large = BloomierFilterImmutable(size=size, num_hashes=num_hashes, val_max_bit_length=8)
        bf_large.build_filter({i: i % 256 for i in range(1000)})

        test_keys = list(range(100))
        t_small = _lookup_time(bf_small, test_keys)
        t_large = _lookup_time(bf_large, test_keys)

        # Looking up 100 keys in a 100-key filter vs a 1000-key filter
        # should be comparable (within 5x to account for variance).
        ratio = max(t_small, t_large) / min(t_small, t_large)
        self.assertLess(ratio, 5.0,
                        f"Lookup not O(1): {ratio:.1f}x difference")

    def test_mutable_lookup_is_constant_time(self):
        """Mutable lookup should also be O(1)."""
        size = 5000
        num_hashes = 3

        bf_small = BloomierFilterMutable(size=size, num_hashes=num_hashes)
        bf_small.build_filter({i: str(i) for i in range(100)})

        bf_large = BloomierFilterMutable(size=size, num_hashes=num_hashes)
        bf_large.build_filter({i: str(i) for i in range(1000)})

        test_keys = list(range(100))
        t_small = _lookup_time(bf_small, test_keys)
        t_large = _lookup_time(bf_large, test_keys)

        ratio = max(t_small, t_large) / min(t_small, t_large)
        self.assertLess(ratio, 5.0,
                        f"Mutable lookup not O(1): {ratio:.1f}x difference")

    # ------------------------------------------------------------------
    # Mutable set() is O(1)
    # ------------------------------------------------------------------

    def test_mutable_set_is_constant_time(self):
        """set() should be O(1) regardless of filter size."""
        size = 5000
        num_hashes = 3

        bf_small = BloomierFilterMutable(size=size, num_hashes=num_hashes)
        bf_small.build_filter({i: 0 for i in range(100)})

        bf_large = BloomierFilterMutable(size=size, num_hashes=num_hashes)
        bf_large.build_filter({i: 0 for i in range(1000)})

        def _set_small():
            for i in range(100):
                bf_small.set(i, i + 1)

        def _set_large():
            for i in range(100):
                bf_large.set(i, i + 1)

        t_small = _timeit(_set_small, iterations=200)
        t_large = _timeit(_set_large, iterations=200)

        ratio = max(t_small, t_large) / min(t_small, t_large)
        self.assertLess(ratio, 5.0,
                        f"Mutable set() not O(1): {ratio:.1f}x difference")

    # ------------------------------------------------------------------
    # Build time vs num_hashes (linear in k)
    # ------------------------------------------------------------------

    def test_build_time_scales_with_num_hashes(self):
        """More hash functions = more work, but should be roughly linear."""
        size = 5000
        d = {i: i % 256 for i in range(200)}

        t3 = _build_time(BloomierFilterImmutable, size, 3, d, val_max_bit_length=8)
        t10 = _build_time(BloomierFilterImmutable, size, 10, d, val_max_bit_length=8)

        # 3.3x the hashes should be less than 10x the time
        ratio = t10 / t3
        self.assertLess(ratio, 10.0,
                        f"Build time scales poorly with num_hashes: {ratio:.1f}x for 10 vs 3 hashes")

    # ------------------------------------------------------------------
    # High load factor stress
    # ------------------------------------------------------------------

    def test_near_capacity_build_completes(self):
        """Building at moderate-to-high load should complete or fail fast."""
        size = 500
        n_keys = 300  # 60% load
        num_hashes = 5
        d = {i: i % 256 for i in range(n_keys)}

        start = time.perf_counter()
        bf = BloomierFilterImmutable(size=size, num_hashes=num_hashes,
                                     val_max_bit_length=8)
        try:
            bf.build_filter(d)
        except RuntimeError:
            pass  # valid failure mode at high load — must not hang
        elapsed = time.perf_counter() - start

        # Must complete (pass or fail) in under 5 seconds
        self.assertLess(elapsed, 5.0,
                        f"Near-capacity build hung: {elapsed:.2f}s")

    def test_empty_filter_lookup_is_fast(self):
        """Looking up keys in empty/unbuilt filter should be fast."""
        bf = BloomierFilterImmutable(size=10000, num_hashes=10, val_max_bit_length=8)

        def _lookup():
            for i in range(1000):
                bf.get(i)

        t = _timeit(_lookup, iterations=100)
        # 1000 lookups with 10 hashes should be well under 200ms on modern hardware
        self.assertLess(t, 0.2,
                        f"Empty filter lookup too slow: {t*1e3:.1f} ms per 1000 keys")

    # ------------------------------------------------------------------
    # Mutable repeated set() stress
    # ------------------------------------------------------------------

    def test_mutable_repeated_set_performance(self):
        """Many set() calls on the same key should remain fast."""
        size = 5000
        bf = BloomierFilterMutable(size=size, num_hashes=3)
        bf.build_filter({0: 0})

        def _repeat_set():
            for i in range(1000):
                bf.set(0, i)

        t = _timeit(_repeat_set, iterations=50)
        # 1000 set() calls should be well under 200ms on modern hardware
        self.assertLess(t, 0.2,
                        f"Repeated set() too slow: {t*1e3:.1f} ms per 1000 sets")


if __name__ == '__main__':
    unittest.main()

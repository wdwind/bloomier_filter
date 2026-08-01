"""Manual benchmark for the Bloomier filter hot paths.

Run with the repo venv:  .venv/Scripts/python.exe test/bench_profile.py
Reports microseconds per lookup / per key.  Named bench_* (not test_*) so
pytest does not collect it.  On power-managed machines the CPU may downclock
under sustained load, so each case is measured in short windows (best-of-3);
for A/B comparisons, interleave old/new runs in fresh processes.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bloomier.bloomier_immutable import BloomierFilterImmutable
from bloomier.bloomier_mutable import BloomierFilterMutable


def make_keys(kind, n):
    if kind == "int":
        return list(range(n))
    if kind == "str":
        return [f"key-{i}-with-some-padding" for i in range(n)]
    if kind == "tuple":
        return [(i, f"tag{i}", i % 7) for i in range(n)]
    if kind == "frozenset":
        return [frozenset([i, i + 1, i + 2, "s"]) for i in range(n)]
    if kind == "longstr":
        return ["x" * 1024 + str(i) for i in range(n)]
    raise ValueError(kind)


def best_of(fn, reps, windows=3):
    best = float("inf")
    for _ in range(windows):
        fn()  # warmup
        t0 = time.perf_counter()
        for _ in range(reps):
            fn()
        best = min(best, (time.perf_counter() - t0) / reps)
    return best


def bench_case(kind):
    n, size = 2000, 20000
    keys = make_keys(kind, n)
    d = {k: i % 1000 for i, k in enumerate(keys)}

    def build():
        bf = BloomierFilterImmutable(size=size, num_hashes=3, val_max_bit_length=10)
        bf.build_filter(d)
    t_build = best_of(build, 10) * 1e6 / n

    bf = BloomierFilterImmutable(size=size, num_hashes=3, val_max_bit_length=10)
    bf.build_filter(d)

    def get_rep():
        for k in keys:
            bf.get(k)
    t_rep = best_of(get_rep, 50) * 1e6 / n

    def get_fresh():
        for i in range(n):
            bf.get((f"fresh-{i}-{kind}", i))
    t_fresh = best_of(get_fresh, 10) * 1e6 / n

    print(f"{kind:<10} build {t_build:6.2f} us/key | get(repeated keys) {t_rep:6.2f} us | "
          f"get(unique keys) {t_fresh:6.2f} us")


def bench_mutable():
    n, size = 2000, 20000
    keys = list(range(n))
    bf = BloomierFilterMutable(size=size, num_hashes=3)
    t0 = time.perf_counter()
    bf.build_filter({k: str(k) for k in keys})
    t_build = (time.perf_counter() - t0) * 1e6 / n

    def mget():
        for k in keys:
            bf.get(k)
    t_g = best_of(mget, 50) * 1e6 / n
    print(f"mutable    build {t_build:6.2f} us/key | get(repeated keys) {t_g:6.2f} us")


if __name__ == "__main__":
    import sys

    cases = sys.argv[1:] or ["int", "str", "tuple", "frozenset", "longstr"]
    for kind in cases:
        bench_case(kind)
    bench_mutable()

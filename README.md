# Bloomier Filter in Python

A Python implementation for the [Bloomier Filter](https://www.cs.princeton.edu/~chazelle/pubs/soda-rev04.pdf) by Chazelle, Bernard, et al.

In detail, both the immutable and the mutable bloomier filters are implemented. The immutable version only supports `int` value, and it can be extended with different types of value with a customized encoder. The mutable version is more powerful and can handle all different types of value by default.

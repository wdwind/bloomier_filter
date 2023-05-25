# Bloomier Filter in Python

A Python implementation of the [Bloomier Filter](https://www.cs.princeton.edu/~chazelle/pubs/soda-rev04.pdf) by Chazelle, Bernard, et al.

In detail, both the immutable and the mutable bloomier filters are implemented. The immutable version only supports `int` value, and it can be extended to support different types of value with customized encoders. The mutable version is more powerful and can handle different types of value by default.

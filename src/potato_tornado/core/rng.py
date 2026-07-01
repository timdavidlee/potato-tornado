"""Deterministic, hierarchically-seeded random number generation.

A single master seed is turned into independent child streams keyed by name, so
adding a new table to a collection does not shift the random draws of the tables
that already existed. This keeps datasets reproducible and stable across edits.
"""

from __future__ import annotations

import hashlib

import numpy as np


class Rng:
    """A named, deterministic random stream built on ``numpy.random.Generator``."""

    __slots__ = ("_generator", "_seed")

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._generator = np.random.default_rng(seed)

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def numpy(self) -> np.random.Generator:
        """The underlying numpy generator, for advanced/direct use."""
        return self._generator

    def child(self, name: str) -> Rng:
        """Derive an independent stream, deterministically keyed by ``name``.

        ``child`` values are stable: the stream for ``"employees"`` is unaffected
        by whether a ``"shifts"`` child was created before or after it.
        """
        digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
        offset = int.from_bytes(digest, "big")
        return Rng((self._seed ^ offset) & 0xFFFFFFFFFFFFFFFF)

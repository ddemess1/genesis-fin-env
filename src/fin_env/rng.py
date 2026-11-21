"""Deterministic RNG with named child streams (no module-level random, no floats)."""
from __future__ import annotations

import hashlib
import random


class DetRng:
    def __init__(self, seed: int, path: tuple = ()):
        h = hashlib.blake2b(repr((seed, tuple(path))).encode(), digest_size=8)
        self._r = random.Random(int.from_bytes(h.digest(), "big"))
        self.seed = seed
        self.path = tuple(path)

    def child(self, *name) -> "DetRng":
        return DetRng(self.seed, self.path + tuple(name))

    def randrange(self, n: int) -> int:
        return self._r.randrange(n)

    def randint(self, a: int, b: int) -> int:
        return a + self._r.randrange(b - a + 1)

    def chance(self, num: int, den: int) -> bool:
        return self._r.randrange(den) < num

    def choice(self, seq):
        """seq MUST be deterministically ordered (sorted)."""
        return seq[self._r.randrange(len(seq))]

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self._r.randrange(i + 1)
            items[i], items[j] = items[j], items[i]

    def pick(self, seq, k: int) -> list:
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]

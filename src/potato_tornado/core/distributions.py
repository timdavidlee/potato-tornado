"""Realistic-distribution helpers layered over a :class:`~potato_tornado.core.rng.Rng`.

These wrap common numpy distributions with signatures that read naturally at the
call site (e.g. money rounded to cents, integers clamped to a range) so that
collection authors can express intent rather than fiddle with array plumbing.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta

import numpy as np

from potato_tornado.core.rng import Rng


class Distributions:
    """Vectorised sampling helpers bound to a single random stream."""

    __slots__ = ("_rng",)

    def __init__(self, rng: Rng) -> None:
        self._rng = rng

    @property
    def _np(self) -> np.random.Generator:
        return self._rng.numpy

    # -- Numeric -----------------------------------------------------------

    def normal(self, n: int, mean: float, sd: float) -> np.ndarray:
        return self._np.normal(mean, sd, size=n)

    def clamped_normal(self, n: int, mean: float, sd: float, low: float, high: float) -> np.ndarray:
        """Normal draws clipped into ``[low, high]``."""
        return np.clip(self._np.normal(mean, sd, size=n), low, high)

    def lognormal(self, n: int, *, median: float, sigma: float) -> np.ndarray:
        """Right-skewed positive values with the given ``median`` (mode of use:
        prices, durations, incomes)."""
        return self._np.lognormal(mean=np.log(median), sigma=sigma, size=n)

    def poisson(self, n: int, lam: float) -> np.ndarray:
        return self._np.poisson(lam, size=n)

    def integers(self, n: int, low: int, high: int) -> np.ndarray:
        """Uniform integers in ``[low, high]`` (inclusive)."""
        return self._np.integers(low, high + 1, size=n)

    def money(self, n: int, *, median: float, sigma: float) -> np.ndarray:
        """Positive, right-skewed monetary amounts rounded to cents."""
        return np.round(self.lognormal(n, median=median, sigma=sigma), 2)

    # -- Categorical -------------------------------------------------------

    def choice(
        self,
        n: int,
        options: Sequence[str],
        weights: Sequence[float] | None = None,
    ) -> np.ndarray:
        p = _normalise(weights, len(options)) if weights is not None else None
        return self._np.choice(np.asarray(options, dtype=object), size=n, p=p)

    def bernoulli(self, n: int, p: float) -> np.ndarray:
        """Boolean array that is ``True`` with probability ``p``."""
        return self._np.random(size=n) < p

    # -- Temporal ----------------------------------------------------------

    def dates_between(self, n: int, start: date, end: date) -> np.ndarray:
        """Uniform random dates in ``[start, end)`` as an object array of ``date``."""
        span = (end - start).days
        offsets = self._np.integers(0, span, size=n)
        return np.array([start + timedelta(days=int(o)) for o in offsets], dtype=object)

    def times_of_day(
        self, n: int, *, peak_hour: float = 12.0, spread_hours: float = 4.0
    ) -> np.ndarray:
        """Clock times clustered around ``peak_hour`` (object array of ``time``)."""
        hours = np.clip(self._np.normal(peak_hour, spread_hours, size=n), 0, 23.999)
        out = np.empty(n, dtype=object)
        for i, h in enumerate(hours):
            minute = int((h % 1) * 60)
            out[i] = time(hour=int(h), minute=minute)
        return out

    def combine(self, days: np.ndarray, clock: np.ndarray) -> np.ndarray:
        """Zip a ``date`` array and a ``time`` array into ``datetime`` values."""
        return np.array(
            [datetime.combine(d, t) for d, t in zip(days, clock, strict=True)], dtype=object
        )


def _normalise(weights: Sequence[float], expected_len: int) -> np.ndarray:
    arr = np.asarray(weights, dtype=float)
    if arr.shape[0] != expected_len:
        raise ValueError(f"expected {expected_len} weights, got {arr.shape[0]}")
    if np.any(arr < 0):
        raise ValueError("weights must be non-negative")
    total = arr.sum()
    if total <= 0:
        raise ValueError("weights must sum to a positive value")
    return arr / total

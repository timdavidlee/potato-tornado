"""Generation configuration shared across collections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    """Knobs that steer a generation run.

    Attributes:
        seed: Master seed. The same seed always yields byte-identical output.
        scale: Multiplier on every collection's base row counts. ``1.0`` is the
            reference size each collection is authored against; ``10.0`` makes an
            (roughly) 10x larger dataset.
        start_date: Inclusive lower bound for generated event dates.
        end_date: Exclusive upper bound for generated event dates.
        pool_dir: Directory of a persisted entity pool (see
            :mod:`potato_tornado.pools`) to sample names / companies / cities
            from. ``None`` (the default) generates those entities from scratch.
    """

    seed: int = 42
    scale: float = 1.0
    start_date: date = date(2024, 1, 1)
    end_date: date = date(2025, 1, 1)
    pool_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"scale must be positive, got {self.scale}")
        if self.end_date <= self.start_date:
            raise ValueError(
                f"end_date ({self.end_date}) must be after start_date ({self.start_date})"
            )

    def scaled(self, base: int) -> int:
        """Scale a base row count, clamped to at least 1."""
        return max(1, round(base * self.scale))

    @property
    def span_days(self) -> int:
        """Number of days in the ``[start_date, end_date)`` window."""
        return (self.end_date - self.start_date).days

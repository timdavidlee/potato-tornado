"""Tests for potato_tornado.core.config."""

from __future__ import annotations

from datetime import date

import pytest

from potato_tornado.core.config import GenerationConfig


@pytest.mark.parametrize(
    ("scale", "base", "expected"),
    [(1.0, 100, 100), (2.5, 100, 250), (0.2, 100, 20), (0.001, 100, 1)],
)
def test_scaled_row_count(scale: float, base: int, expected: int) -> None:
    assert GenerationConfig(scale=scale).scaled(base) == expected


def test_scaled_clamps_to_at_least_one() -> None:
    assert GenerationConfig(scale=1.0).scaled(0) == 1


def test_span_days_counts_the_window() -> None:
    cfg = GenerationConfig(start_date=date(2024, 1, 1), end_date=date(2025, 1, 1))
    assert cfg.span_days == 366  # 2024 is a leap year


def test_rejects_non_positive_scale() -> None:
    with pytest.raises(ValueError, match="scale"):
        GenerationConfig(scale=0)


def test_rejects_inverted_date_window() -> None:
    with pytest.raises(ValueError, match="after"):
        GenerationConfig(start_date=date(2025, 1, 1), end_date=date(2024, 1, 1))

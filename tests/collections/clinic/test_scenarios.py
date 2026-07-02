"""Scenario signals for the clinic collection (the teaching 'answer key')."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def clinic() -> dict[str, pl.DataFrame]:
    return generate("clinic", GenerationConfig(seed=7, scale=0.5))


def test_new_patient_no_show_rate_exceeds_others(clinic: dict[str, pl.DataFrame]) -> None:
    appts = clinic["appointments"]
    by_type = appts.group_by("visit_type").agg((pl.col("status") == "no_show").mean().alias("rate"))
    rates = dict(zip(by_type["visit_type"], by_type["rate"], strict=True))
    other_max = max(rate for visit_type, rate in rates.items() if visit_type != "New Patient")
    assert rates["New Patient"] > 1.4 * other_max

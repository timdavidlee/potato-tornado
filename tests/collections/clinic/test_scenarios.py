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


def test_overall_slot_utilisation_is_about_two_thirds(clinic: dict[str, pl.DataFrame]) -> None:
    booked = clinic["slots"]["is_booked"]
    rate = float(booked.sum()) / booked.len()
    assert 0.60 < rate < 0.75


def test_utilisation_concentrates_in_demand_heavy_specialties(
    clinic: dict[str, pl.DataFrame],
) -> None:
    slots = clinic["slots"].join(
        clinic["providers"].select("provider_id", "specialty"), on="provider_id"
    )
    heavy = slots.filter(pl.col("specialty").is_in(["Dermatology", "Cardiology", "Orthopedics"]))[
        "is_booked"
    ]
    spare = slots.filter(pl.col("specialty").is_in(["Pediatrics", "Family Medicine"]))["is_booked"]
    heavy_util = float(heavy.sum()) / heavy.len()
    spare_util = float(spare.sum()) / spare.len()
    assert heavy_util > spare_util + 0.15

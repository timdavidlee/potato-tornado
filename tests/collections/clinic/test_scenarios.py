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


def test_reminded_appointments_no_show_far_less(clinic: dict[str, pl.DataFrame]) -> None:
    appts = clinic["appointments"]
    by_rem = appts.group_by("reminder_sent").agg(
        (pl.col("status") == "no_show").mean().alias("rate")
    )
    rates = dict(zip(by_rem["reminder_sent"], by_rem["rate"], strict=True))
    # Un-reminded ≈ 0.20 vs reminded ≈ 0.085 at seed 7 / scale 0.5 — a ~2.35x spread.
    assert rates[False] > 2.0 * rates[True]


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


def _appts_per_patient(clinic: dict[str, pl.DataFrame]) -> pl.DataFrame:
    per = clinic["appointments"].group_by("patient_id").agg(pl.len().alias("appts"))
    return (
        clinic["patients"]
        .join(per, on="patient_id", how="left")
        .with_columns(pl.col("appts").fill_null(0))
    )


def test_chronic_patients_book_a_disproportionate_share(clinic: dict[str, pl.DataFrame]) -> None:
    by = (
        _appts_per_patient(clinic)
        .group_by("chronic_flag")
        .agg(pl.len().alias("pats"), pl.col("appts").sum().alias("appts"))
    )
    per_capita = {
        row["chronic_flag"]: row["appts"] / row["pats"] for row in by.iter_rows(named=True)
    }
    # Chronic minority (≈22% of the panel) books ≈2.4x per capita at seed 7 / scale 0.5.
    assert per_capita[True] > 1.8 * per_capita[False]


def test_risk_score_correlates_with_visit_count(clinic: dict[str, pl.DataFrame]) -> None:
    corr = _appts_per_patient(clinic).select(pl.corr("risk_score", "appts")).item()
    # Continuous companion of the chronic tilt: ≈0.38 at seed 7 / scale 0.5, clearing 0.30.
    assert corr > 0.30


def test_allowed_ratio_falls_from_commercial_to_medicaid(clinic: dict[str, pl.DataFrame]) -> None:
    inv = clinic["invoices"]
    allowed = (pl.col("charge") - pl.col("adjustment_amount") - pl.col("denied_amount")) / pl.col(
        "charge"
    )
    ratio = inv.group_by("payer").agg(allowed.mean().alias("allowed")).sort("allowed")
    # Medicaid reimburses least (≈0.71), self-pay most (≈0.95, yet collects worst — see AR).
    assert ratio["payer"].to_list() == ["Medicaid", "Medicare", "Commercial", "Self-pay"]

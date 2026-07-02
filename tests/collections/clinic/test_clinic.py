"""Tests for the clinic collection.

Referential-integrity and workflow invariants (from ``realism-guidance.md``) plus
the planted signals (from ``scenarios/``). One behaviour per test; the collection
is generated once per module at a small scale.
"""

from __future__ import annotations

from typing import cast

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def clinic() -> dict[str, pl.DataFrame]:
    return generate("clinic", GenerationConfig(seed=42, scale=0.5))


# -- Referential integrity / workflow invariants ---------------------------


def test_slots_reference_providers(clinic: dict[str, pl.DataFrame]) -> None:
    provider_ids = set(clinic["providers"]["provider_id"].to_list())
    assert set(clinic["slots"]["provider_id"].to_list()) <= provider_ids


def test_appointments_book_only_booked_slots(clinic: dict[str, pl.DataFrame]) -> None:
    booked = set(clinic["slots"].filter(pl.col("is_booked"))["slot_id"].to_list())
    assert set(clinic["appointments"]["slot_id"].to_list()) == booked


def test_no_double_booking(clinic: dict[str, pl.DataFrame]) -> None:
    appts = clinic["appointments"]
    assert appts["slot_id"].n_unique() == appts.height


def test_appointment_provider_matches_its_slot(clinic: dict[str, pl.DataFrame]) -> None:
    slot_provider = dict(
        zip(
            clinic["slots"]["slot_id"].to_list(),
            clinic["slots"]["provider_id"].to_list(),
            strict=True,
        )
    )
    appts = clinic["appointments"]
    mismatched = appts.filter(
        pl.col("provider_id") != pl.col("slot_id").replace_strict(slot_provider)
    )
    assert mismatched.height == 0


def test_visits_derive_only_from_completed_appointments(clinic: dict[str, pl.DataFrame]) -> None:
    completed = set(
        clinic["appointments"].filter(pl.col("status") == "completed")["appointment_id"].to_list()
    )
    assert set(clinic["visits"]["appointment_id"].to_list()) == completed


def test_every_visit_has_one_invoice(clinic: dict[str, pl.DataFrame]) -> None:
    assert clinic["invoices"]["visit_id"].to_list() == clinic["visits"]["visit_id"].to_list()


def test_billing_identity_holds(clinic: dict[str, pl.DataFrame]) -> None:
    inv = clinic["invoices"]
    off = inv.filter((pl.col("charge") - pl.col("amount_paid") - pl.col("balance")).abs() > 0.001)
    assert off.height == 0


def test_invoice_status_matches_balance(clinic: dict[str, pl.DataFrame]) -> None:
    inv = clinic["invoices"]
    wrong = inv.filter(
        ((pl.col("balance") <= 0.0) & (pl.col("status") != "paid"))
        | ((pl.col("balance") > 0.0) & (pl.col("status") != "outstanding"))
    )
    assert wrong.height == 0


def test_lead_days_within_bounds(clinic: dict[str, pl.DataFrame]) -> None:
    appts = clinic["appointments"]
    assert appts.filter((pl.col("lead_days") < 0) | (pl.col("lead_days") > 120)).height == 0


# -- Planted signals -------------------------------------------------------


def test_no_show_rises_with_lead_time(clinic: dict[str, pl.DataFrame]) -> None:
    appts = clinic["appointments"]
    short = appts.filter(pl.col("lead_days") < 15)
    long = appts.filter(pl.col("lead_days") >= 30)
    short_rate = cast(float, (short["status"] == "no_show").mean())
    long_rate = cast(float, (long["status"] == "no_show").mean())
    assert long_rate > short_rate


def test_minor_procedures_run_over_scheduled_time(clinic: dict[str, pl.DataFrame]) -> None:
    procedures = clinic["visits"].filter(pl.col("visit_type") == "Minor Procedure")
    actual = cast(float, procedures["actual_minutes"].mean())
    scheduled = cast(float, procedures["scheduled_minutes"].mean())
    assert actual / scheduled > 1.1


def test_self_pay_dominates_accounts_receivable(clinic: dict[str, pl.DataFrame]) -> None:
    inv = clinic["invoices"]
    self_pay_ar = cast(float, inv.filter(pl.col("payer") == "Self-pay")["balance"].sum())
    total_ar = cast(float, inv["balance"].sum())
    assert self_pay_ar / total_ar > 0.35


def test_provider_utilisation_varies(clinic: dict[str, pl.DataFrame]) -> None:
    util = clinic["slots"].group_by("provider_id").agg(pl.col("is_booked").mean().alias("u"))
    assert cast(float, util["u"].max()) - cast(float, util["u"].min()) > 0.15


def test_frequent_patients_concentrate_bookings(clinic: dict[str, pl.DataFrame]) -> None:
    per_patient = (
        clinic["appointments"]
        .group_by("patient_id")
        .agg(pl.len().alias("appts"))
        .sort("appts", descending=True)
    )
    top_decile = max(1, per_patient.height // 10)
    total = cast(int, per_patient["appts"].sum())
    top_share = cast(int, per_patient.head(top_decile)["appts"].sum()) / total
    assert top_share > 0.25  # skewed booking; a uniform draw would sit near ~0.15


def test_winter_volume_exceeds_summer(clinic: dict[str, pl.DataFrame]) -> None:
    appts = clinic["appointments"].with_columns(pl.col("scheduled_at").dt.month().alias("m"))
    winter = appts.filter(pl.col("m").is_in([12, 1, 2])).height
    summer = appts.filter(pl.col("m").is_in([6, 7, 8])).height
    assert winter / summer > 1.10  # seasonal peak; a uniform calendar would sit near ~1.0


def test_appointment_volume_grows_year_over_year(clinic: dict[str, pl.DataFrame]) -> None:
    by_year = (
        clinic["appointments"]
        .with_columns(pl.col("scheduled_at").dt.year().alias("y"))
        .group_by("y")
        .len()
        .sort("y")
    )
    first = cast(int, by_year["len"][0])
    last = cast(int, by_year["len"][-1])
    assert last > first * 1.05  # upward trend; ~+8%/yr, year 3 well above year 1


def test_charge_per_visit_varies_by_procedure(clinic: dict[str, pl.DataFrame]) -> None:
    inv = clinic["invoices"].join(
        clinic["visits"].select(["visit_id", "visit_type"]), on="visit_id"
    )
    avg = inv.group_by("visit_type").agg(pl.col("charge").mean().alias("c"))
    assert cast(float, avg["c"].max()) / cast(float, avg["c"].min()) > 3.0  # ~$340 vs ~$90


def test_visit_mix_varies_by_specialty(clinic: dict[str, pl.DataFrame]) -> None:
    appts = clinic["appointments"].join(
        clinic["providers"].select(["provider_id", "specialty"]), on="provider_id"
    )
    minor = appts.group_by("specialty").agg(
        (pl.col("visit_type") == "Minor Procedure").mean().alias("m")
    )
    spread = cast(float, minor["m"].max()) - cast(float, minor["m"].min())
    assert spread > 0.15  # procedure-heavy specialties ~0.22+, paediatrics ~0.00


def test_arrival_delay_grows_through_the_day(clinic: dict[str, pl.DataFrame]) -> None:
    visits = clinic["visits"].join(
        clinic["appointments"].select(["appointment_id", "scheduled_at"]), on="appointment_id"
    )
    visits = visits.with_columns(pl.col("scheduled_at").dt.hour().alias("h"))
    early = cast(float, visits.filter(pl.col("h") < 10)["arrival_delay_min"].mean())
    late = cast(float, visits.filter(pl.col("h") >= 15)["arrival_delay_min"].mean())
    assert late - early > 6.0  # clinic runs behind; ~13 min swing across the day

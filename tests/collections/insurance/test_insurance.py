"""Tests for the insurance collection.

These pin the realism invariants from ``realism-guidance.md`` (referential
integrity, the payment-iff-settled rule, payout bounds, temporal ordering,
non-negativity) — the rules that must hold regardless of any teaching signal.
Subset-signal magnitudes live in ``test_scenarios.py``.
"""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def insurance() -> dict[str, pl.DataFrame]:
    return generate("insurance", GenerationConfig(seed=13, scale=0.3))


def test_policies_reference_policyholders(insurance: dict[str, pl.DataFrame]) -> None:
    holder_ids = set(insurance["policyholders"]["policyholder_id"].to_list())
    assert set(insurance["policies"]["policyholder_id"].to_list()) <= holder_ids


def test_policies_reference_brokers(insurance: dict[str, pl.DataFrame]) -> None:
    broker_ids = set(insurance["brokers"]["broker_id"].to_list())
    assert set(insurance["policies"]["broker_id"].to_list()) <= broker_ids


def test_claims_reference_policies(insurance: dict[str, pl.DataFrame]) -> None:
    policy_ids = set(insurance["policies"]["policy_id"].to_list())
    assert set(insurance["claims"]["policy_id"].to_list()) <= policy_ids


def test_payments_exist_iff_claim_is_settled(insurance: dict[str, pl.DataFrame]) -> None:
    settled = set(
        insurance["claims"]
        .filter(pl.col("status").is_in(["approved", "partial"]))["claim_id"]
        .to_list()
    )
    paid = set(insurance["claim_payments"]["claim_id"].to_list())
    assert paid == settled


def test_at_most_one_payment_per_claim(insurance: dict[str, pl.DataFrame]) -> None:
    payments = insurance["claim_payments"]
    assert payments["claim_id"].n_unique() == payments.height


def test_payout_never_exceeds_the_approved_cap(insurance: dict[str, pl.DataFrame]) -> None:
    priced = (
        insurance["claim_payments"]
        .join(insurance["claims"].select("claim_id", "policy_id", "reported_amount"), on="claim_id")
        .join(
            insurance["policies"].select("policy_id", "coverage_limit", "deductible"),
            on="policy_id",
        )
        .with_columns(
            (pl.min_horizontal("reported_amount", "coverage_limit") - pl.col("deductible"))
            .clip(lower_bound=0.0)
            .alias("cap")
        )
    )
    over_cap = priced.filter(pl.col("paid_amount") > pl.col("cap") + 0.01)
    assert over_cap.height == 0


def test_paid_amount_is_non_negative(insurance: dict[str, pl.DataFrame]) -> None:
    assert insurance["claim_payments"].filter(pl.col("paid_amount") < 0).height == 0


def test_paid_date_is_on_or_after_claim_date(insurance: dict[str, pl.DataFrame]) -> None:
    dated = insurance["claim_payments"].join(
        insurance["claims"].select("claim_id", "claim_date"), on="claim_id"
    )
    assert dated.filter(pl.col("paid_date") < pl.col("claim_date")).height == 0


def test_coverage_limit_exceeds_deductible(insurance: dict[str, pl.DataFrame]) -> None:
    policies = insurance["policies"]
    assert policies.filter(pl.col("coverage_limit") <= pl.col("deductible")).height == 0


def test_reported_amount_and_premium_are_positive(insurance: dict[str, pl.DataFrame]) -> None:
    reported_ok = insurance["claims"].filter(pl.col("reported_amount") <= 0).height == 0
    premium_ok = insurance["policies"].filter(pl.col("annual_premium") <= 0).height == 0
    assert reported_ok and premium_ok

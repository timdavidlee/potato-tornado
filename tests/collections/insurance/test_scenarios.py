"""Scenario signals for the insurance collection (the teaching 'answer key')."""

from __future__ import annotations

from typing import cast

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def insurance() -> dict[str, pl.DataFrame]:
    return generate("insurance", GenerationConfig(seed=7, scale=0.5))


def test_only_a_minority_of_policies_claim(insurance: dict[str, pl.DataFrame]) -> None:
    claim_rate = insurance["claims"]["policy_id"].n_unique() / insurance["policies"].height
    assert 0.08 < claim_rate < 0.18


def test_severity_is_heavy_tailed(insurance: dict[str, pl.DataFrame]) -> None:
    reported = insurance["claims"]["reported_amount"]
    p95 = cast(float, reported.quantile(0.95))
    median = cast(float, reported.median())
    assert p95 > 3 * median


def test_loss_ratio_rises_with_risk_tier(insurance: dict[str, pl.DataFrame]) -> None:
    holders = insurance["policyholders"].select("policyholder_id", "risk_tier")
    policies = insurance["policies"].join(holders, on="policyholder_id")
    premium = policies.group_by("risk_tier").agg(pl.col("annual_premium").sum().alias("prem"))
    paid = (
        insurance["claim_payments"]
        .join(insurance["claims"].select("claim_id", "policy_id"), on="claim_id")
        .join(policies.select("policy_id", "risk_tier"), on="policy_id")
        .group_by("risk_tier")
        .agg(pl.col("paid_amount").sum().alias("paid"))
    )
    ratios = premium.join(paid, on="risk_tier").with_columns(
        (pl.col("paid") / pl.col("prem")).alias("loss_ratio")
    )
    lr = dict(zip(ratios["risk_tier"], ratios["loss_ratio"], strict=True))
    assert cast(float, lr["high_risk"]) > cast(float, lr["preferred"])


def test_total_paid_runs_below_total_reported(insurance: dict[str, pl.DataFrame]) -> None:
    reported = cast(float, insurance["claims"]["reported_amount"].sum())
    paid = cast(float, insurance["claim_payments"]["paid_amount"].sum())
    assert 0.4 < paid / reported < 0.8


def test_denied_claims_have_no_payment(insurance: dict[str, pl.DataFrame]) -> None:
    denied = set(insurance["claims"].filter(pl.col("status") == "denied")["claim_id"].to_list())
    paid = set(insurance["claim_payments"]["claim_id"].to_list())
    assert denied.isdisjoint(paid)

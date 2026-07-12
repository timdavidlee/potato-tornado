"""Scenario signals for the insurance collection (the teaching 'answer key')."""

from __future__ import annotations

from datetime import date
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


_DAYS_PER_MONTH = 30.4


def _claims_per_inforce_by_year(frames: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Per calendar year: raw claim count, in-force policy count, and their ratio.

    A policy is "in force" in year Y when its term — ``start_date`` through
    ``start_date + term_months * 30.4`` days — overlaps ``[Jan 1, Dec 31]`` of Y. One
    row per year with columns ``year``, ``claims``, ``in_force``,
    ``claims_per_inforce``, sorted ascending by year.
    """
    claims = frames["claims"].with_columns(pl.col("claim_date").dt.year().alias("year"))
    raw = claims.group_by("year").agg(pl.len().alias("claims"))
    policies = frames["policies"].with_columns(
        (
            pl.col("start_date")
            + pl.duration(days=(pl.col("term_months") * _DAYS_PER_MONTH).round().cast(pl.Int64))
        ).alias("term_end")
    )
    years = raw["year"].sort()
    in_force = pl.DataFrame(
        {
            "year": years,
            "in_force": [
                policies.filter(
                    (pl.col("start_date") <= date(y, 12, 31))
                    & (pl.col("term_end") >= date(y, 1, 1))
                ).height
                for y in years
            ],
        }
    )
    return (
        raw.join(in_force, on="year")
        .with_columns((pl.col("claims") / pl.col("in_force")).alias("claims_per_inforce"))
        .sort("year")
    )


def test_claim_frequency_flat_despite_rising_counts(insurance: dict[str, pl.DataFrame]) -> None:
    by_year = _claims_per_inforce_by_year(insurance)
    raw = by_year["claims"].to_list()
    cpif = by_year["claims_per_inforce"].to_list()
    # Raw counts ramp materially (64 -> 112, ~1.75x — the naive "book deteriorating" read),
    # but once normalized by the in-force the per-policy frequency is flat (0.072-0.079,
    # spread ~1.09): the rise is exposure growth, not rising risk.
    raw_ramp = raw[-1] / raw[0]
    freq_spread = max(cpif) / min(cpif)
    assert raw_ramp > 1.4 and freq_spread < 1.25


def test_litigated_claims_cost_more_and_settle_slower(insurance: dict[str, pl.DataFrame]) -> None:
    joined = insurance["claim_payments"].join(
        insurance["claims"].select("claim_id", "litigated"), on="claim_id"
    )
    lit = joined.filter(pl.col("litigated"))
    non = joined.filter(~pl.col("litigated"))
    paid_ratio = cast(float, lit["paid_amount"].mean()) / cast(float, non["paid_amount"].mean())
    cycle_ratio = cast(float, lit["settlement_days"].mean()) / cast(
        float, non["settlement_days"].mean()
    )
    # The litigation tax is two-dimensional: the litigated subset runs a heavier paid_amount
    # AND a longer settlement cycle than non-litigated peers. Measured at seed=7 scale=0.5:
    # paid ≈ 1.87x, settlement ≈ 1.69x. Both clearly clear the flat ~1.0 baseline; the bounds
    # stay loose enough for the small litigated subset's seed noise, tight enough to catch a
    # regression back to flat.
    assert paid_ratio > 1.4 and cycle_ratio > 1.35

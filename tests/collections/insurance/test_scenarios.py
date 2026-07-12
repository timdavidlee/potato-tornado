"""Scenario signals for the insurance collection (the teaching 'answer key')."""

from __future__ import annotations

import re
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


# -- Document scenario: gradual water losses settle below sudden ---------------------
# The sudden/gradual coverage trigger lives ONLY in the free-text adjuster note, not in a
# structured column, so it must be parsed from `adjuster_notes.body` before the payout gap
# is visible. See `scenarios/gradual-water-losses-settle-below-sudden.md`.

_GRADUAL_CUES = re.compile(r"seepage|gradual|long-term|wear|deterioration|over time|maintenance")
_SUDDEN_CUES = re.compile(r"burst|sudden|accidental discharge|ruptured|sprang a leak")
_DOLLAR = re.compile(r"\$([\d,]+)")


def _classify_cause(body: str) -> str | None:
    """Recover the sudden/gradual water-loss cause from a note's wording (else None)."""
    if _GRADUAL_CUES.search(body):
        return "gradual"
    if _SUDDEN_CUES.search(body):
        return "sudden"
    return None


def _parse_estimate(body: str) -> int:
    """Pull the first dollar figure (the rendered loss estimate) out of a note."""
    match = _DOLLAR.search(body)
    if match is None:
        raise ValueError(f"no dollar figure in note: {body!r}")
    return int(match.group(1).replace(",", ""))


def _water_notes(frames: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """The `adjuster_notes` rows whose claim is a `water_damage` claim."""
    water_ids = frames["claims"].filter(pl.col("peril") == "water_damage")["claim_id"].to_list()
    return frames["adjuster_notes"].filter(pl.col("claim_id").is_in(water_ids))


def test_adjuster_note_cause_is_recoverable_from_prose(insurance: dict[str, pl.DataFrame]) -> None:
    # Layer 1a (round-trip): the cause a student parses from the note text must equal the
    # withheld `water_cause` answer key for every water-damage note — the signal is genuinely
    # legible from the prose and the parser survives all three template variants.
    notes = _water_notes(insurance)
    mismatches = sum(
        _classify_cause(body) != cause
        for body, cause in zip(notes["body"].to_list(), notes["water_cause"].to_list(), strict=True)
    )
    assert mismatches == 0


def test_adjuster_note_estimate_reconciles_with_reported_amount(
    insurance: dict[str, pl.DataFrame],
) -> None:
    # Layer 1b (round-trip): the dollar figure the note renders is `claims.reported_amount`
    # (rounded to the dollar), so the parsed estimate reconciles against the structured column
    # to within the rounding — no answer leaked, the estimate is real.
    notes = insurance["adjuster_notes"]
    reported = dict(
        zip(
            insurance["claims"]["claim_id"].to_list(),
            insurance["claims"]["reported_amount"].to_list(),
            strict=True,
        )
    )
    max_error = max(
        abs(_parse_estimate(body) - reported[claim_id])
        for claim_id, body in zip(notes["claim_id"].to_list(), notes["body"].to_list(), strict=True)
    )
    assert max_error < 1.0


def test_gradual_water_losses_settle_below_sudden(insurance: dict[str, pl.DataFrame]) -> None:
    # Layer 2 (signal): aggregate the real payout by the *parsed* cause. Denied/open claims
    # have no payment, so a left join treats the missing side as $0.
    notes = _water_notes(insurance)
    parsed = notes.select("claim_id").with_columns(
        pl.Series("cause", [_classify_cause(body) for body in notes["body"].to_list()])
    )
    ratios = (
        parsed.join(insurance["claims"].select("claim_id", "reported_amount"), on="claim_id")
        .join(
            insurance["claim_payments"].select("claim_id", "paid_amount"), on="claim_id", how="left"
        )
        .with_columns(pl.col("paid_amount").fill_null(0.0))
        .group_by("cause")
        .agg((pl.col("paid_amount").sum() / pl.col("reported_amount").sum()).alias("ratio"))
    )
    ratio = dict(zip(ratios["cause"].to_list(), ratios["ratio"].to_list(), strict=True))
    gradual = cast(float, ratio["gradual"])
    sudden = cast(float, ratio["sudden"])
    # Measured at seed=7 scale=0.5: gradual ≈ 0.32, sudden ≈ 0.55 — a ~1.7x gap inside a single
    # `peril`. Gradual losses (excluded wear/seepage) settle far below sudden accidental
    # discharge (a covered cause). Bounds are wide enough for the small water subset's seed
    # noise, tight enough to catch a regression back to the flat book ratio (~0.63 for both).
    assert gradual < 0.40 < sudden and sudden / gradual > 1.4

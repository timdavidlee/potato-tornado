"""Tests for the insurance collection.

These pin the realism invariants from ``realism-guidance.md`` (referential
integrity, the payment-iff-settled rule, payout bounds, temporal ordering,
non-negativity) — the rules that must hold regardless of any teaching signal.
Subset-signal magnitudes live in ``test_scenarios.py``.
"""

from __future__ import annotations

from datetime import timedelta

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate

# Days-per-month the claims generator uses to turn `term_months` into a term end.
_DAYS_PER_MONTH = 30.4


@pytest.fixture(scope="module")
def insurance() -> dict[str, pl.DataFrame]:
    return generate("insurance", GenerationConfig(seed=13, scale=0.3))


@pytest.fixture(scope="module")
def insurance_full() -> dict[str, pl.DataFrame]:
    # Full scale for distribution-shape checks that need enough claims per time
    # bucket to be stable across seeds.
    return generate("insurance", GenerationConfig(seed=7, scale=1.0))


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


def test_claim_date_on_or_after_policy_start(insurance: dict[str, pl.DataFrame]) -> None:
    dated = insurance["claims"].join(
        insurance["policies"].select("policy_id", "start_date"), on="policy_id"
    )
    assert dated.filter(pl.col("claim_date") < pl.col("start_date")).height == 0


def test_claim_date_within_term_and_run_window(insurance: dict[str, pl.DataFrame]) -> None:
    end_date = GenerationConfig().end_date
    dated = insurance["claims"].join(
        insurance["policies"].select("policy_id", "start_date", "term_months"), on="policy_id"
    )
    term_end = pl.col("start_date") + pl.duration(
        days=(pl.col("term_months") * _DAYS_PER_MONTH).round().cast(pl.Int64)
    )
    latest = pl.min_horizontal(term_end, pl.lit(end_date))
    assert dated.filter(pl.col("claim_date") > latest).height == 0


def test_claims_not_piled_at_window_end(insurance_full: dict[str, pl.DataFrame]) -> None:
    # Claim counts scale with each policy's *in-window* exposure, so the final 90
    # days (in-force is stable by then) hold no more claims than the preceding 90 —
    # regression guard against counting a full contractual term into a clipped tail.
    end_date = GenerationConfig().end_date
    claim_date = pl.col("claim_date")
    last90 = insurance_full["claims"].filter(claim_date >= end_date - timedelta(days=90)).height
    prior90 = (
        insurance_full["claims"]
        .filter(
            (claim_date >= end_date - timedelta(days=180))
            & (claim_date < end_date - timedelta(days=90))
        )
        .height
    )
    assert last90 < 1.5 * prior90


def test_coverage_limit_exceeds_deductible(insurance: dict[str, pl.DataFrame]) -> None:
    policies = insurance["policies"]
    assert policies.filter(pl.col("coverage_limit") <= pl.col("deductible")).height == 0


def _auto_standard(frames: dict[str, pl.DataFrame]) -> pl.DataFrame:
    # The largest product/tier cell — isolates the premium↔coverage/deductible
    # co-movement from the (independent) product and tier level shifts.
    return (
        frames["policies"]
        .join(frames["policyholders"].select("policyholder_id", "risk_tier"), on="policyholder_id")
        .filter((pl.col("product") == "auto") & (pl.col("risk_tier") == "standard"))
    )


def test_premium_rises_with_coverage(insurance: dict[str, pl.DataFrame]) -> None:
    sub = _auto_standard(insurance)
    by_cov = sub.group_by("coverage_limit").agg(pl.col("annual_premium").mean().alias("m"))
    means = by_cov.sort("coverage_limit")["m"].to_list()
    assert means[-1] > means[0]


def test_premium_falls_with_higher_deductible(insurance_full: dict[str, pl.DataFrame]) -> None:
    sub = _auto_standard(insurance_full)
    by_ded = sub.group_by("deductible").agg(pl.col("annual_premium").mean().alias("m"))
    means = by_ded.sort("deductible")["m"].to_list()
    assert means[0] > means[-1]


def test_reported_amount_and_premium_are_positive(insurance: dict[str, pl.DataFrame]) -> None:
    reported_ok = insurance["claims"].filter(pl.col("reported_amount") <= 0).height == 0
    premium_ok = insurance["policies"].filter(pl.col("annual_premium") <= 0).height == 0
    assert reported_ok and premium_ok


def test_peril_mix_is_skewed_not_uniform(insurance_full: dict[str, pl.DataFrame]) -> None:
    # Perils are weighted, not uniform (uniform share would be 1/6 ≈ 0.167): collision
    # is the common peril (~0.28) and fire the rare one (~0.06).
    mix = insurance_full["claims"]["peril"].value_counts(normalize=True)
    share = dict(zip(mix["peril"].to_list(), mix["proportion"].to_list(), strict=True))
    assert share["fire"] < 0.10 < 0.25 < share["collision"]


def test_claims_reference_adjusters(insurance: dict[str, pl.DataFrame]) -> None:
    adjuster_ids = set(insurance["adjusters"]["adjuster_id"].to_list())
    assert set(insurance["claims"]["adjuster_id"].to_list()) <= adjuster_ids


def test_adjuster_team_in_catalog(insurance: dict[str, pl.DataFrame]) -> None:
    teams = set(insurance["adjusters"]["team"].to_list())
    assert teams <= {"auto", "property", "liability", "catastrophe"}


def test_quotes_reference_policyholders(insurance: dict[str, pl.DataFrame]) -> None:
    holder_ids = set(insurance["policyholders"]["policyholder_id"].to_list())
    assert set(insurance["quotes"]["policyholder_id"].to_list()) <= holder_ids


def test_converted_quotes_reference_policies(insurance: dict[str, pl.DataFrame]) -> None:
    policy_ids = set(insurance["policies"]["policy_id"].to_list())
    linked = insurance["quotes"].filter(pl.col("policy_id").is_not_null())["policy_id"].to_list()
    assert set(linked) <= policy_ids


def test_quote_converted_iff_policy_id_present(insurance: dict[str, pl.DataFrame]) -> None:
    quotes = insurance["quotes"]
    mismatched = quotes.filter(pl.col("converted") != pl.col("policy_id").is_not_null())
    assert mismatched.height == 0


def test_one_converting_quote_per_policy(insurance: dict[str, pl.DataFrame]) -> None:
    converted = insurance["quotes"].filter(pl.col("converted"))
    assert converted["policy_id"].n_unique() == insurance["policies"].height


def test_converting_quote_precedes_policy_start(insurance: dict[str, pl.DataFrame]) -> None:
    dated = (
        insurance["quotes"]
        .filter(pl.col("converted"))
        .join(insurance["policies"].select("policy_id", "start_date"), on="policy_id")
    )
    assert dated.filter(pl.col("quote_date") > pl.col("start_date")).height == 0


def test_quote_conversion_rate_near_target(insurance: dict[str, pl.DataFrame]) -> None:
    quotes = insurance["quotes"]
    rate = quotes.filter(pl.col("converted")).height / quotes.height
    assert 0.38 < rate < 0.42


# -- Enrichment columns (quick-win realism fields) --------------------------------


@pytest.mark.parametrize(
    ("table", "column", "catalog"),
    [
        ("policyholders", "age_band", {"18-25", "26-40", "41-60", "60+"}),
        ("policies", "channel", {"broker", "direct", "aggregator"}),
        ("policies", "payment_frequency", {"monthly", "quarterly", "annual"}),
        ("claims", "reported_channel", {"phone", "app", "broker", "web"}),
        ("premium_billing", "status", {"paid", "late", "missed"}),
    ],
)
def test_enrichment_column_in_catalog(
    insurance: dict[str, pl.DataFrame], table: str, column: str, catalog: set[str]
) -> None:
    assert set(insurance[table][column].to_list()) <= catalog


def test_policyholder_state_is_a_two_letter_code(insurance: dict[str, pl.DataFrame]) -> None:
    states = insurance["policyholders"]["state"]
    assert states.filter(states.str.len_chars() != 2).len() == 0


def test_policyholder_tenure_years_in_range(insurance: dict[str, pl.DataFrame]) -> None:
    tenure = pl.col("tenure_years")
    out_of_range = insurance["policyholders"].filter((tenure < 0) | (tenure > 15))
    assert out_of_range.height == 0


def test_broker_tenure_years_is_positive(insurance: dict[str, pl.DataFrame]) -> None:
    assert insurance["brokers"].filter(pl.col("tenure_years") < 1).height == 0


def test_policyholder_tenure_is_right_skewed(insurance: dict[str, pl.DataFrame]) -> None:
    # Tenure is geometrically right-skewed, not uniform (uniform[0,15] would split evenly):
    # recent customers (≤3yr) far outnumber long-tenured ones (≥12yr).
    ph = insurance["policyholders"]
    recent = ph.filter(pl.col("tenure_years") <= 3).height
    long_tenured = ph.filter(pl.col("tenure_years") >= 12).height
    assert recent > 3 * long_tenured


def test_broker_commission_rate_in_band(insurance: dict[str, pl.DataFrame]) -> None:
    rate = pl.col("commission_rate")
    out_of_band = insurance["brokers"].filter((rate < 0.08) | (rate > 0.15))
    assert out_of_band.height == 0


def test_bundled_iff_holder_has_multiple_policies(insurance: dict[str, pl.DataFrame]) -> None:
    policies = insurance["policies"]
    expected = policies.with_columns(
        (pl.col("policy_id").count().over("policyholder_id") >= 2).alias("expected")
    )
    assert expected.filter(pl.col("bundled") != pl.col("expected")).height == 0


# -- premium_billing (instalment schedule) ----------------------------------------


def test_premium_billing_references_policies(insurance: dict[str, pl.DataFrame]) -> None:
    policy_ids = set(insurance["policies"]["policy_id"].to_list())
    assert set(insurance["premium_billing"]["policy_id"].to_list()) <= policy_ids


def test_installments_sum_to_annual_premium(insurance: dict[str, pl.DataFrame]) -> None:
    billed = (
        insurance["premium_billing"]
        .group_by("policy_id")
        .agg(pl.col("amount").sum().alias("billed"))
    )
    diff = billed.join(
        insurance["policies"].select("policy_id", "annual_premium"), on="policy_id"
    ).with_columns((pl.col("billed") - pl.col("annual_premium")).abs().alias("diff"))
    assert diff.filter(pl.col("diff") > 0.01).height == 0


def test_installment_count_matches_payment_frequency(insurance: dict[str, pl.DataFrame]) -> None:
    expected = {"monthly": 12, "quarterly": 4, "annual": 1}
    counts = (
        insurance["premium_billing"]
        .group_by("policy_id")
        .len()
        .join(insurance["policies"].select("policy_id", "payment_frequency"), on="policy_id")
        .with_columns(
            pl.col("payment_frequency")
            .replace_strict(expected, return_dtype=pl.UInt32)
            .alias("exp")
        )
    )
    assert counts.filter(pl.col("len") != pl.col("exp")).height == 0


def test_premium_billing_amount_is_positive(insurance: dict[str, pl.DataFrame]) -> None:
    assert insurance["premium_billing"].filter(pl.col("amount") <= 0).height == 0


def test_paid_date_null_iff_installment_missed(insurance: dict[str, pl.DataFrame]) -> None:
    billing = insurance["premium_billing"]
    mismatched = billing.filter((pl.col("status") == "missed") != pl.col("paid_date").is_null())
    assert mismatched.height == 0


def test_installment_due_date_on_or_after_policy_start(insurance: dict[str, pl.DataFrame]) -> None:
    dated = insurance["premium_billing"].join(
        insurance["policies"].select("policy_id", "start_date"), on="policy_id"
    )
    assert dated.filter(pl.col("due_date") < pl.col("start_date")).height == 0


def test_installment_paid_date_on_or_after_due_date(insurance: dict[str, pl.DataFrame]) -> None:
    paid = insurance["premium_billing"].filter(pl.col("paid_date").is_not_null())
    assert paid.filter(pl.col("paid_date") < pl.col("due_date")).height == 0

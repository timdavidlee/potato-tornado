"""Scenario signals for the streaming collection (the teaching 'answer key')."""

from __future__ import annotations

import re

import polars as pl
import pytest

from potato_tornado.collections.streaming.constants import RENTAL_VAT_RATES
from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def streaming() -> dict[str, pl.DataFrame]:
    return generate("streaming", GenerationConfig(seed=7, scale=0.5))


# The deterministic extraction a student would run over `rental_receipts.body`: the
# tax-inclusive total, the VAT rate (absent => 0% on US receipts), the two-letter market,
# and the subtotal that reconciles against `rentals.price`. See
# scenarios/receipts-reveal-a-tax-premium.md.
_TOTAL = re.compile(r"(?:Total charged:\s*|you paid )\$(\d+\.\d{2})")
_RATE = re.compile(r"(?:VAT|GST) \((\d+)%\)")
_MARKET = re.compile(r"\((US|GB|DE|BR|IN|JP)\)")
_SUBTOTAL = re.compile(r"(?:Subtotal:\s*|List price )\$(\d+\.\d{2})")


def _group1(pattern: re.Pattern[str], text: str) -> str:
    """First capture group of ``pattern`` in ``text``; raise if it does not match."""
    match = pattern.search(text)
    if match is None:
        raise AssertionError(f"pattern {pattern.pattern!r} did not match receipt body")
    return match.group(1)


@pytest.fixture(scope="module")
def parsed_receipts(streaming: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Parse every receipt body into structured columns, the way an analyst would.

    Returns one row per receipt: ``rental_id`` plus the ``market``, ``subtotal``,
    ``total`` (tax-inclusive), and ``rate`` (VAT percent) extracted from the prose.
    """
    rows: list[dict[str, object]] = []
    for rental_id, body in zip(
        streaming["rental_receipts"]["rental_id"].to_list(),
        streaming["rental_receipts"]["body"].to_list(),
        strict=True,
    ):
        rate_match = _RATE.search(body)
        rows.append(
            {
                "rental_id": rental_id,
                "market": _group1(_MARKET, body),
                "subtotal": float(_group1(_SUBTOTAL, body)),
                "total": float(_group1(_TOTAL, body)),
                "rate": int(rate_match.group(1)) if rate_match else 0,
            }
        )
    return pl.DataFrame(rows)


def test_standard_is_modal_plan_overall(streaming: dict[str, pl.DataFrame]) -> None:
    counts = streaming["subscriptions"]["plan"].value_counts(sort=True)
    assert counts["plan"][0] == "Standard"


def test_no_title_matches_its_actors_home_genre(streaming: dict[str, pl.DataFrame]) -> None:
    joined = streaming["titles"].join(streaming["actors"], left_on="lead_actor", right_on="actor")
    assert joined.filter(pl.col("genre") == pl.col("home_genre")).height == 0


def test_comedy_is_withheld_from_comedy_native_actors(streaming: dict[str, pl.DataFrame]) -> None:
    comedy_native = streaming["actors"].filter(pl.col("home_genre") == "comedy")["actor"]
    comedy_titles = streaming["titles"].filter(pl.col("genre") == "comedy")
    headlined_by_native = comedy_titles.filter(pl.col("lead_actor").is_in(comedy_native.to_list()))
    # comedy is a real catalogue genre, yet no comedy-native figure ever headlines one.
    assert comedy_titles.height > 0 and headlined_by_native.height == 0


def test_premium_is_modal_plan_in_us(streaming: dict[str, pl.DataFrame]) -> None:
    us_subscribers = streaming["subscribers"].filter(pl.col("region") == "US")["subscriber_id"]
    us_subs = streaming["subscriptions"].filter(
        pl.col("subscriber_id").is_in(us_subscribers.to_list())
    )
    counts = us_subs["plan"].value_counts(sort=True)
    assert counts["plan"][0] == "Premium"


def _cancel_rate_by(streaming: dict[str, pl.DataFrame], column: str) -> dict[str, float]:
    joined = streaming["subscriptions"].join(
        streaming["subscribers"].select("subscriber_id", "acquisition_channel"),
        on="subscriber_id",
    )
    rates = joined.group_by(column).agg((pl.col("status") == "cancelled").mean().alias("rate"))
    return dict(zip(rates[column].to_list(), rates["rate"].to_list(), strict=True))


def test_paid_channels_churn_faster_than_organic(streaming: dict[str, pl.DataFrame]) -> None:
    rate = _cancel_rate_by(streaming, "acquisition_channel")
    paid = (rate["paid_search"] + rate["social"]) / 2
    organic = (rate["organic"] + rate["referral"]) / 2
    # Paid acquisition churns several times the organic base; well past a 2x gap.
    assert paid > 2 * organic


def test_annual_billing_retains_better_than_monthly(streaming: dict[str, pl.DataFrame]) -> None:
    rate = _cancel_rate_by(streaming, "billing_cycle")
    # Annual cancels at a fraction of the monthly rate.
    assert rate["annual"] < 0.5 * rate["monthly"]


def test_content_is_the_top_cancel_reason_in_narrow_catalog_regions(
    streaming: dict[str, pl.DataFrame],
) -> None:
    cancelled = (
        streaming["subscriptions"]
        .join(streaming["subscribers"].select("subscriber_id", "region"), on="subscriber_id")
        .filter(pl.col("status") == "cancelled")
    )
    narrow = cancelled.filter(pl.col("region").is_in(["JP", "IN"]))
    rest = cancelled.filter(~pl.col("region").is_in(["JP", "IN"]))
    narrow_content = narrow.filter(pl.col("cancel_reason") == "content").height / narrow.height
    rest_content = rest.filter(pl.col("cancel_reason") == "content").height / rest.height
    assert narrow_content > rest_content


def test_price_is_a_larger_cancel_reason_on_the_basic_tier(
    streaming: dict[str, pl.DataFrame],
) -> None:
    cancelled = streaming["subscriptions"].filter(pl.col("status") == "cancelled")
    basic = cancelled.filter(pl.col("plan") == "Basic")
    other = cancelled.filter(pl.col("plan") != "Basic")
    basic_price = basic.filter(pl.col("cancel_reason") == "price").height / basic.height
    other_price = other.filter(pl.col("cancel_reason") == "price").height / other.height
    assert basic_price > other_price


def test_priciest_rental_tier_rates_lowest(streaming: dict[str, pl.DataFrame]) -> None:
    rated = streaming["rentals"].filter(pl.col("rating").is_not_null())
    means = dict(rated.group_by("price").agg(pl.col("rating").mean().alias("m")).iter_rows())
    assert means[19.99] < means[4.99] and means[19.99] < means[6.99]


def test_rentals_concentrate_in_a_whale_minority(streaming: dict[str, pl.DataFrame]) -> None:
    per = (
        streaming["rentals"]
        .group_by("subscriber_id")
        .agg(pl.len().alias("rentals"))
        .sort("rentals", descending=True)
    )
    top_decile = max(1, per.height // 10)
    top10_share = int(per.head(top_decile)["rentals"].sum()) / int(per["rentals"].sum())
    # Whale minority: top decile of renters ≈0.45 of rentals at seed 7 / scale 0.5;
    # a uniform renter draw would sit near ~0.21.
    assert top10_share > 0.38


def test_most_subscribers_never_rent(streaming: dict[str, pl.DataFrame]) -> None:
    n_subs = streaming["subscribers"].height
    n_renters = streaming["rentals"]["subscriber_id"].n_unique()
    # The base is thin: only ~30% of subscribers ever rent at seed 7 / scale 0.5.
    assert n_renters / n_subs < 0.40


def test_premium_titles_score_higher(streaming: dict[str, pl.DataFrame]) -> None:
    means = dict(
        streaming["titles"]
        .group_by("is_premium")
        .agg(pl.col("avg_rating").mean().alias("m"))
        .iter_rows()
    )
    assert means[True] > means[False]


def test_catalog_share_runs_from_us_widest_to_japan_narrowest(
    streaming: dict[str, pl.DataFrame],
) -> None:
    n_titles = streaming["titles"].height
    shares = {
        region: count / n_titles
        for region, count in streaming["title_availability"].group_by("region").len().iter_rows()
    }
    widest = max(shares, key=lambda r: shares[r])
    narrowest = min(shares, key=lambda r: shares[r])
    # US carries most of the catalogue (~0.87), Japan the least (~0.30): a ~2.9x gradient.
    assert widest == "US" and narrowest == "JP" and shares["US"] > 2.5 * shares["JP"]


def test_us_arpu_is_a_premium_outlier(streaming: dict[str, pl.DataFrame]) -> None:
    arpu = dict(
        streaming["subscriptions"]
        .join(streaming["subscribers"].select("subscriber_id", "region"), on="subscriber_id")
        .group_by("region")
        .agg((pl.col("mrr").sum() / pl.len()).alias("arpu"))
        .iter_rows()
    )
    us = arpu.pop("US")
    # US ARPU (~$15.6) is a lone premium outlier: it clears every non-US market (a tight
    # ~$11.9-$12.6 band) by a wide margin, despite identical list prices everywhere.
    assert us > 1.15 * max(arpu.values())


def test_annual_books_lower_mrr_but_retains_better(streaming: dict[str, pl.DataFrame]) -> None:
    by_cycle = {
        cycle: (mean_mrr, cancel_rate)
        for cycle, mean_mrr, cancel_rate in streaming["subscriptions"]
        .group_by("billing_cycle")
        .agg(
            pl.col("mrr").mean().alias("mean_mrr"),
            (pl.col("status") == "cancelled").mean().alias("cancel_rate"),
        )
        .iter_rows()
    }
    annual_mrr, annual_cancel = by_cycle["annual"]
    monthly_mrr, monthly_cancel = by_cycle["monthly"]
    # The lowest-MRR cohort is the stickiest: annual books less revenue per sub (~$11.3 vs
    # ~$13.9) yet cancels far less (~0.06 vs ~0.21), so ranking cohorts by MRR inverts value.
    assert annual_mrr < monthly_mrr and annual_cancel < monthly_cancel


# --- receipts-reveal-a-tax-premium (document scenario) -------------------------------
# Layer (a): the receipt prose parses back to the ground truth. Layer (b): the parsed
# effective totals carry the planted per-market VAT premium, with the US the cheapest.


def test_receipt_subtotal_reconciles_with_rental_price(
    parsed_receipts: pl.DataFrame, streaming: dict[str, pl.DataFrame]
) -> None:
    # Layer (a): the subtotal printed on every receipt is exactly `rentals.price` (the
    # receipt renders the real list column — no answer leaked into the prose).
    joined = parsed_receipts.join(streaming["rentals"].select("rental_id", "price"), on="rental_id")
    max_gap = joined.select((pl.col("subtotal") - pl.col("price")).abs().max()).item()
    assert max_gap < 0.005


def test_receipt_total_is_recoverable_from_prose(parsed_receipts: pl.DataFrame) -> None:
    # Layer (a): using only fields parsed out of the prose (subtotal + the VAT rate, which
    # is absent => 0% on US receipts), the tax-inclusive total reconstructs the printed
    # `Total charged` line — the number is genuinely legible across all template variants.
    reconstructed = (pl.col("subtotal") * (1 + pl.col("rate") / 100)).round(2)
    max_gap = parsed_receipts.select((pl.col("total") - reconstructed).abs().max()).item()
    assert max_gap < 0.005


def test_receipt_rate_matches_the_withheld_vat_schedule(parsed_receipts: pl.DataFrame) -> None:
    # Layer (a): the VAT rate printed in each receipt equals the withheld per-market
    # schedule (the answer key held back for scoring), so the prose encodes the right tax.
    expected = pl.col("market").replace_strict(RENTAL_VAT_RATES, return_dtype=pl.Int64)
    mismatches = parsed_receipts.filter(pl.col("rate") != expected).height
    assert mismatches == 0


def test_us_is_the_cheapest_effective_rental_market(parsed_receipts: pl.DataFrame) -> None:
    # Layer (b) signal: aggregate the parsed tax-inclusive totals by market. The US — the
    # largest rental market by volume and the subscription ARPU leader — is the *cheapest*
    # effective ticket (0% VAT), inverting the subscription US-concentration story.
    mean_effective = parsed_receipts.group_by("market").agg(pl.col("total").mean().alias("eff"))
    cheapest = mean_effective.sort("eff").row(0, named=True)["market"]
    assert cheapest == "US"


@pytest.mark.parametrize(
    ("market", "expected_ratio"),
    [("US", 1.00), ("JP", 1.10), ("BR", 1.17), ("IN", 1.18), ("DE", 1.19), ("GB", 1.20)],
)
def test_effective_over_list_ratio_matches_region_vat(
    parsed_receipts: pl.DataFrame, market: str, expected_ratio: float
) -> None:
    # Layer (b) magnitude: within each market the mean effective charge runs (1 + VAT) over
    # the mean list — US flat at 1.00x, up to GB at 1.20x — a ~20% spread hidden from any
    # column. The ratio-of-means is exact up to per-cent rounding, so a tight tolerance.
    rows = parsed_receipts.filter(pl.col("market") == market)
    ratio = rows.select(pl.col("total").mean() / pl.col("subtotal").mean()).item()
    assert abs(ratio - expected_ratio) < 0.01

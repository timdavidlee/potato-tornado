"""Scenario signals for the logistics collection (the teaching 'answer key')."""

from __future__ import annotations

import re
from typing import cast

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def logistics() -> dict[str, pl.DataFrame]:
    return generate("logistics", GenerationConfig(seed=7, scale=0.5))


# --- refund-exposure-tracks-guarantee-not-reliability ---------------------------------
# The rate-card prose in `carrier_policies.body` is the source of truth. The regexes below
# are the extraction a student/analyst would write; they must survive the template
# variants. The guarantee clause carries an integer of days; the pricing terms are dollar
# amounts and a percent that reconcile against the `carriers` dim columns.
_RE_GUARANTEE = re.compile(r"(\d+)\s*(?:\+|or more)?\s*days?", re.IGNORECASE)
_RE_BASE = re.compile(r"\$(\d+\.\d{2})\s*(?:base|per shipment|/shipment)", re.IGNORECASE)
_RE_PER_KG = re.compile(r"\$(\d+\.\d{2})\s*(?:/kg|per kg|per kilogram)", re.IGNORECASE)
_RE_FUEL = re.compile(r"(\d+(?:\.\d)?)\s*%")


def _parse_cards(carrier_policies: pl.DataFrame) -> pl.DataFrame:
    """Parse each rate-card ``body`` into structured terms (the student's extraction).

    Returns one row per policy with ``carrier_id`` plus the parsed
    ``guarantee_days`` / ``base_rate`` / ``per_kg_rate`` / ``fuel_surcharge_pct``.
    """
    carrier_ids: list[str] = []
    guarantee_days: list[int] = []
    base_rate: list[float] = []
    per_kg_rate: list[float] = []
    fuel_surcharge_pct: list[float] = []
    for row in carrier_policies.iter_rows(named=True):
        body = cast(str, row["body"])
        g, base, kg, fuel = (
            _RE_GUARANTEE.search(body),
            _RE_BASE.search(body),
            _RE_PER_KG.search(body),
            _RE_FUEL.search(body),
        )
        assert g and base and kg and fuel, f"rate card did not parse: {body!r}"
        carrier_ids.append(cast(str, row["carrier_id"]))
        guarantee_days.append(int(g.group(1)))
        base_rate.append(float(base.group(1)))
        per_kg_rate.append(float(kg.group(1)))
        fuel_surcharge_pct.append(float(fuel.group(1)) / 100.0)
    return pl.DataFrame(
        {
            "carrier_id": carrier_ids,
            "guarantee_days": guarantee_days,
            "base_rate": base_rate,
            "per_kg_rate": per_kg_rate,
            "fuel_surcharge_pct": fuel_surcharge_pct,
        }
    )


def _refund_exposure(frames: dict[str, pl.DataFrame], policy: pl.DataFrame) -> pl.DataFrame:
    """Refund-to-revenue per carrier under ``policy`` (``carrier_id`` + ``guarantee_days``).

    A delivered parcel owes a refund of its full ``shipping_cost`` when
    ``days_late >= guarantee_days``; summed per carrier over that carrier's shipping revenue.
    """
    return (
        frames["deliveries"]
        .filter(pl.col("status") == "delivered")
        .join(
            frames["shipments"].select("shipment_id", "carrier_id", "shipping_cost"),
            on="shipment_id",
        )
        .join(policy.select("carrier_id", "guarantee_days"), on="carrier_id")
        .join(frames["carriers"].select("carrier_id", "reliability"), on="carrier_id")
        .group_by("carrier_id", "reliability")
        .agg(
            pl.col("shipping_cost")
            .filter(pl.col("days_late") >= pl.col("guarantee_days"))
            .sum()
            .alias("refund"),
            pl.col("shipping_cost").sum().alias("revenue"),
        )
        .with_columns((pl.col("refund") / pl.col("revenue")).alias("refund_to_rev"))
    )


def test_on_time_rate_declines_with_zone(logistics: dict[str, pl.DataFrame]) -> None:
    by_zone = (
        logistics["deliveries"]
        .filter(pl.col("status") == "delivered")
        .join(logistics["shipments"].select("shipment_id", "dest_zone"), on="shipment_id")
        .group_by("dest_zone")
        .agg((pl.col("days_late") <= 0).mean().alias("on_time"))
    )
    rates = dict(zip(by_zone["dest_zone"], by_zone["on_time"], strict=True))
    assert cast(float, rates[1]) > cast(float, rates[8]) + 0.1


def test_shipping_cost_is_right_skewed(logistics: dict[str, pl.DataFrame]) -> None:
    cost = logistics["shipments"]["shipping_cost"]
    assert cast(float, cost.mean()) > cast(float, cost.median())


def test_shipping_cost_rises_with_weight(logistics: dict[str, pl.DataFrame]) -> None:
    corr = logistics["shipments"].select(pl.corr("weight_kg", "shipping_cost")).item()
    assert cast(float, corr) > 0.3


def test_most_delivered_parcels_are_on_time(logistics: dict[str, pl.DataFrame]) -> None:
    delivered = logistics["deliveries"].filter(pl.col("status") == "delivered")
    on_time_rate = cast(float, (delivered["days_late"] <= 0).mean())
    assert 0.8 < on_time_rate < 0.92


def test_late_tail_is_right_skewed_and_bounded(logistics: dict[str, pl.DataFrame]) -> None:
    late = logistics["deliveries"].filter(
        (pl.col("status") == "delivered") & (pl.col("days_late") > 0)
    )["days_late"]
    assert 1 < cast(float, late.mean()) < 4 and cast(int, late.max()) <= 7


def test_dim_weight_bound_parcels_are_about_half(logistics: dict[str, pl.DataFrame]) -> None:
    s = logistics["shipments"]
    dim_weight = s["length_cm"] * s["width_cm"] * s["height_cm"] / 5000.0
    dim_bound_frac = cast(float, (dim_weight > s["weight_kg"]).mean())
    assert 0.45 < dim_bound_frac < 0.58


def test_signature_required_concentrates_in_fast_tiers(logistics: dict[str, pl.DataFrame]) -> None:
    by_tier = (
        logistics["shipments"]
        .group_by("service_level")
        .agg(pl.col("signature_required").mean().alias("sig_rate"))
    )
    rate = {
        lvl: cast(float, r)
        for lvl, r in zip(by_tier["service_level"], by_tier["sig_rate"], strict=True)
    }
    assert (
        rate["ground"] < rate["express"] < rate["overnight"]
        and rate["overnight"] >= 4 * rate["ground"]
    )


# Layer 1 — recoverability: the rate-card prose parses back to the ground truth.


def test_rate_card_pricing_reconciles_with_carrier_columns(
    logistics: dict[str, pl.DataFrame],
) -> None:
    parsed = _parse_cards(logistics["carrier_policies"])
    joined = parsed.join(
        logistics["carriers"].select(
            "carrier_id",
            pl.col("base_rate").alias("base_truth"),
            pl.col("per_kg_rate").alias("kg_truth"),
            pl.col("fuel_surcharge_pct").alias("fuel_truth"),
        ),
        on="carrier_id",
    )
    mismatches = joined.filter(
        ((pl.col("base_rate") - pl.col("base_truth")).abs() > 1e-9)
        | ((pl.col("per_kg_rate") - pl.col("kg_truth")).abs() > 1e-9)
        | ((pl.col("fuel_surcharge_pct") - pl.col("fuel_truth")).abs() > 1e-9)
    )
    assert mismatches.height == 0


def test_rate_card_guarantee_recovers_the_withheld_answer_key(
    logistics: dict[str, pl.DataFrame],
) -> None:
    parsed = _parse_cards(logistics["carrier_policies"]).select("carrier_id", "guarantee_days")
    answer_key = logistics["carrier_policies"].select(
        "carrier_id", pl.col("guarantee_days").alias("guarantee_truth")
    )
    joined = parsed.join(answer_key, on="carrier_id")
    assert joined.filter(pl.col("guarantee_days") != pl.col("guarantee_truth")).height == 0


# Layer 2 — signal: with the parsed thresholds applied, refund exposure does NOT rank
# with reliability, and a uniform threshold shows it otherwise would.


def test_refund_exposure_top_carrier_is_not_the_least_reliable(
    logistics: dict[str, pl.DataFrame],
) -> None:
    exposure = _refund_exposure(logistics, _parse_cards(logistics["carrier_policies"]))
    top = exposure.sort("refund_to_rev", descending=True).row(0, named=True)
    least_reliable = exposure.sort("reliability").row(0, named=True)
    # The heaviest refund bill lands on a strictly more-reliable carrier (a mid-tier
    # carrier tops), not the worst-reliability one — the "worst carrier owes most" story
    # is broken by the per-carrier guarantee thresholds read out of the prose.
    assert cast(float, top["reliability"]) > cast(float, least_reliable["reliability"])


def test_refund_exposure_decouples_from_reliability(
    logistics: dict[str, pl.DataFrame],
) -> None:
    exposure = _refund_exposure(logistics, _parse_cards(logistics["carrier_policies"]))
    corr = cast(float, exposure.select(pl.corr("reliability", "refund_to_rev")).item())
    # Under the parsed per-carrier guarantees the correlation is weak (measured ≈ -0.15 at
    # this seed/scale) — refund exposure is a policy-shaped liability, not a reliability one.
    assert corr > -0.5


def test_uniform_guarantee_would_rank_refunds_with_reliability(
    logistics: dict[str, pl.DataFrame],
) -> None:
    uniform = logistics["carriers"].select(
        "carrier_id", pl.lit(2, dtype=pl.Int64).alias("guarantee_days")
    )
    exposure = _refund_exposure(logistics, uniform)
    corr = cast(float, exposure.select(pl.corr("reliability", "refund_to_rev")).item())
    # Counterfactual anchor: a single uniform 2-day guarantee makes refund exposure descend
    # strongly with reliability (measured ≈ -0.87) — the least reliable carrier owes the
    # most. The divergence from the test above is produced entirely by the prose thresholds.
    assert corr < -0.7

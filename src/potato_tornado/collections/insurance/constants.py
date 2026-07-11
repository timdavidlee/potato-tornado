"""Domain reference data (catalogs) for the insurance collection.

The fixed "seed" facts the generators draw from: the risk-tier ladder (premium
multiplier + annual claim frequency), the product catalogue (base premium +
coverage), and the peril catalogue. Each literal here is read by two or more
tables, so it is the single source of truth; single-table literals (region list,
deductible ladder, adjudication mix) stay inline in the module that uses them. See
``scenarios/`` for the signals these values are tuned to produce.
"""

from __future__ import annotations

# (tier, premium_multiplier, annual_claim_lambda) — the risk ladder.
# `premium_multiplier` scales a product's base premium in `policies`;
# `annual_claim_lambda` is the per-policy-year Poisson rate `claims` draws from.
# Higher tiers pay more premium *and* claim far more often — the engine behind the
# loss-ratio-rises-with-tier signal. Read by `policies` and `claims`.
RISK_TIERS = [
    ("preferred", 0.70, 0.09),
    ("standard", 1.00, 0.18),
    ("high_risk", 1.75, 0.42),
]

# How policyholders distribute across the tiers (a policyholder attribute), kept
# here so `policies`/`claims` can rely on the same three tier names.
RISK_TIER_WEIGHTS = [0.45, 0.40, 0.15]

# (product, premium_median, coverage_base, weight) — the product catalogue.
# `premium_median` (before the tier multiplier) seeds `annual_premium`;
# `coverage_base` seeds `coverage_limit` (x a per-policy coverage step). Read by
# `policies`; product mix referenced by scenarios.
PRODUCTS = [
    ("auto", 1500.0, 60_000.0, 0.50),
    ("home", 1200.0, 300_000.0, 0.30),
    ("renters", 400.0, 30_000.0, 0.20),
]

# The peril catalogue — what a claim is for. Independent of product and geography
# (a deliberate simplification). Read by `claims` and referenced by the realism doc.
PERILS = ["collision", "theft", "weather", "fire", "liability", "water_damage"]

# (line_name, base_limit, deductible_applies, base_weight) per product — the
# coverage-line catalogue. Each product's policy is a bundle of these lines;
# `coverage_lines` expands one policy into one row per line. `base_limit` seeds the
# (jittered) per-line limit; `deductible_applies` decides whether the line carries
# the policy deductible (liability lines don't); `base_weight` is the line's nominal
# share of the annual premium (each product's weights sum to 1.0, with the last line
# holding a healthy share so the remainder-absorbing premium share stays positive).
# This is a **descriptive** premium-side breakdown — the payout path still reads the
# policy-level `coverage_limit`/`deductible`, so `line_limit` is deliberately not
# reconciled against `coverage_limit`. Read only by `coverage_lines`.
COVERAGE_LINES: dict[str, list[tuple[str, float, bool, float]]] = {
    "auto": [
        ("liability", 100_000.0, False, 0.45),
        ("collision", 40_000.0, True, 0.35),
        ("comprehensive", 25_000.0, True, 0.20),
    ],
    "home": [
        ("dwelling", 300_000.0, True, 0.55),
        ("contents", 120_000.0, True, 0.25),
        ("liability", 100_000.0, False, 0.20),
    ],
    "renters": [
        ("contents", 30_000.0, True, 0.65),
        ("liability", 100_000.0, False, 0.35),
    ],
}

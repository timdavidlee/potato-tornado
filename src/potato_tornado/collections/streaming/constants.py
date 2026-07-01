"""Domain reference data (catalogs) for the streaming collection.

The fixed "seed" facts the generators draw from: the subscription-plan ladder, the
subscription lifecycle mix, the one-off premium-rental price points, and a
**placeholder** title-name catalog. See ``scenarios/`` for the signals these
values are tuned to produce.
"""

from __future__ import annotations

# (plan, monthly_price, signup_weight) — the subscription ladder. `PLANS` feeds
# both the `plans` reference table and the `subscriptions` plan mix, so it is the
# single source of truth for tier names/prices.
PLANS = [
    ("Basic", 7.99, 0.30),
    ("Standard", 13.99, 0.50),
    ("Premium", 19.99, 0.20),
]

# Subscription lifecycle: currently paying vs. churned.
SUB_STATUS = ["active", "cancelled"]
SUB_STATUS_WEIGHTS = [0.78, 0.22]

TITLE_KINDS = ["series", "film"]
TITLE_KIND_WEIGHTS = [0.6, 0.4]

# One-off premium-rental price points (PVOD): a cheap catalogue rental, a standard
# new-release rental, and a premium day-and-date release.
PREMIUM_RENTAL_PRICES = [4.99, 6.99, 19.99]

# --- PLACEHOLDER content -------------------------------------------------------
# TODO(content): replace with the curated fake-show catalogue per the naming
# guidance to come. These stand-in word lists only exist so the collection
# generates real rows and a real schema today; `_placeholder_titles` combines
# them into deterministic "<Adjective> <Noun>" titles.
TITLE_ADJECTIVES = [
    "Crimson",
    "Silent",
    "Broken",
    "Golden",
    "Hidden",
    "Northern",
    "Electric",
    "Distant",
]
TITLE_NOUNS = [
    "Harbor",
    "Circuit",
    "Empire",
    "Verdict",
    "Horizon",
    "Ashes",
    "Signal",
    "Frontier",
]

"""The ``coverage_lines`` table: one row per coverage line on a policy.

Expands each policy into the lines of its product's bundle (auto → liability /
collision / comprehensive; home → dwelling / contents / liability; renters →
contents / liability — see ``COVERAGE_LINES``). Each line carries a ``line_limit``
(the product's base line limit with a small lognormal jitter, so the limit is
near-continuous at the line grain), a ``line_deductible`` (the policy deductible on
lines where it applies, else 0 — liability lines carry no deductible), and a
``line_premium_share`` that **sums exactly to the policy's `annual_premium`** (an
arithmetic identity — the last line absorbs the rounding remainder, exactly like
``premium_billing`` instalments).

This is a **premium-side, additive** breakdown only. The claim → payout path is
untouched: claims still price against the policy-level ``coverage_limit`` /
``deductible``, no claim maps to a line, and ``line_limit`` is **deliberately not**
reconciled against ``policies.coverage_limit``. Line-level loss ratios (mapping a
claim's peril to a covered line) are a candidate scenario, not planted here.

Drawn off its own name-keyed child streams (``coverage_split`` for the premium
split, ``coverage_limit_jitter`` for the limit noise), so adding this table leaves
every pre-existing table byte-identical.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.insurance.constants import COVERAGE_LINES
from potato_tornado.core.collection import GenContext

# Lognormal scatter applied to each line's catalog base limit (near-continuous) and
# to its nominal premium weight (so the split isn't a constant ratio). Single-table
# literals.
_LIMIT_SIGMA = 0.15
_SPLIT_SIGMA = 0.25


def build_coverage_lines(ctx: GenContext) -> pl.DataFrame:
    policies = ctx.table("policies")
    policy_ids = policies["policy_id"].to_list()
    products = policies["product"].to_list()
    annual_premium = policies["annual_premium"].to_numpy()
    deductible = policies["deductible"].to_numpy()

    n_pol = len(policy_ids)
    counts = np.array([len(COVERAGE_LINES[p]) for p in products])
    total = int(counts.sum())

    # Expand each policy into its product's lines; `k` is the 0-based line index
    # within its policy (contiguous groups, mirroring premium_billing's expansion).
    policy_idx = np.repeat(np.arange(n_pol), counts)
    group_start = np.repeat(np.cumsum(counts) - counts, counts)
    k = np.arange(total) - group_start
    counts_per = counts[policy_idx]
    is_last = k == counts_per - 1

    # Per-row catalog lookup: the line at index `k` of that policy's product bundle.
    catalog = [COVERAGE_LINES[products[p]][int(kk)] for p, kk in zip(policy_idx, k, strict=True)]
    coverage_line = [c[0] for c in catalog]
    base_limit = np.array([c[1] for c in catalog])
    deductible_applies = np.array([c[2] for c in catalog], dtype=bool)
    base_weight = np.array([c[3] for c in catalog])

    # Limit: catalog base x lognormal jitter, rounded to the nearest $100 — relaxes
    # the policy-level coverage lattice at the line grain (descriptive only).
    limit_jitter = ctx.rng.child("coverage_limit_jitter").numpy.lognormal(0.0, _LIMIT_SIGMA, total)
    line_limit = np.round(base_limit * limit_jitter, -2)

    # Deductible: the policy deductible where the line carries one, else 0 (liability
    # lines) — derived, no draw.
    line_deductible = np.where(deductible_applies, deductible[policy_idx], 0.0)

    # Premium share: base weight x lognormal jitter, normalized per policy so the
    # weights sum to 1, then scaled by `annual_premium` and rounded to cents. The last
    # line of each policy absorbs the rounding remainder so the shares sum to
    # `annual_premium` exactly (same identity as premium_billing instalments).
    split_jitter = ctx.rng.child("coverage_split").numpy.lognormal(0.0, _SPLIT_SIGMA, total)
    raw = base_weight * split_jitter
    policy_raw_sum = np.bincount(policy_idx, weights=raw, minlength=n_pol)
    weight = raw / policy_raw_sum[policy_idx]
    premium_per = annual_premium[policy_idx]
    share = np.round(weight * premium_per, 2)
    non_last_sum = np.bincount(policy_idx, weights=np.where(is_last, 0.0, share), minlength=n_pol)
    last_share = np.round(premium_per - non_last_sum[policy_idx], 2)
    line_premium_share = np.where(is_last, last_share, share)

    return pl.DataFrame(
        {
            "coverage_line_id": [f"CVL-{i:07d}" for i in range(1, total + 1)],
            "policy_id": [policy_ids[p] for p in policy_idx],
            "coverage_line": coverage_line,
            "line_limit": line_limit,
            "line_deductible": line_deductible,
            "line_premium_share": line_premium_share,
        }
    )

"""The ``shipments`` table: one row per parcel dispatched (the plan).

Each shipment leaves a warehouse on a carrier at a service level, bound for a
destination city some distance away (``dest_zone``, a 1-8 distance proxy). It
carries the **plan**: the ``promised_date`` the service level commits to. Weight is
right-skewed (most parcels light, a long heavy tail) and drives a cost identity
alongside the zone and the service multiplier.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.logistics.constants import SERVICE_LEVELS
from potato_tornado.core.collection import GenContext

# Per-zone distance surcharge (a single-table literal), and the middle-heavy zone
# mix — most parcels travel a moderate distance, few are very near or very far.
_ZONE_FEE = 1.25
_ZONES = [1, 2, 3, 4, 5, 6, 7, 8]
_ZONE_WEIGHTS = [0.06, 0.10, 0.16, 0.20, 0.20, 0.14, 0.09, 0.05]

# Parcel form factor (single-table literal), weighted toward small boxes — the bulk
# of e-commerce parcels — with a thin pallet tail. Descriptive covariate for slicing
# cost / weight / SLA; not wired into the cost identity.
_PACKAGE_TYPES = ["envelope", "pak", "small_box", "large_box", "pallet"]
_PACKAGE_WEIGHTS = [0.14, 0.14, 0.44, 0.22, 0.06]

# Signature-required propensity: a low base lifted for premium service tiers and
# heavy parcels (higher-value / higher-liability handling). Composes with
# `deliveries.delivery_method` (signature parcels deliver via the signature path).
_SIG_BASE = 0.05
_SIG_SERVICE_BUMP = {"ground": 0.0, "express": 0.10, "overnight": 0.25}
_SIG_HEAVY_KG = 20.0
_SIG_HEAVY_BUMP = 0.20


def build_shipments(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(8000)
    carriers = ctx.table("carriers")
    warehouse_ids = ctx.table("warehouses")["warehouse_id"].to_list()

    carrier_ids = carriers["carrier_id"].to_list()
    base_of = dict(zip(carrier_ids, carriers["base_rate"].to_list(), strict=True))
    per_kg_of = dict(zip(carrier_ids, carriers["per_kg_rate"].to_list(), strict=True))

    service_names = [name for name, *_ in SERVICE_LEVELS]
    service_weights = [w for *_, w in SERVICE_LEVELS]
    transit_of = {name: days for name, days, _mult, _w in SERVICE_LEVELS}
    mult_of = {name: mult for name, _days, mult, _w in SERVICE_LEVELS}

    carrier = ctx.dist.choice(n, carrier_ids)
    service = ctx.dist.choice(n, service_names, service_weights)
    zone = ctx.dist.choice(n, [str(z) for z in _ZONES], _ZONE_WEIGHTS).astype(int)
    # Round weight before deriving cost so the stored `weight_kg` and `shipping_cost`
    # satisfy the cost identity exactly (a downstream query can recompute one from the
    # other — see realism-guidance.md).
    weight_kg = np.round(np.clip(ctx.dist.lognormal(n, median=2.0, sigma=0.8), 0.1, 50.0), 2)

    base = np.array([base_of[c] for c in carrier])
    per_kg = np.array([per_kg_of[c] for c in carrier])
    mult = np.array([mult_of[s] for s in service])
    shipping_cost = np.round((base + weight_kg * per_kg + zone * _ZONE_FEE) * mult, 2)

    ship_date: list[date] = ctx.dist.dates_between(
        n, ctx.config.start_date, ctx.config.end_date
    ).tolist()
    transit = np.array([transit_of[s] for s in service])
    promised_date = [d + timedelta(days=int(t)) for d, t in zip(ship_date, transit, strict=True)]

    # Descriptive covariates on name-keyed child streams so they don't shift the
    # draws above (cost / date identities stay exact).
    package_type = ctx.rng.child("package_type").numpy.choice(
        _PACKAGE_TYPES, size=n, p=_PACKAGE_WEIGHTS
    )
    p_sig = np.clip(
        _SIG_BASE
        + np.array([_SIG_SERVICE_BUMP[s] for s in service])
        + np.where(weight_kg >= _SIG_HEAVY_KG, _SIG_HEAVY_BUMP, 0.0),
        0.0,
        1.0,
    )
    signature_required = ctx.rng.child("sig").numpy.random(n) < p_sig

    return pl.DataFrame(
        {
            "shipment_id": [f"SHP-{i:07d}" for i in range(1, n + 1)],
            "warehouse_id": ctx.dist.choice(n, warehouse_ids),
            "carrier_id": carrier,
            "service_level": service,
            "dest_city": ctx.entities.cities(n),
            "dest_zone": zone,
            "weight_kg": weight_kg,
            "package_type": package_type,
            "signature_required": signature_required,
            "shipping_cost": shipping_cost,
            "ship_date": ship_date,
            "promised_date": promised_date,
        }
    )

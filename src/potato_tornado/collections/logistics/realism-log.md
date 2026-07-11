# Realism log — logistics

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — invariants and the headline distributions have been swept, two
too-synthetic artifacts fixed (the terminal-time lattice and the once-per-shipment hub city),
and the remaining open realism items confirmed as documented deliberate simplifications; residual
items are those simplifications (open items in `TODO.md`). (as of 2026-07-11)

## Realism iterations

- **2026-07-01 — Initial build + invariant sweep.** Pinned the hard rules (1:1
  `deliveries`↔`shipments`, terminal-status consistency recovered structurally from the scan
  timeline, strictly increasing `scan_ts` by `seq`, date ordering). Made the `shipping_cost`
  identity *exact* — round `weight_kg` **before** deriving cost so a query can recompute one
  from the other with zero mismatch. (`13793d9`)
- **2026-07-01 — Too-synthetic sweep: de-lattice the terminal scan time.** The terminal
  (delivered/exception) scan previously landed at a single fixed clock time (~18:00), a visible
  time-of-day lattice. Now each shipment's terminal scan draws a time uniformly across
  **[12:00, 20:00)** on the terminal calendar day, so `actual_delivery_date` is unchanged but
  the hour spreads. Guarded by the scan-timestamp note in the rubric. (`e27dc41`)
- **2026-07-11 — Too-synthetic sweep: per-hop hub city + confirm the remaining open items.**
  Fixed the last named too-synthetic artifact: the intermediate `in_transit` hub city was drawn
  **once per shipment** (`ctx.entities.cities(n)`), so every multi-hop parcel repeated a single
  hub label on each line-haul scan (measured 100% single-hub on multi-hop shipments). Now
  `tables/scan_events.py` draws one hub per hop — `hub_cities = ctx.entities.cities(sum(1 +
  _extra_hops(zone)))`, handed out in scan order via a `cursor` — dropping single-hub multi-hop
  parcels to ~0% (0.03% at scale=1.0, the rare faker city collision). Kept as the **only**
  `ctx.entities` call and touched no numpy child stream, so `scan_ts` / `scan_type` /
  `facility_type` and all of `deliveries` are byte-for-byte unchanged (verified at seed=7);
  `location_city` dtype stays `Utf8`. Labels remain coarse faker cities — not route-ordered or
  geographically between origin and destination; that grounding is out of scope. Reconciled the
  `location_city` simplification in `realism-guidance.md` and added the invariant test
  `test_multi_hop_shipments_vary_their_hub_city`. Also confirmed the other three open realism
  items as intentional/healthy (no code change): `dest_zone`⊥`dest_city` (6396 distinct cities /
  8000 shipments, 99% of recurring cities span >1 zone — independent labels), memoryless outcomes
  (lag-1 on-time autocorr ≈ -0.016), and the cost tail (only 2 shipments > \$80, max \$84.27,
  none at the 50 kg clamp — weight×zone×multiplier driven). The three scenario-bearing columns
  (`insured_value`, `exception_reason`, `delivery_cost`) stay deferred to
  `/scenario:draft-or-propose`.

## Field-enrichment runs

- **2026-07-02 — Field-enrichment survey.** Surveyed all five tables and wrote the candidate
  backlog (7 quick wins + 5 high-leverage, several scenario-bearing) to [`TODO.md`](TODO.md).
  No columns implemented yet — the backlog is the open work.
- **2026-07-02 — Quick-wins enrichment (all 7 shipped).** Landed every quick-win column from
  `TODO.md`: `shipments.package_type` (weighted toward small boxes) + `signature_required`
  (base 0.05, lifted by service tier and weight ≥ 20 kg → overall ≈ 0.09); `carriers.transport_mode`
  + `fuel_surcharge_pct` (static catalog attributes in `constants.CARRIERS`, **not** wired into
  the cost identity); `warehouses.capacity_units` (lognormal, median ≈ 45k) + `opened_date`
  (1–10 y before the window start); `deliveries.delivery_method` (signature path iff
  `signature_required`, else doorstep/locker/pickup_point, null on non-delivered). All new draws
  use name-keyed child streams (`package_type`, `sig`, `capacity`, `opened`, `delivery_method`)
  so the existing cost/date identities are byte-for-byte unchanged. Reconciled
  `realism-guidance.md` (new catalogs, bounds, the last-mile consistency invariant, mixes,
  simplifications) and added pin tests. Scenario-bearing/high-leverage items remain open in
  `TODO.md`.
- **2026-07-02 — High-leverage realism items (1 + 5 shipped).** Landed the two non-scenario
  high-leverage columns. `scan_events.facility_type` tags each scan's network stage
  (origin_hub / linehaul / destination_hub / local) **derived from the scan ladder + position**
  (no fresh draw): pickup → origin hub, last `in_transit` hop → destination hub, earlier hops →
  line-haul, last-mile scans → local, exception → local iff it reached out-for-delivery else the
  destination hub — unlocking per-stage dwell-time analysis. `shipments.length_cm/width_cm/
  height_cm` come from `weight_kg ÷ drawn density` split by aspect jitter (own `dims` child
  stream), so `dim_weight = L×W×H/5000` and `billable = max(weight, dim_weight)` are derivable;
  density median ≈ 195 (just under the 200 break-even) puts ≈ 0.5 of parcels on dimensional
  weight, `corr(weight, dim_weight)` ≈ 0.8. Shipped **descriptive-only** — dims are *not* folded
  into `shipping_cost`, so the pinned cost identity is byte-for-byte unchanged. Reconciled
  `realism-guidance.md` (facility derivation rule, dim-weight-derivable note, the reworked flat-
  rate simplification) and added pin tests. Remaining `TODO.md` high-leverage items (2/3/4) are
  scenario-bearing → `/scenario:draft-or-propose`.

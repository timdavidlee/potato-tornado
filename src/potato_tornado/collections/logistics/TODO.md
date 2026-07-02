# logistics — field-enrichment TODO

Candidate columns to add to the existing `logistics` tables for analytics richness. Ordered
quick wins first (realism enrichment), then high-leverage items (each unlocks an analysis
domain; scenario-bearing ones go through `/scenario:draft-or-propose`, not the realism
command).

For each: add the column in the relevant `tables/` builder with deterministic draws
(`ctx.dist` / `ctx.rng` / `ctx.entities`, name-keyed child streams — don't reorder existing
draws), then reconcile `realism-guidance.md` and pin tests. See collections/CLAUDE.md.

Context: the collection models parcels dispatched from `warehouses` on `carriers`
(`shipments`), tracked by a `scan_events` timeline and settled in `deliveries`. The current
schema captures the plan (cost, promised date) and the SLA outcome (on-time, terminal status),
but has **no parcel form factor, no per-stage network detail, no cost-vs-price margin, and no
failure-cause detail** — the additions below close those gaps.

## Quick wins (realism enrichment)

All seven quick wins **shipped 2026-07-02** (see `realism-log.md` for the run) — kept here
struck through as a record of what landed:

- [x] **`shipments.package_type`** (`Utf8`) — weighted choice over
      {envelope, pak, small_box, large_box, pallet}, toward small boxes.
- [x] **`shipments.signature_required`** (`Boolean`) — `p` higher for overnight / heavy parcels.
- [x] **`carriers.transport_mode`** (`Utf8`) — catalog literal per carrier (air / ground /
      regional).
- [x] **`carriers.fuel_surcharge_pct`** (`Float64`) — small per-carrier rate (~0.08–0.16).
- [x] **`warehouses.capacity_units`** (`Int64`) — lognormal per facility.
- [x] **`warehouses.opened_date`** (`Date`) — 1–10 years before the window start.
- [x] **`deliveries.delivery_method`** (`Utf8`) — {doorstep, locker, pickup_point, signature},
      keyed off `signature_required`, null on non-delivered.

## High-leverage additions

### 1. `scan_events.facility_type`
- [ ] Tag each scan with its network stage (`Utf8`: origin_hub / linehaul / destination_hub /
      local), derived from `scan_type` + `seq` position rather than a fresh draw.
- **Unlocks:** per-stage dwell-time analysis (elapsed time between stages), where delay
  accrues in the network — a deeper cut of the existing event-log teaching value.
- **Class:** realism enrichment.

### 2. `shipments.insured_value`
- [ ] Declared value (`Float64`, right-skew via `ctx.dist.lognormal`, floored near the cost).
- **Unlocks:** loss/exposure analysis — value at risk on `lost` / `returned_to_sender` parcels.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: loss rate
  or attempts rises with declared value (high-value parcels handled/flagged differently), or
  value concentrates in a service tier. Name the subset signal; don't plant it here.

### 3. `scan_events.exception_reason`
- [ ] Nullable reason on `exception` scans only (`Utf8`: address_issue / refused / damaged /
      customs_hold / lost_in_transit); null on all happy-path scans.
- **Unlocks:** a failure-cause funnel behind the `returned_to_sender` / `lost` outcomes —
  *why* parcels don't arrive, not just that they don't.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: the reason
  mix differs by `dest_zone` or `carrier` (far zones skew address/customs, cheap carriers skew
  damage). Route it, don't build it.

### 4. `deliveries.delivery_cost` (cost vs. price)
- [ ] The carrier's *cost* to deliver (`Float64`), below the customer-facing `shipping_cost`
      (which is price). Draw as `shipping_cost × margin_factor` with per-service jitter.
- **Unlocks:** unit-economics — gross margin per shipment, margin by lane/service.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: margin is
  thin or negative on far zones / overnight (price doesn't fully cover distance cost).

### 5. `shipments` dimensions → dimensional weight
- [ ] Add `length_cm` / `width_cm` / `height_cm` (`Float64`, correlated with `weight_kg`), so
      *billable weight* = `max(weight_kg, dim_weight)` is derivable.
- **Unlocks:** the dimensional-weight pricing lever real carriers use; composes with
  `shipping_cost` and `package_type`.
- **Class:** realism enrichment (would refine, not replace, the current cost identity — note
  the identity in `realism-guidance.md` must be reconciled if billable weight feeds cost).

## Out of scope (new table, not a field)

- **A recipient / customer dimension** (who receives the parcel, with an FK from `shipments`)
  is a genuinely new entity, not a column — route to `/data-collection:propose`, not here.

## Open realism items to investigate

Too-synthetic / drift candidates for `/data-collection:review-edit-regen-for-realism`
(existing data to investigate, not new fields). The realism-log records the *runs*; these are
the *open* items.

- [ ] **Intermediate `in_transit` hub city is drawn once per shipment** and repeats across a
      multi-hop parcel, unrelated to origin→destination geography. If someone maps routes it
      reads as synthetic — check whether hub cities should vary per hop and sit "between"
      origin and destination.
- [ ] **`dest_zone` is independent of `dest_city` / `warehouses.city`.** A parcel can be zone
      1 to a far city or zone 8 to a near one — a distance proxy with no geographic grounding.
      Measure whether a zone×city cross-tab looks implausible.
- [ ] **Memoryless outcomes.** On-time, terminal status, and early/late days are independent
      per shipment — no per-carrier streaks, seasonality, or weather. Confirm there's no
      expectation of autocorrelation a student would notice.
- [ ] **Cost-tail sanity.** Re-confirm the cost tail past \$80 is weight-driven and not
      clipping oddly at the `weight_kg` clamp (50 kg) — spot-check the top decile.

## When the list is done

- [ ] **Revise `realism-guidance.md`.** After the fields above land, reconcile the realism
      rubric and invariant tests with the new columns (new dimensions to slice by, new
      invariants — e.g. `exception_reason` non-null iff terminal scan is `exception`,
      `delivery_cost < shipping_cost`). Run `/data-collection:review-edit-regen-for-realism`
      for this collection.

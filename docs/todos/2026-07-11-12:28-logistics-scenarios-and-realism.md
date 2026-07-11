# Logistics — dated working checklist (2026-07-11 12:28)

- **Scope:** the `logistics` collection only.
- **Source of truth:** [`collections/logistics/TODO.md`](../../src/potato_tornado/collections/logistics/TODO.md).
  This checklist carries **no item substance of its own** — each item below links to its entry in
  `TODO.md` for the recipe, class (realism vs scenario-bearing), and definition of done. It exists
  only to track this dated run's progress: tick an item here when it lands, tick it in `TODO.md`
  too, and log the run in
  [`realism-log.md`](../../src/potato_tornado/collections/logistics/realism-log.md). Workflow lives
  in [collections/CLAUDE.md](../../src/potato_tornado/collections/CLAUDE.md) and the
  `/data-collection:*` / `/scenario:*` commands.
- **Status:** quick wins + the two realism high-leverage items already shipped. The 3
  scenario-bearing columns stay routed to `/scenario:draft-or-propose` per `TODO.md` ("route it,
  don't build it"); the 4 open realism items are all resolved (hub-city de-latticed 2026-07-11, the
  other three confirmed intentional).

## Checklist

**High-leverage columns (scenario-bearing → routed) →** [`TODO.md` § High-leverage additions](../../src/potato_tornado/collections/logistics/TODO.md#high-leverage-additions)

- [ ] `shipments.insured_value`
- [ ] `scan_events.exception_reason`
- [ ] `deliveries.delivery_cost`

**Open realism items →** [`TODO.md` § Open realism items to investigate](../../src/potato_tornado/collections/logistics/TODO.md#open-realism-items-to-investigate)

- [x] Intermediate `in_transit` hub city drawn once per shipment *(2026-07-11 — per-hop fix)*
- [x] `dest_zone` independent of `dest_city` / `warehouses.city` *(2026-07-11 — confirmed intentional)*
- [x] Memoryless outcomes (no streaks / seasonality / weather) *(2026-07-11 — confirmed intentional)*
- [x] Cost-tail sanity past $80 *(2026-07-11 — confirmed healthy)*

**When the list is done →** [`TODO.md` § When the list is done](../../src/potato_tornado/collections/logistics/TODO.md#when-the-list-is-done)

- [ ] Revise `realism-guidance.md` for the routed scenario columns when they land

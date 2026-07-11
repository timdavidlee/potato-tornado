# Streaming — dated working checklist (2026-07-11 12:28)

- **Scope:** the `streaming` collection only.
- **Source of truth:** [`collections/streaming/TODO.md`](../../src/potato_tornado/collections/streaming/TODO.md).
  This checklist carries **no item substance of its own** — each item below links to its entry in
  `TODO.md` for the recipe, class (realism vs scenario-bearing), and definition of done. It exists
  only to track this dated run's progress: tick an item here when it lands, tick it in `TODO.md`
  too, and log the run in
  [`realism-log.md`](../../src/potato_tornado/collections/streaming/realism-log.md). Workflow lives
  in [collections/CLAUDE.md](../../src/potato_tornado/collections/CLAUDE.md) and the
  `/data-collection:*` / `/scenario:*` commands.
- **Status:** 14 of 14 enrichment items shipped (`subscriptions.mrr` built 2026-07-11);
  subscription right-censoring realized 2026-07-11; 3 open realism items remain (whale
  concentration, premium-by-recency, device/region mix — deferred or scenario-bearing).

## Checklist

**Deferred column →** [`TODO.md` § Later / depends-on](../../src/potato_tornado/collections/streaming/TODO.md#later--depends-on)

- [x] `subscriptions.mrr` *(2026-07-11)*

**Open realism items →** [`TODO.md` § Open realism items to investigate](../../src/potato_tornado/collections/streaming/TODO.md#open-realism-items-to-investigate)

- [ ] No heavy-renter concentration
- [x] Subscription lifecycle is birth-only *(right-censoring realized 2026-07-11)*
- [ ] `is_premium` is release-date independent
- [ ] Device/region mixes are flat, unplanted

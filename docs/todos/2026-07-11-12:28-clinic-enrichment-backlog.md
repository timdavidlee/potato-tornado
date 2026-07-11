# Clinic — dated working checklist (2026-07-11 12:28)

- **Scope:** the `clinic` collection only.
- **Source of truth:** [`collections/clinic/TODO.md`](../../src/potato_tornado/collections/clinic/TODO.md).
  This checklist carries **no item substance of its own** — each item below links to its entry in
  `TODO.md` for the recipe, class (realism vs scenario-bearing), and definition of done. It exists
  only to track this dated run's progress: tick an item here when it lands, tick it in `TODO.md`
  too, and log the run in
  [`realism-log.md`](../../src/potato_tornado/collections/clinic/realism-log.md). Workflow lives in
  [collections/CLAUDE.md](../../src/potato_tornado/collections/CLAUDE.md) and the
  `/data-collection:*` / `/scenario:*` commands.
- **Status:** the enrichment backlog was surveyed-only; the full quick-win + high-leverage batch
  (11 columns, scenario-bearing ones built flat) landed 2026-07-11. Three open realism items remain
  intentional; the scenario signals behind the flat columns route out.

## Checklist

**Quick-win columns →** [`TODO.md` § Quick wins](../../src/potato_tornado/collections/clinic/TODO.md#quick-wins-realism-enrichment)

- [x] `patients.age_band` *(2026-07-11)*
- [x] `patients.insurance_type` *(2026-07-11)*
- [x] `providers.years_experience` *(2026-07-11)*
- [x] `slots.telehealth_flag` *(2026-07-11)*
- [x] `appointments.booking_channel` *(2026-07-11)*
- [x] `invoices.days_to_pay` *(2026-07-11)*

**High-leverage additions** (scenario-bearing built flat) **→** [`TODO.md` § High-leverage additions](../../src/potato_tornado/collections/clinic/TODO.md#high-leverage-additions)

- [x] `appointments.reminder_sent` + `reminder_channel` *(2026-07-11 — flat)*
- [x] `visits.diagnosis_category` *(2026-07-11 — flat)*
- [x] `patients.chronic_flag` / `risk_score` *(2026-07-11 — flat)*
- [x] `invoices.adjustment_amount` + denial detail *(2026-07-11 — flat)*
- [x] `providers.panel_size` *(2026-07-11)*

**Open realism items →** [`TODO.md` § Open realism items to investigate](../../src/potato_tornado/collections/clinic/TODO.md#open-realism-items-to-investigate)

- [ ] Slots are independent draws, not a grid
- [ ] `scheduled` status is a flat 8% draw, not date-derived
- [ ] No per-patient no-show history
- [x] Billing collapses the payer process into one row *(2026-07-11 — flat split shipped)*

**When the list is done →** [`TODO.md` § When the list is done](../../src/potato_tornado/collections/clinic/TODO.md#when-the-list-is-done)

- [ ] Revise `realism-guidance.md` (reconciled per column as each landed)

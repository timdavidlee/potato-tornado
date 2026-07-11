# Clinic enrichment backlog — task list

- **Created:** 2026-07-11 12:28
- **Scope:** the `clinic` collection only.
- **Source:** [`collections/clinic/TODO.md`](../../src/potato_tornado/collections/clinic/TODO.md)
  — the authoritative backlog. This file is a working checklist extracted from it; keep the two
  in step (check an item here → check it there when it lands, and record the run in
  [`realism-log.md`](../../src/potato_tornado/collections/clinic/realism-log.md)).
- **Status:** nothing implemented yet — the field-enrichment backlog was surveyed 2026-07-02 and
  no columns have shipped. Everything below is open.

## How to work this list

Each task is classed **realism** or **scenario-bearing**:

- **Realism** items → realize with `/data-collection:review-edit-regen-for-realism clinic`
  (build the column/table flat, reconcile `realism-guidance.md`, pin an invariant test).
- **Scenario-bearing** items → the *flat* version is realism work; the *surprising subset signal*
  goes through `/scenario:draft-or-propose clinic` then `/scenario:review-and-edit-regenerate`.
  Don't plant the signal during the realism pass.

**Definition of done** (every task): draw only from `ctx.dist` / `ctx.rng.child` / `ctx.entities`
on a **name-keyed child stream** without reordering existing draws; reconcile the matching line in
`realism-guidance.md`; add/extend an invariant test in
`tests/collections/clinic/test_clinic.py`; and the full gate is green
(`uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`).

---

## Quick-win columns (realism enrichment)

- [ ] **`patients.age_band`** (`Utf8`, `{peds, 18-40, 41-65, 65+}`)
  - File: `tables/patients.py`. Draw: `ctx.dist.choice` weighted on an own child stream.
  - Unlocks: no-show / visit-type slicing by age.
  - Class: **realism** (flat).

- [ ] **`patients.insurance_type`** (`Utf8`, `{commercial, medicare, medicaid, self_pay}`)
  - File: `tables/patients.py`. Draw: weighted `ctx.dist.choice`; a **patient-level** coverage
    band, distinct from the per-visit `invoices.payer`.
  - Unlocks: payer-mix demographics; a covariate for AR.
  - Class: **realism** (flat).

- [ ] **`providers.years_experience`** (`Int64`)
  - File: `tables/providers.py`. Draw: `ctx.dist.integers(1, 35)` on an own child stream.
  - Unlocks: seniority slicing (overrun / panel by tenure).
  - Class: **realism** (flat).

- [ ] **`slots.telehealth_flag`** (`Boolean`)
  - File: `tables/slots.py`. Draw: `ctx.dist.bernoulli` on an own child stream.
  - Unlocks: modality mix (in-person vs. virtual); a plausible no-show covariate.
  - Class: **realism** (flat).

- [ ] **`appointments.booking_channel`** (`Utf8`, `{phone, portal, walk_in, referral}`)
  - File: `tables/appointments.py`. Draw: weighted `ctx.dist.choice` on an own child stream.
  - Unlocks: booking-funnel analysis.
  - Class: **realism** (flat).

- [ ] **`invoices.days_to_pay`** (`Int64`, nullable until paid)
  - File: `tables/invoices.py`. Draw: derive from a payment-date draw; null while unpaid.
  - Unlocks: AR aging (days-sales-outstanding) beyond the current `balance` / `status`.
  - Class: **realism** (flat).

## High-leverage additions

- [ ] **`appointments.reminder_sent`** (`Boolean`) + optional `reminder_channel` (`sms/email/none`)
  - File: `tables/appointments.py`. Draw: `ctx.dist.bernoulli` on an own child stream.
  - Unlocks: the reminder → attendance funnel — the single most actionable no-show lever.
  - Class: **scenario-bearing** → *reminded appointments no-show materially less* (interacts with
    the existing lead-time gradient). Name it; don't plant it in the realism pass.

- [ ] **`visits.diagnosis_category`** (`Utf8`, `{preventive, acute, chronic_followup, procedure}`)
  - File: `tables/visits.py`. Draw: keyed to `visit_type`, on an own child stream.
  - Unlocks: clinical-mix analysis; a covariate for duration overrun and follow-up.
  - Class: **scenario-bearing** → *overrun concentrates in one category (procedures run long)* —
    a deeper cut of the existing duration-overrun scenario.

- [ ] **`patients.chronic_flag`** (`Boolean`) / `risk_score` (`Float64`)
  - File: `tables/patients.py`. Draw: correlated with `age_band` (build that first), own stream.
  - Unlocks: utilization analysis — do chronic patients book / visit more?
  - Class: **scenario-bearing** → *a small high-risk patient minority drives a disproportionate
    visit share* (a concentration signal).

- [ ] **`invoices.adjustment_amount`** (`Float64`) + denial detail (`denied_amount` / `claim_status`)
  - File: `tables/invoices.py`. Draw: split the payer process so
    `charge → allowed → paid → patient_balance` is visible rather than collapsed; own stream.
  - Unlocks: the payer adjudication funnel — directly addresses the standing realism note that
    billing collapses the payer process into one row (see open realism item below).
  - Class: **scenario-bearing** → *denial / adjustment rate varies by `payer` (Medicaid writes
    down more)* — attributes the AR.

- [ ] **`providers.panel_size`** (`Int64`)
  - File: `tables/providers.py`. Draw: an empanelled patient count, a provider capacity attribute.
  - Unlocks: utilization denominator — visits per panel, provider load.
  - Class: **realism** (flat).

## Open realism items to investigate

Route to `/data-collection:review-edit-regen-for-realism clinic` (existing data to investigate,
not new fields).

- [ ] **Slots are independent draws, not a grid.** Each slot gets a random weekday/time rather
  than a provider's fixed daily schedule — candidate to move to a per-provider grid.
- [ ] **`scheduled` status is a flat 8% draw, not date-derived.** Future-dated appointments aren't
  specifically the still-scheduled ones — check whether the status × date cross-tab reads wrong.
- [ ] **No per-patient no-show history.** No-show depends on lead time only; no repeat no-show
  behaviour by patient. Flag only if per-patient autocorrelation is expected.
- [ ] **Billing collapses the payer process into one row.** No claim-adjustment/denial detail; the
  high-leverage `invoices.adjustment_amount` item above is the fix.

## When the list is done

- [ ] **Revise `realism-guidance.md`.** Reconcile the rubric and invariant tests with the new
  columns (new dimensions to slice by, new invariants — e.g. `days_to_pay ≥ 0` and null iff
  unpaid, `adjustment_amount ≤ charge`, `diagnosis_category` consistent with `visit_type`).

---

## Suggested order

1. **Quick-win columns** (6) — smallest, all realism; one realism pass can land them together
   (`age_band` first so `chronic_flag` can key off it).
2. **`providers.panel_size`** — realism, unlocks the utilization denominator.
3. **`invoices.adjustment_amount`** — highest-leverage single change; closes the standing
   "billing collapses the payer process" realism gap.
4. Remaining scenario-bearing columns (`reminder_sent`, `diagnosis_category`, `chronic_flag`) as
   flat columns first, then route each surprise to `/scenario:draft-or-propose clinic`.

## v0.7.0 (2026-07-11)

### Feat

- **data-collection**: plant high-risk-patient and whale-rental scenario signals

## v0.6.0 (2026-07-11)

### Feat

- **data-collection**: draft one new scenario doc per collection

## v0.5.0 (2026-07-11)

### Feat

- **data-collection**: plant 6 needs-planting scenario signals across collections

## v0.4.0 (2026-07-11)

### Feat

- **data-collection**: add document-based scenario propose/realize commands

## v0.3.0 (2026-07-11)

### Feat

- **data-collection**: document and test 8 already-planted scenario signals

## v0.2.0 (2026-07-11)

### Feat

- **data-collection**: realize enrichment and realism backlogs across collections
- **data-collection**: add tackle-todos command for subagent-driven backlog work
- **data-collection**: add scan-todos command, dated backlogs, refresh inventory

## v0.1.0 (2026-07-02)

### Feat

- **postgres**: psycopg3 DSN fix + seed command (schema per collection)
- **logistics**: add facility_type + parcel dimensions
- **retail**: add returns.item_condition mediating restock (#21)
- **logistics**: add quick-win realism enrichment columns
- **retail**: quick-win field enrichment + realism sweep (#18)
- **insurance**: quick-win field enrichment + premium_billing table (#17)
- **insurance**: add adjusters + quotes tables (#15)
- **collections**: logistics/retail/insurance + hotel/labor/streaming enrichment
- **hotel**: new scenario proposals + lead-time/rate-ladder/room-mix signals
- **clinic**: new scenario proposals + procedure/late-run/patient-mix signals
- **collections**: tune scenarios, add scenario tests, new proposals
- **collections**: clinic+streaming tables/scenarios, 3-year default window (#6)
- **hotel**: room upgrades/stay changes, realism docs, scenario commands, clinic+streaming
- **pools**: entity pools + pydantic dep

### Fix

- **insurance**: skew peril mix and policyholder tenure (realism) (#20)

### Refactor

- **collections**: realism-pass tuning (insurance/labor/logistics) + doc map
- **scenarios**: retire too-general scenarios; rework into subset flips (#10)
- **collections**: folder-per-collection layout

"""Domain reference data (catalogs) for the labor collection.

These literal tables are the fixed "seed" facts the generators draw from — the
department cost centres, the role ladder, employment types and shift windows.
They live here (rather than inline in a table module) so the whole collection
shares one source of truth and the ``tables/`` modules stay focused on
generation logic. See ``scenarios/`` for the signals these values are tuned to
produce.
"""

from __future__ import annotations

# Practice areas of a technology consulting firm.
# (name, base_hourly_rate) — base is the practice's internal blended cost rate.
DEPARTMENTS = [
    ("Strategy & Advisory", 95.0),
    ("Cybersecurity", 90.0),
    ("Data & Analytics", 85.0),
    ("Cloud & Infrastructure", 82.0),
    ("Software Engineering", 78.0),
    ("Product & Design", 74.0),
    ("Project Management", 70.0),
    ("IT Support Services", 64.0),
]

# Practice classification. Client-delivery practices bill work to clients; the two
# enabling functions (PMO and internal IT) are overhead. Used to key the
# billable/utilization fields — the split is expected, so it's a realism mix, not a
# planted scenario. A department is "enabling" iff its name is in this set.
ENABLING_DEPARTMENTS = {"Project Management", "IT Support Services"}

# Primary skill an employee is drawn from, keyed on their department (practice).
# A join-free slice dimension for skills-supply / skill-mix analysis; the draw is
# uniform within a department, so it's realism enrichment (no segment signal). Every
# department name in DEPARTMENTS must have an entry here.
SKILLS_BY_DEPARTMENT = {
    "Strategy & Advisory": ["Market Analysis", "Operating Model", "M&A Diligence", "Change Mgmt"],
    "Cybersecurity": ["Penetration Testing", "SIEM", "Identity & Access", "Incident Response"],
    "Data & Analytics": ["SQL", "Python", "dbt", "Machine Learning"],
    "Cloud & Infrastructure": ["AWS", "Azure", "Kubernetes", "Terraform"],
    "Software Engineering": ["Backend", "Frontend", "Mobile", "DevOps"],
    "Product & Design": ["UX Research", "UI Design", "Product Strategy", "Prototyping"],
    "Project Management": ["Agile Delivery", "PMO Governance", "Risk Mgmt", "Stakeholder Mgmt"],
    "IT Support Services": ["Helpdesk", "Endpoint Mgmt", "Networking", "Systems Admin"],
}

# Where an employee primarily works. A workforce work-arrangement mix to slice by
# (real-estate / return-to-office analysis). Flat weights here; any concentration
# of remote in a slice is a future scenario, not planted. Weights sum to 1.
WORK_MODES = ["onsite", "hybrid", "remote"]
WORK_MODE_WEIGHTS = [0.30, 0.50, 0.20]

# Recruiting channel an employee was hired through. A join-free slice for
# recruiting-channel mix (and a future quality-of-hire / attrition cut). Flat
# weights — any "referrals churn less" signal is a future scenario, not planted
# here. Weights sum to 1.
HIRE_SOURCES = ["referral", "agency", "campus", "direct", "rehire"]
HIRE_SOURCE_WEIGHTS = [0.28, 0.22, 0.20, 0.25, 0.05]

# Role ladder, most senior last; weights are how common each role is.
ROLES = ["Associate", "Senior Associate", "Lead", "Supervisor", "Manager"]
ROLE_WEIGHTS = [0.5, 0.25, 0.13, 0.08, 0.04]

EMPLOYMENT = ["full_time", "part_time", "contractor"]
EMPLOYMENT_WEIGHTS = [0.6, 0.3, 0.1]

# (window_name, start_hour)
SHIFT_WINDOWS = [("morning", 6), ("afternoon", 14), ("night", 22)]

# Company sites employees are based at and projects run from. A small fixed set
# (like DEPARTMENTS) rather than free-form cities, so "same location" is a
# meaningful join — a handful of offices, not ~200 unique places. Weights are
# hub-heavy: New York is HQ, the rest are progressively smaller satellites.
LOCATIONS = ["New York", "Chicago", "Seattle", "Austin", "Atlanta", "Denver"]
LOCATION_WEIGHTS = [0.30, 0.20, 0.16, 0.14, 0.12, 0.08]

# Expected share of a project's members who are off-site (based at a different
# location than the project itself). The big hubs staff locally; the small
# satellites lean on remote/off-site staff because their local pool is thin. This
# spread is the planted signal — see scenarios/off-site-staffing-by-location.md.
REMOTE_RATE_BY_LOCATION = {
    "New York": 0.10,
    "Chicago": 0.18,
    "Seattle": 0.22,
    "Austin": 0.30,
    "Atlanta": 0.40,
    "Denver": 0.50,
}

# Project lifecycle mix.
PROJECT_STATUSES = ["active", "completed", "on_hold"]
PROJECT_STATUS_WEIGHTS = [0.5, 0.4, 0.1]

# Client vertical the project's client operates in. A slice-by dimension for the
# consulting lens (project mix / economics by industry). Drawn independently of
# department and economics — a flat mix, no margin signal planted (that would be a
# scenario). Weights sum to 1.
INDUSTRIES = [
    "Financial Services",
    "Technology",
    "Healthcare",
    "Retail",
    "Public Sector",
    "Manufacturing",
    "Energy",
]
INDUSTRY_WEIGHTS = [0.22, 0.18, 0.16, 0.14, 0.12, 0.12, 0.06]

# Commercial model for the engagement. time_and_materials dominates; fixed_fee and
# retainer are the rest. Flat mix, independent of industry/priority — the
# fixed-fee realization/overrun signals are future scenarios, not planted here.
BILLING_TYPES = ["time_and_materials", "fixed_fee", "retainer"]
BILLING_TYPE_WEIGHTS = [0.55, 0.30, 0.15]

# Client-account tier, a size/importance band on the `clients` dimension. Weighted
# so most accounts are mid/growth and only a few are strategic. Flat mix — the
# revenue-Pareto (a few strategic clients carrying a large share of billed hours)
# is a future scenario, not planted here. Weights sum to 1.
CLIENT_TIERS = ["strategic", "growth", "mid", "small"]
CLIENT_TIER_WEIGHTS = [0.15, 0.30, 0.35, 0.20]

# Engagement priority — a staffing/attention dimension to slice by.
PROJECT_PRIORITIES = ["low", "medium", "high"]
PROJECT_PRIORITY_WEIGHTS = [0.30, 0.50, 0.20]

# Role a member plays on a project (distinct from their org `role`). One lead per
# project (assigned separately); everyone else is a contributor.
PROJECT_MEMBER_ROLES = ["lead", "contributor"]

# Code names projects draw from (cycled, with a phase suffix past the first pass
# so names stay unique at any scale).
PROJECT_CODE_NAMES = [
    "Atlas",
    "Beacon",
    "Cascade",
    "Delta",
    "Everest",
    "Falcon",
    "Granite",
    "Horizon",
    "Iris",
    "Juniper",
    "Kestrel",
    "Lumen",
    "Meridian",
    "Nimbus",
    "Orchard",
    "Pioneer",
    "Quartz",
    "Radar",
    "Summit",
    "Tempo",
    "Umbra",
    "Vertex",
    "Willow",
    "Xenon",
    "Yonder",
    "Zephyr",
]

"""Domain reference data (catalogs) for the labor collection.

These literal tables are the fixed "seed" facts the generators draw from — the
department cost centres, the role ladder, employment types and shift windows.
They live here (rather than inline in a table module) so the whole collection
shares one source of truth and the ``tables/`` modules stay focused on
generation logic. See ``scenarios/`` for the signals these values are tuned to
produce.
"""

from __future__ import annotations

# (name, base_hourly_rate)
DEPARTMENTS = [
    ("Front of House", 26.0),
    ("Kitchen", 24.0),
    ("Housekeeping", 21.0),
    ("Maintenance", 28.0),
    ("Warehouse", 23.0),
    ("Logistics", 27.0),
    ("Guest Services", 25.0),
    ("Security", 24.5),
]

# Role ladder, most senior last; weights are how common each role is.
ROLES = ["Associate", "Senior Associate", "Lead", "Supervisor", "Manager"]
ROLE_WEIGHTS = [0.5, 0.25, 0.13, 0.08, 0.04]

EMPLOYMENT = ["full_time", "part_time", "contractor"]
EMPLOYMENT_WEIGHTS = [0.6, 0.3, 0.1]

# (window_name, start_hour)
SHIFT_WINDOWS = [("morning", 6), ("afternoon", 14), ("night", 22)]

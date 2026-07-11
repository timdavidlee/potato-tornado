"""Table builders for the labor collection.

One module per table; each exposes a ``build_<table>(ctx) -> pl.DataFrame``
function that the collection wires into a ``TableSpec``. Re-exported here so the
collection's ``__init__`` can import them from one place.
"""

from __future__ import annotations

from potato_tornado.collections.labor.tables.assignments import build_assignments
from potato_tornado.collections.labor.tables.clients import build_clients
from potato_tornado.collections.labor.tables.departments import build_departments
from potato_tornado.collections.labor.tables.employee_skills import build_employee_skills
from potato_tornado.collections.labor.tables.employees import build_employees
from potato_tornado.collections.labor.tables.expenses import build_expenses
from potato_tornado.collections.labor.tables.performance_reviews import build_performance_reviews
from potato_tornado.collections.labor.tables.project_members import build_project_members
from potato_tornado.collections.labor.tables.projects import build_projects
from potato_tornado.collections.labor.tables.shifts import build_shifts
from potato_tornado.collections.labor.tables.time_entries import build_time_entries
from potato_tornado.collections.labor.tables.time_off import build_time_off

__all__ = [
    "build_assignments",
    "build_clients",
    "build_departments",
    "build_employee_skills",
    "build_employees",
    "build_expenses",
    "build_performance_reviews",
    "build_project_members",
    "build_projects",
    "build_shifts",
    "build_time_entries",
    "build_time_off",
]

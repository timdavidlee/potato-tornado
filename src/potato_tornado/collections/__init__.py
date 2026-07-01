"""Built-in data collection definitions.

Each collection is a **package** (``<name>/``) — not a single module — laid out as:

- ``__init__.py``  : assembles the :class:`~potato_tornado.core.collection.Collection`
  from its table specs and registers it via
  :func:`~potato_tornado.core.registry.register`.
- ``constants.py`` : domain reference data / catalogs shared across tables.
- ``tables/``      : one module per table, each a ``build_<table>(ctx)`` function.
- ``scenarios/``   : markdown docs describing the intended analytical signals
  planted in the data (the teaching "answer key").

See ``collections/CLAUDE.md`` for the full pattern.
"""

"""Command-line interface: list, describe and generate collections."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer

from potato_tornado.core.config import GenerationConfig
from potato_tornado.core.registry import get_collection, iter_collections
from potato_tornado.pools.store import build_pool
from potato_tornado.runner import generate, generate_to_sink
from potato_tornado.sinks.duckdb_sink import DuckDBSink

app = typer.Typer(
    name="potato-tornado",
    help="Generate synthetic teaching datasets into DuckDB / Postgres.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command("list")
def list_collections() -> None:
    """List the available data collection definitions."""
    for collection in iter_collections():
        typer.secho(collection.name, fg=typer.colors.CYAN, bold=True, nl=False)
        typer.echo(f"  {collection.description}")


@app.command()
def describe(name: str) -> None:
    """Show the tables (and dependencies) of a collection."""
    collection = get_collection(name)
    typer.secho(f"{collection.name}: {collection.description}\n", bold=True)
    for spec in collection.build_order():
        deps = f" (depends on: {', '.join(spec.depends_on)})" if spec.depends_on else ""
        typer.secho(f"  • {spec.name}", fg=typer.colors.GREEN, nl=False)
        typer.echo(f"{deps}\n    {spec.description}")


@app.command("generate")
def generate_cmd(
    name: str = typer.Argument(..., help="Collection name, e.g. 'labor' or 'hotel'."),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="DuckDB file to write. Omit for a dry run (counts only)."
    ),
    seed: int = typer.Option(42, help="Master seed for reproducibility."),
    scale: float = typer.Option(1.0, help="Row-count multiplier (1.0 = reference size)."),
    start: datetime = typer.Option(
        datetime(2024, 1, 1), formats=["%Y-%m-%d"], help="Event window start (YYYY-MM-DD)."
    ),
    end: datetime = typer.Option(
        datetime(2025, 1, 1), formats=["%Y-%m-%d"], help="Event window end (YYYY-MM-DD)."
    ),
    pool: Path | None = typer.Option(
        None,
        "--pool",
        help="Entity-pool directory to sample names/companies/cities from "
        "(built via `build-pool`). Omit to generate those from scratch.",
    ),
) -> None:
    """Generate a collection, optionally loading it into a DuckDB file."""
    config = GenerationConfig(
        seed=seed,
        scale=scale,
        start_date=start.date(),
        end_date=end.date(),
        pool_dir=pool,
    )

    if out is None:
        tables = generate(name, config)
    else:
        with DuckDBSink(out) as sink:
            tables = generate_to_sink(name, sink, config)
        typer.secho(f"Wrote {out}", fg=typer.colors.GREEN, bold=True)

    for table_name, df in tables.items():
        typer.echo(f"  {table_name:<20} {df.height:>10,} rows")


@app.command("build-pool")
def build_pool_cmd(
    out: Path = typer.Argument(..., help="Directory to write the entity pool into."),
    size: int = typer.Option(5000, help="Number of entities to generate per category."),
    seed: int = typer.Option(42, help="Seed for the (offline) pool generation."),
) -> None:
    """Generate an entity pool offline and persist it for later `generate --pool`."""
    pool = build_pool(GenerationConfig(seed=seed), size=size)
    pool.save(out)
    typer.secho(
        f"Wrote entity pool ({size} per category) to {out}", fg=typer.colors.GREEN, bold=True
    )


if __name__ == "__main__":
    app()

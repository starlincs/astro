"""Render pipeline run listings for the CLI."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from rich.console import Console
from rich.table import Table

from astro.storage.sqlite import PipelineStore


def render_run_list(pipeline_dir: Path) -> str:
    """Return a formatted table of stored pipeline runs."""
    store = PipelineStore(pipeline_dir / ".astro" / "stats.db")
    runs = store.list_runs()

    table = Table(title="Pipeline runs")
    table.add_column("Run ID", style="cyan")
    table.add_column("Pipeline")
    table.add_column("Status")
    table.add_column("Source directory")
    table.add_column("Created")
    table.add_column("Ingested")

    if not runs:
        table.add_row("-", "-", "no runs recorded", "-", "-", "-")
    else:
        for run in runs:
            table.add_row(
                str(run["run_id"]),
                str(run["pipeline_name"]),
                str(run["status"]),
                str(run["source_directory"]),
                str(run["created_at"]),
                str(run["ingested_at"] or "-"),
            )

    buffer = StringIO()
    console = Console(file=buffer, width=120, force_terminal=False)
    console.print(table)
    return buffer.getvalue().rstrip()

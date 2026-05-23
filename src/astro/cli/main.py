"""Astro CLI entry point."""

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="astro",
    help="Run and manage CSV import pipelines.",
    no_args_is_help=True,
)


@app.command()
def ingest(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to a CSV file or a directory of files to ingest.",
        ),
    ],
    pipeline_dir: Annotated[
        Path | None,
        typer.Option(
            "--pipeline-dir",
            "-C",
            help="Directory containing pipeline.py. Defaults to the current directory.",
        ),
    ] = None,
) -> None:
    """Ingest a CSV file or directory of files into the pipeline."""
    typer.echo("ingest: not implemented")


@app.command()
def run(
    pipeline_dir: Annotated[
        Path | None,
        typer.Option(
            "--pipeline-dir",
            "-C",
            help="Directory containing pipeline.py. Defaults to the current directory.",
        ),
    ] = None,
) -> None:
    """Run the pipeline."""
    typer.echo("run: not implemented")


@app.command(name="list")
def list_pipelines(
    pipeline_dir: Annotated[
        Path | None,
        typer.Option(
            "--pipeline-dir",
            "-C",
            help="Directory containing pipeline.py. Defaults to the current directory.",
        ),
    ] = None,
) -> None:
    """List registered pipelines and their statistics."""
    typer.echo("list: not implemented")


@app.command()
def cleanup(
    pipeline_dir: Annotated[
        Path | None,
        typer.Option(
            "--pipeline-dir",
            "-C",
            help="Directory containing pipeline.py. Defaults to the current directory.",
        ),
    ] = None,
    all_runs: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Remove all stored pipeline statistics.",
        ),
    ] = False,
) -> None:
    """Clean up stored pipeline data and statistics."""
    typer.echo("cleanup: not implemented")


if __name__ == "__main__":
    app()

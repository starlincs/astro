"""Astro CLI entry point."""

from pathlib import Path
from typing import Annotated

import typer

from astro.ingest import IngestService, IngestValidationError
from astro.pipeline.discovery import discover_pipeline, get_pipeline_instance
from astro.working import SerialIngestConflictError

app = typer.Typer(
    name="astro",
    help="Run and manage CSV import pipelines.",
    no_args_is_help=True,
)


def _resolve_pipeline_dir(pipeline_dir: Path | None) -> Path:
    return pipeline_dir or Path.cwd()


@app.command()
def ingest(
    path: Annotated[
        Path,
        typer.Argument(help="Path to a directory of source files to ingest."),
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
    """Ingest source files into a new pipeline run."""
    search_dir = _resolve_pipeline_dir(pipeline_dir)
    if discover_pipeline(search_dir) is None:
        typer.secho(f"No pipeline.py found in {search_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if not path.exists():
        typer.secho(f"Source path does not exist: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    if not path.is_dir():
        typer.secho(
            f"Source path must be a directory: {path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    pipeline = get_pipeline_instance(search_dir)
    if pipeline is None:
        typer.secho(
            "pipeline.py must export a Pipeline instance named 'pipeline'.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    service = IngestService(search_dir, pipeline)
    try:
        result = service.ingest(path)
    except SerialIngestConflictError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    except IngestValidationError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    except Exception as error:
        typer.secho(f"Ingest failed: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Run {result.run_id} created at {result.run_directory}")
    for file_name in result.ingested_files:
        typer.echo(f"  ingested {file_name}")


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

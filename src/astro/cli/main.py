"""Astro CLI entry point."""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.live import Live
from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn

from astro.cli.display.dashboard import RunDashboard
from astro.cli.display.flow import render_flow_diagram
from astro.cli.display.steps import build_run_tracker
from astro.cli.logging import (
    LogMode,
    get_run_log_path,
    setup_astro_logging,
    write_session_separator,
)
from astro.cli.run_context import RunResolutionError, resolve_run_directory
from astro.ingest import IngestService, IngestValidationError
from astro.pipeline.discovery import discover_pipeline, get_pipeline_instance
from astro.run import RunService
from astro.working import SerialIngestConflictError

app = typer.Typer(
    name="astro",
    help="Run and manage CSV import pipelines.",
    no_args_is_help=True,
)

logger = logging.getLogger("astro.cli")


class DisplayMode(StrEnum):
    DASHBOARD = "dashboard"
    CLI = "cli"


def _resolve_pipeline_dir(pipeline_dir: Path | None) -> Path:
    return pipeline_dir or Path.cwd()


def _exit_with_logged_error(message: str, *, code: int = 1) -> None:
    logger.error(message)
    raise typer.Exit(code=code)


def _execute_run(
    *,
    search_dir: Path,
    run_directory: Path,
    manifest,
    mode: DisplayMode,
    log_file: Path,
    append: bool,
) -> None:
    if discover_pipeline(search_dir) is None:
        raise RunResolutionError(f"No pipeline.py found in {search_dir}")

    pipeline = get_pipeline_instance(search_dir)
    if pipeline is None:
        raise RunResolutionError("pipeline.py must export a Pipeline instance named 'pipeline'.")
    assert pipeline is not None

    run_service = RunService()
    tracker = build_run_tracker(pipeline, manifest)

    if mode == DisplayMode.CLI:
        with setup_astro_logging(LogMode.CONSOLE_AND_FILE, log_file=log_file):
            write_session_separator(
                log_file,
                command="run",
                run_id=manifest.run_id,
                append=append,
            )
            run_service.run(
                search_dir,
                pipeline,
                run_directory,
                manifest,
                tracker=tracker,
            )
        return

    with setup_astro_logging(LogMode.FILE_AND_BUFFER, log_file=log_file) as context:
        write_session_separator(
            log_file,
            command="run",
            run_id=manifest.run_id,
            append=append,
        )
        dashboard = RunDashboard(tracker, context.buffer)

        def refresh_dashboard() -> None:
            dashboard.render_once()

        try:
            with Live(
                dashboard.build_layout(),
                console=dashboard.console,
                refresh_per_second=4,
                screen=False,
            ) as live:

                def progress_callback() -> None:
                    live.update(dashboard.build_layout())

                run_service.run(
                    search_dir,
                    pipeline,
                    run_directory,
                    manifest,
                    tracker=tracker,
                    progress_callback=progress_callback,
                )
                progress_callback()
        except Exception:
            refresh_dashboard()
            raise


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
    logging_context = setup_astro_logging(LogMode.CONSOLE_ONLY)
    logging_context.__enter__()

    try:
        if discover_pipeline(search_dir) is None:
            _exit_with_logged_error(f"No pipeline.py found in {search_dir}")

        if not path.exists():
            _exit_with_logged_error(f"Source path does not exist: {path}")
        if not path.is_dir():
            _exit_with_logged_error(f"Source path must be a directory: {path}")

        pipeline = get_pipeline_instance(search_dir)
        if pipeline is None:
            _exit_with_logged_error("pipeline.py must export a Pipeline instance named 'pipeline'.")
        assert pipeline is not None

        service = IngestService(search_dir, pipeline)
        progress_tasks: dict[str, TaskID] = {}

        def on_run_created(run_directory: Path, run_id: str) -> None:
            logging_context.attach_run_log(
                get_run_log_path(run_directory),
                command="ingest",
                run_id=run_id,
                append=False,
            )

        try:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                transient=True,
            ) as progress:

                def on_ingest_progress(
                    file_name: str,
                    rows_done: int,
                    total_rows: int | None,
                ) -> None:
                    if file_name not in progress_tasks:
                        progress_tasks[file_name] = progress.add_task(
                            f"Materializing {file_name}",
                            total=total_rows or 100,
                        )
                    task_id = progress_tasks[file_name]
                    if total_rows is not None and total_rows > 0:
                        progress.update(
                            task_id,
                            completed=min(rows_done, total_rows),
                            total=total_rows,
                            description=f"{file_name}: {rows_done:,} / {total_rows:,} rows",
                        )
                        return
                    progress.update(task_id, description=f"{file_name}: {rows_done:,} rows")

                result = service.ingest(
                    path,
                    on_run_created=on_run_created,
                    on_ingest_progress=on_ingest_progress,
                )
        except SerialIngestConflictError as error:
            _exit_with_logged_error(str(error))
        except IngestValidationError as error:
            _exit_with_logged_error(str(error))
        except Exception as error:
            _exit_with_logged_error(f"Ingest failed: {error}")

        logger.info(
            "Run %s created at %s with %s ingested file(s)",
            result.run_id,
            result.run_directory,
            len(result.ingested_files),
        )
        for file_name in result.ingested_files:
            logger.info("Ingested %s", file_name)
    finally:
        logging_context.__exit__(None, None, None)


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
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="Run identifier to process. Defaults to the latest ingested run.",
        ),
    ] = None,
    mode: Annotated[
        DisplayMode,
        typer.Option(
            "--mode",
            help="Display mode: dashboard (default) or plain CLI logs.",
        ),
    ] = DisplayMode.DASHBOARD,
) -> None:
    """Run the pipeline."""
    search_dir = _resolve_pipeline_dir(pipeline_dir)

    try:
        run_directory, manifest = resolve_run_directory(search_dir, run_id=run_id)
    except RunResolutionError as error:
        with setup_astro_logging(LogMode.CONSOLE_ONLY):
            _exit_with_logged_error(str(error))

    log_file = get_run_log_path(run_directory)
    append = log_file.exists()

    try:
        _execute_run(
            search_dir=search_dir,
            run_directory=run_directory,
            manifest=manifest,
            mode=mode,
            log_file=log_file,
            append=append,
        )
    except RunResolutionError as error:
        with setup_astro_logging(LogMode.CONSOLE_ONLY):
            _exit_with_logged_error(str(error))
    except Exception as error:
        with setup_astro_logging(LogMode.CONSOLE_ONLY):
            _exit_with_logged_error(f"Run failed: {error}")


@app.command()
def describe(
    pipeline_dir: Annotated[
        Path | None,
        typer.Option(
            "--pipeline-dir",
            "-C",
            help="Directory containing pipeline.py. Defaults to the current directory.",
        ),
    ] = None,
) -> None:
    """Display the pipeline steps as a flow diagram."""
    search_dir = _resolve_pipeline_dir(pipeline_dir)
    with setup_astro_logging(LogMode.CONSOLE_ONLY):
        if discover_pipeline(search_dir) is None:
            _exit_with_logged_error(f"No pipeline.py found in {search_dir}")

        pipeline = get_pipeline_instance(search_dir)
        if pipeline is None:
            _exit_with_logged_error("pipeline.py must export a Pipeline instance named 'pipeline'.")
        assert pipeline is not None

        typer.echo(render_flow_diagram(pipeline))


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
    with setup_astro_logging(LogMode.CONSOLE_ONLY):
        _resolve_pipeline_dir(pipeline_dir)
        logger.warning("list: not implemented")


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
    with setup_astro_logging(LogMode.CONSOLE_ONLY):
        _resolve_pipeline_dir(pipeline_dir)
        if all_runs:
            logger.warning("cleanup --all: not implemented")
        else:
            logger.warning("cleanup: not implemented")


if __name__ == "__main__":
    app()

"""CLI command tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from astro.cli.main import app
from astro.working.manifest import RunStatus
from astro.working.run_manager import RunManager


def test_root_command_shows_help(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Run and manage CSV import pipelines." in result.output


def test_ingest_command_help(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "Ingest source files" in result.output


def test_run_command_help(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "Run the pipeline." in result.output


def test_ingest_command_creates_run(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    result = cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    assert result.exit_code == 0
    assert "Run " in result.output
    assert "establishments" in result.output


def test_ingest_command_rejects_file_path(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    csv_file: Path,
) -> None:
    result = cli_runner.invoke(
        app,
        [
            "ingest",
            str(csv_file),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    assert result.exit_code == 1
    assert "must be a directory" in result.output


def test_ingest_command_reports_serial_conflict(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    first = cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    assert first.exit_code == 0

    second = cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    assert second.exit_code == 1
    assert "Ingest blocked" in second.output


def test_run_command_cli_mode_requires_ingested_run(
    cli_runner: CliRunner,
    pipeline_directory: Path,
) -> None:
    result = cli_runner.invoke(
        app,
        ["run", "--mode", "cli", "--pipeline-dir", str(pipeline_directory)],
    )
    assert result.exit_code == 1
    assert "No runnable pipeline runs" in result.output


def test_run_command_cli_mode_completes_ingested_run(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    ingest_result = cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    assert ingest_result.exit_code == 0

    result = cli_runner.invoke(
        app,
        ["run", "--mode", "cli", "--pipeline-dir", str(pipeline_directory)],
    )
    assert result.exit_code == 0
    assert "completed" in result.output.lower()


def test_run_command_dashboard_mode_completes_ingested_run(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    ingest_result = cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    assert ingest_result.exit_code == 0

    result = cli_runner.invoke(
        app,
        ["run", "--pipeline-dir", str(pipeline_directory)],
    )
    assert result.exit_code == 0


def test_list_command_shows_runs(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    ingest_result = cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    assert ingest_result.exit_code == 0

    result = cli_runner.invoke(
        app,
        ["list", "--pipeline-dir", str(pipeline_directory)],
    )
    assert result.exit_code == 0
    assert "Pipeline runs" in result.output
    assert "ingested" in result.output


def test_list_command_without_runs(cli_runner: CliRunner, tmp_path: Path) -> None:
    result = cli_runner.invoke(app, ["list", "--pipeline-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "no runs recorded" in result.output


def test_cleanup_dry_run_leaves_completed_run(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    run_result = cli_runner.invoke(
        app,
        ["run", "--mode", "cli", "--pipeline-dir", str(pipeline_directory)],
    )
    assert run_result.exit_code == 0

    dry_run = cli_runner.invoke(
        app,
        ["cleanup", "--pipeline-dir", str(pipeline_directory), "--dry-run"],
    )
    assert dry_run.exit_code == 0
    assert "would remove" in dry_run.output

    working_root = pipeline_directory / ".working"
    assert any(working_root.iterdir())


def test_cleanup_removes_completed_run_with_yes(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    cli_runner.invoke(
        app,
        ["run", "--mode", "cli", "--pipeline-dir", str(pipeline_directory)],
    )

    result = cli_runner.invoke(
        app,
        ["cleanup", "--pipeline-dir", str(pipeline_directory), "--yes"],
    )
    assert result.exit_code == 0
    assert "removed run" in result.output.lower()

    working_root = pipeline_directory / ".working"
    assert not working_root.exists() or not any(working_root.iterdir())


def test_cleanup_all_removes_stats_db(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    stats_db = pipeline_directory / ".astro" / "stats.db"
    assert stats_db.is_file()

    result = cli_runner.invoke(
        app,
        ["cleanup", "--pipeline-dir", str(pipeline_directory), "--all", "--yes"],
    )
    assert result.exit_code == 0
    assert not stats_db.exists()


def test_describe_command_renders_pipeline_flow(
    cli_runner: CliRunner,
    pipeline_directory: Path,
) -> None:
    result = cli_runner.invoke(
        app,
        ["describe", "--pipeline-dir", str(pipeline_directory)],
    )
    assert result.exit_code == 0
    assert "test-pipeline (serial)" in result.output
    assert "Ingest" in result.output
    assert "No-op" in result.output
    assert "──►" in result.output


def test_describe_command_reports_missing_pipeline(cli_runner: CliRunner, tmp_path: Path) -> None:
    result = cli_runner.invoke(
        app,
        ["describe", "--pipeline-dir", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "No pipeline.py found" in result.output


def test_cleanup_skips_non_terminal_runs(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    ingest_result = cli_runner.invoke(
        app,
        [
            "ingest",
            str(source_directory),
            "--pipeline-dir",
            str(pipeline_directory),
        ],
    )
    assert ingest_result.exit_code == 0

    run_dirs = list((pipeline_directory / ".working").iterdir())
    assert len(run_dirs) == 1
    manifest = RunManager(pipeline_directory).load_manifest(run_dirs[0])
    assert manifest.status == RunStatus.INGESTED

    result = cli_runner.invoke(
        app,
        ["cleanup", "--pipeline-dir", str(pipeline_directory), "--yes"],
    )
    assert result.exit_code == 0
    assert "Nothing to clean up" in result.output
    assert run_dirs[0].exists()

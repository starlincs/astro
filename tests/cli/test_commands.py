"""CLI command tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from astro.cli.main import app


def test_root_command_shows_help(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Run and manage CSV import pipelines." in result.output


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
    assert "ingested establishments" in result.output


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


def test_run_command_stub(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert "run: not implemented" in result.output


def test_list_command_stub(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "list: not implemented" in result.output


def test_cleanup_command_stub(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["cleanup"])
    assert result.exit_code == 0
    assert "cleanup: not implemented" in result.output


def test_cleanup_all_flag_stub(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["cleanup", "--all"])
    assert result.exit_code == 0
    assert "cleanup: not implemented" in result.output

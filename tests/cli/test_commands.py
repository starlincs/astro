"""CLI command tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from astro.cli.main import app


def test_root_command_shows_help(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Run and manage CSV import pipelines." in result.output


def test_ingest_command_stub(cli_runner: CliRunner, tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("id\n1\n", encoding="utf-8")

    result = cli_runner.invoke(app, ["ingest", str(csv_path)])
    assert result.exit_code == 0
    assert "ingest: not implemented" in result.output


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

"""CLI logging tests."""

from __future__ import annotations

import logging
from pathlib import Path

from typer.testing import CliRunner

from astro.cli.logging import LOG_FILENAME, LogMode, setup_astro_logging, write_session_separator


def test_write_session_separator_includes_command_and_run_id(tmp_path: Path) -> None:
    log_file = tmp_path / LOG_FILENAME
    log_file.write_text("previous content\n", encoding="utf-8")

    write_session_separator(log_file, command="ingest", run_id="abc12", append=True)

    content = log_file.read_text(encoding="utf-8")
    assert "previous content" in content
    assert "Astro session started:" in content
    assert "command=ingest" in content
    assert "run_id=abc12" in content


def test_console_only_mode_does_not_create_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / LOG_FILENAME
    logger = logging.getLogger("astro.test.console_only")

    with setup_astro_logging(LogMode.CONSOLE_ONLY):
        logger.info("console message")

    assert not log_file.exists()


def test_console_and_file_mode_writes_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / LOG_FILENAME
    logger = logging.getLogger("astro.test.file_mode")

    with setup_astro_logging(LogMode.CONSOLE_AND_FILE, log_file=log_file):
        write_session_separator(log_file, command="ingest", run_id="abc12", append=False)
        logger.info("persisted message")

    content = log_file.read_text(encoding="utf-8")
    assert "persisted message" in content
    assert "command=ingest" in content


def test_file_and_buffer_mode_populates_buffer(tmp_path: Path) -> None:
    log_file = tmp_path / LOG_FILENAME
    logger = logging.getLogger("astro.test.buffer_mode")

    with setup_astro_logging(LogMode.FILE_AND_BUFFER, log_file=log_file) as context:
        write_session_separator(log_file, command="run", run_id="xyz99", append=False)
        logger.warning("buffered warning")
        assert len(context.buffer.records) >= 1


def test_logging_context_removes_handlers_after_exit() -> None:
    logger = logging.getLogger("astro")
    initial_handler_count = len(logger.handlers)

    with setup_astro_logging(LogMode.CONSOLE_ONLY):
        assert len(logger.handlers) > initial_handler_count

    assert len(logger.handlers) == initial_handler_count


def test_ingest_command_creates_run_log_file(
    cli_runner: CliRunner,
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    from astro.cli.main import app

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

    working_root = pipeline_directory / ".working"
    run_directories = [path for path in working_root.iterdir() if path.is_dir()]
    assert len(run_directories) == 1
    log_file = run_directories[0] / LOG_FILENAME
    assert log_file.is_file()
    assert "Astro session started:" in log_file.read_text(encoding="utf-8")

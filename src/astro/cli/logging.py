"""Shared CLI logging configuration for Astro commands."""

from __future__ import annotations

import logging
from collections import deque
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from rich.logging import RichHandler

LOG_FILENAME = "astro.log"
ASTRO_LOGGER_NAME = "astro"
_SEPARATOR_WIDTH = 80


class LogMode(StrEnum):
    CONSOLE_ONLY = "console_only"
    CONSOLE_AND_FILE = "console_and_file"
    FILE_AND_BUFFER = "file_and_buffer"


class InMemoryLogBuffer(logging.Handler):
    """Ring buffer of log records for dashboard rendering."""

    def __init__(self, max_records: int = 500) -> None:
        super().__init__()
        self.records: deque[logging.LogRecord] = deque(maxlen=max_records)

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class PlainLogFormatter(logging.Formatter):
    """Plain-text formatter for log files and dashboard buffers."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


class AstroLoggingContext(AbstractContextManager["AstroLoggingContext"]):
    """Manage Astro logger handlers for one CLI command invocation."""

    def __init__(
        self,
        mode: LogMode,
        *,
        log_file: Path | None = None,
        level: int = logging.INFO,
    ) -> None:
        self.mode = mode
        self.log_file = log_file
        self.level = level
        self.logger = logging.getLogger(ASTRO_LOGGER_NAME)
        self.buffer = InMemoryLogBuffer()
        self._previous_level = self.logger.level
        self._previous_propagate = self.logger.propagate
        self._handlers: list[logging.Handler] = []

    def __enter__(self) -> AstroLoggingContext:
        self.logger.handlers.clear()
        self.logger.setLevel(self.level)
        self.logger.propagate = False

        plain_formatter = PlainLogFormatter()
        if self.mode in {LogMode.CONSOLE_ONLY, LogMode.CONSOLE_AND_FILE}:
            console_handler = RichHandler(
                show_time=True,
                show_level=True,
                show_path=False,
                markup=True,
                rich_tracebacks=False,
            )
            console_handler.setLevel(self.level)
            self.logger.addHandler(console_handler)
            self._handlers.append(console_handler)

        if self.mode in {LogMode.CONSOLE_AND_FILE, LogMode.FILE_AND_BUFFER}:
            if self.log_file is None:
                raise ValueError("log_file is required for file logging modes.")
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setFormatter(plain_formatter)
            file_handler.setLevel(self.level)
            self.logger.addHandler(file_handler)
            self._handlers.append(file_handler)

        if self.mode == LogMode.FILE_AND_BUFFER:
            self.buffer.setFormatter(plain_formatter)
            self.buffer.setLevel(self.level)
            self.logger.addHandler(self.buffer)
            self._handlers.append(self.buffer)

        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for handler in self._handlers:
            handler.close()
            self.logger.removeHandler(handler)
        self.logger.setLevel(self._previous_level)
        self.logger.propagate = self._previous_propagate
        return None

    def attach_run_log(
        self,
        log_file: Path,
        *,
        command: str,
        run_id: str,
        append: bool = False,
    ) -> None:
        """Add file logging to an active console-only context."""
        if self.mode != LogMode.CONSOLE_ONLY:
            raise ValueError("attach_run_log requires an active CONSOLE_ONLY context.")

        self.log_file = log_file
        log_file.parent.mkdir(parents=True, exist_ok=True)
        write_session_separator(log_file, command=command, run_id=run_id, append=append)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(PlainLogFormatter())
        file_handler.setLevel(self.level)
        self.logger.addHandler(file_handler)
        self._handlers.append(file_handler)
        self.mode = LogMode.CONSOLE_AND_FILE


def setup_astro_logging(
    mode: LogMode,
    *,
    log_file: Path | None = None,
    level: int = logging.INFO,
) -> AstroLoggingContext:
    return AstroLoggingContext(mode, log_file=log_file, level=level)


def write_session_separator(
    log_file: Path,
    *,
    command: str,
    run_id: str,
    append: bool,
) -> None:
    timestamp = datetime.now(UTC).isoformat()
    separator_lines = [
        "=" * _SEPARATOR_WIDTH,
        f"Astro session started: {timestamp}  command={command}  run_id={run_id}",
        "=" * _SEPARATOR_WIDTH,
        "",
    ]
    content = "\n".join(separator_lines)
    if append and log_file.exists():
        existing = log_file.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        log_file.write_text(f"{existing}{content}", encoding="utf-8")
        return
    log_file.write_text(content, encoding="utf-8")


def get_run_log_path(run_directory: Path) -> Path:
    return run_directory / LOG_FILENAME

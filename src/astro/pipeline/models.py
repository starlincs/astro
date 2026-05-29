"""Pipeline configuration models."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import pandera.polars as pa
import polars as pl

_SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ExecutionMode(StrEnum):
    """Ingest concurrency mode."""

    SERIAL = "serial"
    PARALLEL = "parallel"


class StepExecutionMode(StrEnum):
    """Run-step scheduling mode within a single pipeline run."""

    SERIAL = "serial"
    PARALLEL = "parallel"


@dataclass(frozen=True)
class IngestFileSpec:
    """Expected source file and Pandera schema for CLI ingest.

    ``preprocess``, when set, replaces default CSV loading and is invoked with the
    matched source path before Pandera validation. ``optional``, when True, allows
    the source file to be absent; at least one ingest file must still match.
    """

    name: str
    source_pattern: str
    schema: pa.DataFrameSchema
    encoding: str = "utf-8"
    has_header: bool = True
    column_names: tuple[str, ...] | None = None
    preprocess: Callable[[Path], pl.DataFrame] | None = field(
        default=None, compare=False, hash=False
    )
    optional: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Ingest file name must not be empty.")
        if not _SAFE_NAME_PATTERN.match(self.name):
            raise ValueError(
                "Ingest file name must be alphanumeric and may contain '.', '_', or '-'."
            )
        if not self.source_pattern:
            raise ValueError("Ingest source_pattern must not be empty.")
        if not self.encoding:
            raise ValueError("Ingest encoding must not be empty.")
        if not self.has_header and not self.column_names:
            raise ValueError("Headerless ingest requires column_names.")

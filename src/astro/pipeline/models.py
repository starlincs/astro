"""Pipeline configuration models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

import pandera.polars as pa

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
    """Expected source file and Pandera schema for CLI ingest."""

    name: str
    source_pattern: str
    schema: pa.DataFrameSchema
    encoding: str = "utf-8"
    has_header: bool = True
    column_names: tuple[str, ...] | None = None

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

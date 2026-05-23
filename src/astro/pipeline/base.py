"""Base pipeline interface for Astro library users."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import polars as pl

from astro.pipeline.models import ExecutionMode, IngestFileSpec


@dataclass(frozen=True)
class IngestedSource:
    """One ingested file and its raw data. Schemas may differ across sources."""

    path: Path
    data: pl.DataFrame


class Pipeline(ABC):
    """Base class for CSV import pipelines defined in external repositories."""

    name: str = "pipeline"
    execution_mode: ExecutionMode = ExecutionMode.SERIAL
    ingest_files: ClassVar[list[IngestFileSpec]]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        ingest_files = getattr(cls, "ingest_files", [])
        if not ingest_files:
            raise TypeError(f"{cls.__name__} must define a non-empty ingest_files list.")
        names = [spec.name for spec in ingest_files]
        if len(names) != len(set(names)):
            raise TypeError(f"{cls.__name__} ingest_files names must be unique.")

    @abstractmethod
    def transform(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        """Apply pipeline-specific transformations to one source file."""
        ...

    @abstractmethod
    def validate(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        """Validate one source file against the appropriate pipeline schema."""
        ...

    def run(self, path: Path) -> list[IngestedSource]:
        """Legacy entry point; use ``astro run`` once implemented."""
        raise NotImplementedError(
            "Pipeline.run() is not available yet. Use astro ingest and astro run."
        )

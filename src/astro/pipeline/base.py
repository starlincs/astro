"""Base pipeline interface for Astro library users."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class IngestedSource:
    """One ingested file and its raw data. Schemas may differ across sources."""

    path: Path
    data: pl.DataFrame


class Pipeline(ABC):
    """Base class for CSV import pipelines defined in external repositories."""

    name: str = "pipeline"

    @abstractmethod
    def ingest(self, path: Path) -> list[IngestedSource]:
        """Load data from a CSV file or a directory of files.

        When ``path`` is a directory, each file is ingested independently.
        Source files are not required to share the same schema.
        """
        ...

    @abstractmethod
    def transform(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        """Apply pipeline-specific transformations to one source file."""
        ...

    @abstractmethod
    def validate(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        """Validate one source file against the appropriate pipeline schema."""
        ...

    def run(self, path: Path) -> list[IngestedSource]:
        """Execute ingest → transform → validate for each source file."""
        results: list[IngestedSource] = []
        for ingested in self.ingest(path):
            transformed = self.transform(ingested.data, ingested.path)
            validated = self.validate(transformed, ingested.path)
            results.append(IngestedSource(path=ingested.path, data=validated))
        return results

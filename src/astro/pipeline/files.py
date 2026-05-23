"""File containers for pipeline run steps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import polars as pl

from astro.working.manifest import IngestedFileRecord


class AstroFileSpec:
    """Declarative per-file configuration referenced by run steps."""

    ingest_name: ClassVar[str]


@dataclass
class AstroFile:
    """Runtime wrapper for one ingested file within a pipeline run."""

    spec: AstroFileSpec
    ingest_record: IngestedFileRecord
    run_directory: Path
    _active_path: Path

    @property
    def active_path(self) -> Path:
        return self._active_path

    def load(self) -> pl.DataFrame:
        return pl.read_parquet(self._active_path)

    def save_in_place(self, dataframe: pl.DataFrame) -> None:
        output_path = Path(self.ingest_record.parquet_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.write_parquet(output_path)
        self._active_path = output_path

    def save_to(self, subfolder: str, filename: str, dataframe: pl.DataFrame) -> Path:
        if not subfolder:
            raise ValueError("subfolder must not be empty.")
        if not filename:
            raise ValueError("filename must not be empty.")
        output_path = self.output_path(subfolder, filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.write_parquet(output_path)
        self._active_path = output_path
        return output_path

    def output_path(self, subfolder: str, filename: str) -> Path:
        if not subfolder:
            raise ValueError("subfolder must not be empty.")
        if not filename:
            raise ValueError("filename must not be empty.")
        return self.run_directory / subfolder / filename

    @classmethod
    def hydrate(
        cls,
        *,
        spec: AstroFileSpec,
        ingest_record: IngestedFileRecord,
        run_directory: Path,
    ) -> AstroFile:
        return cls(
            spec=spec,
            ingest_record=ingest_record,
            run_directory=run_directory,
            _active_path=Path(ingest_record.parquet_path),
        )

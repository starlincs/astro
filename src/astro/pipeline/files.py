"""File containers for pipeline run steps."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import polars as pl

from astro.io.constants import DEFAULT_LARGE_FILE_THRESHOLD_BYTES, DEFAULT_RUN_BATCH_SIZE
from astro.io.parquet import is_large_file, iter_parquet_batches, parquet_row_count
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
    large_file_threshold_bytes: int = DEFAULT_LARGE_FILE_THRESHOLD_BYTES
    run_batch_size: int = DEFAULT_RUN_BATCH_SIZE

    @property
    def active_path(self) -> Path:
        return self._active_path

    def is_large_file(self) -> bool:
        return is_large_file(
            self._active_path,
            threshold_bytes=self.large_file_threshold_bytes,
        )

    def load(self) -> pl.DataFrame:
        return pl.read_parquet(self._active_path)

    def scan(self) -> pl.LazyFrame:
        return pl.scan_parquet(self._active_path)

    def row_count(self) -> int:
        return parquet_row_count(self._active_path)

    def iter_batches(self, batch_size: int | None = None) -> Iterator[pl.DataFrame]:
        resolved_batch_size = batch_size or self.run_batch_size
        yield from iter_parquet_batches(self._active_path, resolved_batch_size)

    def sink(self, lazy_frame: pl.LazyFrame, *, row_group_size: int | None = None) -> None:
        if row_group_size is None:
            lazy_frame.sink_parquet(self._active_path)
            return
        lazy_frame.sink_parquet(self._active_path, row_group_size=row_group_size)

    def save_in_place(self, dataframe: pl.DataFrame) -> None:
        output_path = Path(self.ingest_record.parquet_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.write_parquet(output_path)
        self._active_path = output_path

    def save_in_place_lazy(self, lazy_frame: pl.LazyFrame) -> None:
        output_path = Path(self.ingest_record.parquet_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lazy_frame.sink_parquet(output_path)
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

    def save_to_lazy(self, subfolder: str, filename: str, lazy_frame: pl.LazyFrame) -> Path:
        if not subfolder:
            raise ValueError("subfolder must not be empty.")
        if not filename:
            raise ValueError("filename must not be empty.")
        output_path = self.output_path(subfolder, filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lazy_frame.sink_parquet(output_path)
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
        large_file_threshold_bytes: int = DEFAULT_LARGE_FILE_THRESHOLD_BYTES,
        run_batch_size: int = DEFAULT_RUN_BATCH_SIZE,
    ) -> AstroFile:
        return cls(
            spec=spec,
            ingest_record=ingest_record,
            run_directory=run_directory,
            _active_path=Path(ingest_record.parquet_path),
            large_file_threshold_bytes=large_file_threshold_bytes,
            run_batch_size=run_batch_size,
        )

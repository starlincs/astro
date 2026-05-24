"""Parquet metadata and batched write helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import polars as pl
import pyarrow.parquet as pq

from astro.io.constants import DEFAULT_LARGE_FILE_THRESHOLD_BYTES


def is_large_file(path: Path, *, threshold_bytes: int = DEFAULT_LARGE_FILE_THRESHOLD_BYTES) -> bool:
    return path.is_file() and path.stat().st_size >= threshold_bytes


def parquet_row_count(path: Path) -> int:
    if not path.is_file():
        return 0
    metadata = pq.ParquetFile(path).metadata
    if metadata is None:
        return 0
    return metadata.num_rows


def parquet_has_rows(path: Path) -> bool:
    return parquet_row_count(path) > 0


def parquet_row_count_many(paths: list[Path]) -> int:
    return sum(parquet_row_count(path) for path in paths)


def iter_parquet_batches(path: Path, batch_size: int) -> Iterator[pl.DataFrame]:
    parquet_file = pq.ParquetFile(path)
    for batch in parquet_file.iter_batches(batch_size=batch_size):
        yield cast(pl.DataFrame, pl.from_arrow(batch))


class ParquetBatchWriter:
    """Append validated Polars batches to a single Parquet file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._writer: pq.ParquetWriter | None = None
        self.row_count = 0
        self.column_count = 0

    def write_batch(self, dataframe: pl.DataFrame) -> None:
        if dataframe.is_empty():
            return
        table = dataframe.to_arrow()
        if self._writer is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = pq.ParquetWriter(self.path, table.schema)
            self.column_count = len(dataframe.columns)
        self._writer.write_table(table)
        self.row_count += dataframe.height

    def close(self) -> tuple[int, int]:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        return self.row_count, self.column_count

    def abort(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if self.path.exists():
            self.path.unlink()

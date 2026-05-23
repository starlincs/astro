"""Filtered row path helpers and parquet IO."""

from __future__ import annotations

from pathlib import Path

import polars as pl

FILTERED_DIRNAME = "filtered"


class FilterStore:
    """Manage filtered-row parquet files for a run directory."""

    def __init__(self, run_directory: Path) -> None:
        self.run_directory = run_directory

    def filtered_path(self, step_id: str, ingest_name: str) -> Path:
        return self.run_directory / FILTERED_DIRNAME / step_id / f"{ingest_name}.parquet"

    def write_filtered(self, path: Path, rows: pl.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows.write_parquet(path)

    def read_filtered(self, path: Path) -> pl.DataFrame:
        if not path.exists():
            return pl.DataFrame()
        return pl.read_parquet(path)

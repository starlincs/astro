"""Quarantine path helpers and parquet IO."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import cast

import polars as pl

from astro.io.parquet import parquet_has_rows, parquet_row_count_many

QUARANTINE_DIRNAME = "quarantine"
SNAPSHOT_DIRNAME = "snapshots"
QUARANTINE_REASON_COLUMN = "_astro_quarantine_reason"
QUARANTINE_PART_SUFFIX = ".part-"


class QuarantineStore:
    """Manage quarantine and snapshot parquet files for a run directory."""

    def __init__(self, run_directory: Path) -> None:
        self.run_directory = run_directory

    def quarantine_path(self, step_id: str, ingest_name: str) -> Path:
        return self.run_directory / QUARANTINE_DIRNAME / step_id / f"{ingest_name}.parquet"

    def snapshot_path(self, step_id: str, ingest_name: str) -> Path:
        return self.run_directory / SNAPSHOT_DIRNAME / step_id / f"{ingest_name}.parquet"

    def quarantine_part_paths(self, base_path: Path) -> list[Path]:
        return sorted(base_path.parent.glob(f"{base_path.name}{QUARANTINE_PART_SUFFIX}*.parquet"))

    def all_quarantine_paths(self, base_path: Path) -> list[Path]:
        part_paths = self.quarantine_part_paths(base_path)
        if base_path.exists():
            return [base_path, *part_paths]
        return part_paths

    def append_rows(self, path: Path, rows: pl.DataFrame, *, reason: str) -> None:
        if not reason:
            raise ValueError("reason must not be empty.")
        if rows.is_empty():
            raise ValueError("rows must not be empty.")

        annotated = rows.with_columns(pl.lit(reason).alias(QUARANTINE_REASON_COLUMN))
        path.parent.mkdir(parents=True, exist_ok=True)
        part_path = self._next_part_path(path)
        annotated.write_parquet(part_path)

    def read_rows(self, path: Path) -> pl.DataFrame:
        paths = self.all_quarantine_paths(path)
        if not paths:
            return pl.DataFrame()
        if len(paths) == 1:
            return pl.read_parquet(paths[0])
        return cast(pl.DataFrame, pl.scan_parquet(paths).collect(engine="streaming"))

    def row_count(self, path: Path) -> int:
        return parquet_row_count_many(self.all_quarantine_paths(path))

    def has_rows(self, path: Path) -> bool:
        return any(parquet_has_rows(candidate) for candidate in self.all_quarantine_paths(path))

    def truncate(self, path: Path) -> None:
        for candidate in self.all_quarantine_paths(path):
            candidate.unlink(missing_ok=True)

    def capture_snapshot(self, snapshot_path: Path, source_path: Path) -> None:
        if snapshot_path.exists():
            return
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, snapshot_path)

    def merge_snapshot_with_quarantine(
        self,
        *,
        snapshot_path: Path,
        quarantine_path: Path,
        output_path: Path,
    ) -> None:
        quarantine_paths = self.all_quarantine_paths(quarantine_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not quarantine_paths:
            shutil.copy2(snapshot_path, output_path)
            return

        snapshot_lazy = pl.scan_parquet(snapshot_path)
        quarantine_lazy = pl.scan_parquet(quarantine_paths)
        if QUARANTINE_REASON_COLUMN in quarantine_lazy.collect_schema().names():
            quarantine_lazy = quarantine_lazy.drop(QUARANTINE_REASON_COLUMN)
        merged = pl.concat([snapshot_lazy, quarantine_lazy], how="diagonal_relaxed")
        merged.sink_parquet(output_path)

    def _next_part_path(self, base_path: Path) -> Path:
        next_sequence = len(self.quarantine_part_paths(base_path)) + 1
        part_name = f"{base_path.name}{QUARANTINE_PART_SUFFIX}{next_sequence:05d}.parquet"
        return base_path.parent / part_name

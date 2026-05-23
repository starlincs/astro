"""Quarantine path helpers and parquet IO."""

from __future__ import annotations

import shutil
from pathlib import Path

import polars as pl

QUARANTINE_DIRNAME = "quarantine"
SNAPSHOT_DIRNAME = "snapshots"
QUARANTINE_REASON_COLUMN = "_astro_quarantine_reason"


class QuarantineStore:
    """Manage quarantine and snapshot parquet files for a run directory."""

    def __init__(self, run_directory: Path) -> None:
        self.run_directory = run_directory

    def quarantine_path(self, step_id: str, ingest_name: str) -> Path:
        return self.run_directory / QUARANTINE_DIRNAME / step_id / f"{ingest_name}.parquet"

    def snapshot_path(self, step_id: str, ingest_name: str) -> Path:
        return self.run_directory / SNAPSHOT_DIRNAME / step_id / f"{ingest_name}.parquet"

    def append_rows(self, path: Path, rows: pl.DataFrame, *, reason: str) -> None:
        if not reason:
            raise ValueError("reason must not be empty.")
        if rows.is_empty():
            raise ValueError("rows must not be empty.")

        annotated = rows.with_columns(pl.lit(reason).alias(QUARANTINE_REASON_COLUMN))
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = pl.read_parquet(path)
            combined = pl.concat([existing, annotated], how="diagonal_relaxed")
            combined.write_parquet(path)
            return
        annotated.write_parquet(path)

    def read_rows(self, path: Path) -> pl.DataFrame:
        if not path.exists():
            return pl.DataFrame()
        return pl.read_parquet(path)

    def has_rows(self, path: Path) -> bool:
        return path.exists() and pl.read_parquet(path).height > 0

    def truncate(self, path: Path) -> None:
        if not path.exists():
            return
        existing = pl.read_parquet(path)
        empty = existing.clear()
        empty.write_parquet(path)

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
        snapshot = pl.read_parquet(snapshot_path)
        if quarantine_path.exists():
            quarantined = pl.read_parquet(quarantine_path)
            if QUARANTINE_REASON_COLUMN in quarantined.columns:
                quarantined = quarantined.drop(QUARANTINE_REASON_COLUMN)
            if not quarantined.is_empty():
                snapshot = pl.concat([snapshot, quarantined], how="diagonal_relaxed")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_parquet(output_path)

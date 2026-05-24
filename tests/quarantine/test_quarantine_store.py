"""Quarantine store tests."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from astro.quarantine.store import (
    QUARANTINE_REASON_COLUMN,
    QuarantineStore,
)


def test_append_rows_writes_reason_column(tmp_path: Path) -> None:
    store = QuarantineStore(tmp_path)
    path = store.quarantine_path("mark-processed", "establishments")
    rows = pl.DataFrame({"URN": ["1"], "EstablishmentName": ["Bad"]})

    store.append_rows(path, rows, reason="invalid name")

    loaded = store.read_rows(path)
    assert loaded.height == 1
    assert loaded[QUARANTINE_REASON_COLUMN][0] == "invalid name"


def test_append_rows_rejects_empty_reason(tmp_path: Path) -> None:
    store = QuarantineStore(tmp_path)
    path = store.quarantine_path("mark-processed", "establishments")
    rows = pl.DataFrame({"URN": ["1"]})

    with pytest.raises(ValueError, match="reason"):
        store.append_rows(path, rows, reason="")


def test_truncate_clears_quarantine_file(tmp_path: Path) -> None:
    store = QuarantineStore(tmp_path)
    path = store.quarantine_path("mark-processed", "establishments")
    store.append_rows(path, pl.DataFrame({"URN": ["1"]}), reason="bad")

    store.truncate(path)

    assert not store.has_rows(path)


def test_snapshot_path_is_step_scoped(tmp_path: Path) -> None:
    store = QuarantineStore(tmp_path)

    assert store.snapshot_path("step-a", "establishments") == (
        tmp_path / "snapshots" / "step-a" / "establishments.parquet"
    )


def test_append_rows_writes_part_files_without_rewriting_existing_parts(tmp_path: Path) -> None:
    store = QuarantineStore(tmp_path)
    path = store.quarantine_path("mark-processed", "establishments")
    store.append_rows(path, pl.DataFrame({"URN": ["1"]}), reason="first")
    store.append_rows(path, pl.DataFrame({"URN": ["2"]}), reason="second")

    part_paths = store.quarantine_part_paths(path)
    assert len(part_paths) == 2
    assert store.row_count(path) == 2
    assert store.has_rows(path)


def test_merge_snapshot_with_quarantine_combines_part_files(tmp_path: Path) -> None:
    store = QuarantineStore(tmp_path)
    snapshot_path = store.snapshot_path("mark-processed", "establishments")
    quarantine_path = store.quarantine_path("mark-processed", "establishments")
    output_path = tmp_path / "merged.parquet"
    snapshot_path.parent.mkdir(parents=True)
    pl.DataFrame({"URN": ["1"], "EstablishmentName": ["Good"]}).write_parquet(snapshot_path)
    bad_rows = pl.DataFrame({"URN": ["2"], "EstablishmentName": ["Bad"]})
    store.append_rows(quarantine_path, bad_rows, reason="bad")

    store.merge_snapshot_with_quarantine(
        snapshot_path=snapshot_path,
        quarantine_path=quarantine_path,
        output_path=output_path,
    )

    merged = pl.read_parquet(output_path)
    assert merged.height == 2
    assert set(merged["URN"].to_list()) == {"1", "2"}

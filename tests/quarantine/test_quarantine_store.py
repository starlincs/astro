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

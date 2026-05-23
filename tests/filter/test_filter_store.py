"""Filter store tests."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from astro.filter.store import FilterStore


def test_filtered_path_is_step_scoped(tmp_path: Path) -> None:
    store = FilterStore(tmp_path)

    assert store.filtered_path("remove-closed", "establishments") == (
        tmp_path / "filtered" / "remove-closed" / "establishments.parquet"
    )


def test_write_and_read_filtered_rows(tmp_path: Path) -> None:
    store = FilterStore(tmp_path)
    path = store.filtered_path("remove-closed", "establishments")
    rows = pl.DataFrame({"URN": ["2"], "EstablishmentName": ["Closed School"]})

    store.write_filtered(path, rows)

    loaded = store.read_filtered(path)
    assert loaded.height == 1
    assert loaded["URN"][0] == "2"


def test_write_filtered_empty_clears_existing_file(tmp_path: Path) -> None:
    store = FilterStore(tmp_path)
    path = store.filtered_path("remove-closed", "establishments")
    store.write_filtered(path, pl.DataFrame({"URN": ["2"], "EstablishmentName": ["Closed School"]}))

    store.write_filtered(path, pl.DataFrame({"URN": [], "EstablishmentName": []}))

    assert store.read_filtered(path).is_empty()

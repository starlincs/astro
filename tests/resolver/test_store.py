"""Tests for resolver Parquet store."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from astro.resolver.models import hash_column_name
from astro.resolver.store import (
    ResolverStore,
    empty_store,
    store_path_for,
)


@pytest.fixture
def hash_groups() -> dict[str, list[str] | str]:
    return {
        "entry_changed": "*all",
        "address_changed": ["address1", "postcode"],
    }


@pytest.fixture
def pipeline_dir(tmp_path: Path) -> Path:
    return tmp_path / "pipeline"


def test_store_path_uses_persistent_subdirectory(pipeline_dir: Path) -> None:
    assert store_path_for(pipeline_dir, "establishments") == (
        pipeline_dir / ".persistent" / "establishments.parquet"
    )


def test_empty_store_has_expected_schema(hash_groups: dict[str, list[str] | str]) -> None:
    store = empty_store(hash_groups)
    assert store.is_empty()
    assert set(store.columns) == {
        "source_key",
        "canonical_id",
        "last_changed_date",
        "update_dates",
        hash_column_name("entry_changed"),
        hash_column_name("address_changed"),
    }


def test_load_returns_empty_store_when_file_missing(
    pipeline_dir: Path,
    hash_groups: dict[str, list[str] | str],
) -> None:
    resolver_store = ResolverStore(pipeline_dir, "establishments", hash_groups)
    loaded = resolver_store.load()
    assert loaded.is_empty()
    assert loaded.columns == empty_store(hash_groups).columns


def test_save_and_load_roundtrip(
    pipeline_dir: Path,
    hash_groups: dict[str, list[str] | str],
) -> None:
    resolver_store = ResolverStore(pipeline_dir, "establishments", hash_groups)
    store = pl.DataFrame(
        {
            "source_key": ["establishments:1"],
            "canonical_id": ["11111111-1111-4111-8111-111111111111"],
            "last_changed_date": [date(2026, 5, 22)],
            "update_dates": [[date(2026, 5, 22)]],
            hash_column_name("entry_changed"): ["abc"],
            hash_column_name("address_changed"): ["def"],
        }
    )

    resolver_store.save(store)
    loaded = resolver_store.load()

    assert loaded.to_dicts() == store.to_dicts()
    assert resolver_store.path.is_file()
    assert not resolver_store.path.with_suffix(".parquet.tmp").exists()


def test_save_rejects_missing_hash_columns(
    pipeline_dir: Path,
    hash_groups: dict[str, list[str] | str],
) -> None:
    resolver_store = ResolverStore(pipeline_dir, "establishments", hash_groups)
    invalid_store = pl.DataFrame(
        {
            "source_key": ["establishments:1"],
            "canonical_id": ["11111111-1111-4111-8111-111111111111"],
            "last_changed_date": [date(2026, 5, 22)],
            "update_dates": [[date(2026, 5, 22)]],
        }
    )

    with pytest.raises(ValueError, match="missing columns"):
        resolver_store.save(invalid_store)

"""Tests for CanonicalIdResolver."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from astro.resolver import CanonicalIdResolver, EntryStatus
from astro.resolver.models import changed_column_name
from astro.resolver.store import store_path_for


@pytest.fixture
def hash_groups() -> dict[str, list[str] | str]:
    return {
        "entry_changed": "*all",
        "address_changed": ["address1", "postcode"],
        "owner_changed": ["owner"],
    }


@pytest.fixture
def pipeline_dir(tmp_path: Path) -> Path:
    return tmp_path / "pipeline"


@pytest.fixture
def resolver(pipeline_dir: Path, hash_groups: dict[str, list[str] | str]) -> CanonicalIdResolver:
    return CanonicalIdResolver(pipeline_dir, "establishments", hash_groups)


def _sample_data(**overrides: object) -> pl.DataFrame:
    row = {
        "source_key": "file:1",
        "address1": "1 High Street",
        "postcode": "AB1 2CD",
        "owner": "trust-a",
    }
    row.update(overrides)
    return pl.DataFrame([row])


def test_resolve_assigns_new_entry_with_changed_flags(
    resolver: CanonicalIdResolver,
    pipeline_dir: Path,
) -> None:
    result = resolver.resolve(
        _sample_data(),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 22),
    )

    assert result.height == 1
    assert result["status"].item() == EntryStatus.NEW.value
    assert result["canonical_id"].item()
    assert result[changed_column_name("entry_changed")].item() is True
    assert result[changed_column_name("address_changed")].item() is True
    assert result[changed_column_name("owner_changed")].item() is True
    assert store_path_for(pipeline_dir, "establishments").is_file()


def test_resolve_keeps_uuid_and_status_for_unchanged_entry(resolver: CanonicalIdResolver) -> None:
    first = resolver.resolve(
        _sample_data(),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 22),
    )
    second = resolver.resolve(
        _sample_data(),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 23),
    )

    assert second["status"].item() == EntryStatus.UNCHANGED.value
    assert second["canonical_id"].item() == first["canonical_id"].item()
    assert second[changed_column_name("entry_changed")].item() is False
    assert second[changed_column_name("address_changed")].item() is False
    assert second[changed_column_name("owner_changed")].item() is False


def test_resolve_detects_partial_field_group_change(resolver: CanonicalIdResolver) -> None:
    resolver.resolve(
        _sample_data(),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 22),
    )
    result = resolver.resolve(
        _sample_data(address1="2 High Street"),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 23),
    )

    assert result["status"].item() == EntryStatus.CHANGED.value
    assert result[changed_column_name("entry_changed")].item() is True
    assert result[changed_column_name("address_changed")].item() is True
    assert result[changed_column_name("owner_changed")].item() is False


def test_resolve_preserves_canonical_id_when_entry_changes(resolver: CanonicalIdResolver) -> None:
    first = resolver.resolve(
        _sample_data(),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 22),
    )
    changed = resolver.resolve(
        _sample_data(owner="trust-b"),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 23),
    )

    assert changed["status"].item() == EntryStatus.CHANGED.value
    assert changed["canonical_id"].item() == first["canonical_id"].item()


def test_resolve_tracks_update_dates_in_store(resolver: CanonicalIdResolver) -> None:
    resolver.resolve(
        _sample_data(),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 22),
    )
    resolver.resolve(
        _sample_data(owner="trust-b"),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 23),
    )

    store = pl.read_parquet(resolver.store_path)
    row = store.filter(pl.col("source_key") == "establishments:file:1").to_dicts()[0]

    assert row["last_changed_date"] == date(2026, 5, 23)
    assert row["update_dates"] == [date(2026, 5, 22), date(2026, 5, 23)]


def test_named_stores_are_isolated(pipeline_dir: Path) -> None:
    hash_groups = {"entry_changed": ["owner"]}
    establishments = CanonicalIdResolver(pipeline_dir, "establishments", hash_groups)
    links = CanonicalIdResolver(pipeline_dir, "links", hash_groups)

    establishments.resolve(
        pl.DataFrame({"source_key": ["file:1"], "owner": ["trust-a"]}),
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 22),
    )
    links.resolve(
        pl.DataFrame({"source_key": ["file:1"], "owner": ["trust-a"]}),
        source_key_column="source_key",
        namespace="links",
        run_date=date(2026, 5, 22),
    )

    establishment_ids = pl.read_parquet(establishments.store_path)["canonical_id"].to_list()
    link_ids = pl.read_parquet(links.store_path)["canonical_id"].to_list()
    assert establishment_ids != link_ids


def test_resolve_rejects_missing_hash_fields(resolver: CanonicalIdResolver) -> None:
    with pytest.raises(ValueError, match="missing columns"):
        resolver.resolve(
            pl.DataFrame({"source_key": ["file:1"], "address1": ["1 High Street"]}),
            source_key_column="source_key",
            namespace="establishments",
            run_date=date(2026, 5, 22),
        )

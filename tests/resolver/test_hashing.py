"""Tests for resolver hash computation."""

from __future__ import annotations

import polars as pl

from astro.resolver.hashing import (
    canonical_field_string,
    compute_hash_columns,
    hash_field_values,
    sha256_hex,
)
from astro.resolver.models import hash_column_name


def test_canonical_field_string_normalizes_nulls_and_whitespace() -> None:
    assert canonical_field_string(["  alpha ", None, "beta"]) == "alpha\x1f\x1fbeta"


def test_sha256_hex_is_stable() -> None:
    value = canonical_field_string(["alpha", "beta"])
    assert sha256_hex(value) == sha256_hex(value)
    assert len(sha256_hex(value)) == 64


def test_hash_field_values_is_stable_for_same_input() -> None:
    data = pl.DataFrame({"address1": [" 1 High Street "], "postcode": [None]})
    first = hash_field_values(data, ["address1", "postcode"])
    second = hash_field_values(data, ["address1", "postcode"])
    assert first.to_list() == second.to_list()


def test_hash_field_values_changes_when_any_field_changes() -> None:
    unchanged = pl.DataFrame({"address1": ["1 High Street"], "postcode": ["AB1 2CD"]})
    changed = pl.DataFrame({"address1": ["2 High Street"], "postcode": ["AB1 2CD"]})
    unchanged_hash = hash_field_values(unchanged, ["address1", "postcode"]).item()
    changed_hash = hash_field_values(changed, ["address1", "postcode"]).item()
    assert unchanged_hash != changed_hash


def test_compute_hash_columns_adds_group_columns() -> None:
    data = pl.DataFrame(
        {
            "source_key": ["file:1"],
            "address1": ["1 High Street"],
            "postcode": ["AB1 2CD"],
            "owner": ["trust-a"],
        }
    )
    result = compute_hash_columns(
        data,
        {
            "entry_changed": "*all",
            "address_changed": ["address1", "postcode"],
            "owner_changed": ["owner"],
        },
        source_key_column="source_key",
    )

    assert hash_column_name("entry_changed") in result.columns
    assert hash_column_name("address_changed") in result.columns
    assert hash_column_name("owner_changed") in result.columns


def test_compute_hash_columns_excludes_source_key_from_all_group() -> None:
    data = pl.DataFrame({"source_key": ["file:1"], "value": ["alpha"]})
    with_source_key = compute_hash_columns(
        data,
        {"entry_changed": "*all"},
        source_key_column="source_key",
    )
    without_source_key = compute_hash_columns(
        data.drop("source_key"),
        {"entry_changed": "*all"},
        source_key_column="source_key",
    )
    assert with_source_key[hash_column_name("entry_changed")].item() == (
        without_source_key[hash_column_name("entry_changed")].item()
    )

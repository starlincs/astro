"""Pandera schema to Polars dtype mapping tests."""

from __future__ import annotations

import pandera.polars as pa
import polars as pl
import pytest

from astro.io.schema import pandera_schema_overrides


@pytest.mark.parametrize(
    ("dtype", "expected"),
    [
        (str, pl.String()),
        (int, pl.Int64()),
        (float, pl.Float64()),
        (bool, pl.Boolean()),
    ],
)
def test_pandera_schema_overrides_map_python_types(dtype: object, expected: pl.DataType) -> None:
    schema = pa.DataFrameSchema({"value": pa.Column(dtype)})
    overrides = pandera_schema_overrides(schema)
    assert overrides["value"] == expected


def test_pandera_schema_overrides_map_date_and_datetime() -> None:
    schema = pa.DataFrameSchema(
        {
            "day": pa.Column(pl.Date),
            "ts": pa.Column(pl.Datetime),
        }
    )
    overrides = pandera_schema_overrides(schema)
    assert overrides["day"] == pl.Date()
    assert overrides["ts"] == pl.Datetime()


def test_pandera_schema_overrides_falls_back_to_string_for_unknown_dtype() -> None:
    schema = pa.DataFrameSchema({"value": pa.Column(object)})
    overrides = pandera_schema_overrides(schema)
    assert overrides["value"] == pl.String()

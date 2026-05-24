"""Map Pandera schemas to Polars read options."""

from __future__ import annotations

import pandera.polars as pa
import polars as pl


def pandera_schema_overrides(schema: pa.DataFrameSchema) -> dict[str, pl.DataType]:
    return {name: _pandera_dtype_to_polars(column.dtype) for name, column in schema.columns.items()}


def _pandera_dtype_to_polars(dtype: object) -> pl.DataType:
    if dtype is str:
        return pl.String()
    if dtype is int:
        return pl.Int64()
    if dtype is float:
        return pl.Float64()
    if dtype is bool:
        return pl.Boolean()

    dtype_name = getattr(dtype, "type", None)
    if dtype_name is str:
        return pl.String()
    if dtype_name is int:
        return pl.Int64()
    if dtype_name is float:
        return pl.Float64()
    if dtype_name is bool:
        return pl.Boolean()

    normalized = str(dtype).lower()
    if "string" in normalized or normalized == "str":
        return pl.String()
    if "int" in normalized:
        return pl.Int64()
    if "float" in normalized or "double" in normalized:
        return pl.Float64()
    if "bool" in normalized:
        return pl.Boolean()
    if "date" in normalized and "time" not in normalized:
        return pl.Date()
    if "datetime" in normalized or "timestamp" in normalized:
        return pl.Datetime()
    return pl.String()

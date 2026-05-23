"""SHA-256 hash computation for canonical ID change detection."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

import polars as pl

from astro.resolver.models import HashGroupsConfig, hash_column_name

FIELD_SEPARATOR = "\x1f"


def _normalize_value(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def canonical_field_string(values: Iterable[object]) -> str:
    return FIELD_SEPARATOR.join(_normalize_value(value) for value in values)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_fields_expr(fields: list[str]) -> pl.Expr:
    ordered_fields = [pl.col(field).cast(pl.String).fill_null("") for field in fields]
    canonical_values = pl.concat_str(ordered_fields, separator=FIELD_SEPARATOR)
    return canonical_values.map_elements(sha256_hex, return_dtype=pl.String)


def hash_all_fields_expr(
    data: pl.DataFrame,
    *,
    exclude_columns: frozenset[str],
) -> pl.Expr:
    included_columns = sorted(column for column in data.columns if column not in exclude_columns)
    if not included_columns:
        return pl.lit(sha256_hex(""))
    return hash_fields_expr(included_columns)


def hash_field_values(data: pl.DataFrame, fields: list[str]) -> pl.Series:
    return data.select(hash_fields_expr(fields).alias("_hash")).to_series()


def compute_hash_columns(
    data: pl.DataFrame,
    hash_groups: HashGroupsConfig,
    *,
    source_key_column: str,
    exclude_columns: frozenset[str] = frozenset(),
) -> pl.DataFrame:
    excluded_for_all = exclude_columns | {source_key_column}
    expressions: list[pl.Expr] = []

    for group_name, fields in hash_groups.items():
        column_name = hash_column_name(group_name)
        if fields == "*all":
            expression = hash_all_fields_expr(data, exclude_columns=excluded_for_all)
        else:
            expression = hash_fields_expr(list(fields))
        expressions.append(expression.alias(column_name))

    if not expressions:
        return data

    return data.with_columns(expressions)

"""Persistent Parquet store for canonical ID mappings."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import polars as pl

from astro.resolver.models import HashGroupsConfig, hash_column_name

PERSISTENT_DIRNAME = ".persistent"
SOURCE_KEY_COLUMN = "source_key"
CANONICAL_ID_COLUMN = "canonical_id"
LAST_CHANGED_DATE_COLUMN = "last_changed_date"
UPDATE_DATES_COLUMN = "update_dates"


def store_path_for(pipeline_dir: Path, name: str) -> Path:
    return pipeline_dir / PERSISTENT_DIRNAME / f"{name}.parquet"


def empty_store_schema(hash_groups: HashGroupsConfig) -> dict[str, pl.DataType]:
    schema = {
        SOURCE_KEY_COLUMN: pl.String(),
        CANONICAL_ID_COLUMN: pl.String(),
        LAST_CHANGED_DATE_COLUMN: pl.Date(),
        UPDATE_DATES_COLUMN: pl.List(pl.Date()),
    }
    for group_name in hash_groups:
        schema[hash_column_name(group_name)] = pl.String()
    return cast(dict[str, pl.DataType], schema)


def empty_store(hash_groups: HashGroupsConfig) -> pl.DataFrame:
    return pl.DataFrame(schema=empty_store_schema(hash_groups))


class ResolverStore:
    """Load and save named canonical ID stores under a pipeline directory."""

    def __init__(self, pipeline_dir: Path, name: str, hash_groups: HashGroupsConfig) -> None:
        self.pipeline_dir = pipeline_dir
        self.name = name
        self.hash_groups = hash_groups
        self.path = store_path_for(pipeline_dir, name)

    def load(self) -> pl.DataFrame:
        if not self.path.is_file():
            return empty_store(self.hash_groups)

        store = pl.read_parquet(self.path)
        self._validate_store_columns(store.columns)
        return store

    def save(self, store: pl.DataFrame) -> None:
        self._validate_store_columns(store.columns)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".parquet.tmp")
        store.write_parquet(temporary_path)
        temporary_path.replace(self.path)

    def _validate_store_columns(self, columns: list[str]) -> None:
        required = set(empty_store_schema(self.hash_groups))
        missing = required - set(columns)
        if missing:
            missing_columns = ", ".join(sorted(missing))
            raise ValueError(f"Resolver store {self.path} is missing columns: {missing_columns}")

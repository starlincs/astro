"""Canonical ID resolver with vectorized Polars operations."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import polars as pl

from astro.resolver.hashing import compute_hash_columns
from astro.resolver.models import (
    EntryStatus,
    HashGroupsConfig,
    ResolverConfig,
    changed_column_name,
    hash_column_name,
)
from astro.resolver.store import (
    CANONICAL_ID_COLUMN,
    LAST_CHANGED_DATE_COLUMN,
    SOURCE_KEY_COLUMN,
    UPDATE_DATES_COLUMN,
    ResolverStore,
)

_NAMESPACED_SOURCE_KEY_COLUMN = "_astro_source_key"
_STORED_SUFFIX = "_stored"


class CanonicalIdResolver:
    """Map source keys to canonical UUIDs and detect grouped field changes.

    Stores persistent state at ``{pipeline_dir}/.persistent/{name}.parquet``.
    """

    def __init__(
        self,
        pipeline_dir: Path,
        name: str,
        hash_groups: HashGroupsConfig,
    ) -> None:
        """Create a resolver scoped to a named persistent store.

        Args:
            pipeline_dir: Pipeline working directory.
            name: Store name (for example ``establishments``).
            hash_groups: Mapping of group names to ``"*all"`` or field name lists.
        """
        self._config = ResolverConfig(name=name, hash_groups=hash_groups)
        self.hash_groups = hash_groups
        self._store = ResolverStore(pipeline_dir, name, hash_groups)

    @property
    def store_path(self) -> Path:
        return self._store.path

    def resolve(
        self,
        data: pl.DataFrame,
        *,
        source_key_column: str,
        namespace: str,
        run_date: date,
        exclude_columns: frozenset[str] = frozenset(),
    ) -> pl.DataFrame:
        """Resolve canonical IDs and change flags for each row in ``data``.

        Args:
            data: Input DataFrame containing ``source_key_column``.
            source_key_column: Column with pipeline-provided identifiers.
            namespace: Prefix for stored keys as ``{namespace}:{source_key}``.
            run_date: Date used for change tracking.
            exclude_columns: Columns excluded from ``"*all"`` hash groups.

        Returns:
            DataFrame augmented with ``canonical_id``, ``status``, and
            ``{group}_changed`` columns.
        """
        self._validate_input(data, source_key_column=source_key_column, namespace=namespace)

        working = compute_hash_columns(
            data,
            self.hash_groups,
            source_key_column=source_key_column,
            exclude_columns=exclude_columns,
        )
        working = working.with_columns(
            pl.concat_str(
                [pl.lit(f"{namespace}:"), pl.col(source_key_column).cast(pl.String)]
            ).alias(_NAMESPACED_SOURCE_KEY_COLUMN)
        )

        store = self._store.load()
        store_for_join = store.select(
            pl.col(SOURCE_KEY_COLUMN),
            pl.col(CANONICAL_ID_COLUMN).alias(f"{CANONICAL_ID_COLUMN}{_STORED_SUFFIX}"),
            pl.col(LAST_CHANGED_DATE_COLUMN).alias(f"{LAST_CHANGED_DATE_COLUMN}{_STORED_SUFFIX}"),
            pl.col(UPDATE_DATES_COLUMN).alias(f"{UPDATE_DATES_COLUMN}{_STORED_SUFFIX}"),
            *[
                pl.col(hash_column_name(group_name)).alias(
                    f"{hash_column_name(group_name)}{_STORED_SUFFIX}"
                )
                for group_name in self.hash_groups
            ],
        )
        joined = working.join(
            store_for_join,
            left_on=_NAMESPACED_SOURCE_KEY_COLUMN,
            right_on=SOURCE_KEY_COLUMN,
            how="left",
        )

        is_new = pl.col(f"{CANONICAL_ID_COLUMN}{_STORED_SUFFIX}").is_null()
        group_changed_exprs: list[pl.Expr] = []
        hash_changed_exprs: list[pl.Expr] = []

        for group_name in self.hash_groups:
            hash_column = hash_column_name(group_name)
            stored_hash_column = f"{hash_column}{_STORED_SUFFIX}"
            changed_column = changed_column_name(group_name)
            group_changed = is_new | (
                pl.col(hash_column) != pl.col(stored_hash_column).fill_null("__missing__")
            )
            group_changed_exprs.append(group_changed.alias(changed_column))
            hash_changed_exprs.append(group_changed)

        any_hash_changed = pl.any_horizontal(hash_changed_exprs) if hash_changed_exprs else is_new
        all_hashes_match = ~is_new & ~any_hash_changed

        joined = joined.with_columns(group_changed_exprs).with_columns(
            pl.when(is_new)
            .then(pl.lit(EntryStatus.NEW.value))
            .when(all_hashes_match)
            .then(pl.lit(EntryStatus.UNCHANGED.value))
            .otherwise(pl.lit(EntryStatus.CHANGED.value))
            .alias("status")
        )

        joined = self._assign_new_canonical_ids(joined, is_new=is_new)
        joined = joined.with_columns(
            pl.coalesce(
                pl.col(f"{CANONICAL_ID_COLUMN}{_STORED_SUFFIX}"),
                pl.col("_astro_new_canonical_id"),
            ).alias(CANONICAL_ID_COLUMN)
        )

        run_date_expr = pl.lit(run_date, dtype=pl.Date)
        joined = joined.with_columns(
            pl.when(is_new | any_hash_changed)
            .then(run_date_expr)
            .otherwise(pl.col(f"{LAST_CHANGED_DATE_COLUMN}{_STORED_SUFFIX}"))
            .alias(LAST_CHANGED_DATE_COLUMN),
            pl.when(is_new)
            .then(pl.concat_list([run_date_expr]))
            .when(any_hash_changed & ~is_new)
            .then(
                pl.col(f"{UPDATE_DATES_COLUMN}{_STORED_SUFFIX}")
                .fill_null(pl.lit([], dtype=pl.List(pl.Date)))
                .list.concat(run_date_expr)
            )
            .otherwise(pl.col(f"{UPDATE_DATES_COLUMN}{_STORED_SUFFIX}"))
            .alias(UPDATE_DATES_COLUMN),
        )

        store_updates = joined.select(
            pl.col(_NAMESPACED_SOURCE_KEY_COLUMN).alias(SOURCE_KEY_COLUMN),
            pl.col(CANONICAL_ID_COLUMN),
            pl.col(LAST_CHANGED_DATE_COLUMN),
            pl.col(UPDATE_DATES_COLUMN),
            *[pl.col(hash_column_name(group_name)) for group_name in self.hash_groups],
        )
        self._upsert_store(store, store_updates)

        output_columns = [
            *data.columns,
            CANONICAL_ID_COLUMN,
            "status",
            *[changed_column_name(group_name) for group_name in self.hash_groups],
        ]
        return joined.select(output_columns)

    def _assign_new_canonical_ids(self, joined: pl.DataFrame, *, is_new: pl.Expr) -> pl.DataFrame:
        new_keys = (
            joined.filter(is_new)
            .select(_NAMESPACED_SOURCE_KEY_COLUMN)
            .unique()
            .to_series()
            .to_list()
        )
        if not new_keys:
            return joined.with_columns(
                pl.lit(None, dtype=pl.String).alias("_astro_new_canonical_id")
            )

        uuid_assignments = pl.DataFrame(
            {
                _NAMESPACED_SOURCE_KEY_COLUMN: new_keys,
                "_astro_new_canonical_id": [str(uuid.uuid4()) for _ in new_keys],
            }
        )
        return joined.join(uuid_assignments, on=_NAMESPACED_SOURCE_KEY_COLUMN, how="left")

    def _upsert_store(self, store: pl.DataFrame, store_updates: pl.DataFrame) -> None:
        if store_updates.is_empty():
            return
        batch_keys = store_updates.get_column(SOURCE_KEY_COLUMN)
        unchanged_store = store.filter(~pl.col(SOURCE_KEY_COLUMN).is_in(batch_keys))
        merged_store = pl.concat([unchanged_store, store_updates], how="vertical_relaxed").unique(
            SOURCE_KEY_COLUMN,
            keep="last",
        )
        self._store.save(merged_store)

    def _validate_input(
        self,
        data: pl.DataFrame,
        *,
        source_key_column: str,
        namespace: str,
    ) -> None:
        if not namespace:
            raise ValueError("namespace must not be empty.")
        if source_key_column not in data.columns:
            raise ValueError(f"source_key_column {source_key_column!r} not found in data.")

        missing_fields: set[str] = set()
        for _group_name, fields in self.hash_groups.items():
            if fields == "*all":
                continue
            missing_fields.update(set(fields) - set(data.columns))

        if missing_fields:
            missing_columns = ", ".join(sorted(missing_fields))
            raise ValueError(f"Hash groups reference missing columns: {missing_columns}")

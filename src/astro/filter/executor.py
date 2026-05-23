"""Filter step execution."""

from __future__ import annotations

import polars as pl

from astro.filter.store import FilterStore
from astro.filter.types import FilterFn
from astro.pipeline.files import AstroFile
from astro.pipeline.steps import StepContext


class FilterValidationError(ValueError):
    """Raised when a filter returns rows that are not present in the input."""


def apply_filter_step(
    context: StepContext,
    files: list[AstroFile],
    filter_fn: FilterFn,
) -> None:
    filter_store = FilterStore(context.run_directory)
    total_filtered = 0

    for file in files:
        dataframe = file.load()
        removed = filter_fn(dataframe)
        if not isinstance(removed, pl.DataFrame):
            raise TypeError("Filter function must return a Polars DataFrame.")

        ingest_name = file.spec.__class__.ingest_name
        if removed.is_empty():
            kept = dataframe
            filter_store.write_filtered(
                filter_store.filtered_path(context.step_id, ingest_name),
                removed,
            )
        else:
            _validate_removed_rows(dataframe, removed)
            kept = dataframe.join(removed, on=dataframe.columns, how="anti")
            filter_store.write_filtered(
                filter_store.filtered_path(context.step_id, ingest_name),
                removed,
            )

        file.save_in_place(kept)
        context.stats.record_file(ingest_name, "rows_filtered", removed.height)
        context.stats.record_file(ingest_name, "rows_kept", kept.height)
        total_filtered += removed.height

    context.stats.record_step("rows_filtered", total_filtered)


def _validate_removed_rows(dataframe: pl.DataFrame, removed: pl.DataFrame) -> None:
    if set(removed.columns) != set(dataframe.columns):
        raise FilterValidationError("Filter returned columns that do not match the input file.")

    ordered_removed = removed.select(dataframe.columns)
    matched = ordered_removed.join(dataframe, on=dataframe.columns, how="inner")
    if matched.height != ordered_removed.height:
        raise FilterValidationError("Filter returned rows that are not present in the input file.")

"""Filter step execution."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import polars as pl

from astro.filter.store import FilterStore
from astro.filter.types import FilterFn
from astro.io.parquet import ParquetBatchWriter, parquet_row_count
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
        if file.is_large_file():
            filtered_count = _apply_filter_batched(context, file, filter_fn, filter_store)
        else:
            filtered_count = _apply_filter_eager(context, file, filter_fn, filter_store)
        total_filtered += filtered_count

    context.stats.record_step("rows_filtered", total_filtered)


def apply_predicate_filter_step(
    context: StepContext,
    files: list[AstroFile],
    predicate: pl.Expr,
) -> None:
    filter_store = FilterStore(context.run_directory)
    total_filtered = 0

    for file in files:
        ingest_name = file.spec.__class__.ingest_name
        filtered_path = filter_store.filtered_path(context.step_id, ingest_name)
        lazy_frame = file.scan()
        removed_lazy = lazy_frame.filter(predicate)
        kept_lazy = lazy_frame.filter(~predicate)

        removed_lazy.sink_parquet(filtered_path)
        if file.is_large_file():
            file.save_in_place_lazy(kept_lazy)
        else:
            file.save_in_place(cast(pl.DataFrame, kept_lazy.collect()))

        removed_count = parquet_row_count(filtered_path)
        kept_count = file.row_count()
        context.stats.record_file(ingest_name, "rows_filtered", removed_count)
        context.stats.record_file(ingest_name, "rows_kept", kept_count)
        total_filtered += removed_count

    context.stats.record_step("rows_filtered", total_filtered)


def _apply_filter_eager(
    context: StepContext,
    file: AstroFile,
    filter_fn: FilterFn,
    filter_store: FilterStore,
) -> int:
    dataframe = file.load()
    removed = filter_fn(dataframe)
    if not isinstance(removed, pl.DataFrame):
        raise TypeError("Filter function must return a Polars DataFrame.")

    ingest_name = file.spec.__class__.ingest_name
    filtered_path = filter_store.filtered_path(context.step_id, ingest_name)
    if removed.is_empty():
        kept = dataframe
    else:
        _validate_removed_rows(dataframe, removed)
        kept = dataframe.join(removed, on=dataframe.columns, how="anti")

    filter_store.write_filtered(filtered_path, removed)
    file.save_in_place(kept)
    context.stats.record_file(ingest_name, "rows_filtered", removed.height)
    context.stats.record_file(ingest_name, "rows_kept", kept.height)
    return removed.height


def _apply_filter_batched(
    context: StepContext,
    file: AstroFile,
    filter_fn: FilterFn,
    filter_store: FilterStore,
) -> int:
    ingest_name = file.spec.__class__.ingest_name
    filtered_path = filter_store.filtered_path(context.step_id, ingest_name)
    kept_temp_path = _temporary_path(file.active_path, suffix=".kept.tmp.parquet")
    removed_temp_path = _temporary_path(filtered_path, suffix=".tmp.parquet")
    kept_writer = ParquetBatchWriter(kept_temp_path)
    removed_writer = ParquetBatchWriter(removed_temp_path)
    total_filtered = 0

    try:
        for batch in file.iter_batches():
            removed = filter_fn(batch)
            if not isinstance(removed, pl.DataFrame):
                raise TypeError("Filter function must return a Polars DataFrame.")

            if removed.is_empty():
                kept = batch
            else:
                _validate_removed_rows(batch, removed)
                kept = batch.join(removed, on=batch.columns, how="anti")

            kept_writer.write_batch(kept)
            removed_writer.write_batch(removed)
            total_filtered += removed.height

        kept_count, _ = kept_writer.close()
        removed_writer.close()
        _replace_file(kept_temp_path, Path(file.ingest_record.parquet_path))
        _replace_file(removed_temp_path, filtered_path)
        file._active_path = Path(file.ingest_record.parquet_path)
    except Exception:
        kept_writer.abort()
        removed_writer.abort()
        kept_temp_path.unlink(missing_ok=True)
        removed_temp_path.unlink(missing_ok=True)
        raise

    context.stats.record_file(ingest_name, "rows_filtered", total_filtered)
    context.stats.record_file(ingest_name, "rows_kept", kept_count)
    return total_filtered


def _validate_removed_rows(dataframe: pl.DataFrame, removed: pl.DataFrame) -> None:
    if set(removed.columns) != set(dataframe.columns):
        raise FilterValidationError("Filter returned columns that do not match the input file.")

    ordered_removed = removed.select(dataframe.columns)
    matched = ordered_removed.join(dataframe, on=dataframe.columns, how="inner")
    if matched.height != ordered_removed.height:
        raise FilterValidationError("Filter returned rows that are not present in the input file.")


def _temporary_path(path: Path, *, suffix: str) -> Path:
    return path.with_name(f"{path.name}{suffix}")


def _replace_file(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.replace(destination_path)

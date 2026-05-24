"""CSV batch iteration helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Literal, cast

import polars as pl
import pyarrow.csv as pacsv

from astro.io.schema import pandera_schema_overrides
from astro.pipeline.models import IngestFileSpec

_POLARS_ENCODING_ALIASES = {
    "utf-8": "utf8",
    "utf_8": "utf8",
}

_PYARROW_ENCODING_ALIASES = {
    "utf-8": "utf8",
    "utf_8": "utf8",
    "windows-1252": "CP1252",
    "cp1252": "CP1252",
}

IngestBatchCallback = Callable[[int, int | None], None]


def polars_encoding(encoding: str) -> str:
    return _POLARS_ENCODING_ALIASES.get(encoding.lower(), encoding)


def _encoding_supports_scan_csv(encoding: str) -> bool:
    normalized = polars_encoding(encoding).lower()
    return normalized in {"utf8", "utf8-lossy"}


def _pyarrow_encoding(encoding: str) -> str:
    return _PYARROW_ENCODING_ALIASES.get(encoding.lower(), encoding)


def estimate_csv_row_count(
    source_path: Path,
    *,
    has_header: bool,
    sample_lines: int = 1000,
) -> int | None:
    file_size = source_path.stat().st_size
    if file_size == 0:
        return 0

    header_bytes = 0
    sample_bytes = 0
    sample_rows = 0
    with source_path.open("rb") as handle:
        if has_header:
            header = handle.readline()
            if not header:
                return 0
            header_bytes = len(header)
        for _ in range(sample_lines):
            line = handle.readline()
            if not line:
                break
            sample_bytes += len(line)
            sample_rows += 1

    if sample_rows == 0:
        return None

    body_size = max(file_size - header_bytes, 1)
    average_row_bytes = max(sample_bytes / sample_rows, 1)
    return max(int(body_size / average_row_bytes), sample_rows)


def iter_csv_batches(
    source_path: Path,
    spec: IngestFileSpec,
    *,
    batch_size: int,
    on_batch: IngestBatchCallback | None = None,
    estimated_total_rows: int | None = None,
) -> Iterator[pl.DataFrame]:
    if estimated_total_rows is None:
        estimated_total_rows = estimate_csv_row_count(source_path, has_header=spec.has_header)

    encoding = polars_encoding(spec.encoding)
    if _encoding_supports_scan_csv(encoding):
        yield from _iter_csv_batches_scan(
            source_path,
            spec,
            batch_size=batch_size,
            encoding=encoding,
            on_batch=on_batch,
            estimated_total_rows=estimated_total_rows,
        )
        return

    yield from _iter_csv_batches_pyarrow(
        source_path,
        spec,
        batch_size=batch_size,
        encoding=_pyarrow_encoding(spec.encoding),
        on_batch=on_batch,
        estimated_total_rows=estimated_total_rows,
    )


def _iter_csv_batches_scan(
    source_path: Path,
    spec: IngestFileSpec,
    *,
    batch_size: int,
    encoding: str,
    on_batch: IngestBatchCallback | None,
    estimated_total_rows: int | None,
) -> Iterator[pl.DataFrame]:
    schema_overrides = pandera_schema_overrides(spec.schema)
    scan_encoding = cast(Literal["utf8", "utf8-lossy"], encoding)
    rows_processed = 0
    if spec.has_header:
        lazy_frame = pl.scan_csv(
            source_path,
            infer_schema_length=0,
            encoding=scan_encoding,
            schema_overrides=schema_overrides,
        )
    else:
        lazy_frame = pl.scan_csv(
            source_path,
            infer_schema_length=0,
            encoding=scan_encoding,
            schema_overrides=schema_overrides,
            has_header=False,
            new_columns=list(spec.column_names or spec.schema.columns.keys()),
        )
    for batch in lazy_frame.collect_batches(chunk_size=batch_size):
        if batch.is_empty():
            break
        rows_processed += batch.height
        if on_batch is not None:
            on_batch(rows_processed, estimated_total_rows)
        yield batch
        if batch.height < batch_size:
            break


def _iter_csv_batches_pyarrow(
    source_path: Path,
    spec: IngestFileSpec,
    *,
    batch_size: int,
    encoding: str,
    on_batch: IngestBatchCallback | None,
    estimated_total_rows: int | None,
) -> Iterator[pl.DataFrame]:
    parse_options = pacsv.ParseOptions(newlines_in_values=True)
    if not spec.has_header:
        parse_options = pacsv.ParseOptions(
            newlines_in_values=True,
            column_names=list(spec.column_names or spec.schema.columns.keys()),
        )
    read_options = pacsv.ReadOptions(
        encoding=encoding,
        block_size=max(batch_size * 256, 1024 * 1024),
        skip_rows=1 if spec.has_header else 0,
    )
    reader = pacsv.open_csv(
        source_path,
        read_options=read_options,
        parse_options=parse_options,
    )

    pending_frames: list[pl.DataFrame] = []
    pending_rows = 0
    rows_processed = 0

    for record_batch in reader:
        chunk = cast(pl.DataFrame, pl.from_arrow(record_batch))
        if chunk.is_empty():
            continue
        pending_frames.append(chunk)
        pending_rows += chunk.height

        while pending_rows >= batch_size:
            if len(pending_frames) > 1:
                combined = pl.concat(pending_frames, rechunk=True)
            else:
                combined = pending_frames[0]
            batch = combined.head(batch_size)
            remainder = combined.slice(batch_size)
            pending_frames = [remainder] if not remainder.is_empty() else []
            pending_rows = remainder.height
            rows_processed += batch.height
            if on_batch is not None:
                on_batch(rows_processed, estimated_total_rows)
            yield batch

    if pending_rows > 0:
        if len(pending_frames) > 1:
            combined = pl.concat(pending_frames, rechunk=True)
        else:
            combined = pending_frames[0]
        rows_processed += combined.height
        if on_batch is not None:
            on_batch(rows_processed, estimated_total_rows)
        yield combined

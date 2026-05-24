"""CSV ingest materialization to Parquet."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from astro.ingest.validator import MatchedIngestFile
from astro.io.constants import DEFAULT_INGEST_BATCH_SIZE, DEFAULT_LARGE_FILE_THRESHOLD_BYTES
from astro.io.csv import estimate_csv_row_count, iter_csv_batches, polars_encoding
from astro.io.parquet import ParquetBatchWriter
from astro.io.schema import pandera_schema_overrides
from astro.pipeline.models import IngestFileSpec
from astro.working.manifest import IngestedFileRecord

IngestProgressCallback = Callable[[str, int, int | None], None]


@dataclass(frozen=True)
class MaterializedIngestFile:
    record: IngestedFileRecord


def _read_csv_eager(source_path: Path, spec: IngestFileSpec) -> pl.DataFrame:
    encoding = polars_encoding(spec.encoding)
    schema_overrides = pandera_schema_overrides(spec.schema)
    if spec.has_header:
        return pl.read_csv(
            source_path,
            infer_schema_length=0,
            encoding=encoding,
            schema_overrides=schema_overrides,
        )
    return pl.read_csv(
        source_path,
        infer_schema_length=0,
        encoding=encoding,
        schema_overrides=schema_overrides,
        has_header=False,
        new_columns=list(spec.column_names or ()),
    )


def _materialize_eager(
    source_path: Path,
    spec: IngestFileSpec,
    *,
    ingest_directory: Path,
) -> MaterializedIngestFile:
    dataframe = _read_csv_eager(source_path, spec)
    validated = spec.schema.validate(dataframe)
    parquet_path = ingest_directory / f"{spec.name}.parquet"
    validated.write_parquet(parquet_path)
    return MaterializedIngestFile(
        record=IngestedFileRecord(
            name=spec.name,
            source_path=str(source_path.resolve()),
            parquet_path=str(parquet_path.resolve()),
            row_count=validated.height,
            column_count=len(validated.columns),
            source_size_bytes=source_path.stat().st_size,
        )
    )


def _materialize_batched(
    source_path: Path,
    spec: IngestFileSpec,
    *,
    ingest_directory: Path,
    ingest_batch_size: int,
    progress_callback: IngestProgressCallback | None = None,
) -> MaterializedIngestFile:
    parquet_path = ingest_directory / f"{spec.name}.parquet"
    writer = ParquetBatchWriter(parquet_path)
    estimated_total_rows = estimate_csv_row_count(source_path, has_header=spec.has_header)

    def on_batch(rows_done: int, total_rows: int | None) -> None:
        if progress_callback is not None:
            progress_callback(spec.name, rows_done, total_rows or estimated_total_rows)

    try:
        for batch in iter_csv_batches(
            source_path,
            spec,
            batch_size=ingest_batch_size,
            on_batch=on_batch,
            estimated_total_rows=estimated_total_rows,
        ):
            validated = spec.schema.validate(batch)
            writer.write_batch(validated)
    except Exception:
        writer.abort()
        raise

    row_count, column_count = writer.close()
    if row_count == 0:
        writer.abort()
        raise ValueError(f"No rows materialized for ingest file {spec.name!r}.")

    return MaterializedIngestFile(
        record=IngestedFileRecord(
            name=spec.name,
            source_path=str(source_path.resolve()),
            parquet_path=str(parquet_path.resolve()),
            row_count=row_count,
            column_count=column_count,
            source_size_bytes=source_path.stat().st_size,
        )
    )


def materialize_ingest_file(
    matched_file: MatchedIngestFile,
    *,
    ingest_directory: Path,
    large_file_threshold_bytes: int = DEFAULT_LARGE_FILE_THRESHOLD_BYTES,
    ingest_batch_size: int = DEFAULT_INGEST_BATCH_SIZE,
    progress_callback: IngestProgressCallback | None = None,
) -> MaterializedIngestFile:
    ingest_directory.mkdir(parents=True, exist_ok=True)
    source_path = matched_file.source_path
    spec = matched_file.spec
    source_size_bytes = source_path.stat().st_size

    if source_size_bytes >= large_file_threshold_bytes:
        return _materialize_batched(
            source_path,
            spec,
            ingest_directory=ingest_directory,
            ingest_batch_size=ingest_batch_size,
            progress_callback=progress_callback,
        )

    return _materialize_eager(source_path, spec, ingest_directory=ingest_directory)

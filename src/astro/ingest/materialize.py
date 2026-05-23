"""CSV ingest materialization to Parquet."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from astro.ingest.validator import MatchedIngestFile
from astro.working.manifest import IngestedFileRecord


@dataclass(frozen=True)
class MaterializedIngestFile:
    record: IngestedFileRecord
    dataframe: pl.DataFrame


def materialize_ingest_file(
    matched_file: MatchedIngestFile,
    *,
    ingest_directory: Path,
) -> MaterializedIngestFile:
    ingest_directory.mkdir(parents=True, exist_ok=True)
    source_path = matched_file.source_path
    dataframe = pl.read_csv(
        source_path,
        infer_schema_length=0,
        encoding=matched_file.spec.encoding,
    )
    validated = matched_file.spec.schema.validate(dataframe)
    parquet_path = ingest_directory / f"{matched_file.spec.name}.parquet"
    validated.write_parquet(parquet_path)

    record = IngestedFileRecord(
        name=matched_file.spec.name,
        source_path=str(source_path.resolve()),
        parquet_path=str(parquet_path.resolve()),
        row_count=validated.height,
        column_count=len(validated.columns),
        source_size_bytes=source_path.stat().st_size,
    )
    return MaterializedIngestFile(record=record, dataframe=validated)

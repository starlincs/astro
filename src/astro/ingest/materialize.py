"""CSV ingest materialization to Parquet."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import polars as pl

from astro.ingest.validator import MatchedIngestFile
from astro.pipeline.models import IngestFileSpec
from astro.working.manifest import IngestedFileRecord

_STREAMING_INGEST_THRESHOLD_BYTES = 500 * 1024 * 1024

_POLARS_ENCODING_ALIASES = {
    "utf-8": "utf8",
    "utf_8": "utf8",
    "windows-1252": "utf8-lossy",
    "cp1252": "utf8-lossy",
}


def _polars_encoding(encoding: str) -> Literal["utf8", "utf8-lossy"] | str:
    return _POLARS_ENCODING_ALIASES.get(encoding.lower(), encoding)


@dataclass(frozen=True)
class MaterializedIngestFile:
    record: IngestedFileRecord
    dataframe: pl.DataFrame


def _read_csv(source_path: Path, spec: IngestFileSpec) -> pl.DataFrame:
    encoding = cast(Literal["utf8", "utf8-lossy"], _polars_encoding(spec.encoding))
    if spec.has_header:
        if source_path.stat().st_size >= _STREAMING_INGEST_THRESHOLD_BYTES:
            return cast(
                pl.DataFrame,
                pl.scan_csv(source_path, infer_schema_length=0, encoding=encoding).collect(
                    engine="streaming"
                ),
            )
        return pl.read_csv(source_path, infer_schema_length=0, encoding=encoding)

    column_names = list(spec.column_names or ())
    if source_path.stat().st_size >= _STREAMING_INGEST_THRESHOLD_BYTES:
        return cast(
            pl.DataFrame,
            pl.scan_csv(
                source_path,
                infer_schema_length=0,
                encoding=encoding,
                has_header=False,
                new_columns=column_names,
            ).collect(engine="streaming"),
        )
    return pl.read_csv(
        source_path,
        infer_schema_length=0,
        encoding=encoding,
        has_header=False,
        new_columns=column_names,
    )


def materialize_ingest_file(
    matched_file: MatchedIngestFile,
    *,
    ingest_directory: Path,
) -> MaterializedIngestFile:
    ingest_directory.mkdir(parents=True, exist_ok=True)
    source_path = matched_file.source_path
    spec = matched_file.spec
    dataframe = _read_csv(source_path, spec)
    validated = spec.schema.validate(dataframe)
    parquet_path = ingest_directory / f"{spec.name}.parquet"
    validated.write_parquet(parquet_path)

    record = IngestedFileRecord(
        name=spec.name,
        source_path=str(source_path.resolve()),
        parquet_path=str(parquet_path.resolve()),
        row_count=validated.height,
        column_count=len(validated.columns),
        source_size_bytes=source_path.stat().st_size,
    )
    return MaterializedIngestFile(record=record, dataframe=validated)

"""Ingest materialization tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest
from pandera.errors import SchemaError, SchemaErrors

from astro.ingest.materialize import materialize_ingest_file
from astro.ingest.validator import MatchedIngestFile, match_ingest_files
from astro.pipeline import IngestFileSpec


def test_materialize_writes_parquet_and_stats(
    sample_ingest_spec: IngestFileSpec,
    source_directory: Path,
    tmp_path: Path,
) -> None:
    matched = match_ingest_files(source_directory, [sample_ingest_spec])[0]
    ingest_directory = tmp_path / "ingested"

    materialized = materialize_ingest_file(matched, ingest_directory=ingest_directory)

    assert materialized.record.row_count == 1
    assert materialized.record.column_count == 2
    assert Path(materialized.record.parquet_path).is_file()
    loaded = pl.read_parquet(materialized.record.parquet_path)
    assert loaded.columns == ["URN", "EstablishmentName"]


def test_materialize_raises_when_pandera_validation_fails(
    source_directory: Path,
    tmp_path: Path,
) -> None:
    invalid_spec = IngestFileSpec(
        name="establishments",
        source_pattern="edubase*.csv",
        schema=pa.DataFrameSchema({"MissingColumn": pa.Column(str)}, strict="filter"),
    )
    matched = MatchedIngestFile(
        spec=invalid_spec,
        source_path=source_directory / "edubase20260522.csv",
    )

    with pytest.raises((SchemaError, SchemaErrors)):
        materialize_ingest_file(matched, ingest_directory=tmp_path / "ingested")

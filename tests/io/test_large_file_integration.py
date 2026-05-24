"""Large-file integration tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest

from astro.ingest.materialize import materialize_ingest_file
from astro.ingest.validator import MatchedIngestFile
from astro.pipeline.models import IngestFileSpec


@pytest.mark.large
def test_batched_ingest_handles_large_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "large.csv"
    row_count = 120_000
    with csv_path.open("w", encoding="utf-8") as handle:
        handle.write("id,value\n")
        for index in range(row_count):
            handle.write(f"{index},{index % 1000}\n")

    spec = IngestFileSpec(
        name="large",
        source_pattern="large.csv",
        schema=pa.DataFrameSchema(
            {"id": pa.Column(int), "value": pa.Column(int)},
            strict="filter",
        ),
    )
    matched = MatchedIngestFile(spec=spec, source_path=csv_path)
    ingest_directory = tmp_path / "ingested"

    materialized = materialize_ingest_file(
        matched,
        ingest_directory=ingest_directory,
        large_file_threshold_bytes=1024,
        ingest_batch_size=25_000,
    )

    assert materialized.record.row_count == row_count
    assert pl.read_parquet(materialized.record.parquet_path).height == row_count

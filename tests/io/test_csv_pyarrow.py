"""PyArrow CSV batch iteration tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl

from astro.ingest.materialize import materialize_ingest_file
from astro.ingest.validator import MatchedIngestFile
from astro.io.csv import iter_csv_batches
from astro.pipeline.models import IngestFileSpec


def test_iter_csv_batches_applies_schema_overrides_for_non_utf8(tmp_path: Path) -> None:
    csv_path = tmp_path / "data.csv"
    csv_path.write_bytes("id,value\n1,10\n2,20\n".encode("cp1252"))
    spec = IngestFileSpec(
        name="sample",
        source_pattern="data.csv",
        schema=pa.DataFrameSchema(
            {
                "id": pa.Column(int),
                "value": pa.Column(int),
            },
            strict="filter",
        ),
        encoding="windows-1252",
    )

    batches = list(iter_csv_batches(csv_path, spec, batch_size=10))

    assert len(batches) == 1
    assert batches[0].schema == {"id": pl.Int64, "value": pl.Int64}


def test_batched_materialize_uses_pyarrow_path_for_non_utf8(tmp_path: Path) -> None:
    csv_path = tmp_path / "data.csv"
    csv_path.write_bytes("id,name\n1,alpha\n".encode("cp1252"))
    spec = IngestFileSpec(
        name="sample",
        source_pattern="data.csv",
        schema=pa.DataFrameSchema(
            {"id": pa.Column(int), "name": pa.Column(str)},
            strict="filter",
        ),
        encoding="windows-1252",
    )
    matched = MatchedIngestFile(spec=spec, source_path=csv_path)
    ingest_directory = tmp_path / "ingested"

    materialized = materialize_ingest_file(
        matched,
        ingest_directory=ingest_directory,
        large_file_threshold_bytes=1,
        ingest_batch_size=100,
    )

    assert materialized.record.row_count == 1
    parquet = pl.read_parquet(materialized.record.parquet_path)
    assert parquet.schema == {"id": pl.Int64, "name": pl.String}

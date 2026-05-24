"""Large-file I/O tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest
from pandera.errors import SchemaError, SchemaErrors

from astro.ingest.materialize import materialize_ingest_file
from astro.ingest.validator import MatchedIngestFile
from astro.io.csv import estimate_csv_row_count, iter_csv_batches
from astro.io.parquet import (
    ParquetBatchWriter,
    is_large_file,
    parquet_has_rows,
    parquet_row_count,
)
from astro.io.schema import pandera_schema_overrides
from astro.pipeline.models import IngestFileSpec


def _write_establishments_csv(path: Path, row_count: int) -> None:
    rows = "\n".join(f"{index},School {index}" for index in range(row_count))
    path.write_text(f"URN,EstablishmentName\n{rows}", encoding="utf-8")


def test_pandera_schema_overrides_map_string_columns() -> None:
    schema = pa.DataFrameSchema(
        {"URN": pa.Column(str), "Count": pa.Column(int)},
        strict="filter",
    )

    overrides = pandera_schema_overrides(schema)

    assert overrides["URN"] == pl.String()
    assert overrides["Count"] == pl.Int64()


def test_parquet_row_count_uses_metadata(tmp_path: Path) -> None:
    path = tmp_path / "rows.parquet"
    pl.DataFrame({"value": list(range(2500))}).write_parquet(path)

    assert parquet_row_count(path) == 2500
    assert parquet_has_rows(path)
    assert is_large_file(path, threshold_bytes=10**12) is False


def test_estimate_csv_row_count_extrapolates_from_sample(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    _write_establishments_csv(csv_path, 5000)

    estimated = estimate_csv_row_count(csv_path, has_header=True)

    assert estimated is not None
    assert 4000 <= estimated <= 6500


def test_iter_csv_batches_reads_all_rows_in_single_pass(tmp_path: Path) -> None:
    csv_path = tmp_path / "large.csv"
    _write_establishments_csv(csv_path, 2500)
    spec = IngestFileSpec(
        name="establishments",
        source_pattern="large.csv",
        schema=pa.DataFrameSchema(
            {"URN": pa.Column(str), "EstablishmentName": pa.Column(str)},
            strict="filter",
        ),
    )

    batches = list(iter_csv_batches(csv_path, spec, batch_size=1000))

    assert sum(batch.height for batch in batches) == 2500
    assert len(batches) == 3


def test_materialize_uses_batched_path_for_large_source_files(tmp_path: Path) -> None:
    csv_path = tmp_path / "large.csv"
    _write_establishments_csv(csv_path, 2500)
    spec = IngestFileSpec(
        name="establishments",
        source_pattern="large.csv",
        schema=pa.DataFrameSchema(
            {"URN": pa.Column(str), "EstablishmentName": pa.Column(str)},
            strict="filter",
        ),
    )
    matched = MatchedIngestFile(spec=spec, source_path=csv_path)
    progress_updates: list[tuple[int, int | None]] = []

    materialized = materialize_ingest_file(
        matched,
        ingest_directory=tmp_path / "ingested",
        large_file_threshold_bytes=1,
        ingest_batch_size=1000,
        progress_callback=lambda _name, rows_done, total_rows: progress_updates.append(
            (rows_done, total_rows)
        ),
    )

    assert materialized.record.row_count == 2500
    assert progress_updates
    assert progress_updates[-1][0] == 2500
    loaded = pl.read_parquet(materialized.record.parquet_path)
    assert loaded.height == 2500


def test_batched_materialize_removes_partial_output_on_validation_failure(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid.csv"
    rows = []
    for index in range(1500):
        urn = "bad" if index == 500 else str(index)
        rows.append(f"{urn},School {index}")
    csv_path.write_text("URN,EstablishmentName\n" + "\n".join(rows), encoding="utf-8")
    spec = IngestFileSpec(
        name="establishments",
        source_pattern="invalid.csv",
        schema=pa.DataFrameSchema(
            {
                "URN": pa.Column(str, checks=pa.Check.str_matches(r"^\d+$")),
                "EstablishmentName": pa.Column(str),
            },
            strict="filter",
        ),
    )
    matched = MatchedIngestFile(spec=spec, source_path=csv_path)
    parquet_path = tmp_path / "ingested" / "establishments.parquet"

    with pytest.raises((SchemaError, SchemaErrors)):
        materialize_ingest_file(
            matched,
            ingest_directory=tmp_path / "ingested",
            large_file_threshold_bytes=1,
            ingest_batch_size=1000,
        )

    assert not parquet_path.exists()


def test_parquet_batch_writer_appends_multiple_batches(tmp_path: Path) -> None:
    path = tmp_path / "batched.parquet"
    writer = ParquetBatchWriter(path)
    writer.write_batch(pl.DataFrame({"value": [1, 2]}))
    writer.write_batch(pl.DataFrame({"value": [3]}))
    row_count, column_count = writer.close()

    assert row_count == 3
    assert column_count == 1
    assert parquet_row_count(path) == 3


@pytest.mark.large
def test_materialize_accepts_large_csv_without_loading_entire_file_in_one_batch(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "medium.csv"
    _write_establishments_csv(csv_path, 5000)
    spec = IngestFileSpec(
        name="establishments",
        source_pattern="medium.csv",
        schema=pa.DataFrameSchema(
            {"URN": pa.Column(str), "EstablishmentName": pa.Column(str)},
            strict="filter",
        ),
    )
    matched = MatchedIngestFile(spec=spec, source_path=csv_path)

    materialized = materialize_ingest_file(
        matched,
        ingest_directory=tmp_path / "ingested",
        large_file_threshold_bytes=1,
        ingest_batch_size=500,
    )

    assert materialized.record.row_count == 5000

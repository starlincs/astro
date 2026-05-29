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


def test_materialize_reads_cp1252_encoded_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "edubase20260313.csv"
    csv_path.write_bytes("URN,EstablishmentName\n1,St Paul\u2019s School\n".encode("cp1252"))
    spec = IngestFileSpec(
        name="establishments",
        source_pattern="edubase*.csv",
        encoding="windows-1252",
        schema=pa.DataFrameSchema(
            {"URN": pa.Column(str), "EstablishmentName": pa.Column(str)},
            strict="filter",
        ),
    )
    matched = MatchedIngestFile(spec=spec, source_path=csv_path)
    ingest_directory = tmp_path / "ingested"

    materialized = materialize_ingest_file(matched, ingest_directory=ingest_directory)

    loaded = pl.read_parquet(materialized.record.parquet_path)
    assert loaded["EstablishmentName"][0] == "St Paul\u2019s School"


def test_materialize_reads_headerless_csv_with_column_names(tmp_path: Path) -> None:
    csv_path = tmp_path / "paf.csv"
    csv_path.write_text("AB10 1AB,ABERDEEN,52447276\n", encoding="utf-8")
    spec = IngestFileSpec(
        name="raw_paf",
        source_pattern="paf.csv",
        has_header=False,
        column_names=("postcode", "post_town", "udprn"),
        schema=pa.DataFrameSchema(
            {
                "postcode": pa.Column(str),
                "post_town": pa.Column(str),
                "udprn": pa.Column(str),
            },
            strict="filter",
        ),
    )
    matched = MatchedIngestFile(spec=spec, source_path=csv_path)
    ingest_directory = tmp_path / "ingested"

    materialized = materialize_ingest_file(matched, ingest_directory=ingest_directory)

    loaded = pl.read_parquet(materialized.record.parquet_path)
    assert loaded.columns == ["postcode", "post_town", "udprn"]
    assert loaded["postcode"][0] == "AB10 1AB"


def test_materialize_uses_preprocess_before_pandera_validation(tmp_path: Path) -> None:
    source_path = tmp_path / "ignored.txt"
    source_path.write_text("not csv", encoding="utf-8")

    def preprocess(_path: Path) -> pl.DataFrame:
        return pl.DataFrame({"URN": ["100001"], "EstablishmentName": ["From preprocess"]})

    spec = IngestFileSpec(
        name="establishments",
        source_pattern="ignored.txt",
        schema=pa.DataFrameSchema(
            {"URN": pa.Column(str), "EstablishmentName": pa.Column(str)},
            strict="filter",
        ),
        preprocess=preprocess,
    )
    matched = MatchedIngestFile(spec=spec, source_path=source_path)
    ingest_directory = tmp_path / "ingested"

    materialized = materialize_ingest_file(matched, ingest_directory=ingest_directory)

    loaded = pl.read_parquet(materialized.record.parquet_path)
    assert loaded["EstablishmentName"][0] == "From preprocess"


def test_materialize_preprocess_invalid_data_raises_pandera_error(tmp_path: Path) -> None:
    source_path = tmp_path / "ignored.txt"
    source_path.write_text("not csv", encoding="utf-8")

    def preprocess(_path: Path) -> pl.DataFrame:
        return pl.DataFrame({"WrongColumn": ["value"]})

    spec = IngestFileSpec(
        name="establishments",
        source_pattern="ignored.txt",
        schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
        preprocess=preprocess,
    )
    matched = MatchedIngestFile(spec=spec, source_path=source_path)

    with pytest.raises((SchemaError, SchemaErrors)):
        materialize_ingest_file(matched, ingest_directory=tmp_path / "ingested")


def test_materialize_preprocess_uses_eager_path_for_large_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "large.bin"
    source_path.write_bytes(b"x" * 200)

    batched_called = {"value": False}

    def fake_materialize_batched(*_args, **_kwargs):
        batched_called["value"] = True
        raise AssertionError("batched path should not be used when preprocess is set")

    monkeypatch.setattr(
        "astro.ingest.materialize._materialize_batched",
        fake_materialize_batched,
    )

    def preprocess(_path: Path) -> pl.DataFrame:
        return pl.DataFrame({"URN": ["1"]})

    spec = IngestFileSpec(
        name="establishments",
        source_pattern="large.bin",
        schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
        preprocess=preprocess,
    )
    matched = MatchedIngestFile(spec=spec, source_path=source_path)

    materialize_ingest_file(
        matched,
        ingest_directory=tmp_path / "ingested",
        large_file_threshold_bytes=10,
    )

    assert batched_called["value"] is False

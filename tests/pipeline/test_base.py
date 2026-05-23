"""Pipeline base class tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest

from astro import Pipeline
from astro.pipeline import ExecutionMode, IngestFileSpec


class RecordingPipeline(Pipeline):
    name = "recording"
    execution_mode = ExecutionMode.PARALLEL
    ingest_files = [
        IngestFileSpec(
            name="records",
            source_pattern="*.csv",
            schema=pa.DataFrameSchema({"value": pa.Column(str)}, strict="filter"),
        ),
    ]

    def __init__(self) -> None:
        self.transform_calls: list[Path] = []
        self.validate_calls: list[Path] = []

    def transform(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        self.transform_calls.append(source)
        return data.with_columns(pl.lit("transformed").alias("stage"))

    def validate(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        self.validate_calls.append(source)
        return data.with_columns(pl.lit("validated").alias("status"))


def test_pipeline_run_is_not_implemented_yet() -> None:
    pipeline = RecordingPipeline()
    with pytest.raises(NotImplementedError, match="astro ingest"):
        pipeline.run(Path("/tmp/source"))


def test_pipeline_transform_and_validate_can_be_called_directly() -> None:
    pipeline = RecordingPipeline()
    source = Path("/tmp/a.csv")
    data = pl.DataFrame({"value": ["1"]})

    transformed = pipeline.transform(data, source)
    validated = pipeline.validate(transformed, source)

    assert pipeline.transform_calls == [source]
    assert pipeline.validate_calls == [source]
    assert validated.columns == ["value", "stage", "status"]

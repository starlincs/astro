"""Pipeline base class tests."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from astro import IngestedSource, Pipeline


class RecordingPipeline(Pipeline):
    name = "recording"

    def __init__(self) -> None:
        self.transform_calls: list[Path] = []
        self.validate_calls: list[Path] = []

    def ingest(self, path: Path) -> list[IngestedSource]:
        return [
            IngestedSource(path=path / "a.csv", data=pl.DataFrame({"value": [1]})),
            IngestedSource(path=path / "b.csv", data=pl.DataFrame({"value": [2]})),
        ]

    def transform(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        self.transform_calls.append(source)
        return data.with_columns(pl.lit("transformed").alias("stage"))

    def validate(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        self.validate_calls.append(source)
        return data.with_columns(pl.lit("validated").alias("status"))


def test_pipeline_run_processes_each_source_independently(tmp_path: Path) -> None:
    pipeline = RecordingPipeline()

    results = pipeline.run(tmp_path)

    assert len(results) == 2
    assert {result.path.name for result in results} == {"a.csv", "b.csv"}
    assert pipeline.transform_calls == [tmp_path / "a.csv", tmp_path / "b.csv"]
    assert pipeline.validate_calls == [tmp_path / "a.csv", tmp_path / "b.csv"]
    assert results[0].data.columns == ["value", "stage", "status"]

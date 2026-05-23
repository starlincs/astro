"""Example pipeline definition for an external project repository."""

from pathlib import Path

import pandera.polars as pa
import polars as pl

from astro import Pipeline
from astro.pipeline import ExecutionMode, IngestFileSpec


class ExamplePipeline(Pipeline):
    name = "example"
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema(
                {
                    "URN": pa.Column(str),
                    "EstablishmentName": pa.Column(str),
                },
                strict="filter",
            ),
        ),
    ]

    def transform(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        raise NotImplementedError

    def validate(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        raise NotImplementedError


pipeline = ExamplePipeline()

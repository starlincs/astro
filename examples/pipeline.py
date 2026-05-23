"""Example pipeline definition for an external project repository."""

from pathlib import Path

import polars as pl

from astro import IngestedSource, Pipeline


class ExamplePipeline(Pipeline):
    name = "example"

    def ingest(self, path: Path) -> list[IngestedSource]:
        raise NotImplementedError

    def transform(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        raise NotImplementedError

    def validate(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        raise NotImplementedError


pipeline = ExamplePipeline()

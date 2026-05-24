"""Example pipeline definition for an external project repository."""

import pandera.polars as pa
import polars as pl

from astro import AstroFileSpec, Pipeline
from astro.pipeline import ExecutionMode, IngestFileSpec
from astro.pipeline.files import AstroFile
from astro.pipeline.steps import StepContext


class EstablishmentsFile(AstroFileSpec):
    """Ingest file spec for establishment CSV sources."""

    ingest_name = "establishments"


def remove_closed(_dataframe: pl.DataFrame) -> pl.DataFrame:
    return _dataframe.filter(pl.col("EstablishmentName").str.contains("Closed"))


def step_copy_establishments(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    file.save_to("processed", "establishments.parquet", file.load())


class ExamplePipeline(Pipeline):
    """Sample pipeline with a filter step and a copy step."""

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

    def configure_steps(self) -> None:
        self.add_filter("Remove closed establishments", remove_closed, [EstablishmentsFile()])
        self.add_step(
            "Copy establishments to processed",
            step_copy_establishments,
            [EstablishmentsFile()],
            depends_on=["remove-closed-establishments"],
        )


pipeline = ExamplePipeline()

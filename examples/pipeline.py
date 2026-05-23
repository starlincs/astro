"""Example pipeline definition for an external project repository."""

import pandera.polars as pa

from astro import AstroFileSpec, Pipeline
from astro.pipeline import ExecutionMode, IngestFileSpec
from astro.pipeline.files import AstroFile
from astro.pipeline.steps import StepContext


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def step_copy_establishments(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    file.save_to("processed", "establishments.parquet", file.load())


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

    def configure_steps(self) -> None:
        self.add_step(
            "Copy establishments to processed",
            step_copy_establishments,
            [EstablishmentsFile()],
        )


pipeline = ExamplePipeline()

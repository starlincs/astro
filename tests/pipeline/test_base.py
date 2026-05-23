"""Pipeline base class tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest

from astro import Pipeline
from astro.pipeline import AstroFileSpec, ExecutionMode, IngestFileSpec
from astro.pipeline.files import AstroFile
from astro.pipeline.steps import StepContext


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def step_record(_ctx: StepContext, files: list[AstroFile]) -> None:
    _ctx.logger.info("loaded %s rows", len(files[0].load()))


class RecordingPipeline(Pipeline):
    name = "recording"
    execution_mode = ExecutionMode.PARALLEL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="*.csv",
            schema=pa.DataFrameSchema({"value": pa.Column(str)}, strict="filter"),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step("Record", step_record, [EstablishmentsFile()])


def test_pipeline_run_is_not_implemented_yet() -> None:
    pipeline = RecordingPipeline()
    with pytest.raises(NotImplementedError, match="astro ingest"):
        pipeline.run(Path("/tmp/source"))


def test_pipeline_registers_run_steps() -> None:
    pipeline = RecordingPipeline()

    assert len(pipeline.steps) == 1
    assert pipeline.steps[0].step_id == "record"


class FilteringPipeline(RecordingPipeline):
    def configure_steps(self) -> None:
        self.add_filter(
            "Remove closed",
            lambda dataframe: dataframe.filter(pl.col("value") == "closed"),
            [EstablishmentsFile()],
        )


def test_pipeline_registers_filter_steps() -> None:
    pipeline = FilteringPipeline()

    assert len(pipeline.steps) == 1
    assert pipeline.steps[0].step_id == "remove-closed"

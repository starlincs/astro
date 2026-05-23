"""Pipeline step registration tests."""

from __future__ import annotations

import pandera.polars as pa
import pytest

from astro.pipeline.base import Pipeline
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.models import ExecutionMode, IngestFileSpec
from astro.pipeline.steps import StepContext


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def step_one(_ctx: StepContext, _files: list[AstroFile]) -> None:
    return None


def step_two(_ctx: StepContext, _files: list[AstroFile]) -> None:
    return None


class SteppedPipeline(Pipeline):
    name = "stepped"
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step("First step", step_one, [EstablishmentsFile()])
        self.add_step(
            "Second step",
            step_two,
            [EstablishmentsFile()],
            depends_on=["first-step"],
        )


class EmptyStepsPipeline(SteppedPipeline):
    def configure_steps(self) -> None:
        return None


class UnknownFilePipeline(SteppedPipeline):
    class MissingFile(AstroFileSpec):
        ingest_name = "missing"

    def configure_steps(self) -> None:
        self.add_step("Bad step", step_one, [self.MissingFile()])


def test_pipeline_registers_steps_with_slugified_ids() -> None:
    pipeline = SteppedPipeline()

    assert len(pipeline.steps) == 2
    assert pipeline.steps[0].step_id == "first-step"
    assert pipeline.steps[1].depends_on == ("first-step",)


def test_pipeline_requires_at_least_one_step() -> None:
    with pytest.raises(ValueError, match="at least one run step"):
        EmptyStepsPipeline()


def test_add_step_rejects_unknown_ingest_name() -> None:
    with pytest.raises(ValueError, match="ingest_files"):
        UnknownFilePipeline()


def test_add_step_rejects_unknown_dependency() -> None:
    class BadDependencyPipeline(SteppedPipeline):
        def configure_steps(self) -> None:
            self.add_step(
                "Only step",
                step_one,
                [EstablishmentsFile()],
                depends_on=["missing-step"],
            )

    with pytest.raises(ValueError, match="depends_on"):
        BadDependencyPipeline()


def test_add_step_rejects_duplicate_step_id() -> None:
    class DuplicatePipeline(SteppedPipeline):
        def configure_steps(self) -> None:
            self.add_step("First step", step_one, [EstablishmentsFile()])
            self.add_step("First step", step_two, [EstablishmentsFile()])

    with pytest.raises(ValueError, match="unique"):
        DuplicatePipeline()

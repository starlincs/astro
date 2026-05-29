"""Run behaviour when optional ingest files are absent."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest

from astro.ingest.service import IngestService
from astro.pipeline.base import Pipeline
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.models import ExecutionMode, IngestFileSpec, StepExecutionMode
from astro.pipeline.steps import StepContext
from astro.run.optional import (
    StepOptionalAction,
    absent_optional_ingest_names,
    classify_step_for_optional_ingests,
)
from astro.run.service import RunService
from astro.working.manifest import RunStatus, StepRunStatus
from astro.working.run_manager import RunManager


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


class ExtrasFile(AstroFileSpec):
    ingest_name = "extras"


def step_mark_establishments(ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load().with_columns(pl.lit("processed").alias("stage"))
    file.save_to("processed", "establishments.parquet", dataframe)
    ctx.stats.record_file("establishments", "rows_processed", dataframe.height)


def step_mark_extras(ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load().with_columns(pl.lit("extra").alias("stage"))
    file.save_to("processed", "extras.parquet", dataframe)
    ctx.stats.record_file("extras", "rows_processed", dataframe.height)


def step_merge_both(_ctx: StepContext, _files: list[AstroFile]) -> None:
    return None


def step_after_extras(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load()
    if "stage" not in dataframe.columns:
        raise ValueError("Expected processed column")


class OptionalIngestRunPipeline(Pipeline):
    name = "optional-ingest-run"
    execution_mode = ExecutionMode.PARALLEL
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
        IngestFileSpec(
            name="extras",
            source_pattern="extras*.csv",
            schema=pa.DataFrameSchema({"id": pa.Column(str)}, strict="filter"),
            optional=True,
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step("Mark establishments", step_mark_establishments, [EstablishmentsFile()])
        self.add_step("Mark extras", step_mark_extras, [ExtrasFile()])
        self.add_step(
            "Validate establishments",
            step_after_extras,
            [EstablishmentsFile()],
            depends_on=["mark-extras"],
        )


class OptionalIngestWithExtrasRunPipeline(OptionalIngestRunPipeline):
    name = "optional-ingest-with-extras-run"

    def configure_steps(self) -> None:
        self.add_step("Mark establishments", step_mark_establishments, [EstablishmentsFile()])
        self.add_step("Mark extras", step_mark_extras, [ExtrasFile()])


class ParallelOptionalIngestRunPipeline(OptionalIngestRunPipeline):
    step_execution_mode = StepExecutionMode.PARALLEL


class MixedOptionalIngestRunPipeline(OptionalIngestRunPipeline):
    name = "mixed-optional-ingest-run"

    def configure_steps(self) -> None:
        self.add_step("Merge both", step_merge_both, [EstablishmentsFile(), ExtrasFile()])


@pytest.fixture
def run_source_directory(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "edubase20260522.csv").write_text(
        "URN,EstablishmentName\n100001,Example School\n",
        encoding="utf-8",
    )
    return source_dir


@pytest.fixture
def run_source_directory_with_extras(run_source_directory: Path) -> Path:
    (run_source_directory / "extras20260522.csv").write_text("id\n1\n", encoding="utf-8")
    return run_source_directory


def _ingest(pipeline_dir: Path, pipeline: Pipeline, source_directory: Path):
    result = IngestService(pipeline_dir, pipeline).ingest(source_directory)
    manifest = RunManager(pipeline_dir).load_manifest(result.run_directory)
    return result, manifest


def test_absent_optional_ingest_names_excludes_ingested_optional_files(
    run_source_directory_with_extras: Path,
    tmp_path: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = OptionalIngestRunPipeline()
    _, manifest = _ingest(pipeline_dir, pipeline, run_source_directory_with_extras)

    assert absent_optional_ingest_names(pipeline, manifest) == set()


def test_classify_step_for_optional_ingests_skip_run_fail_matrix(
    run_source_directory: Path,
    tmp_path: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = OptionalIngestRunPipeline()
    _, manifest = _ingest(pipeline_dir, pipeline, run_source_directory)

    establishments_step = pipeline.steps[0]
    extras_step = pipeline.steps[1]

    skip_outcome = classify_step_for_optional_ingests(extras_step, pipeline, manifest)
    assert skip_outcome.action == StepOptionalAction.SKIP
    assert "extras" in skip_outcome.detail

    run_outcome = classify_step_for_optional_ingests(establishments_step, pipeline, manifest)
    assert run_outcome.action == StepOptionalAction.RUN

    mixed_pipeline = MixedOptionalIngestRunPipeline()
    merge_step = mixed_pipeline.steps[0]
    fail_outcome = classify_step_for_optional_ingests(merge_step, mixed_pipeline, manifest)
    assert fail_outcome.action == StepOptionalAction.FAIL
    assert fail_outcome.error is not None
    assert "extras" in str(fail_outcome.error)
    assert "establishments" in str(fail_outcome.error)


def test_run_skips_optional_only_step_when_extras_not_ingested(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = OptionalIngestRunPipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, run_source_directory)

    RunService().run(
        pipeline_dir,
        pipeline,
        ingest_result.run_directory,
        manifest,
    )

    completed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert completed.status == RunStatus.COMPLETED
    statuses = completed.step_status_map()
    assert statuses["mark-establishments"] == StepRunStatus.COMPLETE
    assert statuses["mark-extras"] == StepRunStatus.SKIPPED
    assert statuses["validate-establishments"] == StepRunStatus.COMPLETE
    assert (ingest_result.run_directory / "processed" / "establishments.parquet").is_file()
    assert not (ingest_result.run_directory / "processed" / "extras.parquet").exists()


def test_run_executes_optional_step_when_extras_ingested(
    tmp_path: Path,
    run_source_directory_with_extras: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = OptionalIngestWithExtrasRunPipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, run_source_directory_with_extras)

    RunService().run(
        pipeline_dir,
        pipeline,
        ingest_result.run_directory,
        manifest,
    )

    completed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert completed.status == RunStatus.COMPLETED
    assert completed.step_status_map()["mark-extras"] == StepRunStatus.COMPLETE
    assert (ingest_result.run_directory / "processed" / "extras.parquet").is_file()


def test_run_fails_on_mixed_optional_and_present_ingest_step(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = MixedOptionalIngestRunPipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, run_source_directory)

    with pytest.raises(ValueError, match="optional ingest\\(s\\) extras"):
        RunService().run(
            pipeline_dir,
            pipeline,
            ingest_result.run_directory,
            manifest,
        )

    failed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert failed.status == RunStatus.FAILED
    assert failed.step_status_map()["merge-both"] == StepRunStatus.FAILED


def test_run_allows_downstream_step_after_skipped_optional_dependency(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = OptionalIngestRunPipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, run_source_directory)

    RunService().run(
        pipeline_dir,
        pipeline,
        ingest_result.run_directory,
        manifest,
    )

    completed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert completed.step_status_map()["validate-establishments"] == StepRunStatus.COMPLETE


def test_parallel_run_skips_optional_only_step(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = ParallelOptionalIngestRunPipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, run_source_directory)

    RunService().run(
        pipeline_dir,
        pipeline,
        ingest_result.run_directory,
        manifest,
    )

    completed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert completed.status == RunStatus.COMPLETED
    assert completed.step_status_map()["mark-extras"] == StepRunStatus.SKIPPED

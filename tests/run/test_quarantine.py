"""Run service quarantine tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest

from astro.ingest.service import IngestService
from astro.pipeline.base import Pipeline
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.models import ExecutionMode, IngestFileSpec
from astro.pipeline.steps import StepContext
from astro.quarantine.store import QuarantineStore
from astro.run.service import RunService
from astro.working.manifest import RunStatus, StepRunStatus
from astro.working.run_manager import RunManager


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def step_quarantine_one_row(ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load()
    bad_rows = dataframe.filter(pl.col("URN") == "999")
    good_rows = dataframe.filter(pl.col("URN") != "999")
    if bad_rows.height:
        ctx.quarantine.quarantine_rows(file, bad_rows, reason="invalid urn")
    file.save_to("processed", "establishments.parquet", good_rows)


def step_validate_processed(_ctx: StepContext, files: list[AstroFile]) -> None:
    dataframe = files[0].load()
    if "stage" not in dataframe.columns:
        raise ValueError("Expected processed column")


def step_mark_processed(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load().with_columns(pl.lit("processed").alias("stage"))
    file.save_to("processed", "establishments.parquet", dataframe)


class QuarantinePipeline(Pipeline):
    name = "quarantine-test"
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
    ]

    def configure_steps(self) -> None:
        self.add_step("Quarantine bad rows", step_quarantine_one_row, [EstablishmentsFile()])


class DependentQuarantinePipeline(QuarantinePipeline):
    name = "dependent-quarantine"

    def configure_steps(self) -> None:
        self.add_step("Quarantine bad rows", step_quarantine_one_row, [EstablishmentsFile()])
        self.add_step(
            "Validate processed",
            step_validate_processed,
            [EstablishmentsFile()],
            depends_on=["quarantine-bad-rows"],
        )


class IndependentQuarantinePipeline(QuarantinePipeline):
    name = "independent-quarantine"

    def configure_steps(self) -> None:
        self.add_step("Quarantine bad rows", step_quarantine_one_row, [EstablishmentsFile()])
        self.add_step("Mark processed", step_mark_processed, [EstablishmentsFile()])


class RetryQuarantinePipeline(DependentQuarantinePipeline):
    name = "retry-quarantine"
    quarantine_on_first_pass = True

    def configure_steps(self) -> None:
        self.add_step("Quarantine bad rows", self._quarantine_step, [EstablishmentsFile()])
        self.add_step(
            "Validate processed",
            step_validate_processed,
            [EstablishmentsFile()],
            depends_on=["quarantine-bad-rows"],
        )

    def _quarantine_step(self, ctx: StepContext, files: list[AstroFile]) -> None:
        if self.quarantine_on_first_pass:
            step_quarantine_one_row(ctx, files)
            return
        step_mark_processed(ctx, files)


@pytest.fixture
def run_source_directory(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "edubase20260522.csv").write_text(
        "URN,EstablishmentName\n100001,Good School\n999,Bad School\n",
        encoding="utf-8",
    )
    return source_dir


def test_step_quarantine_marks_run_quarantined_and_continues_independent_step(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = IndependentQuarantinePipeline()
    ingest_result = IngestService(pipeline_dir, pipeline).ingest(run_source_directory)
    manifest = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)

    RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, manifest)

    updated = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert updated.status == RunStatus.QUARANTINED
    step_status = {record.step_id: record.status for record in updated.step_states}
    assert step_status["quarantine-bad-rows"] == StepRunStatus.QUARANTINED
    assert step_status["mark-processed"] == StepRunStatus.COMPLETE


def test_dependent_step_blocked_by_quarantined_dependency(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = DependentQuarantinePipeline()
    ingest_result = IngestService(pipeline_dir, pipeline).ingest(run_source_directory)
    manifest = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)

    RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, manifest)

    updated = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert updated.status == RunStatus.FAILED
    step_status = {record.step_id: record.status for record in updated.step_states}
    assert step_status["quarantine-bad-rows"] == StepRunStatus.QUARANTINED
    assert step_status["validate-processed"] == StepRunStatus.BLOCKED


def test_retry_merges_quarantine_and_reruns_only_quarantined_step(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = RetryQuarantinePipeline()
    ingest_result = IngestService(pipeline_dir, pipeline).ingest(run_source_directory)
    manifest = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)

    RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, manifest)
    first_pass = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert first_pass.status == RunStatus.FAILED

    pipeline.quarantine_on_first_pass = False
    RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, first_pass)

    updated = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert updated.status == RunStatus.COMPLETED
    step_status = {record.step_id: record.status for record in updated.step_states}
    assert step_status["quarantine-bad-rows"] == StepRunStatus.COMPLETE
    assert step_status["validate-processed"] == StepRunStatus.COMPLETE

    store = QuarantineStore(ingest_result.run_directory)
    assert not store.has_rows(store.quarantine_path("quarantine-bad-rows", "establishments"))

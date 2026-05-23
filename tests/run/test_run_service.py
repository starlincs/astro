"""Run service tests."""

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
from astro.run.service import RunService
from astro.stats.models import StatScope
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunStatus
from astro.working.run_manager import RunManager


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def step_mark_processed(ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load().with_columns(pl.lit("processed").alias("stage"))
    file.save_to("processed", "establishments.parquet", dataframe)
    ctx.stats.record_run("rows_processed", dataframe.height)


def step_validate_only(_ctx: StepContext, files: list[AstroFile]) -> None:
    dataframe = files[0].load()
    if "stage" not in dataframe.columns:
        raise ValueError("Expected processed column")


def step_fail(_ctx: StepContext, _files: list[AstroFile]) -> None:
    raise RuntimeError("step failed")


class RunTestPipeline(Pipeline):
    name = "run-test"
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
        self.add_step("Mark processed", step_mark_processed, [EstablishmentsFile()])
        self.add_step(
            "Validate processed",
            step_validate_only,
            [EstablishmentsFile()],
            depends_on=["mark-processed"],
        )


class FailingRunPipeline(RunTestPipeline):
    name = "failing-run"

    def configure_steps(self) -> None:
        self.add_step("Fail", step_fail, [EstablishmentsFile()])


@pytest.fixture
def run_source_directory(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "edubase20260522.csv").write_text(
        "URN,EstablishmentName\n100001,Example School\n",
        encoding="utf-8",
    )
    return source_dir


def test_run_service_executes_steps_and_marks_completed(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = RunTestPipeline()
    ingest_result = IngestService(pipeline_dir, pipeline).ingest(run_source_directory)
    manifest = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)

    result = RunService().run(
        pipeline_dir,
        pipeline,
        ingest_result.run_directory,
        manifest,
    )

    assert result.run_id == ingest_result.run_id
    completed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert completed.status == RunStatus.COMPLETED
    output_path = ingest_result.run_directory / "processed" / "establishments.parquet"
    assert output_path.is_file()
    assert pl.read_parquet(output_path)["stage"][0] == "processed"

    store = PipelineStore(pipeline_dir / ".astro" / "stats.db")
    runs = store.list_runs(pipeline.name)
    assert runs[0]["status"] == RunStatus.COMPLETED.value

    run_stats = store.list_stats(result.run_id, scope=StatScope.RUN)
    run_stat_actions = {stat.action: stat.value for stat in run_stats}
    assert run_stat_actions["steps_completed"] == 2
    assert run_stat_actions["rows_processed"] == 1
    assert "duration_ms" in run_stat_actions

    step_stats = store.list_stats(
        result.run_id,
        scope=StatScope.STEP,
        subject="mark-processed",
        action="duration_ms",
    )
    assert len(step_stats) == 1


def test_run_service_marks_failed_on_step_error(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = FailingRunPipeline()
    ingest_result = IngestService(pipeline_dir, pipeline).ingest(run_source_directory)
    manifest = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)

    with pytest.raises(RuntimeError, match="step failed"):
        RunService().run(
            pipeline_dir,
            pipeline,
            ingest_result.run_directory,
            manifest,
        )

    failed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert failed.status == RunStatus.FAILED

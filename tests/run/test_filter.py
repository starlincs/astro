"""Run service filter step tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest

from astro.filter.store import FilterStore
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


def remove_closed(_dataframe: pl.DataFrame) -> pl.DataFrame:
    return _dataframe.filter(pl.col("EstablishmentName").str.contains("Closed"))


def step_count_open(_ctx: StepContext, files: list[AstroFile]) -> None:
    assert files[0].load().height == 1


class FilterRunPipeline(Pipeline):
    name = "filter-run"
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
        self.add_filter("Remove closed schools", remove_closed, [EstablishmentsFile()])
        self.add_step(
            "Count open schools",
            step_count_open,
            [EstablishmentsFile()],
            depends_on=["remove-closed-schools"],
        )


@pytest.fixture
def filter_source_directory(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "edubase20260522.csv").write_text(
        "URN,EstablishmentName\n100001,Open School\n100002,Closed School\n",
        encoding="utf-8",
    )
    return source_dir


def test_run_service_applies_filter_and_records_stats(
    tmp_path: Path,
    filter_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = FilterRunPipeline()
    ingest_result = IngestService(pipeline_dir, pipeline).ingest(filter_source_directory)
    manifest = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)

    RunService().run(
        pipeline_dir,
        pipeline,
        ingest_result.run_directory,
        manifest,
    )

    completed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert completed.status == RunStatus.COMPLETED

    active_path = ingest_result.run_directory / "ingested" / "establishments.parquet"
    assert pl.read_parquet(active_path).height == 1

    filtered_store = FilterStore(ingest_result.run_directory)
    filtered_path = filtered_store.filtered_path("remove-closed-schools", "establishments")
    assert filtered_store.read_filtered(filtered_path).height == 1

    store = PipelineStore(pipeline_dir / ".astro" / "stats.db")
    step_stats = store.list_stats(
        ingest_result.run_id,
        scope=StatScope.STEP,
        subject="remove-closed-schools",
        action="rows_filtered",
    )
    assert step_stats[0].value == 1

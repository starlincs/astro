"""Ingest service tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest

from astro.ingest.service import IngestService
from astro.pipeline.base import Pipeline
from astro.pipeline.models import ExecutionMode, IngestFileSpec
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunStatus
from astro.working.run_manager import RunManager, SerialIngestConflictError


class SerialTestPipeline(Pipeline):
    name = "serial-test"
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
        return data

    def validate(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        return data


class ParallelTestPipeline(SerialTestPipeline):
    name = "parallel-test"
    execution_mode = ExecutionMode.PARALLEL


def test_ingest_service_creates_run_and_parquet(
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    from astro.pipeline.discovery import get_pipeline_instance

    pipeline = get_pipeline_instance(pipeline_directory)
    assert pipeline is not None

    result = IngestService(pipeline_directory, pipeline).ingest(source_directory)

    assert len(result.run_id) == 5
    assert (result.run_directory / "ingested" / "establishments.parquet").is_file()
    manifest = RunManager(pipeline_directory).load_manifest(result.run_directory)
    assert manifest.status == RunStatus.INGESTED
    assert manifest.ingested_files[0].row_count == 1


def test_ingest_service_records_sqlite_stats(
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    from astro.pipeline.discovery import get_pipeline_instance

    pipeline = get_pipeline_instance(pipeline_directory)
    assert pipeline is not None

    result = IngestService(pipeline_directory, pipeline).ingest(source_directory)
    store = PipelineStore(pipeline_directory / ".astro" / "stats.db")
    runs = store.list_runs(pipeline.name)

    assert runs[0]["run_id"] == result.run_id
    assert runs[0]["status"] == RunStatus.INGESTED.value


def test_serial_pipeline_blocks_second_ingest(
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    pipeline = SerialTestPipeline()
    service = IngestService(pipeline_directory, pipeline)
    service.ingest(source_directory)

    with pytest.raises(SerialIngestConflictError):
        service.ingest(source_directory)


def test_parallel_pipeline_allows_multiple_runs(
    pipeline_directory: Path,
    source_directory: Path,
) -> None:
    pipeline = ParallelTestPipeline()
    service = IngestService(pipeline_directory, pipeline)

    first = service.ingest(source_directory)
    second = service.ingest(source_directory)

    assert first.run_id != second.run_id

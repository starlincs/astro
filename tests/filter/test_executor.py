"""Filter executor tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from astro.filter.executor import FilterValidationError, apply_filter_step
from astro.filter.store import FilterStore
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.steps import StepContext
from astro.quarantine.collector import StepQuarantine
from astro.stats.models import StatScope
from astro.stats.recorder import StatisticsRecorder
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import IngestedFileRecord, RunStatus


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def _noop_progress(_value: float | None) -> None:
    return None


def _build_context(tmp_path: Path, store: PipelineStore) -> StepContext:
    return StepContext(
        pipeline_dir=tmp_path / "pipeline",
        run_directory=tmp_path / "run",
        run_id="abcde",
        run_date=datetime(2026, 5, 22, tzinfo=UTC).date(),
        step_id="remove-closed",
        logger=__import__("logging").getLogger("test"),
        report_progress=_noop_progress,
        quarantine=StepQuarantine(tmp_path / "run", "remove-closed"),
        stats=StatisticsRecorder("abcde", store, step_id="remove-closed"),
    )


def _build_file(tmp_path: Path) -> AstroFile:
    run_directory = tmp_path / "run"
    ingested_directory = run_directory / "ingested"
    ingested_directory.mkdir(parents=True)
    parquet_path = ingested_directory / "establishments.parquet"
    pl.DataFrame(
        {
            "URN": ["1", "2"],
            "EstablishmentName": ["Open School", "Closed School"],
        }
    ).write_parquet(parquet_path)
    return AstroFile.hydrate(
        spec=EstablishmentsFile(),
        ingest_record=IngestedFileRecord(
            name="establishments",
            source_path="/tmp/source.csv",
            parquet_path=str(parquet_path),
            row_count=2,
            column_count=2,
            source_size_bytes=10,
        ),
        run_directory=run_directory,
    )


def test_apply_filter_step_splits_rows_and_records_stats(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    store.record_run(
        run_id="abcde",
        pipeline_name="example",
        status=RunStatus.INGESTED.value,
        source_directory="/tmp/source",
        created_at=datetime(2026, 5, 22, tzinfo=UTC),
    )
    context = _build_context(tmp_path, store)
    file = _build_file(tmp_path)

    def remove_closed(dataframe: pl.DataFrame) -> pl.DataFrame:
        return dataframe.filter(pl.col("EstablishmentName").str.contains("Closed"))

    apply_filter_step(context, [file], remove_closed)

    kept = file.load()
    assert kept.height == 1
    assert kept["URN"][0] == "1"

    filtered_store = FilterStore(tmp_path / "run")
    filtered_path = filtered_store.filtered_path("remove-closed", "establishments")
    filtered = filtered_store.read_filtered(filtered_path)
    assert filtered.height == 1
    assert filtered["URN"][0] == "2"

    file_stats = store.list_stats(
        "abcde",
        scope=StatScope.FILE,
        subject="establishments",
    )
    stat_actions = {stat.action: stat.value for stat in file_stats}
    assert stat_actions["rows_filtered"] == 1
    assert stat_actions["rows_kept"] == 1


def test_apply_filter_step_rejects_rows_not_in_input(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    store.record_run(
        run_id="abcde",
        pipeline_name="example",
        status=RunStatus.INGESTED.value,
        source_directory="/tmp/source",
        created_at=datetime(2026, 5, 22, tzinfo=UTC),
    )
    context = _build_context(tmp_path, store)
    file = _build_file(tmp_path)

    def invalid_filter(_dataframe: pl.DataFrame) -> pl.DataFrame:
        return pl.DataFrame({"URN": ["999"], "EstablishmentName": ["Missing"]})

    with pytest.raises(FilterValidationError, match="not present"):
        apply_filter_step(context, [file], invalid_filter)

"""StatisticsRecorder tests."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from astro.stats.models import StatScope
from astro.stats.recorder import StatisticsRecorder
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunStatus


@pytest.fixture
def stats_store(tmp_path: Path) -> PipelineStore:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    store.record_run(
        run_id="abcde",
        pipeline_name="example",
        status=RunStatus.INGESTED.value,
        source_directory="/tmp/source",
        created_at=datetime(2026, 5, 22, tzinfo=UTC),
    )
    return store


def test_statistics_recorder_logs_and_persists_run_stat(
    stats_store: PipelineStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="astro.stats")
    recorder = StatisticsRecorder("abcde", stats_store)

    recorder.record_run("files_ingested", 2)

    assert "STAT run=abcde scope=run subject=- action=files_ingested value=2" in caplog.text
    stats = stats_store.list_stats("abcde", scope=StatScope.RUN, action="files_ingested")
    assert len(stats) == 1
    assert stats[0].value == 2
    assert stats[0].subject is None


def test_statistics_recorder_persists_file_and_step_stats(stats_store: PipelineStore) -> None:
    recorder = StatisticsRecorder("abcde", stats_store)

    recorder.record_file("establishments", "row_count", 10)
    recorder.record_step("duration_ms", 42, step_id="validate")

    file_stats = stats_store.list_stats(
        "abcde",
        scope=StatScope.FILE,
        subject="establishments",
    )
    assert {stat.action: stat.value for stat in file_stats} == {"row_count": 10}

    step_stats = stats_store.list_stats("abcde", scope=StatScope.STEP, subject="validate")
    assert step_stats[0].value == 42


def test_statistics_recorder_upserts_existing_stat(stats_store: PipelineStore) -> None:
    recorder = StatisticsRecorder("abcde", stats_store)

    recorder.record_run("files_ingested", 1)
    recorder.record_run("files_ingested", 3)

    stats = stats_store.list_stats("abcde", scope=StatScope.RUN, action="files_ingested")
    assert len(stats) == 1
    assert stats[0].value == 3


def test_statistics_recorder_rejects_empty_action(stats_store: PipelineStore) -> None:
    recorder = StatisticsRecorder("abcde", stats_store)

    with pytest.raises(ValueError, match="action"):
        recorder.record_run("", 1)


def test_statistics_recorder_requires_step_id_when_unbound(stats_store: PipelineStore) -> None:
    recorder = StatisticsRecorder("abcde", stats_store)

    with pytest.raises(ValueError, match="step_id"):
        recorder.record_step("duration_ms", 1)


def test_statistics_recorder_uses_bound_step_id(stats_store: PipelineStore) -> None:
    recorder = StatisticsRecorder("abcde", stats_store, step_id="copy-data")

    recorder.record_step("rows_written", 5)

    stats = stats_store.list_stats("abcde", scope=StatScope.STEP, subject="copy-data")
    assert stats[0].value == 5

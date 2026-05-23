"""PipelineStore statistics table tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from astro.stats.models import StatScope
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunStatus


def _seed_run(store: PipelineStore, run_id: str = "abcde") -> None:
    store.record_run(
        run_id=run_id,
        pipeline_name="example",
        status=RunStatus.INGESTED.value,
        source_directory="/tmp/source",
        created_at=datetime(2026, 5, 22, tzinfo=UTC),
    )


def test_record_stat_upserts_by_scope_subject_action(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    _seed_run(store)

    store.record_stat("abcde", StatScope.RUN, None, "files_ingested", 1)
    store.record_stat("abcde", StatScope.RUN, None, "files_ingested", 2)

    stats = store.list_stats("abcde", scope=StatScope.RUN, action="files_ingested")
    assert len(stats) == 1
    assert stats[0].value == 2


def test_list_stats_filters_by_scope_subject_and_action(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    _seed_run(store)

    store.record_stat("abcde", StatScope.FILE, "establishments", "row_count", 10)
    store.record_stat("abcde", StatScope.FILE, "establishments", "column_count", 2)
    store.record_stat("abcde", StatScope.STEP, "validate", "duration_ms", 50)

    assert len(store.list_stats("abcde", scope=StatScope.FILE)) == 2
    assert len(store.list_stats("abcde", subject="validate")) == 1
    assert store.list_stats("abcde", action="row_count")[0].value == 10


def test_cleanup_removes_statistics_rows(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    _seed_run(store)
    store.record_stat("abcde", StatScope.RUN, None, "files_ingested", 1)

    store.cleanup("example")

    assert store.list_stats("abcde") == []
    assert store.list_runs("example") == []

"""SQLite store migration and concurrency tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from astro.stats.models import StatScope
from astro.storage.sqlite import PipelineStore


def test_initialize_creates_schema_version(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    store.initialize()

    with store._connect() as connection:
        version = connection.execute("SELECT version FROM schema_version").fetchone()

    assert version == (1,)


def test_delete_run_removes_related_rows(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    created_at = datetime.now(UTC)
    store.record_run(
        run_id="abc12",
        pipeline_name="demo",
        status="completed",
        source_directory="/tmp/source",
        created_at=created_at,
    )
    store.record_stat("abc12", StatScope.RUN, None, "steps_completed", 2)

    store.delete_run("abc12")

    assert store.list_runs() == []
    assert store.list_stats("abc12") == []


def test_record_stat_uses_utc_timestamp(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    created_at = datetime.now(UTC)
    store.record_run(
        run_id="abc12",
        pipeline_name="demo",
        status="ingested",
        source_directory="/tmp/source",
        created_at=created_at,
    )
    store.record_stat("abc12", StatScope.RUN, None, "files_ingested", 1)

    stats = store.list_stats("abc12", action="files_ingested")
    assert stats[0].recorded_at.tzinfo is not None

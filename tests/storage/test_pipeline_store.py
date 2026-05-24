"""PipelineStore tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from astro.storage.sqlite import PipelineStore
from astro.working.manifest import IngestedFileRecord, OutputFileRecord, RunStatus


def test_pipeline_store_records_run_and_ingest_files(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    created_at = datetime(2026, 5, 22, tzinfo=UTC)
    ingested_at = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)

    store.record_run(
        run_id="abcde",
        pipeline_name="example",
        status=RunStatus.INGESTED.value,
        source_directory="/tmp/source",
        created_at=created_at,
        ingested_at=ingested_at,
    )
    store.record_ingest_files(
        "abcde",
        [
            IngestedFileRecord(
                name="establishments",
                source_path="/tmp/source/edubase.csv",
                parquet_path="/tmp/working/abcde/ingested/establishments.parquet",
                row_count=10,
                column_count=2,
                source_size_bytes=123,
            )
        ],
    )

    runs = store.list_runs("example")
    assert runs[0]["run_id"] == "abcde"
    assert runs[0]["status"] == RunStatus.INGESTED.value


def test_pipeline_store_records_output_files(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    created_at = datetime(2026, 5, 22, tzinfo=UTC)

    store.record_run(
        run_id="abcde",
        pipeline_name="example",
        status=RunStatus.COMPLETED.value,
        source_directory="/tmp/source",
        created_at=created_at,
    )
    store.record_output_files(
        "abcde",
        [
            OutputFileRecord(
                name="establishments",
                source_path="/tmp/working/abcde/ingested/establishments.parquet",
                parquet_path="/tmp/working/abcde/output/establishments.parquet",
                row_count=10,
                column_count=5,
                output_size_bytes=456,
            )
        ],
    )

    with store._connect() as connection:
        rows = connection.execute(
            "SELECT file_name, row_count, column_count, output_size_bytes FROM output_files"
        ).fetchall()

    assert rows == [("establishments", 10, 5, 456)]


def test_pipeline_store_cleanup_removes_runs(tmp_path: Path) -> None:
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    created_at = datetime(2026, 5, 22, tzinfo=UTC)
    store.record_run(
        run_id="abcde",
        pipeline_name="example",
        status=RunStatus.CREATED.value,
        source_directory="/tmp/source",
        created_at=created_at,
    )

    store.cleanup("example")
    assert store.list_runs("example") == []

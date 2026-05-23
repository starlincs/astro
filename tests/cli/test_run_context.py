"""Run resolution tests for astro run."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from astro.cli.run_context import RunResolutionError, resolve_run_directory
from astro.pipeline.models import ExecutionMode
from astro.working.manifest import IngestedFileRecord, RunManifest, RunStatus
from astro.working.run_manager import RunManager


@pytest.fixture
def pipeline_dir(tmp_path: Path) -> Path:
    return tmp_path / "pipeline"


def _save_ingested_manifest(
    run_manager: RunManager,
    run_directory: Path,
    *,
    ingested_at: datetime,
) -> RunManifest:
    manifest = run_manager.load_manifest(run_directory)
    manifest.status = RunStatus.INGESTED
    manifest.ingested_at = ingested_at
    manifest.ingested_files = [
        IngestedFileRecord(
            name="establishments",
            source_path="/tmp/edubase.csv",
            parquet_path=str(run_directory / "ingested" / "establishments.parquet"),
            row_count=1,
            column_count=2,
            source_size_bytes=10,
        )
    ]
    run_manager.save_manifest(run_directory, manifest)
    return manifest


def test_resolve_latest_ingested_run(pipeline_dir: Path) -> None:
    run_manager = RunManager(pipeline_dir)
    older_directory, _older_manifest = run_manager.create_run(
        pipeline_name="example",
        execution_mode=ExecutionMode.SERIAL,
        source_directory=pipeline_dir / "source",
    )
    newer_directory, _newer_manifest = run_manager.create_run(
        pipeline_name="example",
        execution_mode=ExecutionMode.SERIAL,
        source_directory=pipeline_dir / "source",
    )
    _save_ingested_manifest(
        run_manager,
        older_directory,
        ingested_at=datetime(2026, 5, 20, tzinfo=UTC),
    )
    _save_ingested_manifest(
        run_manager,
        newer_directory,
        ingested_at=datetime(2026, 5, 22, tzinfo=UTC),
    )

    run_directory, manifest = resolve_run_directory(pipeline_dir)

    assert run_directory == newer_directory
    assert manifest.run_id == newer_directory.name


def test_resolve_run_directory_with_run_id(pipeline_dir: Path) -> None:
    run_manager = RunManager(pipeline_dir)
    run_directory, _manifest = run_manager.create_run(
        pipeline_name="example",
        execution_mode=ExecutionMode.SERIAL,
        source_directory=pipeline_dir / "source",
    )
    _save_ingested_manifest(
        run_manager,
        run_directory,
        ingested_at=datetime(2026, 5, 22, tzinfo=UTC),
    )

    resolved_directory, manifest = resolve_run_directory(
        pipeline_dir,
        run_id=run_directory.name,
    )

    assert resolved_directory == run_directory
    assert manifest.status == RunStatus.INGESTED


def test_resolve_run_directory_rejects_missing_run_id(pipeline_dir: Path) -> None:
    with pytest.raises(RunResolutionError, match="not found"):
        resolve_run_directory(pipeline_dir, run_id="nope")


def test_resolve_run_directory_rejects_non_ingested_run(pipeline_dir: Path) -> None:
    run_manager = RunManager(pipeline_dir)
    run_directory, _manifest = run_manager.create_run(
        pipeline_name="example",
        execution_mode=ExecutionMode.SERIAL,
        source_directory=pipeline_dir / "source",
    )

    with pytest.raises(RunResolutionError, match="not ready"):
        resolve_run_directory(pipeline_dir, run_id=run_directory.name)


def test_resolve_run_directory_errors_when_no_ingested_runs(pipeline_dir: Path) -> None:
    with pytest.raises(RunResolutionError, match="No ingested runs"):
        resolve_run_directory(pipeline_dir)

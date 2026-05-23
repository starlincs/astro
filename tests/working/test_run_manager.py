"""Run manager tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from astro.pipeline.models import ExecutionMode
from astro.working.manifest import RunStatus
from astro.working.run_manager import RunManager, SerialIngestConflictError


@pytest.fixture
def pipeline_dir(tmp_path: Path) -> Path:
    return tmp_path / "pipeline"


def test_create_run_allocates_five_character_run_id(pipeline_dir: Path) -> None:
    run_manager = RunManager(pipeline_dir)
    run_directory, manifest = run_manager.create_run(
        pipeline_name="example",
        execution_mode=ExecutionMode.SERIAL,
        source_directory=pipeline_dir / "source",
    )

    assert len(manifest.run_id) == 5
    assert run_directory.name == manifest.run_id
    assert (run_directory / "ingested").is_dir()
    assert manifest.status == RunStatus.CREATED


def test_manifest_roundtrip(pipeline_dir: Path) -> None:
    run_manager = RunManager(pipeline_dir)
    run_directory, manifest = run_manager.create_run(
        pipeline_name="example",
        execution_mode=ExecutionMode.PARALLEL,
        source_directory=pipeline_dir / "source",
    )

    loaded = run_manager.load_manifest(run_directory)
    assert loaded.model_dump() == manifest.model_dump()


def test_find_incomplete_runs_excludes_completed(pipeline_dir: Path) -> None:
    run_manager = RunManager(pipeline_dir)
    run_directory, _manifest = run_manager.create_run(
        pipeline_name="example",
        execution_mode=ExecutionMode.SERIAL,
        source_directory=pipeline_dir / "source",
    )
    completed_manifest = run_manager.load_manifest(run_directory)
    completed_manifest.status = RunStatus.COMPLETED
    run_manager.save_manifest(run_directory, completed_manifest)

    assert run_manager.find_incomplete_runs() == []


def test_serial_gate_blocks_when_incomplete_run_exists(pipeline_dir: Path) -> None:
    run_manager = RunManager(pipeline_dir)
    run_directory, _manifest = run_manager.create_run(
        pipeline_name="example",
        execution_mode=ExecutionMode.SERIAL,
        source_directory=pipeline_dir / "source",
    )

    with pytest.raises(SerialIngestConflictError) as error:
        run_manager.assert_serial_ingest_allowed(ExecutionMode.SERIAL)

    assert run_directory.name in error.value.blocking_run_ids


def test_manifest_without_file_counts_as_incomplete(pipeline_dir: Path) -> None:
    working_root = pipeline_dir / ".working"
    run_directory = working_root / "ghost"
    run_directory.mkdir(parents=True)

    incomplete = RunManager(pipeline_dir).find_incomplete_runs()
    assert len(incomplete) == 1
    assert incomplete[0].run_id == "ghost"

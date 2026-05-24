"""Working directory cleanup tests."""

from __future__ import annotations

from pathlib import Path

from astro.pipeline.models import ExecutionMode
from astro.storage.sqlite import PipelineStore
from astro.working.cleanup import execute_cleanup, plan_cleanup
from astro.working.manifest import RunStatus
from astro.working.run_manager import RunManager


def test_plan_cleanup_selects_completed_runs(tmp_path: Path) -> None:
    run_manager = RunManager(tmp_path)
    run_directory, manifest = run_manager.create_run(
        pipeline_name="demo",
        execution_mode=ExecutionMode.SERIAL,
        source_directory=tmp_path / "source",
    )
    manifest.status = RunStatus.COMPLETED
    run_manager.save_manifest(run_directory, manifest)

    plan = plan_cleanup(tmp_path, remove_all_data=False)

    assert len(plan.targets) == 1
    assert plan.removed_run_ids == (manifest.run_id,)


def test_execute_cleanup_deletes_run_and_store_rows(tmp_path: Path) -> None:
    run_manager = RunManager(tmp_path)
    run_directory, manifest = run_manager.create_run(
        pipeline_name="demo",
        execution_mode=ExecutionMode.SERIAL,
        source_directory=tmp_path / "source",
    )
    manifest.status = RunStatus.COMPLETED
    run_manager.save_manifest(run_directory, manifest)
    store = PipelineStore(tmp_path / ".astro" / "stats.db")
    store.record_run(
        run_id=manifest.run_id,
        pipeline_name="demo",
        status=RunStatus.COMPLETED.value,
        source_directory=str(tmp_path / "source"),
        created_at=manifest.created_at,
    )

    plan = plan_cleanup(tmp_path, remove_all_data=False)
    actions = execute_cleanup(tmp_path, plan, dry_run=False, remove_all_data=False)

    assert actions
    assert not run_directory.exists()
    assert store.list_runs() == []


def test_plan_cleanup_with_all_includes_stats_db(tmp_path: Path) -> None:
    stats_db = tmp_path / ".astro" / "stats.db"
    stats_db.parent.mkdir(parents=True)
    stats_db.write_text("", encoding="utf-8")

    plan = plan_cleanup(tmp_path, remove_all_data=True)

    assert any(target.path == stats_db for target in plan.targets)

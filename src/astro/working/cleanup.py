"""Cleanup helpers for pipeline working directories and stored data."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from astro.resolver.store import PERSISTENT_DIRNAME
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunStatus
from astro.working.run_manager import MANIFEST_FILENAME, RunManager

ASTRO_DIRNAME = ".astro"
STATS_DB_FILENAME = "stats.db"


@dataclass(frozen=True)
class CleanupTarget:
    """One filesystem path scheduled for removal."""

    path: Path
    description: str


@dataclass(frozen=True)
class CleanupPlan:
    """Paths selected for cleanup."""

    targets: tuple[CleanupTarget, ...]
    removed_run_ids: tuple[str, ...]


def plan_cleanup(pipeline_dir: Path, *, remove_all_data: bool) -> CleanupPlan:
    """Build a cleanup plan for removable runs and optional stored data."""
    pipeline_dir = pipeline_dir.resolve()
    run_manager = RunManager(pipeline_dir)
    targets: list[CleanupTarget] = []
    removed_run_ids: list[str] = []

    working_root = run_manager.working_root
    if working_root.is_dir():
        for run_directory in sorted(working_root.iterdir()):
            if not run_directory.is_dir():
                continue
            manifest_path = run_directory / MANIFEST_FILENAME
            if not manifest_path.is_file():
                if remove_all_data:
                    targets.append(
                        CleanupTarget(
                            path=run_directory,
                            description=f"run directory {run_directory.name} (no manifest)",
                        )
                    )
                    removed_run_ids.append(run_directory.name)
                continue

            manifest = run_manager.load_manifest(run_directory)
            if remove_all_data or manifest.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                targets.append(
                    CleanupTarget(
                        path=run_directory,
                        description=(f"run {manifest.run_id} (status={manifest.status.value})"),
                    )
                )
                removed_run_ids.append(manifest.run_id)

    if remove_all_data:
        stats_db = pipeline_dir / ASTRO_DIRNAME / STATS_DB_FILENAME
        if stats_db.is_file():
            targets.append(CleanupTarget(path=stats_db, description="statistics database"))
        persistent_dir = pipeline_dir / PERSISTENT_DIRNAME
        if persistent_dir.is_dir():
            targets.append(
                CleanupTarget(path=persistent_dir, description="persistent resolver stores")
            )

    return CleanupPlan(targets=tuple(targets), removed_run_ids=tuple(removed_run_ids))


def execute_cleanup(
    pipeline_dir: Path,
    plan: CleanupPlan,
    *,
    dry_run: bool,
    remove_all_data: bool,
) -> list[str]:
    """Remove planned paths and return human-readable action lines."""
    actions: list[str] = []
    for target in plan.targets:
        if dry_run:
            actions.append(f"would remove {target.description}: {target.path}")
            continue
        if target.path.is_dir():
            shutil.rmtree(target.path)
        else:
            target.path.unlink(missing_ok=True)
        actions.append(f"removed {target.description}: {target.path}")

    if dry_run:
        return actions

    stats_db = pipeline_dir / ASTRO_DIRNAME / STATS_DB_FILENAME
    if stats_db.is_file():
        store = PipelineStore(stats_db)
        if remove_all_data:
            store.cleanup()
        else:
            for run_id in plan.removed_run_ids:
                store.delete_run(run_id)

    return actions

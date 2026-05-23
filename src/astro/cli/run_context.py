"""Resolve pipeline runs for astro run."""

from __future__ import annotations

from pathlib import Path

from astro.working.manifest import RunManifest, RunStatus, StepRunStatus
from astro.working.run_manager import MANIFEST_FILENAME, RunManager

_RUNNABLE_STATUSES = {RunStatus.INGESTED, RunStatus.QUARANTINED, RunStatus.FAILED}


class RunResolutionError(RuntimeError):
    """Raised when astro run cannot resolve a target run."""


def resolve_run_directory(
    pipeline_dir: Path,
    *,
    run_id: str | None = None,
) -> tuple[Path, RunManifest]:
    run_manager = RunManager(pipeline_dir)
    working_root = run_manager.working_root

    if run_id is not None:
        run_directory = working_root / run_id
        manifest_path = run_directory / MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise RunResolutionError(f"Run not found: {run_id}")
        manifest = run_manager.load_manifest(run_directory)
        if not _is_runnable_manifest(manifest):
            raise RunResolutionError(
                f"Run {run_id} is not ready for processing (status={manifest.status.value})."
            )
        return run_directory, manifest

    if not working_root.is_dir():
        raise RunResolutionError("No runnable pipeline runs found under .working/.")

    runnable_runs: list[tuple[Path, RunManifest]] = []
    for run_directory in working_root.iterdir():
        if not run_directory.is_dir():
            continue
        manifest_path = run_directory / MANIFEST_FILENAME
        if not manifest_path.is_file():
            continue
        manifest = run_manager.load_manifest(run_directory)
        if _is_runnable_manifest(manifest):
            runnable_runs.append((run_directory, manifest))

    if not runnable_runs:
        raise RunResolutionError("No runnable pipeline runs found under .working/.")

    quarantined_runs = [item for item in runnable_runs if item[1].status == RunStatus.QUARANTINED]
    if quarantined_runs:
        quarantined_runs.sort(
            key=lambda item: item[1].ingested_at or item[1].created_at,
            reverse=True,
        )
        run_directory, manifest = quarantined_runs[0]
        return run_directory, manifest

    retry_failed_runs = [
        item
        for item in runnable_runs
        if item[1].status == RunStatus.FAILED
        and any(record.status == StepRunStatus.QUARANTINED for record in item[1].step_states)
    ]
    if retry_failed_runs:
        retry_failed_runs.sort(
            key=lambda item: item[1].ingested_at or item[1].created_at,
            reverse=True,
        )
        run_directory, manifest = retry_failed_runs[0]
        return run_directory, manifest

    ingested_runs = [item for item in runnable_runs if item[1].status == RunStatus.INGESTED]
    ingested_runs.sort(
        key=lambda item: item[1].ingested_at or item[1].created_at,
        reverse=True,
    )
    run_directory, manifest = ingested_runs[0]
    return run_directory, manifest


def _is_runnable_manifest(manifest: RunManifest) -> bool:
    if manifest.status == RunStatus.INGESTED and manifest.ingested_at is not None:
        return True
    if manifest.status == RunStatus.QUARANTINED:
        return True
    if manifest.status == RunStatus.FAILED:
        return any(record.status == StepRunStatus.QUARANTINED for record in manifest.step_states)
    return False

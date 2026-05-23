"""Resolve pipeline runs for astro run."""

from __future__ import annotations

from pathlib import Path

from astro.working.manifest import RunManifest, RunStatus
from astro.working.run_manager import MANIFEST_FILENAME, RunManager


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
        if manifest.status != RunStatus.INGESTED:
            raise RunResolutionError(
                f"Run {run_id} is not ready for processing (status={manifest.status.value})."
            )
        return run_directory, manifest

    if not working_root.is_dir():
        raise RunResolutionError("No ingested runs found under .working/.")

    ingested_runs: list[tuple[Path, RunManifest]] = []
    for run_directory in working_root.iterdir():
        if not run_directory.is_dir():
            continue
        manifest_path = run_directory / MANIFEST_FILENAME
        if not manifest_path.is_file():
            continue
        manifest = run_manager.load_manifest(run_directory)
        if manifest.status != RunStatus.INGESTED or manifest.ingested_at is None:
            continue
        ingested_runs.append((run_directory, manifest))

    if not ingested_runs:
        raise RunResolutionError("No ingested runs found under .working/.")

    ingested_runs.sort(key=lambda item: item[1].ingested_at or item[1].created_at, reverse=True)
    run_directory, manifest = ingested_runs[0]
    return run_directory, manifest

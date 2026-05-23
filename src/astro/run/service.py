"""Run orchestration service."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from astro.cli.display.steps import StepTracker, build_run_tracker
from astro.pipeline.base import Pipeline
from astro.pipeline.files import AstroFile
from astro.pipeline.steps import StepContext
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunManifest, RunStatus
from astro.working.run_manager import RunManager

logger = logging.getLogger("astro.run")


@dataclass(frozen=True)
class RunResult:
    run_id: str
    run_directory: Path
    steps_completed: int


class RunService:
    """Execute registered pipeline steps for an ingested run."""

    def run(
        self,
        pipeline_dir: Path,
        pipeline: Pipeline,
        run_directory: Path,
        manifest: RunManifest,
        *,
        tracker: StepTracker | None = None,
        progress_callback: Callable[[], None] | None = None,
    ) -> RunResult:
        if manifest.status != RunStatus.INGESTED:
            raise ValueError(
                "Run "
                f"{manifest.run_id} is not ready for processing "
                f"(status={manifest.status.value})."
            )

        run_manager = RunManager(pipeline_dir)
        store = PipelineStore(pipeline_dir / ".astro" / "stats.db")
        active_tracker = tracker or build_run_tracker(pipeline, manifest)
        completed_step_ids: set[str] = {"ingest"}
        file_pool = self._hydrate_files(pipeline, manifest, run_directory)
        step_logger = logging.getLogger("astro.run.steps")

        def report_progress(progress_percent: float | None) -> None:
            active_tracker.set_progress_percent(progress_percent)
            if progress_callback is not None:
                progress_callback()

        current_step = pipeline.steps[0]
        try:
            for step in pipeline.steps:
                current_step = step
                self._assert_dependencies_completed(
                    step.step_id,
                    step.depends_on,
                    completed_step_ids,
                )
                active_tracker.mark_running(step.step_id)
                active_tracker.set_status_message(step.label)
                active_tracker.set_progress_percent(None)
                if progress_callback is not None:
                    progress_callback()

                step_files = [
                    self._resolve_step_file(file_spec, file_pool, manifest, run_directory)
                    for file_spec in step.file_specs
                ]
                context = StepContext(
                    pipeline_dir=pipeline_dir,
                    run_directory=run_directory,
                    run_id=manifest.run_id,
                    run_date=date.today(),
                    logger=step_logger,
                    report_progress=report_progress,
                )
                logger.info("Running step %s", step.label)
                step.fn(context, step_files)
                active_tracker.mark_complete(step.step_id)
                completed_step_ids.add(step.step_id)
                if progress_callback is not None:
                    progress_callback()
        except Exception as error:
            logger.error("Run failed during step %s: %s", current_step.label, error)
            active_tracker.mark_failed(current_step.step_id, detail=str(error))
            active_tracker.set_status_message(f"Failed: {error}")
            manifest.status = RunStatus.FAILED
            run_manager.save_manifest(run_directory, manifest)
            store.record_run(
                run_id=manifest.run_id,
                pipeline_name=manifest.pipeline_name,
                status=manifest.status.value,
                source_directory=manifest.source_directory,
                created_at=manifest.created_at,
                ingested_at=manifest.ingested_at,
            )
            raise

        manifest.status = RunStatus.COMPLETED
        run_manager.save_manifest(run_directory, manifest)
        store.record_run(
            run_id=manifest.run_id,
            pipeline_name=manifest.pipeline_name,
            status=manifest.status.value,
            source_directory=manifest.source_directory,
            created_at=manifest.created_at,
            ingested_at=manifest.ingested_at,
        )
        active_tracker.set_status_message("Run completed")
        active_tracker.set_progress_percent(None)
        logger.info("Run %s completed", manifest.run_id)
        return RunResult(
            run_id=manifest.run_id,
            run_directory=run_directory,
            steps_completed=len(pipeline.steps),
        )

    def _hydrate_files(
        self,
        pipeline: Pipeline,
        manifest: RunManifest,
        run_directory: Path,
    ) -> dict[str, AstroFile]:
        records_by_name = {record.name: record for record in manifest.ingested_files}
        file_pool: dict[str, AstroFile] = {}

        for step in pipeline.steps:
            for file_spec in step.file_specs:
                ingest_name = file_spec.__class__.ingest_name
                if ingest_name in file_pool:
                    continue
                record = records_by_name.get(ingest_name)
                if record is None:
                    raise ValueError(f"Ingested file {ingest_name!r} is missing from run manifest.")
                file_pool[ingest_name] = AstroFile.hydrate(
                    spec=file_spec,
                    ingest_record=record,
                    run_directory=run_directory,
                )
        return file_pool

    def _resolve_step_file(
        self,
        file_spec,
        file_pool: dict[str, AstroFile],
        manifest: RunManifest,
        run_directory: Path,
    ) -> AstroFile:
        ingest_name = file_spec.__class__.ingest_name
        existing = file_pool.get(ingest_name)
        if existing is not None:
            return existing

        records_by_name = {record.name: record for record in manifest.ingested_files}
        record = records_by_name[ingest_name]
        hydrated = AstroFile.hydrate(
            spec=file_spec,
            ingest_record=record,
            run_directory=run_directory,
        )
        file_pool[ingest_name] = hydrated
        return hydrated

    def _assert_dependencies_completed(
        self,
        step_id: str,
        depends_on: tuple[str, ...],
        completed_step_ids: set[str],
    ) -> None:
        missing = [dependency for dependency in depends_on if dependency not in completed_step_ids]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Step {step_id} blocked by incomplete dependencies: {joined}")

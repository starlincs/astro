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
from astro.pipeline.steps import StepContext, StepDefinition
from astro.quarantine.collector import StepQuarantine
from astro.quarantine.store import QuarantineStore
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunManifest, RunStatus, StepRunStatus
from astro.working.run_manager import RunManager

logger = logging.getLogger("astro.run")


@dataclass(frozen=True)
class RunResult:
    run_id: str
    run_directory: Path
    steps_completed: int


class DependencyQuarantinedError(RuntimeError):
    """Raised when a step depends on a quarantined predecessor."""


class RunService:
    """Execute registered pipeline steps for an ingested or quarantined run."""

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
        if not self._can_process_run(manifest):
            raise ValueError(
                "Run "
                f"{manifest.run_id} is not ready for processing "
                f"(status={manifest.status.value})."
            )

        run_manager = RunManager(pipeline_dir)
        store = PipelineStore(pipeline_dir / ".astro" / "stats.db")
        active_tracker = tracker or build_run_tracker(pipeline, manifest)
        file_pool = self._hydrate_files(pipeline, manifest, run_directory)
        quarantine_store = QuarantineStore(run_directory)
        step_logger = logging.getLogger("astro.run.steps")
        is_retry = manifest.status in {RunStatus.QUARANTINED, RunStatus.FAILED}
        steps_completed = sum(
            1 for record in manifest.step_states if record.status == StepRunStatus.COMPLETE
        )
        stop_reason: str | None = None

        def report_progress(progress_percent: float | None) -> None:
            active_tracker.set_progress_percent(progress_percent)
            if progress_callback is not None:
                progress_callback()

        self._initialize_step_states(pipeline, manifest)

        for step in pipeline.steps:
            current_status = manifest.step_status_map().get(step.step_id, StepRunStatus.PENDING)
            if current_status == StepRunStatus.COMPLETE:
                continue
            if is_retry and current_status not in {
                StepRunStatus.QUARANTINED,
                StepRunStatus.PENDING,
                StepRunStatus.BLOCKED,
            }:
                continue

            try:
                self._check_dependencies(step, manifest)
            except DependencyQuarantinedError as error:
                manifest.upsert_step_state(step.step_id, StepRunStatus.BLOCKED, detail=str(error))
                active_tracker.mark_failed(step.step_id, detail=str(error))
                stop_reason = str(error)
                break

            step_files = [
                self._resolve_step_file(file_spec, file_pool, manifest, run_directory)
                for file_spec in step.file_specs
            ]
            if current_status == StepRunStatus.QUARANTINED:
                self._prepare_step_retry(step, step_files, quarantine_store)

            self._capture_snapshots(step, step_files, quarantine_store)
            active_tracker.mark_running(step.step_id)
            active_tracker.set_status_message(step.label)
            active_tracker.set_progress_percent(None)
            if progress_callback is not None:
                progress_callback()

            quarantine = StepQuarantine(run_directory, step.step_id)
            context = StepContext(
                pipeline_dir=pipeline_dir,
                run_directory=run_directory,
                run_id=manifest.run_id,
                run_date=date.today(),
                step_id=step.step_id,
                logger=step_logger,
                report_progress=report_progress,
                quarantine=quarantine,
            )

            try:
                logger.info("Running step %s", step.label)
                step.fn(context, step_files)
            except Exception as error:
                logger.error("Run failed during step %s: %s", step.label, error)
                manifest.upsert_step_state(step.step_id, StepRunStatus.FAILED, detail=str(error))
                active_tracker.mark_failed(step.step_id, detail=str(error))
                active_tracker.set_status_message(f"Failed: {error}")
                self._persist_manifest(
                    run_manager,
                    store,
                    run_directory,
                    manifest,
                    RunStatus.FAILED,
                )
                raise

            if quarantine.has_quarantined_rows:
                manifest.upsert_step_state(
                    step.step_id,
                    StepRunStatus.QUARANTINED,
                    detail="Rows quarantined",
                )
                active_tracker.mark_quarantined(step.step_id, detail="Rows quarantined")
            else:
                manifest.upsert_step_state(step.step_id, StepRunStatus.COMPLETE)
                active_tracker.mark_complete(step.step_id)
                steps_completed += 1

            self._persist_manifest(
                run_manager,
                store,
                run_directory,
                manifest,
                self._derive_run_status(manifest),
            )
            if progress_callback is not None:
                progress_callback()

        final_status = RunStatus.FAILED if stop_reason else self._derive_run_status(manifest)
        self._persist_manifest(run_manager, store, run_directory, manifest, final_status)

        if final_status == RunStatus.QUARANTINED:
            active_tracker.set_status_message("Run quarantined")
        elif final_status == RunStatus.FAILED:
            active_tracker.set_status_message(stop_reason or "Run failed")
        else:
            active_tracker.set_status_message("Run completed")
        active_tracker.set_progress_percent(None)
        logger.info("Run %s finished with status %s", manifest.run_id, final_status.value)
        return RunResult(
            run_id=manifest.run_id,
            run_directory=run_directory,
            steps_completed=steps_completed,
        )

    def _can_process_run(self, manifest: RunManifest) -> bool:
        if manifest.status == RunStatus.INGESTED:
            return True
        if manifest.status == RunStatus.QUARANTINED:
            return True
        if manifest.status == RunStatus.FAILED:
            return any(
                record.status == StepRunStatus.QUARANTINED for record in manifest.step_states
            )
        return False

    def _initialize_step_states(self, pipeline: Pipeline, manifest: RunManifest) -> None:
        if manifest.step_states:
            return
        for step in pipeline.steps:
            manifest.upsert_step_state(step.step_id, StepRunStatus.PENDING)

    def _check_dependencies(self, step: StepDefinition, manifest: RunManifest) -> None:
        statuses = manifest.step_status_map()
        for dependency_id in step.depends_on:
            dependency_status = statuses.get(dependency_id, StepRunStatus.PENDING)
            if dependency_status == StepRunStatus.QUARANTINED:
                raise DependencyQuarantinedError(
                    f"Step {step.step_id} blocked by quarantined dependency: {dependency_id}"
                )
            if dependency_status != StepRunStatus.COMPLETE:
                joined = ", ".join(step.depends_on)
                raise RuntimeError(
                    f"Step {step.step_id} blocked by incomplete dependencies: {joined}"
                )

    def _capture_snapshots(
        self,
        step: StepDefinition,
        step_files: list[AstroFile],
        quarantine_store: QuarantineStore,
    ) -> None:
        for file in step_files:
            ingest_name = file.spec.__class__.ingest_name
            snapshot_path = quarantine_store.snapshot_path(step.step_id, ingest_name)
            quarantine_store.capture_snapshot(snapshot_path, file.active_path)

    def _prepare_step_retry(
        self,
        step: StepDefinition,
        step_files: list[AstroFile],
        quarantine_store: QuarantineStore,
    ) -> None:
        for file in step_files:
            ingest_name = file.spec.__class__.ingest_name
            snapshot_path = quarantine_store.snapshot_path(step.step_id, ingest_name)
            quarantine_path = quarantine_store.quarantine_path(step.step_id, ingest_name)
            quarantine_store.merge_snapshot_with_quarantine(
                snapshot_path=snapshot_path,
                quarantine_path=quarantine_path,
                output_path=file.active_path,
            )
            quarantine_store.truncate(quarantine_path)

    def _derive_run_status(self, manifest: RunManifest) -> RunStatus:
        statuses = list(manifest.step_status_map().values())
        if any(status == StepRunStatus.QUARANTINED for status in statuses):
            return RunStatus.QUARANTINED
        if statuses and all(status == StepRunStatus.COMPLETE for status in statuses):
            return RunStatus.COMPLETED
        if manifest.status == RunStatus.INGESTED:
            return RunStatus.INGESTED
        return manifest.status

    def _persist_manifest(
        self,
        run_manager: RunManager,
        store: PipelineStore,
        run_directory: Path,
        manifest: RunManifest,
        status: RunStatus,
    ) -> None:
        manifest.status = status
        run_manager.save_manifest(run_directory, manifest)
        store.record_run(
            run_id=manifest.run_id,
            pipeline_name=manifest.pipeline_name,
            status=manifest.status.value,
            source_directory=manifest.source_directory,
            created_at=manifest.created_at,
            ingested_at=manifest.ingested_at,
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

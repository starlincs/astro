"""Run orchestration service."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from astro.cli.display.steps import StepTracker, build_run_tracker
from astro.pipeline.base import Pipeline
from astro.pipeline.files import AstroFile
from astro.pipeline.models import StepExecutionMode
from astro.pipeline.steps import StepContext, StepDefinition
from astro.quarantine.collector import StepQuarantine
from astro.quarantine.store import QuarantineStore
from astro.run.context import RunExecutionContext, RunProgress, StepExecutionOutcome
from astro.stats.recorder import StatisticsRecorder
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunManifest, RunStatus, StepRunStatus
from astro.working.run_manager import RunManager

logger = logging.getLogger("astro.run")


@dataclass(frozen=True)
class RunResult:
    """Outcome of a completed ``astro run`` invocation."""

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
        stats_recorder = StatisticsRecorder(manifest.run_id, store)
        active_tracker = tracker or build_run_tracker(pipeline, manifest)
        file_pool = self._hydrate_files(pipeline, manifest, run_directory)
        quarantine_store = QuarantineStore(run_directory)
        step_logger = logging.getLogger("astro.run.steps")
        is_retry = manifest.status in {RunStatus.QUARANTINED, RunStatus.FAILED}
        progress = RunProgress(
            steps_completed=sum(
                1 for record in manifest.step_states if record.status == StepRunStatus.COMPLETE
            )
        )
        run_started_at = time.monotonic()

        def report_progress(progress_percent: float | None) -> None:
            active_tracker.set_progress_percent(progress_percent)
            if progress_callback is not None:
                progress_callback()

        self._initialize_step_states(pipeline, manifest)

        file_locks = {ingest_name: threading.Lock() for ingest_name in file_pool}
        ctx = RunExecutionContext(
            pipeline_dir=pipeline_dir,
            pipeline=pipeline,
            run_directory=run_directory,
            manifest=manifest,
            run_manager=run_manager,
            store=store,
            stats_recorder=stats_recorder,
            active_tracker=active_tracker,
            file_pool=file_pool,
            quarantine_store=quarantine_store,
            step_logger=step_logger,
            is_retry=is_retry,
            report_progress=report_progress,
            progress_callback=progress_callback,
            run_started_at=run_started_at,
            file_locks=file_locks,
        )

        if pipeline.step_execution_mode == StepExecutionMode.PARALLEL:
            from astro.run.scheduler import ParallelStepScheduler

            ParallelStepScheduler(self, ctx, progress).run()
        else:
            self._run_serial(ctx, progress)

        if progress.hard_error is not None or progress.stop_reason:
            final_status = RunStatus.FAILED
        else:
            final_status = self._derive_run_status(manifest)
        self._persist_manifest(run_manager, store, run_directory, manifest, final_status)
        self._record_run_statistics(
            stats_recorder,
            manifest,
            steps_completed=progress.steps_completed,
            run_started_at=run_started_at,
        )

        if final_status == RunStatus.QUARANTINED:
            active_tracker.set_status_message("Run quarantined")
        elif final_status == RunStatus.FAILED:
            active_tracker.set_status_message(progress.stop_reason or "Run failed")
        else:
            active_tracker.set_status_message("Run completed")
        active_tracker.set_progress_percent(None)
        logger.info("Run %s finished with status %s", manifest.run_id, final_status.value)

        if progress.hard_error is not None:
            raise progress.hard_error

        return RunResult(
            run_id=manifest.run_id,
            run_directory=run_directory,
            steps_completed=progress.steps_completed,
        )

    def _run_serial(self, ctx: RunExecutionContext, progress: RunProgress) -> None:
        for step in ctx.pipeline.steps:
            if progress.stop_reason:
                break

            current_status = ctx.manifest.step_status_map().get(step.step_id, StepRunStatus.PENDING)
            if current_status == StepRunStatus.COMPLETE:
                continue
            if ctx.is_retry and current_status not in {
                StepRunStatus.QUARANTINED,
                StepRunStatus.PENDING,
                StepRunStatus.BLOCKED,
            }:
                continue

            try:
                self.check_dependencies(step, ctx.manifest)
            except DependencyQuarantinedError as error:
                with ctx.state_lock:
                    ctx.manifest.upsert_step_state(
                        step.step_id,
                        StepRunStatus.BLOCKED,
                        detail=str(error),
                    )
                    ctx.active_tracker.mark_failed(step.step_id, detail=str(error))
                progress.stop_reason = str(error)
                break

            outcome = self.execute_step(step, ctx)
            if outcome.hard_error is not None:
                progress.hard_error = outcome.hard_error
                break
            if outcome.dependency_blocked_detail is not None:
                progress.stop_reason = outcome.dependency_blocked_detail
                break
            progress.steps_completed += outcome.steps_completed_delta

    def execute_step(self, step: StepDefinition, ctx: RunExecutionContext) -> StepExecutionOutcome:
        current_status = ctx.manifest.step_status_map().get(step.step_id, StepRunStatus.PENDING)
        step_files = [
            self._resolve_step_file(
                file_spec,
                ctx.file_pool,
                ctx.manifest,
                ctx.run_directory,
                ctx.pipeline,
            )
            for file_spec in step.file_specs
        ]

        with ctx.state_lock:
            if current_status == StepRunStatus.QUARANTINED:
                self._prepare_step_retry(step, step_files, ctx.quarantine_store)
            self._capture_snapshots(step, step_files, ctx.quarantine_store)
            ctx.active_tracker.mark_running(step.step_id)
            ctx.active_tracker.set_status_message(step.label)
            ctx.active_tracker.set_progress_percent(None)
            if ctx.progress_callback is not None:
                ctx.progress_callback()

        quarantine = StepQuarantine(ctx.run_directory, step.step_id)
        step_stats = ctx.stats_recorder.for_step(step.step_id)
        context = StepContext(
            pipeline_dir=ctx.pipeline_dir,
            run_directory=ctx.run_directory,
            run_id=ctx.manifest.run_id,
            run_date=date.today(),
            step_id=step.step_id,
            logger=ctx.step_logger,
            report_progress=ctx.report_progress,
            quarantine=quarantine,
            stats=step_stats,
        )

        ingest_names = sorted({file_spec.__class__.ingest_name for file_spec in step.file_specs})
        file_locks = [ctx.file_locks[ingest_name] for ingest_name in ingest_names]

        step_started_at = time.monotonic()
        try:
            logger.info("Running step %s", step.label)
            with ExitStack() as lock_stack:
                for file_lock in file_locks:
                    lock_stack.enter_context(file_lock)
                step.fn(context, step_files)
            step_stats.record_step(
                "duration_ms",
                (time.monotonic() - step_started_at) * 1000,
            )
        except Exception as error:
            step_stats.record_step(
                "duration_ms",
                (time.monotonic() - step_started_at) * 1000,
            )
            logger.error("Run failed during step %s: %s", step.label, error, exc_info=True)
            with ctx.state_lock:
                ctx.manifest.upsert_step_state(
                    step.step_id,
                    StepRunStatus.FAILED,
                    detail=str(error),
                )
                ctx.active_tracker.mark_failed(step.step_id, detail=str(error))
                ctx.active_tracker.set_status_message(f"Failed: {error}")
                self._persist_manifest(
                    ctx.run_manager,
                    ctx.store,
                    ctx.run_directory,
                    ctx.manifest,
                    RunStatus.FAILED,
                )
            return StepExecutionOutcome(step_id=step.step_id, hard_error=error)

        if quarantine.has_quarantined_rows:
            quarantine_row_count = sum(
                ctx.quarantine_store.row_count(
                    ctx.quarantine_store.quarantine_path(
                        step.step_id,
                        file.spec.__class__.ingest_name,
                    )
                )
                for file in step_files
            )
            step_stats.record_step("rows_quarantined", quarantine_row_count)
            with ctx.state_lock:
                ctx.manifest.upsert_step_state(
                    step.step_id,
                    StepRunStatus.QUARANTINED,
                    detail="Rows quarantined",
                )
                ctx.active_tracker.mark_quarantined(step.step_id, detail="Rows quarantined")
        else:
            with ctx.state_lock:
                ctx.manifest.upsert_step_state(step.step_id, StepRunStatus.COMPLETE)
                ctx.active_tracker.mark_complete(step.step_id)

        with ctx.state_lock:
            self._persist_manifest(
                ctx.run_manager,
                ctx.store,
                ctx.run_directory,
                ctx.manifest,
                self._derive_run_status(ctx.manifest),
            )
            if ctx.progress_callback is not None:
                ctx.progress_callback()

        return StepExecutionOutcome(
            step_id=step.step_id,
            steps_completed_delta=0 if quarantine.has_quarantined_rows else 1,
        )

    def check_dependencies(self, step: StepDefinition, manifest: RunManifest) -> None:
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

    def _record_run_statistics(
        self,
        stats_recorder: StatisticsRecorder,
        manifest: RunManifest,
        *,
        steps_completed: int,
        run_started_at: float,
    ) -> None:
        stats_recorder.record_run("steps_completed", steps_completed)
        stats_recorder.record_run("duration_ms", (time.monotonic() - run_started_at) * 1000)
        quarantined_step_count = sum(
            1 for record in manifest.step_states if record.status == StepRunStatus.QUARANTINED
        )
        if quarantined_step_count:
            stats_recorder.record_run("steps_quarantined", quarantined_step_count)

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
                    large_file_threshold_bytes=pipeline.large_file_threshold_bytes,
                    run_batch_size=pipeline.run_batch_size,
                )
        return file_pool

    def _resolve_step_file(
        self,
        file_spec,
        file_pool: dict[str, AstroFile],
        manifest: RunManifest,
        run_directory: Path,
        pipeline: Pipeline,
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
            large_file_threshold_bytes=pipeline.large_file_threshold_bytes,
            run_batch_size=pipeline.run_batch_size,
        )
        file_pool[ingest_name] = hydrated
        return hydrated

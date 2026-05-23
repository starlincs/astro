"""Parallel pipeline step scheduler."""

from __future__ import annotations

import os
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from astro.pipeline.steps import StepDefinition
from astro.run.context import RunExecutionContext, RunProgress, StepExecutionOutcome
from astro.run.service import DependencyQuarantinedError, RunService
from astro.working.manifest import RunManifest, StepRunStatus


class ParallelStepScheduler:
    """Dispatch ready steps to a thread pool until the run reaches a terminal state."""

    def __init__(
        self,
        service: RunService,
        ctx: RunExecutionContext,
        progress: RunProgress,
    ) -> None:
        self._service = service
        self._ctx = ctx
        self._progress = progress
        self._max_workers = self._resolve_max_workers()

    def run(self) -> None:
        pending_futures: dict[Future[StepExecutionOutcome], StepDefinition] = {}
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            while True:
                self._mark_quarantine_blocked_steps()
                self._submit_ready_steps(executor, pending_futures)

                if not pending_futures:
                    if self._progress.stop_scheduling or self._progress.hard_error:
                        break
                    if self._all_steps_terminal():
                        break
                    continue

                done, _ = wait(pending_futures, return_when=FIRST_COMPLETED)
                for future in done:
                    step = pending_futures.pop(future)
                    with self._ctx.state_lock:
                        self._ctx.running_step_ids.discard(step.step_id)
                    outcome = future.result()
                    self._handle_outcome(outcome)

                if self._progress.hard_error and not pending_futures:
                    break

    def _resolve_max_workers(self) -> int:
        configured = self._ctx.pipeline.max_parallel_workers
        if configured is not None:
            if configured < 1:
                raise ValueError("max_parallel_workers must be at least 1.")
            return configured
        return min(32, (os.cpu_count() or 1) + 4)

    def _submit_ready_steps(
        self,
        executor: ThreadPoolExecutor,
        pending_futures: dict[Future[StepExecutionOutcome], StepDefinition],
    ) -> None:
        if self._progress.stop_scheduling or self._progress.hard_error:
            return

        with self._ctx.state_lock:
            in_flight = len(pending_futures)
            available_slots = self._max_workers - in_flight
            if available_slots <= 0:
                return

            for step in self._ctx.pipeline.steps:
                if available_slots <= 0:
                    break
                if not self._is_step_ready(step):
                    continue
                self._ctx.running_step_ids.add(step.step_id)
                future = executor.submit(self._service.execute_step, step, self._ctx)
                pending_futures[future] = step
                available_slots -= 1

            self._update_status_message()

    def _handle_outcome(self, outcome: StepExecutionOutcome) -> None:
        if outcome.hard_error is not None:
            self._progress.hard_error = outcome.hard_error
            self._progress.stop_scheduling = True
            return

        if outcome.dependency_blocked_detail is not None:
            self._progress.stop_reason = outcome.dependency_blocked_detail
            self._progress.stop_scheduling = True
            return

        self._progress.steps_completed += outcome.steps_completed_delta

    def _mark_quarantine_blocked_steps(self) -> None:
        with self._ctx.state_lock:
            for step in self._ctx.pipeline.steps:
                status = self._ctx.manifest.step_status_map().get(
                    step.step_id,
                    StepRunStatus.PENDING,
                )
                if status in {
                    StepRunStatus.COMPLETE,
                    StepRunStatus.BLOCKED,
                    StepRunStatus.FAILED,
                }:
                    continue
                if step.step_id in self._ctx.running_step_ids:
                    continue
                blocked_error = self._dependency_quarantine_error(step, self._ctx.manifest)
                if blocked_error is None:
                    continue
                self._ctx.manifest.upsert_step_state(
                    step.step_id,
                    StepRunStatus.BLOCKED,
                    detail=str(blocked_error),
                )
                self._ctx.active_tracker.mark_failed(step.step_id, detail=str(blocked_error))
                self._progress.stop_reason = str(blocked_error)
                self._progress.stop_scheduling = True

    def _dependency_quarantine_error(
        self,
        step: StepDefinition,
        manifest: RunManifest,
    ) -> DependencyQuarantinedError | None:
        statuses = manifest.step_status_map()
        for dependency_id in step.depends_on:
            if statuses.get(dependency_id) == StepRunStatus.QUARANTINED:
                return DependencyQuarantinedError(
                    f"Step {step.step_id} blocked by quarantined dependency: {dependency_id}"
                )
        return None

    def _should_skip_step(self, step: StepDefinition) -> bool:
        status = self._ctx.manifest.step_status_map().get(step.step_id, StepRunStatus.PENDING)
        if status == StepRunStatus.COMPLETE:
            return True
        return bool(
            self._ctx.is_retry
            and status
            not in {
                StepRunStatus.QUARANTINED,
                StepRunStatus.PENDING,
                StepRunStatus.BLOCKED,
            }
        )

    def _is_step_ready(self, step: StepDefinition) -> bool:
        if self._should_skip_step(step):
            return False
        if step.step_id in self._ctx.running_step_ids:
            return False

        status = self._ctx.manifest.step_status_map().get(step.step_id, StepRunStatus.PENDING)
        if status == StepRunStatus.BLOCKED:
            return False

        statuses = self._ctx.manifest.step_status_map()
        for dependency_id in step.depends_on:
            dependency_status = statuses.get(dependency_id, StepRunStatus.PENDING)
            if dependency_status != StepRunStatus.COMPLETE:
                return False
        return True

    def _all_steps_terminal(self) -> bool:
        for step in self._ctx.pipeline.steps:
            if self._should_skip_step(step):
                continue
            status = self._ctx.manifest.step_status_map().get(step.step_id, StepRunStatus.PENDING)
            if status not in {
                StepRunStatus.COMPLETE,
                StepRunStatus.QUARANTINED,
                StepRunStatus.FAILED,
                StepRunStatus.BLOCKED,
            }:
                return False
        return True

    def _update_status_message(self) -> None:
        running_count = len(self._ctx.running_step_ids)
        if running_count > 1:
            self._ctx.active_tracker.set_status_message(f"Running {running_count} steps")
        elif running_count == 1:
            running_id = next(iter(self._ctx.running_step_ids))
            step = next(
                candidate
                for candidate in self._ctx.pipeline.steps
                if candidate.step_id == running_id
            )
            self._ctx.active_tracker.set_status_message(step.label)

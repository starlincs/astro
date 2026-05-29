"""Pipeline step tracking for the run dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from astro.pipeline.base import Pipeline
from astro.working.manifest import RunManifest, RunStatus, StepRunStatus


class StepStatus(StrEnum):
    """Dashboard display status for one pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    WARNING = "warning"
    QUARANTINED = "quarantined"
    SKIPPED = "skipped"


@dataclass
class PipelineStep:
    """One step row shown in the run dashboard."""

    id: str
    label: str
    status: StepStatus
    detail: str | None = None


class StepTracker:
    """Track pipeline step completion for dashboard rendering."""

    def __init__(self, steps: list[PipelineStep]) -> None:
        self.steps = steps
        self.status_message = ""
        self.progress_percent: float | None = None

    def get_step(self, step_id: str) -> PipelineStep:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(step_id)

    def mark_running(self, step_id: str, *, detail: str | None = None) -> None:
        step = self.get_step(step_id)
        step.status = StepStatus.RUNNING
        if detail is not None:
            step.detail = detail

    def mark_complete(self, step_id: str, *, detail: str | None = None) -> None:
        step = self.get_step(step_id)
        step.status = StepStatus.COMPLETE
        if detail is not None:
            step.detail = detail

    def mark_failed(self, step_id: str, *, detail: str | None = None) -> None:
        step = self.get_step(step_id)
        step.status = StepStatus.FAILED
        if detail is not None:
            step.detail = detail

    def mark_quarantined(self, step_id: str, *, detail: str | None = None) -> None:
        step = self.get_step(step_id)
        step.status = StepStatus.QUARANTINED
        if detail is not None:
            step.detail = detail

    def mark_skipped(self, step_id: str, *, detail: str | None = None) -> None:
        step = self.get_step(step_id)
        step.status = StepStatus.SKIPPED
        if detail is not None:
            step.detail = detail

    def set_status(self, step_id: str, status: StepStatus, *, detail: str | None = None) -> None:
        step = self.get_step(step_id)
        step.status = status
        if detail is not None:
            step.detail = detail

    def set_status_message(self, message: str) -> None:
        self.status_message = message

    def set_progress_percent(self, progress_percent: float | None) -> None:
        self.progress_percent = progress_percent


def _map_step_run_status(status: StepRunStatus) -> StepStatus:
    mapping = {
        StepRunStatus.PENDING: StepStatus.PENDING,
        StepRunStatus.COMPLETE: StepStatus.COMPLETE,
        StepRunStatus.QUARANTINED: StepStatus.QUARANTINED,
        StepRunStatus.FAILED: StepStatus.FAILED,
        StepRunStatus.BLOCKED: StepStatus.FAILED,
        StepRunStatus.SKIPPED: StepStatus.SKIPPED,
    }
    return mapping[status]


def build_run_tracker(pipeline: Pipeline, manifest: RunManifest) -> StepTracker:
    ingest_status = (
        StepStatus.COMPLETE
        if manifest.status
        in {RunStatus.INGESTED, RunStatus.QUARANTINED, RunStatus.COMPLETED, RunStatus.FAILED}
        and manifest.ingested_files
        else StepStatus.PENDING
    )
    persisted_statuses = manifest.step_status_map()
    steps = [
        PipelineStep(id="ingest", label="Ingest", status=ingest_status),
    ]
    for step_definition in pipeline.steps:
        persisted = persisted_statuses.get(step_definition.step_id)
        status = _map_step_run_status(persisted) if persisted else StepStatus.PENDING
        steps.append(
            PipelineStep(
                id=step_definition.step_id,
                label=step_definition.label,
                status=status,
            )
        )
    return StepTracker(steps)


def build_run_steps(manifest: RunManifest) -> list[PipelineStep]:
    """Backward-compatible helper for tests without a pipeline instance."""
    ingest_status = (
        StepStatus.COMPLETE
        if manifest.status == RunStatus.INGESTED and manifest.ingested_files
        else StepStatus.PENDING
    )
    return [PipelineStep(id="ingest", label="Ingest", status=ingest_status)]

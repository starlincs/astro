"""Run manifest models for pipeline working directories."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    """Lifecycle status for a pipeline run."""

    CREATED = "created"
    INGESTED = "ingested"
    QUARANTINED = "quarantined"
    COMPLETED = "completed"
    FAILED = "failed"


class StepRunStatus(StrEnum):
    """Execution status for one pipeline step."""

    PENDING = "pending"
    COMPLETE = "complete"
    QUARANTINED = "quarantined"
    FAILED = "failed"
    BLOCKED = "blocked"


class IngestedFileRecord(BaseModel):
    """Metadata for one ingested source file in a run manifest."""

    name: str
    source_path: str
    parquet_path: str
    row_count: int
    column_count: int
    source_size_bytes: int


class OutputFileRecord(BaseModel):
    """Metadata for one output file recorded in statistics."""

    name: str
    source_path: str
    parquet_path: str
    row_count: int
    column_count: int
    output_size_bytes: int


class StepRunRecord(BaseModel):
    """Persisted step status for one run."""

    step_id: str
    status: StepRunStatus
    detail: str | None = None


class RunManifest(BaseModel):
    """Run manifest stored at ``.working/{run_id}/manifest.json``."""

    run_id: str
    pipeline_name: str
    status: RunStatus
    execution_mode: str
    source_directory: str
    created_at: datetime
    ingested_at: datetime | None = None
    ingested_files: list[IngestedFileRecord] = Field(default_factory=list)
    step_states: list[StepRunRecord] = Field(default_factory=list)

    def is_incomplete(self) -> bool:
        return self.status != RunStatus.COMPLETED

    def step_status_map(self) -> dict[str, StepRunStatus]:
        return {record.step_id: record.status for record in self.step_states}

    def upsert_step_state(
        self,
        step_id: str,
        status: StepRunStatus,
        *,
        detail: str | None = None,
    ) -> None:
        for index, record in enumerate(self.step_states):
            if record.step_id == step_id:
                self.step_states[index] = StepRunRecord(
                    step_id=step_id,
                    status=status,
                    detail=detail,
                )
                return
        self.step_states.append(StepRunRecord(step_id=step_id, status=status, detail=detail))

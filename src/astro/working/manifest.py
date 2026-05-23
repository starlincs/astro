"""Run manifest models for pipeline working directories."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    CREATED = "created"
    INGESTED = "ingested"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestedFileRecord(BaseModel):
    name: str
    source_path: str
    parquet_path: str
    row_count: int
    column_count: int
    source_size_bytes: int


class RunManifest(BaseModel):
    run_id: str
    pipeline_name: str
    status: RunStatus
    execution_mode: str
    source_directory: str
    created_at: datetime
    ingested_at: datetime | None = None
    ingested_files: list[IngestedFileRecord] = Field(default_factory=list)

    def is_incomplete(self) -> bool:
        return self.status != RunStatus.COMPLETED

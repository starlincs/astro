"""Statistics models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class StatScope(StrEnum):
    """Statistics aggregation scope."""

    RUN = "run"
    FILE = "file"
    STEP = "step"


@dataclass(frozen=True)
class StatRecord:
    """One persisted statistics row."""

    run_id: str
    scope: StatScope
    subject: str | None
    action: str
    value: float
    recorded_at: datetime

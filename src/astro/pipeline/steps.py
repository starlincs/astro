"""Pipeline run step definitions and execution context."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path

from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.quarantine.collector import StepQuarantine
from astro.stats.recorder import StatisticsRecorder

StepFn = Callable[["StepContext", list[AstroFile]], None]
ProgressCallback = Callable[[float | None], None]


class StepKind(StrEnum):
    STEP = "step"
    FILTER = "filter"


@dataclass(frozen=True)
class StepDefinition:
    step_id: str
    label: str
    fn: StepFn
    file_specs: tuple[AstroFileSpec, ...]
    depends_on: tuple[str, ...]
    kind: StepKind = field(default=StepKind.STEP)


@dataclass(frozen=True)
class StepContext:
    pipeline_dir: Path
    run_directory: Path
    run_id: str
    run_date: date
    step_id: str
    logger: logging.Logger
    report_progress: ProgressCallback
    quarantine: StepQuarantine
    stats: StatisticsRecorder


def slugify_step_label(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "step"

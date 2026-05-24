"""Shared run execution context."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from astro.cli.display.steps import StepTracker
from astro.pipeline.base import Pipeline
from astro.pipeline.files import AstroFile
from astro.quarantine.store import QuarantineStore
from astro.stats.recorder import StatisticsRecorder
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunManifest
from astro.working.run_manager import RunManager


@dataclass
class RunProgress:
    """Mutable run scheduling progress shared by serial and parallel executors."""

    steps_completed: int = 0
    stop_reason: str | None = None
    hard_error: Exception | None = None
    stop_scheduling: bool = False


@dataclass
class StepExecutionOutcome:
    """Result of executing one pipeline step."""

    step_id: str
    steps_completed_delta: int = 0
    hard_error: Exception | None = None
    dependency_blocked_detail: str | None = None


@dataclass
class RunExecutionContext:
    """Shared state for one ``astro run`` invocation."""

    pipeline_dir: Path
    pipeline: Pipeline
    run_directory: Path
    manifest: RunManifest
    run_manager: RunManager
    store: PipelineStore
    stats_recorder: StatisticsRecorder
    active_tracker: StepTracker
    file_pool: dict[str, AstroFile]
    quarantine_store: QuarantineStore
    step_logger: logging.Logger
    is_retry: bool
    report_progress: Callable[[float | None], None]
    progress_callback: Callable[[], None] | None
    run_started_at: float
    state_lock: threading.Lock = field(default_factory=threading.Lock)
    file_locks: dict[str, threading.Lock] = field(default_factory=dict)
    running_step_ids: set[str] = field(default_factory=set)

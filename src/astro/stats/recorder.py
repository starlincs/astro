"""Statistics recorder for run, file, and step metrics."""

from __future__ import annotations

import logging

from astro.stats.models import StatScope
from astro.storage.sqlite import PipelineStore

logger = logging.getLogger("astro.stats")


class StatisticsRecorder:
    """Record numeric statistics scoped to a run, file, or step."""

    def __init__(
        self,
        run_id: str,
        store: PipelineStore,
        *,
        step_id: str | None = None,
    ) -> None:
        self._run_id = run_id
        self._store = store
        self._step_id = step_id

    def record_run(self, action: str, value: int | float) -> None:
        self._record(StatScope.RUN, None, action, value)

    def record_file(self, file_name: str, action: str, value: int | float) -> None:
        if not file_name:
            raise ValueError("file_name must not be empty.")
        self._record(StatScope.FILE, file_name, action, value)

    def record_step(
        self,
        action: str,
        value: int | float,
        *,
        step_id: str | None = None,
    ) -> None:
        resolved_step_id = step_id or self._step_id
        if not resolved_step_id:
            raise ValueError("step_id is required when recording step statistics.")
        self._record(StatScope.STEP, resolved_step_id, action, value)

    def for_step(self, step_id: str) -> StatisticsRecorder:
        return StatisticsRecorder(self._run_id, self._store, step_id=step_id)

    def _record(
        self,
        scope: StatScope,
        subject: str | None,
        action: str,
        value: int | float,
    ) -> None:
        if not action:
            raise ValueError("action must not be empty.")
        if not isinstance(value, int | float):
            raise TypeError("value must be int or float.")

        self._store.record_stat(self._run_id, scope, subject, action, float(value))
        subject_label = subject or "-"
        logger.info(
            "STAT run=%s scope=%s subject=%s action=%s value=%s",
            self._run_id,
            scope.value,
            subject_label,
            action,
            value,
        )

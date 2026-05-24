"""Base pipeline interface for Astro library users."""

from __future__ import annotations

from abc import ABC
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import polars as pl

from astro.filter.types import FilterFn
from astro.io.constants import (
    DEFAULT_INGEST_BATCH_SIZE,
    DEFAULT_LARGE_FILE_THRESHOLD_BYTES,
    DEFAULT_RUN_BATCH_SIZE,
)
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.models import ExecutionMode, IngestFileSpec, StepExecutionMode
from astro.pipeline.steps import (
    StepContext,
    StepDefinition,
    StepFn,
    StepKind,
    slugify_step_label,
)


@dataclass(frozen=True)
class IngestedSource:
    """One ingested file and its raw data. Schemas may differ across sources."""

    path: Path
    data: pl.DataFrame


class Pipeline(ABC):
    """Base class for CSV import pipelines defined in external repositories.

    Subclass ``Pipeline``, define ``ingest_files``, implement ``configure_steps()``,
    and export a module-level ``pipeline`` instance from ``pipeline.py``.

    Attributes:
        name: Pipeline identifier stored in statistics.
        execution_mode: Ingest concurrency rules (``serial`` or ``parallel``).
        step_execution_mode: Run-step scheduling (``serial`` or ``parallel``).
        max_parallel_workers: Cap on concurrent run steps when parallel.
        large_file_threshold_bytes: Size above which batched I/O paths are used.
        ingest_batch_size: CSV rows per batch during large-file ingest.
        run_batch_size: Parquet rows per batch during filter and ``iter_batches()``.
        ingest_files: Expected source file patterns and Pandera schemas.
    """

    name: str = "pipeline"
    execution_mode: ExecutionMode = ExecutionMode.SERIAL
    step_execution_mode: StepExecutionMode = StepExecutionMode.SERIAL
    max_parallel_workers: int | None = None
    large_file_threshold_bytes: int = DEFAULT_LARGE_FILE_THRESHOLD_BYTES
    ingest_batch_size: int = DEFAULT_INGEST_BATCH_SIZE
    run_batch_size: int = DEFAULT_RUN_BATCH_SIZE
    ingest_files: ClassVar[list[IngestFileSpec]]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        ingest_files = getattr(cls, "ingest_files", [])
        if not ingest_files:
            raise TypeError(f"{cls.__name__} must define a non-empty ingest_files list.")
        names = [spec.name for spec in ingest_files]
        if len(names) != len(set(names)):
            raise TypeError(f"{cls.__name__} ingest_files names must be unique.")

    def __init__(self) -> None:
        self._steps: list[StepDefinition] = []
        self.configure_steps()
        if not self._steps:
            raise ValueError(f"{self.__class__.__name__} must define at least one run step.")

    def configure_steps(self) -> None:  # noqa: B027
        """Register run steps via ``add_step`` and ``add_filter``."""

    def add_step(
        self,
        label: str,
        fn: StepFn,
        files: Sequence[AstroFileSpec],
        *,
        step_id: str | None = None,
        depends_on: Sequence[str] | None = None,
        kind: StepKind = StepKind.STEP,
    ) -> None:
        """Register a custom run step.

        Args:
            label: Human-readable step name shown in the dashboard and logs.
            fn: Step function receiving ``(StepContext, list[AstroFile])``.
            files: ``AstroFileSpec`` subclasses this step reads and writes.
            step_id: Optional explicit step id (defaults to slugified label).
            depends_on: Step ids that must complete before this step runs.
            kind: Step kind (``step`` or ``filter``); use ``add_filter`` for filters.
        """
        if not files:
            raise ValueError("Each step must reference at least one AstroFileSpec.")

        resolved_step_id = step_id or slugify_step_label(label)
        registered_ids = {step.step_id for step in self._steps}
        if resolved_step_id in registered_ids:
            raise ValueError(f"Step id must be unique: {resolved_step_id}")

        ingest_names = {spec.name for spec in self.ingest_files}
        for file_spec in files:
            ingest_name = getattr(file_spec.__class__, "ingest_name", None)
            if not ingest_name:
                raise ValueError(
                    f"{file_spec.__class__.__name__} must define an ingest_name class attribute."
                )
            if ingest_name not in ingest_names:
                raise ValueError(
                    f"AstroFileSpec ingest_name {ingest_name!r} is not declared in ingest_files."
                )

        dependency_ids = tuple(depends_on or ())
        unknown_dependencies = set(dependency_ids) - registered_ids
        if unknown_dependencies:
            joined = ", ".join(sorted(unknown_dependencies))
            raise ValueError(f"Unknown depends_on step id(s): {joined}")

        self._steps.append(
            StepDefinition(
                step_id=resolved_step_id,
                label=label,
                fn=fn,
                file_specs=tuple(files),
                depends_on=dependency_ids,
                kind=kind,
            )
        )

    def add_filter(
        self,
        label: str,
        fn: FilterFn | pl.Expr,
        files: Sequence[AstroFileSpec],
        *,
        step_id: str | None = None,
        depends_on: Sequence[str] | None = None,
    ) -> None:
        """Register a filter step that removes rows from one or more files.

        Args:
            label: Human-readable filter name.
            fn: Filter function returning **removed** rows, or a Polars expression predicate.
            files: ``AstroFileSpec`` subclasses to filter.
            step_id: Optional explicit step id (defaults to slugified label).
            depends_on: Step ids that must complete before this filter runs.
        """
        from astro.filter.executor import apply_filter_step, apply_predicate_filter_step

        if isinstance(fn, pl.Expr):
            predicate = fn

            def filter_step(context: StepContext, step_files: list[AstroFile]) -> None:
                apply_predicate_filter_step(context, step_files, predicate)

        else:

            def filter_step(context: StepContext, step_files: list[AstroFile]) -> None:
                apply_filter_step(context, step_files, fn)

        self.add_step(
            label,
            filter_step,
            files,
            step_id=step_id,
            depends_on=depends_on,
            kind=StepKind.FILTER,
        )

    @property
    def steps(self) -> list[StepDefinition]:
        return list(self._steps)

    def run(self, path: Path) -> list[IngestedSource]:
        """Legacy entry point; use ``astro ingest`` and ``astro run`` instead."""
        raise NotImplementedError(
            "Pipeline.run() is not available. Use astro ingest and astro run."
        )

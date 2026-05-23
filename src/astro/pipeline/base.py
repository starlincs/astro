"""Base pipeline interface for Astro library users."""

from __future__ import annotations

from abc import ABC
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import polars as pl

from astro.filter.types import FilterFn
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.models import ExecutionMode, IngestFileSpec
from astro.pipeline.steps import StepContext, StepDefinition, StepFn, slugify_step_label


@dataclass(frozen=True)
class IngestedSource:
    """One ingested file and its raw data. Schemas may differ across sources."""

    path: Path
    data: pl.DataFrame


class Pipeline(ABC):
    """Base class for CSV import pipelines defined in external repositories."""

    name: str = "pipeline"
    execution_mode: ExecutionMode = ExecutionMode.SERIAL
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
        """Register run steps via ``add_step``."""

    def add_step(
        self,
        label: str,
        fn: StepFn,
        files: Sequence[AstroFileSpec],
        *,
        step_id: str | None = None,
        depends_on: Sequence[str] | None = None,
    ) -> None:
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
            )
        )

    def add_filter(
        self,
        label: str,
        fn: FilterFn,
        files: Sequence[AstroFileSpec],
        *,
        step_id: str | None = None,
        depends_on: Sequence[str] | None = None,
    ) -> None:
        from astro.filter.executor import apply_filter_step

        def filter_step(context: StepContext, step_files: list[AstroFile]) -> None:
            apply_filter_step(context, step_files, fn)

        self.add_step(
            label,
            filter_step,
            files,
            step_id=step_id,
            depends_on=depends_on,
        )

    @property
    def steps(self) -> list[StepDefinition]:
        return list(self._steps)

    def run(self, path: Path) -> list[IngestedSource]:
        """Legacy entry point; use ``astro ingest`` and ``astro run`` instead."""
        raise NotImplementedError(
            "Pipeline.run() is not available. Use astro ingest and astro run."
        )

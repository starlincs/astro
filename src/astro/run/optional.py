"""Optional ingest handling during pipeline runs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from astro.pipeline.base import Pipeline
from astro.pipeline.steps import StepDefinition
from astro.working.manifest import RunManifest


class StepOptionalAction(StrEnum):
    """Classification outcome for optional ingest handling."""

    RUN = "run"
    SKIP = "skip"
    FAIL = "fail"


@dataclass(frozen=True)
class StepOptionalOutcome:
    """Result of classifying one step against absent optional ingests."""

    action: StepOptionalAction
    detail: str | None = None
    error: ValueError | None = None


def ingested_file_names(manifest: RunManifest) -> set[str]:
    return {record.name for record in manifest.ingested_files}


def optional_ingest_names(pipeline: Pipeline) -> set[str]:
    return {spec.name for spec in pipeline.ingest_files if spec.optional}


def absent_optional_ingest_names(pipeline: Pipeline, manifest: RunManifest) -> set[str]:
    return optional_ingest_names(pipeline) - ingested_file_names(manifest)


def classify_step_for_optional_ingests(
    step: StepDefinition,
    pipeline: Pipeline,
    manifest: RunManifest,
) -> StepOptionalOutcome:
    absent_optional = absent_optional_ingest_names(pipeline, manifest)
    if not absent_optional:
        return StepOptionalOutcome(action=StepOptionalAction.RUN)

    step_ingest_names = {file_spec.__class__.ingest_name for file_spec in step.file_specs}
    missing_optional = step_ingest_names & absent_optional
    if not missing_optional:
        return StepOptionalOutcome(action=StepOptionalAction.RUN)

    ingested_names = ingested_file_names(manifest)
    present_ingests = step_ingest_names & ingested_names
    if present_ingests:
        missing = ", ".join(sorted(missing_optional))
        present = ", ".join(sorted(present_ingests))
        error = ValueError(
            f"Step {step.step_id!r} references optional ingest(s) {missing} "
            f"that were not ingested alongside present ingest(s): {present}."
        )
        return StepOptionalOutcome(action=StepOptionalAction.FAIL, error=error)

    missing = ", ".join(sorted(missing_optional))
    detail = f"Optional ingest file(s) not present: {missing}"
    return StepOptionalOutcome(action=StepOptionalAction.SKIP, detail=detail)

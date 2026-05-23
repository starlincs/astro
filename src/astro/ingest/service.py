"""Ingest orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from astro.ingest.materialize import materialize_ingest_file
from astro.ingest.validator import IngestValidationError, match_ingest_files
from astro.pipeline.base import Pipeline
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunStatus
from astro.working.run_manager import RunManager


@dataclass(frozen=True)
class IngestResult:
    run_id: str
    run_directory: Path
    ingested_files: list[str]


class IngestService:
    """Coordinate CLI ingest for a discovered pipeline."""

    def __init__(self, pipeline_dir: Path, pipeline: Pipeline) -> None:
        self.pipeline_dir = pipeline_dir
        self.pipeline = pipeline
        self.run_manager = RunManager(pipeline_dir)
        self.store = PipelineStore(pipeline_dir / ".astro" / "stats.db")

    def ingest(self, source_directory: Path) -> IngestResult:
        source_directory = source_directory.resolve()
        self.run_manager.assert_serial_ingest_allowed(self.pipeline.execution_mode)

        run_directory, manifest = self.run_manager.create_run(
            pipeline_name=self.pipeline.name,
            execution_mode=self.pipeline.execution_mode,
            source_directory=source_directory,
        )

        try:
            matched_files = match_ingest_files(source_directory, self.pipeline.ingest_files)
            ingest_directory = self.run_manager.ingest_directory_for(run_directory)
            materialized_files = [
                materialize_ingest_file(matched_file, ingest_directory=ingest_directory)
                for matched_file in matched_files
            ]
        except (IngestValidationError, Exception):
            self._mark_failed(run_directory)
            raise

        ingested_at = datetime.now(UTC)
        manifest.status = RunStatus.INGESTED
        manifest.ingested_at = ingested_at
        manifest.ingested_files = [item.record for item in materialized_files]
        self.run_manager.save_manifest(run_directory, manifest)

        self.store.record_run(
            run_id=manifest.run_id,
            pipeline_name=manifest.pipeline_name,
            status=manifest.status.value,
            source_directory=manifest.source_directory,
            created_at=manifest.created_at,
            ingested_at=ingested_at,
        )
        self.store.record_ingest_files(manifest.run_id, manifest.ingested_files)

        return IngestResult(
            run_id=manifest.run_id,
            run_directory=run_directory,
            ingested_files=[record.name for record in manifest.ingested_files],
        )

    def _mark_failed(self, run_directory: Path) -> None:
        manifest = self.run_manager.load_manifest(run_directory)
        manifest.status = RunStatus.FAILED
        self.run_manager.save_manifest(run_directory, manifest)

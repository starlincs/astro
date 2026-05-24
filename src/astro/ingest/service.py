"""Ingest orchestration service."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from astro.ingest.materialize import IngestProgressCallback, materialize_ingest_file
from astro.ingest.validator import IngestValidationError, match_ingest_files
from astro.pipeline.base import Pipeline
from astro.stats.recorder import StatisticsRecorder
from astro.storage.sqlite import PipelineStore
from astro.working.manifest import RunStatus
from astro.working.run_manager import RunManager

logger = logging.getLogger("astro.ingest")


@dataclass(frozen=True)
class IngestResult:
    """Outcome of a successful CLI ingest."""

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

    def ingest(
        self,
        source_directory: Path,
        *,
        on_run_created: Callable[[Path, str], None] | None = None,
        on_ingest_progress: IngestProgressCallback | None = None,
    ) -> IngestResult:
        source_directory = source_directory.resolve()
        self.run_manager.assert_serial_ingest_allowed(self.pipeline.execution_mode)
        logger.info("Serial ingest gate passed for pipeline %s", self.pipeline.name)

        run_directory, manifest = self.run_manager.create_run(
            pipeline_name=self.pipeline.name,
            execution_mode=self.pipeline.execution_mode,
            source_directory=source_directory,
        )
        logger.info("Run %s created at %s", manifest.run_id, run_directory)
        if on_run_created is not None:
            on_run_created(run_directory, manifest.run_id)

        try:
            logger.info("Matching source files in %s", source_directory)
            matched_files = match_ingest_files(source_directory, self.pipeline.ingest_files)
            ingest_directory = self.run_manager.ingest_directory_for(run_directory)
            materialized_files = []
            for matched_file in matched_files:
                source_size_bytes = matched_file.source_path.stat().st_size
                logger.info("Materializing %s", matched_file.spec.name)
                progress_state = {"last_percent": -1}

                def progress_callback(
                    file_name: str,
                    rows_done: int,
                    total_rows: int | None,
                    *,
                    _progress_state: dict[str, int] = progress_state,
                ) -> None:
                    if on_ingest_progress is not None:
                        on_ingest_progress(file_name, rows_done, total_rows)
                        return
                    if total_rows is None or total_rows <= 0:
                        if rows_done % max(self.pipeline.ingest_batch_size, 1) == 0:
                            logger.info("Materializing %s: %s rows", file_name, f"{rows_done:,}")
                        return
                    percent = int(rows_done / total_rows * 100)
                    if percent >= _progress_state["last_percent"] + 5 or rows_done >= total_rows:
                        _progress_state["last_percent"] = percent
                        logger.info(
                            "Materializing %s: %s / %s rows (%s%%)",
                            file_name,
                            f"{rows_done:,}",
                            f"{total_rows:,}",
                            percent,
                        )

                materialized = materialize_ingest_file(
                    matched_file,
                    ingest_directory=ingest_directory,
                    large_file_threshold_bytes=self.pipeline.large_file_threshold_bytes,
                    ingest_batch_size=self.pipeline.ingest_batch_size,
                    progress_callback=progress_callback
                    if source_size_bytes >= self.pipeline.large_file_threshold_bytes
                    else None,
                )
                materialized_files.append(materialized)
                logger.info(
                    "Ingested %s (%s rows)",
                    matched_file.spec.name,
                    materialized.record.row_count,
                )
        except IngestValidationError as error:
            logger.error("Ingest validation failed: %s", error, exc_info=True)
            self._mark_failed(run_directory)
            raise
        except Exception as error:
            logger.error("Ingest failed: %s", error, exc_info=True)
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
        stats = StatisticsRecorder(manifest.run_id, self.store)
        for materialized in materialized_files:
            record = materialized.record
            stats.record_file(record.name, "row_count", record.row_count)
            stats.record_file(record.name, "column_count", record.column_count)
            stats.record_file(record.name, "source_size_bytes", record.source_size_bytes)
        stats.record_run("files_ingested", len(materialized_files))
        self.store.record_ingest_files(manifest.run_id, manifest.ingested_files)
        logger.info(
            "Run %s marked ingested with %s file(s)",
            manifest.run_id,
            len(materialized_files),
        )

        return IngestResult(
            run_id=manifest.run_id,
            run_directory=run_directory,
            ingested_files=[record.name for record in manifest.ingested_files],
        )

    def _mark_failed(self, run_directory: Path) -> None:
        manifest = self.run_manager.load_manifest(run_directory)
        manifest.status = RunStatus.FAILED
        self.run_manager.save_manifest(run_directory, manifest)
        self.store.record_run(
            run_id=manifest.run_id,
            pipeline_name=manifest.pipeline_name,
            status=manifest.status.value,
            source_directory=manifest.source_directory,
            created_at=manifest.created_at,
            ingested_at=manifest.ingested_at,
        )
        StatisticsRecorder(manifest.run_id, self.store).record_run("ingest_failed", 1)

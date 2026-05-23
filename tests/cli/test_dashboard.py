"""Dashboard and step tracker tests."""

from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO

import pandera.polars as pa
from rich.console import Console

from astro.cli.display.dashboard import RunDashboard
from astro.cli.display.steps import PipelineStep, StepStatus, StepTracker, build_run_tracker
from astro.cli.logging import InMemoryLogBuffer, PlainLogFormatter
from astro.pipeline.base import Pipeline
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.models import ExecutionMode, IngestFileSpec
from astro.pipeline.steps import StepContext
from astro.working.manifest import IngestedFileRecord, RunManifest, RunStatus


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def step_noop(_ctx: StepContext, _files: list[AstroFile]) -> None:
    return None


class ExamplePipeline(Pipeline):
    name = "example"
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step("Resolve establishments", step_noop, [EstablishmentsFile()])


def _sample_manifest() -> RunManifest:
    return RunManifest(
        run_id="abc12",
        pipeline_name="example",
        status=RunStatus.INGESTED,
        execution_mode="serial",
        source_directory="/tmp/source",
        created_at=datetime(2026, 5, 22, tzinfo=UTC),
        ingested_at=datetime(2026, 5, 22, 1, 0, tzinfo=UTC),
        ingested_files=[
            IngestedFileRecord(
                name="establishments",
                source_path="/tmp/edubase.csv",
                parquet_path="/tmp/.working/abc12/ingested/establishments.parquet",
                row_count=10,
                column_count=2,
                source_size_bytes=100,
            )
        ],
    )


def test_build_run_tracker_includes_registered_steps() -> None:
    pipeline = ExamplePipeline()
    tracker = build_run_tracker(pipeline, _sample_manifest())

    assert tracker.steps[0].label == "Ingest"
    assert tracker.steps[0].status == StepStatus.COMPLETE
    assert tracker.steps[1].label == "Resolve establishments"
    assert tracker.steps[1].status == StepStatus.PENDING


def test_step_tracker_updates_status() -> None:
    tracker = StepTracker(
        [
            PipelineStep(id="ingest", label="Ingest", status=StepStatus.PENDING),
            PipelineStep(id="finalize", label="Finalize", status=StepStatus.PENDING),
        ]
    )

    tracker.mark_running("ingest")
    tracker.mark_complete("ingest")
    tracker.set_status_message("Ready")

    assert tracker.get_step("ingest").status == StepStatus.COMPLETE
    assert tracker.status_message == "Ready"


def test_dashboard_renders_layout_to_string() -> None:
    pipeline = ExamplePipeline()
    tracker = build_run_tracker(pipeline, _sample_manifest())
    tracker.set_status_message("Run completed")
    buffer = InMemoryLogBuffer()
    formatter = PlainLogFormatter()
    buffer.setFormatter(formatter)

    import logging

    record = logging.LogRecord(
        name="astro.run",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Run abc12 completed",
        args=(),
        exc_info=None,
    )
    buffer.emit(record)

    output = StringIO()
    dashboard = RunDashboard(tracker, buffer, console=Console(file=output, width=120, height=50))
    dashboard.render_once()

    rendered = output.getvalue()
    assert "Ingest" in rendered
    assert "Resolve" in rendered
    assert "establishments" in rendered
    assert "Run completed" in rendered


def test_dashboard_limits_visible_log_lines() -> None:
    import logging

    from astro.cli.display.dashboard import MAX_VISIBLE_LOG_LINES

    tracker = StepTracker([PipelineStep(id="ingest", label="Ingest", status=StepStatus.COMPLETE)])
    buffer = InMemoryLogBuffer()
    buffer.setFormatter(PlainLogFormatter())

    total_records = MAX_VISIBLE_LOG_LINES + 15
    for index in range(total_records):
        buffer.emit(
            logging.LogRecord(
                name="astro.run",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg=f"Log line {index:03d}",
                args=(),
                exc_info=None,
            )
        )

    output = StringIO()
    dashboard = RunDashboard(tracker, buffer, console=Console(file=output, width=120, height=50))
    dashboard.render_once()
    rendered = output.getvalue()

    assert f"Log line {total_records - 1:03d}" in rendered
    assert "Log line 000" not in rendered
    assert rendered.count("Log line") == MAX_VISIBLE_LOG_LINES


def test_dashboard_keeps_panels_side_by_side_with_long_log_lines() -> None:
    import logging

    tracker = StepTracker([PipelineStep(id="ingest", label="Ingest", status=StepStatus.COMPLETE)])
    buffer = InMemoryLogBuffer()
    buffer.setFormatter(PlainLogFormatter())
    long_message = "STAT run=abcde scope=file subject=establishments action=row_count value=1 " + (
        "x" * 200
    )
    record = logging.LogRecord(
        name="astro.stats",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=long_message,
        args=(),
        exc_info=None,
    )
    record.astro_display_message = "Stat · establishments · row count · 1"
    buffer.emit(record)

    output = StringIO()
    dashboard = RunDashboard(tracker, buffer, console=Console(file=output, width=100, height=50))
    dashboard.render_once()
    rendered = output.getvalue()

    assert any("Steps" in line and "Live log" in line for line in rendered.splitlines()[:8])

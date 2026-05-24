"""Dashboard rendering tests."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from astro.cli.display.dashboard import RunDashboard
from astro.cli.display.steps import PipelineStep, StepStatus, StepTracker
from astro.cli.logging import InMemoryLogBuffer


def test_dashboard_build_layout_includes_quarantined_and_failed_steps() -> None:
    tracker = StepTracker(
        [
            PipelineStep(id="ingest", label="Ingest", status=StepStatus.COMPLETE),
            PipelineStep(
                id="validate",
                label="Validate",
                status=StepStatus.QUARANTINED,
                detail="Rows quarantined",
            ),
            PipelineStep(
                id="export",
                label="Export",
                status=StepStatus.FAILED,
                detail="missing column",
            ),
        ]
    )
    tracker.set_status_message("Run failed")
    buffer = StringIO()
    dashboard = RunDashboard(
        tracker,
        InMemoryLogBuffer(),
        console=Console(file=buffer, width=120, force_terminal=False),
    )

    layout = dashboard.build_layout()
    dashboard.console.print(layout)

    rendered = buffer.getvalue()
    assert "Validate" in rendered
    assert "Export" in rendered
    assert "Run failed" in rendered
